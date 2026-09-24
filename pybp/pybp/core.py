"""
pybp.core — VS Code の赤丸（ブレークポイント）で停止しつつスクリプトを実行する。

構成:
  - find_vscode_dir : スクリプト位置から上へ辿って .vscode/py_breakpoints.json を探す
  - VsPdb           : pdb (ipdb 優先) の拡張。停止位置を JSON で通知し、
                      スクリプト終了時や標準ライブラリ内では止まらない
  - run_script      : ブレークポイントを登録して名前空間 ns でスクリプトを実行
  - run_cell        : ファイルの一部の行範囲だけを、元の行番号のまま実行
                      （セル実行 / 選択範囲の実行 / 現在行の実行）
  - %pybp / %pybp_cell マジック : IPython セッション内から上の 2 つを呼ぶ
  - ワークスペースビュー : セルの終了時と停止時に変数一覧を書き出す（pybp.workspace）
"""

from __future__ import annotations

import ast
import json
import os
import sys
import textwrap
import traceback
from bdb import BdbQuit
from pathlib import Path

from . import workspace

try:
    from ipdb.__main__ import _get_debugger_cls

    Pdb = _get_debugger_cls()  # IPython 補完・色付きの pdb
except ImportError:  # ipdb 未導入なら標準 pdb
    from pdb import Pdb

# VS Code 拡張とやり取りするファイル名（すべて .vscode/ 直下）
BP_NAME = "py_breakpoints.json"  # 拡張 → Python : 赤丸の一覧
STATE_NAME = "py_debug_state.json"  # Python → 拡張 : 現在の停止位置
SESSION_NAME = "py_session.json"  # Python → 拡張 : IPython セッション生存通知

# この中のモジュールでは絶対に停止しない（ステップインでも潜らない）
SKIP = [
    "pybp.core",  # セル実行はこのモジュールの関数を経由するので、その中では止まらない
    "runpy",
    "importlib*",
    "_frozen_importlib*",
    "codecs",
    "encodings*",
    "IPython*",
    "prompt_toolkit*",
    "traitlets*",
    "matplotlib*",
]

FIGURES_NAME = "py_figures.json"  # Python → 拡張 : figure 表示ページの URL

# セッションの .vscode/（python -m pybp が起動時に決める）。ワークスペースビューの書き出し先
session_vscode_dir: Path | None = None


def notify_figures(vscode_dir: Path | None) -> None:
    """webagg 稼働中なら、現在の figure 番号一覧を拡張に通知する"""
    if vscode_dir is None:
        return
    try:
        import matplotlib.pyplot as plt

        from pybp import webagg
    except ImportError:
        return
    if not webagg.url:
        return
    (vscode_dir / FIGURES_NAME).write_text(
        json.dumps({"url": webagg.url, "figures": plt.get_fignums()}),
        encoding="utf-8",
    )


def find_vscode_dir(start: Path) -> Path | None:
    """start から親ディレクトリへ辿り、赤丸 JSON を持つ .vscode/ を返す"""
    if env := os.environ.get("PYBP_FILE"):
        return Path(env).parent
    for d in [start, *start.parents]:
        if (d / ".vscode" / BP_NAME).exists():
            return d / ".vscode"
    return None


