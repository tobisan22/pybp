# Change Log

All notable changes to the "pybp" extension will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/).

## [0.4.3] - 2026-09-24

### Changed

- **F5 とセル実行（Ctrl+Enter / Shift+Enter / Ctrl+Shift+Enter）では、エラーが起きても止まらなくなりました。** トレースバックを出して IPython プロンプトに戻ります。これまでの「エラーの行で自動的に止まる」動作は Alt+F5 に移りました。赤丸で止まる動作は変わりません。

### Added

- **PyBP: Run (Stop on Error)**（`Alt+F5`）: 実行し、エラーが出たらその行で止まります（0.4.2 までの F5 の動作）。
- **PyBP: Debug Last Error**: 直前の実行のエラーの行で、後から事後デバッグに入ります。走り直さずに入れるので、重い計算の後で落ちたときもその時点の変数を調べられます。
  - エラーで終わるとステータスバーに `⚠ ZeroDivisionError (script.py:12)` のように出て、クリックで入れます
  - IPython プロンプトから `%pybp_pm` と打っても同じです
  - 入れるのは次の実行（F5 / セル実行）を始めるまでです
- マジックに `--pm` オプションを追加しました（`%pybp --pm "file"`、`%pybp_cell --pm ...`、`python -m pybp --pm`）。

### Fixed

- 赤丸が 1 つも無いスクリプトでエラーの行に止まったとき、`q` で抜けようとすると `AttributeError: 'VsPdb' object has no attribute 'botframe'` になっていた問題を修正しました。

## [0.4.2] - 2026-09-24

### Added

- **複数セッションの同時実行**に対応しました。重いスクリプトを実行している間に、別のスクリプトを F5 で並行して実行できます。
  - F5 / セル実行は、アクティブなセッションが実行中なら、空いている別のセッションで実行します。空きが無ければ新しいセッション（ターミナル `PyBP 2`, `PyBP 3`, …）を起動します
  - **PyBP: Run in New Session**（`Ctrl+Alt+F5`、エディタ右上の ▷ の隣）を使うと、必ず新しいセッションで実行します
  - PyBP のターミナルを切り替えると、そのセッションが F5 の送り先になり、ワークスペースビューもそのセッションの変数を表示します。ステータスバーのクリックか **PyBP: Select Session** からも切り替えられます
  - 2 つ目以降のセッションの Figure タブには `Figure 1 (PyBP 2)` のようにセッション名が付きます。webagg のポートは `pybp.webaggPort` + (番号 − 1) を使います
  - Ctrl+Shift+F5（Restart）は、アクティブなセッションだけを作り直します
  - ブレークポイントで停止中のセッションや、起動中・実行中のセッションへは F5 / セル実行を送りません
  - 同じスクリプトを複数のセッションで同時に実行することもできます。赤丸は全セッション共通なので、置くとどのセッションも同じ行で止まります

### Changed

- 停止位置・figure 一覧・変数一覧などの通知ファイルの置き場所を `.vscode/` 直下から `.vscode/py_sessions/<番号>/` に移しました（Python 側は環境変数 `PYBP_SESSION_DIR` で受け取ります）。赤丸の `py_breakpoints.json` は従来どおり `.vscode/` 直下で、全セッションが共有します。

## [0.4.0]

### Added

- **ワークスペースビュー**を追加しました（MATLAB の「ワークスペース」にあたるもの）。アクティビティバーの PyBP アイコン → WORKSPACE に、セッションの変数を「名前・値・サイズ・クラス」の表で表示します。
  - 実行が終わるたび、IPython プロンプトで何か打つたびに自動で更新されます
  - ブレークポイントで止まっている間は、止まった関数のローカル変数を表示します。ステップ（F10 など）のたびに更新され、`u` / `d` でフレームを移るとそのフレームの変数に切り替わります
  - 前回から新しくできた変数（緑）と値が変わった変数（黄）に印が付きます
  - dict・list・自作クラスのインスタンスは 1 段だけ開いて中を見られます（▸ をクリック、または行をダブルクリック）
  - モジュール・関数・クラスと、`_` で始まる変数は表示しません
  - 巨大な配列でも実行が遅くならないよう、要素数が 100 万を超える配列は min / max を計算しません

### Fixed

- セッション起動時の実行（1 回目の F5・セル実行）で作った変数が、IPython の `%who` / `%whos` に出なかった問題を修正。
  IPython が起動時のコードで作った変数を「隠す」扱いにしていたためで、ワークスペースビューでも次の実行以降に変数が消えていました。

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
