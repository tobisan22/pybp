"""
python -m pybp [script.py]

IPython セッションを起動し、%pybp マジックを登録する。
script.py が渡されていれば起動直後にそれを実行し、終了後もセッションを維持する。

環境変数:
  PYBP_MPL   matplotlib バックエンド (既定 "webagg")。"qt", "tk", "inline", "none" など
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
    mpl = os.environ.get("PYBP_MPL", "webagg").lower()
    exec_lines: list[str] = []
    if mpl != "none":
        exec_lines.append(f"%matplotlib {mpl}")
    if mpl == "webagg":
        port = int(os.environ.get("PYBP_PORT", "8988"))
        exec_lines += [
            "import matplotlib as _mpl; _mpl.rcParams['webagg.open_in_browser'] = False; del _mpl",
            f"from pybp.webagg import start_server as _s; print('[pybp] figures:', _s({port})); del _s",
        ]
    exec_lines += ["%load_ext autoreload", "%autoreload 2"]
    if script:
        exec_lines.append(f'%pybp "{script}"')

    c = Config()
    c.InteractiveShellApp.extensions = ["pybp.core"]
    c.InteractiveShellApp.exec_lines = exec_lines
    c.TerminalInteractiveShell.confirm_exit = False
    c.TerminalInteractiveShell.banner1 = ""

    print(f"[pybp] session started ({mpl} backend). F5 で再実行 / exit で終了")
    start_ipython(argv=[], config=c)


if __name__ == "__main__":
    main()
