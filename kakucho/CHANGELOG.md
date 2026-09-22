# Change Log

All notable changes to the "pybp" extension will be documented in this file.

Check [Keep a Changelog](http://keepachangelog.com/) for recommendations on how to structure this file.

## [Unreleased]

- Figure タブを開くと `'FigureManagerQT' object has no attribute 'add_web_socket'`
  になる問題を修正。セッション起動時のバックエンド切り替えを `%matplotlib webagg`
  から `matplotlib.use("WebAgg", force=True)` + `matplotlib.interactive(True)` に
  変更した。`%matplotlib` は gui 名を IPython 側のテーブルで解決するため、
  `webagg` を知らない IPython では例外になる。`exec_lines` の例外はセッションを
  止めないので、バックエンドは既定（Qt binding が入っていれば QtAgg）のまま残り、
  figure が Qt マネージャで作られていた。その状態で webagg サーバーの WebSocket が
  `manager.add_web_socket` を呼ぶと、`FigureManagerQT` には無いため落ちる。
  Qt/Tk はイベントループ統合が必要なので `%matplotlib` のままにしてある。
  回帰テスト: `pybp/tests/test_startup_lines.py`
- Python 3.9 に対応。`pybp/webagg.py` のモジュール直下アノテーション
  （`url: str | None` / `_log_path: Path | None`）は PEP 604 のため 3.9 では
  import 時に評価されて `TypeError` になっていた。他の 2 ファイルと同じく
  `from __future__ import annotations` を追加して遅延評価にした。
  あわせて `requires-python` を `>=3.10` から `>=3.9` へ。
- Initial release