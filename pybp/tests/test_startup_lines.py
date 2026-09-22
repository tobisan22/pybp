"""起動シーケンス（IPython exec_lines）の回帰テスト

別 PC で figure タブを開いた際に
    'FigureManagerQT' object has no attribute 'add_web_socket'
が出た件の再発防止。

原因は `%matplotlib webagg` が IPython の gui 名テーブルに依存していたこと。
その解決に失敗した IPython では例外を出したままセッションが続行し、
バックエンドが既定（QtAgg）のまま残る。figure が Qt マネージャで作られ、
webagg サーバの WebSocket が manager.add_web_socket を呼んだ時点で落ちる。

よって webagg のバックエンド切り替えは IPython を経由させない。
"""

import matplotlib
import pytest

from pybp.__main__ import startup_lines


def _setup_lines(lines):
    """マジックとサーバー起動を除いた、素の Python として実行できる行"""
    return [
        ln for ln in lines
        if not ln.startswith("%") and "start_server" not in ln
    ]


def test_webagg_does_not_go_through_ipython_magic():
    lines = startup_lines("webagg", port=8988, script=None)
    assert not any(ln.startswith("%matplotlib") for ln in lines), (
        "webagg では %matplotlib を使わない（IPython の gui 名解決に依存するため）"
    )


def test_webagg_setup_lines_actually_select_webagg():
    """素の Python として実行するだけで WebAgg に切り替わること"""
    matplotlib.use("Agg", force=True)          # 別バックエンドから開始
    matplotlib.interactive(False)

    for ln in _setup_lines(startup_lines("webagg", port=8988, script=None)):
        exec(ln, {})

    import matplotlib.pyplot as plt

    assert matplotlib.get_backend().lower() == "webagg"
    assert matplotlib.is_interactive(), "figure が作成時点で描画されるよう対話モードが必要"
    assert type(plt.figure().canvas.manager).__name__ == "FigureManagerWebAgg"
    plt.close("all")


def test_webagg_keeps_open_in_browser_off():
    lines = startup_lines("webagg", port=8988, script=None)
    assert any("webagg.open_in_browser" in ln for ln in lines)


def test_webagg_passes_port_to_server():
    lines = startup_lines("webagg", port=9123, script=None)
    assert any("start_server" in ln and "9123" in ln for ln in lines)


@pytest.mark.parametrize("gui", ["qt", "tk", "inline"])
def test_other_backends_still_use_ipython_magic(gui):
    """Qt/Tk は IPython のイベントループ統合が必要なので %matplotlib のまま"""
    lines = startup_lines(gui, port=8988, script=None)
    assert f"%matplotlib {gui}" in lines
    assert not any("start_server" in ln for ln in lines)


def test_none_selects_no_backend():
    lines = startup_lines("none", port=8988, script=None)
    assert not any("matplotlib" in ln for ln in lines)


def test_script_is_run_last():
    lines = startup_lines("webagg", port=8988, script=r"C:\work\a.py")
    assert lines[-1] == r'%pybp "C:\work\a.py"'


def test_autoreload_enabled():
    lines = startup_lines("webagg", port=8988, script=None)
    assert "%load_ext autoreload" in lines
    assert "%autoreload 2" in lines
