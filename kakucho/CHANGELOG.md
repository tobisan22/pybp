# Change Log

All notable changes to the "pybp" extension will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/).

## [Unreleased]

## [0.3.0] - 2026-09-23

### Added

- **セル実行**を追加しました。`# %%`（`#%%` も可）でスクリプトを区切ると、セル単位で実行できます。
  - `Ctrl+Enter`: カーソルのあるセルを実行
  - `Shift+Enter`: セルを実行して次のセルへ進む
  - `Ctrl+Shift+Enter`: 選択範囲（選択が無ければ現在行）を実行
  - 変数はセッションに残るため、重い前処理を一度だけ走らせて、続きのセルだけを試せます
  - 行番号を元ファイルに合わせて実行するので、**赤丸（ブレークポイント）も例外行のハイライトもセル実行で効きます**
  - セルの最後が式なら、その値を `Out[n]` として表示します
  - 字下げされた範囲（`for` の中身だけなど）を選んで実行してもエラーになりません
- `# %%` の行に区切り線を引き、カーソルのあるセルを薄く強調するようにしました。セル単位の折りたたみにも対応しています。
  設定 `pybp.showCellDecorations` で切り替えられます。
- `python -m pybp script.py --cell 開始行 終了行` を追加しました。セッションがまだ無い状態でセルを実行したときの起動に使います。
- IPython プロンプトから `%pybp_cell "script.py" 開始行 終了行` として直接呼ぶこともできます。
- セル区切りが 1 つも無いファイルでは、全体を 1 セルとして実行します（`Ctrl+Enter` = F5 と同じ範囲）。
- `PyBP: Use PyBP Cell Keys` コマンドを追加しました。`Ctrl+Enter` などを PyBP に割り当てる設定を、
  ユーザーの `keybindings.json` に書き込みます。Jupyter 拡張が入っている環境では起動時に一度だけ確認も出ます。

### Note

- **`Ctrl+Enter` / `Shift+Enter` は Jupyter 拡張（`ms-toolsai.jupyter`）や Python 拡張も使っています。**
  拡張どうしの優先順位は選べず、そのままではインタラクティブウィンドウが開くことがあります。
  `PyBP: Use PyBP Cell Keys` を実行すると、ユーザーのキー設定（拡張より優先されます）に PyBP の割り当てを追加します。
- `Ctrl+Enter` は Python ファイル上で VS Code 標準の「下に行を挿入」を置き換えます。

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
