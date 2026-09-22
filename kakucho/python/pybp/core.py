"""
pybp.core — VS Code の赤丸（ブレークポイント）で停止しつつスクリプトを実行する。

構成:
  - find_vscode_dir : スクリプト位置から上へ辿って .vscode/py_breakpoints.json を探す
  - VsPdb           : pdb (ipdb 優先) の拡張。停止位置を JSON で通知し、
                      スクリプト終了時や標準ライブラリ内では止まらない
  - run_script      : ブレークポイントを登録して名前空間 ns でスクリプトを実行
  - %pybp マジック   : IPython セッション内から run_script を呼ぶ
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from bdb import BdbQuit
from pathlib import Path

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


def run_script(script: Path, ns: dict) -> None:
    """VS Code の赤丸で停止しつつ、名前空間 ns でスクリプトを実行する"""
    script = script.resolve()
    if not script.exists():
        print(f"pybp: file not found: {script}")
        return

    vsdir = find_vscode_dir(script.parent)

    dbg = VsPdb(script, vsdir)
    dbg.sync_breakpoints(force=True)
    bps = dbg.breaks  # {filename: [lines]}

    ns["__file__"] = str(script)
    ns.setdefault("__name__", "__main__")
    code = compile(script.read_text(encoding="utf-8"), str(script), "exec")

    try:
        if bps:
            dbg.runcall(exec, code, ns)
        else:
            exec(code, ns)
    except (SystemExit, BdbQuit):
        pass
    except BaseException:
        traceback.print_exc()
        dbg.interaction(None, sys.exc_info()[2])
    finally:
        dbg._clear_state()
        dbg.clear_all_breaks()
        notify_figures(vsdir)


# ---- IPython 拡張: %pybp マジック --------------------------------------------
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


def load_ipython_extension(ip):
    ip.register_magics(PybpMagics)
