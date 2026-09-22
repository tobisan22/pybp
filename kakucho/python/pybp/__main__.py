"""
python -m pybp [script.py]

IPython セッションを起動し、%pybp マジックを登録する。
script.py が渡されていれば起動直後にそれを実行し、終了後もセッションを維持する。

環境変数:
  PYBP_MPL   matplotlib バックエンド (既定 "webagg")。"qt", "tk", "inline", "none",
             および "auto"（Qt → Tk → webagg の順に、入っているものを選ぶ）。
             VS Code から起動した場合は設定 pybp.figureDisplay が決める
  PYBP_PORT  webagg のポート (既定 8988)。VS Code 設定 pybp.webaggPort から渡される
  PYBP_FILE  赤丸 JSON のパスを明示したい場合
"""

from __future__ import annotations

import atexit
import json
import os
import sys
from pathlib import Path

from IPython import start_ipython
from traitlets.config import Config

from .core import FIGURES_NAME, SESSION_NAME, find_vscode_dir


# "auto" を解決するときに探す GUI バインディング。先に見つかった方を使う。
_GUI_BINDINGS = (
    ("qt", ("PyQt5", "PyQt6", "PySide6", "PySide2")),
    ("tk", ("tkinter",)),
)


def resolve_backend(mpl: str) -> str:
    """"auto" を、その環境で実際に使えるバックエンド名へ解決する。

    別ウィンドウ表示（VS Code 設定 pybp.figureDisplay = window）で使う。
    Qt も Tk も無い環境で %matplotlib qt に失敗すると、バックエンドが既定のまま
    残って図が一切出なくなるため、ここで webagg へ落としておく。
    """
    if mpl != "auto":
        return mpl

    import importlib.util as u

    for gui, mods in _GUI_BINDINGS:
        for mod in mods:
            try:
                found = u.find_spec(mod) is not None
            except (ImportError, ValueError):
                found = False
            if found:
                return gui
    print("[pybp] 警告: Qt / Tk が見つからないため webagg で表示します")
    return "webagg"


def startup_lines(mpl: str, port: int, script: str | Path | None) -> list[str]:
    """IPython の exec_lines を組む。

    webagg だけは %matplotlib を通さない。%matplotlib は gui 名を IPython 側の
    テーブルで解決するため、'webagg' を知らない IPython では例外になる。
    exec_lines の例外はセッションを止めないので、バックエンドは既定
    （Qt binding が入っていれば QtAgg）のまま残り、figure が Qt マネージャで
    作られる。その状態で figure タブを開くと webagg サーバーの WebSocket が
    manager.add_web_socket を呼び、FigureManagerQT には無いため
    AttributeError になる。切り替えは matplotlib へ直接指示する。

    Qt/Tk はイベントループ統合が必要なので %matplotlib に任せる。
    """
    lines: list[str] = []
    if mpl == "webagg":
        lines += [
            "import matplotlib as _mpl; _mpl.use('WebAgg', force=True);"
            " _mpl.interactive(True);"
            " _mpl.rcParams['webagg.open_in_browser'] = False; del _mpl",
            f"from pybp.webagg import start_server as _s;"
            f" print('[pybp] figures:', _s({port})); del _s",
        ]
    elif mpl != "none":
        lines.append(f"%matplotlib {mpl}")
    lines += ["%load_ext autoreload", "%autoreload 2"]
    if script:
        lines.append(f'%pybp "{script}"')
    return lines


def main() -> None:
    script = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None

    # --- セッション生存通知（拡張側が「2回目以降は %pybp を送る」判定に使う） ---
    vsdir = find_vscode_dir(script.parent if script else Path.cwd())
    if vsdir:
        session = vsdir / SESSION_NAME
        figures = vsdir / FIGURES_NAME
        figures.unlink(missing_ok=True)  # 前回の残骸を消す
        session.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        atexit.register(lambda: session.unlink(missing_ok=True))
        atexit.register(lambda: figures.unlink(missing_ok=True))

    # --- IPython 設定 ---
    mpl = resolve_backend(os.environ.get("PYBP_MPL", "webagg").lower())
    port = int(os.environ.get("PYBP_PORT", "8988"))
    exec_lines = startup_lines(mpl, port, script)

    c = Config()
    c.InteractiveShellApp.extensions = ["pybp.core"]
    c.InteractiveShellApp.exec_lines = exec_lines
    c.TerminalInteractiveShell.confirm_exit = False
    c.TerminalInteractiveShell.banner1 = ""

    print(f"[pybp] session started ({mpl} backend). F5 で再実行 / exit で終了")
    start_ipython(argv=[], config=c)


if __name__ == "__main__":
    main()