class VsPdb(Pdb):
    def __init__(self, script: Path, vscode_dir: Path | None, **kw):
        super().__init__(skip=SKIP, **kw)
        self.script = script.resolve()
        self.vscode_dir = vscode_dir
        self.state_file = vscode_dir / STATE_NAME if vscode_dir else None
        self._bp_mtime: float | None = None

    def setup(self, f, tb):
        super().setup(f, tb)
        if f is not None:
            return  # 通常停止時はそのまま
        # 事後デバッグ: skip 対象モジュール（ライブラリ内部）を避け、
        # 最も深いユーザーコードのフレームを現在フレームにする
        for i in range(len(self.stack) - 1, -1, -1):
            frame = self.stack[i][0]
            if not self.is_skipped_module(frame.f_globals.get("__name__", "")):
                self.curindex = i
                self.curframe = frame
                if hasattr(self, "curframe_locals"):
                    self.curframe_locals = frame.f_locals
                break
        self._write_state(self.curframe)  # エディタ側で例外行をハイライト

    def stop_here(self, frame):
        # IPython 9 の stop_here は skip 対象モジュールを通過するたびに
        # "[... skipped 1 ignored module(s)]" を無条件に print する。
        # ここで先に判定して抜けることで、その出力を抑止する。
        if self.skip and self.is_skipped_module(frame.f_globals.get("__name__", "")):
            return False
        return super().stop_here(frame)

    # --- 赤丸の同期 ---------------------------------------------------------
    def sync_breakpoints(self, force: bool = False) -> None:
        """JSON が更新されていれば、pdb 側のブレークポイントを作り直す"""
        if self.vscode_dir is None:
            return
        bp_file = self.vscode_dir / BP_NAME
        try:
            mtime = bp_file.stat().st_mtime
        except FileNotFoundError:
            mtime = None
        if not force and mtime == self._bp_mtime:
            return
        self._bp_mtime = mtime

        self.clear_all_breaks()
        for bp in load_breakpoints(self.vscode_dir):
            self.set_break(
                str(Path(bp["file"]).resolve()),
                bp["line"],
                cond=bp.get("condition") or None,
            )

    def precmd(self, line: str) -> str:
        self.sync_breakpoints()  # c / n / s 等の直前に最新の赤丸へ揃える
        return super().precmd(line)

    # reset / user_return / interaction / _write_state / _clear_state は変更なし

    # --- 停止制御 -----------------------------------------------------------
    def reset(self):
        super().reset()
        # 既定では stopframe=None（= 全行で停止）なので、実行開始直後に止まってしまう。
        # トレース対象にならないフレームを stopframe に入れ、stoplineno=-1 にすることで
        # 「ブレークポイントでのみ停止」から開始する。
        self._set_stopinfo(sys._getframe(), None, -1)

    def user_return(self, frame, return_value):
        code = frame.f_code
        if (
            code.co_name == "<module>"
            and Path(code.co_filename).resolve() == self.script
        ):
            self.set_continue()  # スクリプト本体の終了では止まらず抜ける
            return
        super().user_return(frame, return_value)

    # --- ワークスペースビュー（停止中はそのフレームの変数を出す） --------------
    def _write_workspace(self) -> None:
        frame = getattr(self, "curframe", None)
        if frame is None or self.vscode_dir is None:
            return
        ns = getattr(self, "curframe_locals", None)
        if ns is None:
            ns = frame.f_locals
        scope, label, where = workspace.frame_scope(frame)
        hidden = None
        try:
            from IPython import get_ipython

            ip = get_ipython()
            if ip is not None and ns is ip.user_ns:
                hidden = ip.user_ns_hidden  # スクリプト本体で停止 = IPython の名前空間そのもの
        except ImportError:
            pass
        workspace.write(
            self.vscode_dir, ns, hidden=hidden, scope=scope, label=label, where=where
        )

    def preloop(self):
        self._write_workspace()  # 停止するたび（ステップごと・事後デバッグ）
        super().preloop()

    def postcmd(self, stop, line):
        if not stop:  # `x = 3` や `p x` など、停止したまま打ったコマンドの後
            self._write_workspace()
        return super().postcmd(stop, line)

    # u / d でフレームを移ったら、そのフレームの変数に切り替える
    def do_up(self, arg):
        r = super().do_up(arg)
        self._write_workspace()
        return r

    def do_down(self, arg):
        r = super().do_down(arg)
        self._write_workspace()
        return r

    do_u = do_up
    do_d = do_down

    # --- 停止位置の通知（拡張側がハイライトに使う） ---------------------------
    def interaction(self, frame, tb_or_exc):
        self._write_state(frame)
        try:
            super().interaction(frame, tb_or_exc)
        finally:
            self._clear_state()

    def _write_state(self, frame):
        if self.state_file is None or frame is None:
            return
        self.state_file.write_text(
            json.dumps(
                {
                    "file": str(Path(frame.f_code.co_filename).resolve()),
                    "line": frame.f_lineno,
                }
            ),
            encoding="utf-8",
        )

    def _clear_state(self):
        if self.state_file is not None:
            self.state_file.unlink(missing_ok=True)


def load_breakpoints(vscode_dir: Path | None) -> list[dict]:
    if vscode_dir is None:
        return []
    bp_file = vscode_dir / BP_NAME
    if not bp_file.exists():
        return []
    raw = json.loads(bp_file.read_text(encoding="utf-8"))
    return [b for b in raw if b.get("enabled", True)]


def _execute(script: Path, vsdir, run) -> None:
    """赤丸を仕込んだデバッガの下で run() を実行する（スクリプト実行・セル実行の共通部）

    赤丸が1つも無ければトレースを一切入れない。例外は事後デバッグに渡し、
    終わったら停止状態と figure 一覧を拡張へ通知する。
    """
    dbg = VsPdb(script, vsdir)
    dbg.sync_breakpoints(force=True)

    try:
        if dbg.breaks:  # {filename: [lines]}
            dbg.runcall(run)
        else:
            run()
    except (SystemExit, BdbQuit):
        pass
    except BaseException:
        traceback.print_exc()
        dbg.interaction(None, sys.exc_info()[2])
    finally:
        dbg._clear_state()
        dbg.clear_all_breaks()
        notify_figures(vsdir)


