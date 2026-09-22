# Change Log

All notable changes to the "pybp" extension will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/).

## [Unreleased]

## [0.2.0] - 2026-09-22

### Added

- `pybp.figureDisplay` 設定を追加。matplotlib の figure をどこに表示するか選べます。
  - `tab`（既定）: figure ごとにタブを自動で開く
  - `manual`: タブは使うが自動では開かない
  - `window`: Qt / Tk のネイティブウィンドウに表示
  - `none`: 表示しない（非対話モード。`savefig` によるファイル出力は引き続き使えます）
- `pybp.windowBackend` 設定を追加（`auto` / `qt` / `tk`）。`figureDisplay: window` のときに使うバックエンドを選べます。`auto` は PyQt5 → PyQt6 → PySide6 → PySide2 → tkinter の順に自動検出します。
- Python 3.9 に対応（これまでは 3.10 以上が必須でした）。

### Changed

- `pybp.autoOpenFigures` は `pybp.figureDisplay` に統合され、非推奨になりました。既存の `false` 設定は `manual` として扱われるため、設定の変更は不要です。
- `figureDisplay: window` のときは Figure タブに関するボタン・コマンドを非表示にするようにしました（タブ自体が存在しないため）。
- 不具合調査用のログ出力を整理し、セッション起動・依存関係の診断・コピー／保存の失敗など、実際に役立つ情報だけを記録するようにしました。

### Fixed

- 同梱の Python（`useBundledPython: true`）を使っている場合に `ModuleNotFoundError` が発生することがある問題を修正。診断で確認した Python インタプリタをそのままターミナルの起動に使うことで、conda / venv の自動アクティベートなどによる環境のずれを防ぎます。import できない場合は、原因を示した上でターミナルを開かないようにしました。
- Figure タブを開くと `'FigureManagerQT' object has no attribute 'add_web_socket'` エラーになることがある問題を修正。

## [0.1.0]

- Initial release
