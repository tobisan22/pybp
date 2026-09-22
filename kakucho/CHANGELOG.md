# Change Log

All notable changes to the "pybp" extension will be documented in this file.

Check [Keep a Changelog](http://keepachangelog.com/) for recommendations on how to structure this file.

## [Unreleased]

- 図をタブに出すかどうかを VS Code 設定にした。`pybp.figureDisplay` が
  `tab`（既定 / figure ごとにタブを自動で開く）・`manual`（タブだが自動では
  開かない）・`window`（Qt / Tk の別ウィンドウ。webagg サーバーを起動しない）を取る。
  - `window` のバックエンドは `pybp.windowBackend`（`auto` / `qt` / `tk`）。`auto` は
    Python 側の `resolve_backend()` が PyQt5 / PyQt6 / PySide6 / PySide2 → tkinter の
    順に探し、どれも無ければ webagg へ落とす。`%matplotlib qt` に失敗すると
    バックエンドが既定のまま残って図が一切出なくなるための保険。
  - 設定値は環境変数 `PYBP_MPL` としてセッションに渡す。`PYBP_MPL` 自体は
    `python -m pybp` を手で叩く時用として残してある。
  - `pybp.autoOpenFigures` は `figureDisplay` に統合（非推奨）。明示的に `false` に
    してある場合は `manual` として扱うので、既存の設定はそのまま動く。
  - `window` では Figure タブが無いため、📈 と 📋 のボタンとコマンドを隠す
    （コンテキストキー `pybp.figureWindow`）。設定を変えるとセッション再起動を促す。

- 調査用の計測ログを撤去。`pybp/webagg.py` の `log()` と `_install_probes()`
  （HTTP / WebSocket の全イベント記録）を削除し、`py_webagg_log.txt` は出力しなく
  なった。WebSocket 送信をサーバースレッドのループへ委譲するスレッドセーフ化だけを
  `_install_threadsafe_send()` として残してある。副次効果として、matplotlib の
  バージョン差で消えうる `WebAggApplication.Download` への依存が無くなった。
  拡張側の `py_ext_log.txt` は不具合報告に使うので残し、`PANEL` / `CTX` / `SYNC`
  など高頻度のノイズを削って、セッション起動・依存診断・コピー／保存の失敗だけに
  絞った。

- 同梱 pybp（`useBundledPython: true`）で `ModuleNotFoundError` になる問題に対処。
  - ターミナルの `python` は拡張ホストの PATH とは別に解決される（conda / venv の
    自動アクティベート）ため、依存を診断した処理系と実際に動く処理系がずれていた。
    診断時に `sys.executable` を持ち帰り、ターミナルはその絶対パスの Python を
    `shellPath` で直接起動するようにした。シェルを挟まないので、パスに空白がある
    場合のクォート（PowerShell の `&` 演算子）や、プロファイル・自動アクティベート
    の割り込みも起きない。
  - 診断で `pybp` 自身の `find_spec` も確認し、import できなければターミナルを
    開かずに原因（PYTHONPATH / `useBundledPython`）を添えて通知する。
  - `py_ext_log.txt` に `SESSION PYTHONPATH=` / `PROBE exe=` / `PROBE pybp=` を記録。

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