def run_script(script: Path, ns: dict) -> None:
    """VS Code の赤丸で停止しつつ、名前空間 ns でスクリプトを実行する"""
    script = script.resolve()
    if not script.exists():
        print(f"pybp: file not found: {script}")
        return

    vsdir = find_vscode_dir(script.parent)

    ns["__file__"] = str(script)
    ns.setdefault("__name__", "__main__")
    code = compile(script.read_text(encoding="utf-8"), str(script), "exec")

    _execute(script, vsdir, lambda: exec(code, ns))


# ---- セル実行（# %% 区切り / 選択範囲 / 現在行） --------------------------------


def compile_range(src: str, start: int, filename: str):
    """行範囲のソースを「本体」と「末尾の式」に分けてコンパイルする。

    - 先頭に空行を詰めて、コード中の行番号をファイル上の行番号に合わせる。
      こうしないと赤丸もトレースバックもエディタの行とずれる
    - 末尾が式なら切り離して eval 用にする。IPython のセルと同じく、
      最後の式の値を Out[n] として表示するため
    - `for` の中だけを選んで実行したときのように、範囲全体が字下げされている
      場合に備え、IndentationError のときだけ字下げを外して作り直す
    """
    pad = "\n" * (start - 1)
    try:
        mod = ast.parse(pad + src, filename, "exec")
    except IndentationError:
        mod = ast.parse(pad + textwrap.dedent(src), filename, "exec")

    tail = None
    if mod.body and isinstance(mod.body[-1], ast.Expr):
        expr = mod.body.pop()
        tail = compile(ast.Expression(expr.value), filename, "eval")
    return compile(mod, filename, "exec"), tail


def run_cell(script: Path, start: int, end: int, ns: dict) -> None:
    """script の start..end 行（1 始まり・両端含む）だけを ns で実行する。

    セル実行・選択範囲の実行・現在行の実行はすべてここを通る。
    ファイルは拡張側が保存済みで、行番号はそのファイル上の番号。
    """
    script = script.resolve()
    if not script.exists():
        print(f"pybp: file not found: {script}")
        return

    lines = script.read_text(encoding="utf-8").splitlines(keepends=True)
    start = max(1, start)
    end = min(len(lines), end)
    if start > end:
        return
    src = "".join(lines[start - 1 : end])
    if not src.strip():
        return

    try:
        code, tail = compile_range(src, start, str(script))
    except SyntaxError as e:
        print("".join(traceback.format_exception_only(type(e), e)), end="")
        return

    ns["__file__"] = str(script)
    ns.setdefault("__name__", "__main__")

    def run():
        exec(code, ns)
        if tail is not None:
            sys.displayhook(eval(tail, ns))  # 末尾の式は Out[n] として表示

    _execute(script, find_vscode_dir(script.parent), run)


# ---- IPython 拡張: %pybp / %pybp_cell マジック ---------------------------------
from IPython.core.magic import Magics, line_magic, magics_class


@magics_class
class PybpMagics(Magics):
    @line_magic
    def pybp(self, line: str):
        """%pybp script.py — 赤丸で停止しつつ、現在の名前空間でスクリプトを実行"""
        path = line.strip().strip('"').strip("'")
        if not path:
            print("usage: %pybp script.py")
            return
        run_script(Path(path), self.shell.user_ns)

    @line_magic
    def pybp_cell(self, line: str):
        """%pybp_cell script.py START END — その行範囲だけを現在の名前空間で実行"""
        try:
            head, start, end = line.strip().rsplit(None, 2)
            span = (int(start), int(end))
        except ValueError:
            print("usage: %pybp_cell script.py START END")
            return
        path = head.strip().strip('"').strip("'")
        run_cell(Path(path), span[0], span[1], self.shell.user_ns)


def load_ipython_extension(ip):
    ip.register_magics(PybpMagics)

    vsdir = session_vscode_dir or find_vscode_dir(Path.cwd())

    def update_workspace(*_):
        workspace.write(vsdir, ip.user_ns, hidden=ip.user_ns_hidden)

    # F5 / セル実行（%pybp・%pybp_cell もセルの 1 つ）/ プロンプトで打った 1 行、すべての後
    ip.events.register("post_run_cell", update_workspace)
    update_workspace()  # 起動直後の空の一覧（拡張が「セッションあり」と分かるように）
