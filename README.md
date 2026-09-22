# PyBP — 変数も図も残る Python 実行環境 for VS Code

## フォルダ構成

```
pybp/                        （このフォルダ。場所は自由）
├─ setup.ps1                 セットアップ／修復スクリプト
├─ pybp/                     Python 側（pip -e でインストール）
│  ├─ pyproject.toml
│  └─ pybp/  __init__.py / core.py / __main__.py / webagg.py
└─ kakucho/                  VS Code 拡張側（TypeScript）
   ├─ package.json / package-lock.json
   └─ src/extension.ts       → npm run compile → out/extension.js
```

役割: 拡張が赤丸を `<作業フォルダ>/.vscode/py_breakpoints.json` に書き、
ターミナルで `python -m pybp` を起動する。Python 側は `pybp` パッケージが import できれば動く。
**パスの直書きは無い**ので、フォルダを移動して壊れる原因は下記の「インストール済みの登録情報」だけ。

## 配布・インストール（使う人向け）

`.vsix` には **pybp 本体の Python コードが同梱**されており、拡張が `PYTHONPATH` を通すので
`pip install pybp` は不要。

1. `code --install-extension pybp-0.2.0.vsix` → VS Code を再起動
2. .py を開いて F5

ただし **ipython / ipdb / matplotlib / tornado は利用者の Python に必要**。不足していれば
初回起動時に拡張が検出して、インストールするか尋ねる（`python -m pip install …` を実行）。

- 対応 Python は **3.9 以上**（`pybp/pyproject.toml` の `requires-python`）
- 3.9 では pip が ipython 8.18 系 / matplotlib 3.9 系を自動で選ぶ（各パッケージの
  `Requires-Python` メタデータによる）ので、こちら側でのバージョン指定は不要

- 使う Python は VS Code 設定 `pybp.pythonPath`（既定 `python`）で決まる
- Marketplace 公開はしていないので、配布は .vsix を配る形になる
- **開発時は設定 `pybp.useBundledPython` を `false` にすること。** `true` のままだと
  同梱版が `pip install -e` を隠し、`pybp/` を編集しても反映されない

## セットアップ（開発者向け：新PC・フォルダ移動後・動かなくなった時 共通）

```powershell
cd <このフォルダ>
.\setup.ps1                      # Python + 拡張を両方やり直す
.\setup.ps1 -Python C:\path\python.exe   # pybp.pythonPath と同じ Python を指定したい場合
```

完了後は **VS Code を完全終了して再起動**。スクリプトがやること:

| # | 対象 | 内容 |
|---|---|---|
| 1 | Python | 旧 `pybp` を pip uninstall、古い `pybp.egg-info` を削除 |
| 2 | Python | `pip install -e ./pybp[qt,web]`（新しい場所を登録） |
| 3 | Python | `import pybp, IPython, ipdb, matplotlib, tornado` で検証 |
| 4 | 拡張 | `node_modules` と `out` を削除し `npm install` → `npm run compile` |
| 5 | 拡張 | `vsce package` で .vsix 作成 |
| 6 | 拡張 | 旧拡張を uninstall → 新 .vsix を install |

手動でやる場合は上表の順に同じコマンドを実行する（Python 側: `python -m pip install -e ./pybp[qt,web]`、
拡張側: `npm install; npm run compile; npx @vscode/vsce package --skip-license; code --install-extension pybp-0.2.0.vsix --force`）。

開発中の確認は `kakucho` を VS Code で開き F5（Extension Development Host）。

## 動作確認チェックリスト

1. `python -c "import pybp; print(pybp.__file__)"` → **このフォルダ配下の pybp\pybp** が表示される
2. `python -m pybp` → `[pybp] session started` が出て IPython プロンプトになる
3. `code --list-extensions | findstr pybp` → `local.pybp`
4. .py を開いて F5 → ターミナル「PyBP」が起動し実行される
5. 赤丸を付けて F5 → 停止行がハイライトされる

## トラブルシュート

| 症状 | 原因 | 対処 |
|---|---|---|
| `No module named pybp` | 拡張が `pybp` を見つけられない | 起動前に検出して原因付きで通知される。`.vscode/py_ext_log.txt` の `PROBE pybp=` と `SESSION PYTHONPATH=` を見る。`useBundledPython: false` なら `setup.ps1`、`true` なら拡張を再インストール |
| 依存は入れたのに `ModuleNotFoundError` | ターミナルの `python` が、拡張が診断した Python と別（conda / venv の自動アクティベート） | 対処済み。ターミナルは診断した絶対パスの Python を直接起動する。`py_ext_log.txt` の `PROBE exe=` で実際の処理系を確認できる |
| import できるが古い挙動 | 旧 egg-info(0.1.0) や別 site-packages のコピーが優先 | `pip uninstall pybp` を `pip show pybp` が空になるまで繰り返し → `setup.ps1` |
| F5 が反応しない / コマンドが無い | 旧パスの拡張が入ったまま、または未インストール | `code --uninstall-extension local.pybp` → 再インストール → VS Code 再起動 |
| `tsc` が動かない・compile 失敗 | 移動でコピーされた `node_modules` が壊れている（`.bin` のリンク等） | `node_modules` を削除して `npm install` |
| `pip install -e` が日本語パスで失敗 | 非ASCIIパス + OneDrive 同期 | ASCII パス（例 `C:\dev\pybp`）に置く。OneDrive 配下は避ける |
| 図が出ない | webagg ポート競合 | `pybp.webaggPort` と環境変数 `PYBP_PORT` を揃える／変更 |
| `pybp/` を編集しても反映されない | 同梱版が `PYTHONPATH` 経由で優先されている | 設定 `pybp.useBundledPython` を `false` にする |
| 依存パッケージの確認ダイアログが毎回出る | `pybp.pythonPath` が依存を入れた Python と別 | `pybp.pythonPath` を確認する |
| Figure タブが空白（特に最初の1枚） | 背面で生成されたタブでは canvas のサイズ確定が後から走り、同サイズ resize に差分画像しか返らない | Python 側（`webagg.py` の `_force_full_redraw_on_resize`）で対処済み。再発したらパネルの境界をドラッグしてサイズを変える |

## 引っ越し時のルール

- 移動するのは `pybp/`・`kakucho/`・`setup.ps1`・`README.md` だけ。**`node_modules/`・`out/`・`kakucho/python/`・`*.egg-info/`・`__pycache__/`・`*.vsix` は持ち出さない**（`.gitignore` 済み。ZIP で渡すなら除外）
- `kakucho/python/` は `scripts/bundle-python.js` が `pybp/pybp/` からコピーして作る生成物。**直接編集しない**
- 移動後は必ず `setup.ps1`。git 管理なら clone → `setup.ps1` で再現できる
- バージョンを上げる時は `pybp/pyproject.toml` と `kakucho/package.json` の version を揃える

## 使い方

| キー | 状態 | 動作 |
|---|---|---|
| F5 | 通常 | 初回: IPython セッション起動 + 実行 / 2回目以降: 同セッションで再実行 |
| F5 | 停止中 | 続行 (`c`) |
| F10 | 停止中 | ステップオーバー (`n`) |
| F11 / Shift+F11 | 停止中 | ステップイン (`s`) / ステップアウト (`r`) |
| Shift+F5 | 停止中 | デバッガ終了 (`q`) → IPython プロンプトへ |
| Ctrl+Shift+F5 | 通常 | セッションを破棄して再起動（`exit` + F5 相当） |
| Ctrl+C | Figure タブ | その figure の画像をクリップボードへコピー（タブ右上の 📋 アイコンと同じ） |

- 赤丸はエディタの行番号左をクリック（VS Code 標準機能）
- Figure タブ右上の 📋 で画像をコピーし、Word / PowerPoint などにそのまま貼り付けられる（Windows のみ。VS Code のクリップボード API はテキスト専用のため PowerShell 経由で入れている）
- グラフのツールバー（Home / 拡大 などが並んでいる場所）にも **Copy** ボタンがある。用途は上と同じ
- ツールバーの **保存**（フロッピー）は VS Code の保存ダイアログを開く。形式は隣のドロップダウン（png / svg / pdf など）に従う
  - webview は `window.open` とダウンロードをブロックするため、matplotlib 標準の保存は無反応になる。そこで押下をサーバー経由で拡張に渡し、拡張側で保存している
  - この経路は VS Code の拡張が動いていることが前提。ブラウザで `http://127.0.0.1:8988/1` を直接開いた場合は保存が効かない
- 実行が終わってもセッションは生きている。IPython プロンプトでそのまま変数を確認・追加計算できる（MATLAB のコマンドウィンドウと同じ使い心地）
- matplotlib の figure は webagg バックエンドでノンブロッキング表示され、figure ごとに VS Code のタブが開く。実行後も残る
- `%reset` でワークスペースをクリア、`plt.close("all")` で figure を全閉
- 自作モジュールは `autoreload` で編集が自動反映（挙動が怪しければ Ctrl+Shift+F5）

## 設定

- VS Code 設定 `pybp.pythonPath` : セッション起動に使う Python（既定 `python`）
- VS Code 設定 `pybp.useBundledPython` : 同梱の pybp を `PYTHONPATH` 経由で使う（既定 `true`）。**開発時は `false`**
- VS Code 設定 `pybp.webaggPort` : webagg のポート（既定 `8988`）。セッション起動時に環境変数 `PYBP_PORT` として Python へ渡される
- VS Code 設定 `pybp.figureDisplay` : 図の表示先（既定 `tab`）
  - `tab` … figure ごとに VS Code のタブを自動で開く
  - `manual` … webagg だがタブは自動で開かない（📈 で開く）。旧 `autoOpenFigures: false` 相当
  - `window` … Qt / Tk の別ウィンドウ。webagg サーバーは起動しない
  - `none` … 表示しない。webagg サーバーもポートも使わない（Agg。`savefig` は使える）
- VS Code 設定 `pybp.windowBackend` : `figureDisplay: window` のバックエンド（`auto` / `qt` / `tk`、既定 `auto`）
- VS Code 設定 `pybp.autoOpenFigures` : **非推奨**。`figureDisplay` に統合（`false` = `manual`）
- 環境変数 `PYBP_MPL` : matplotlib バックエンド（既定 `webagg`。`qt` / `tk` / `inline` / `none` / `auto`）。
  ターミナルから `python -m pybp` を直接叩く時用。VS Code から起動した場合は
  `pybp.figureDisplay` / `pybp.windowBackend` が上書きする

## 制約

- 赤丸がある実行は pdb トレースが入るため、純粋な数値計算は遅くなる（赤丸ゼロなら素の速度）
- 停止中の変数ホバー表示は非対応（`ipdb>` で変数名を打つ）
- `figureDisplay: window` では Figure タブが無いため、📋 コピーと VS Code の保存ダイアログは使えない
  （matplotlib 標準のウィンドウのツールバーを使う）
- 標準ライブラリ・IPython・matplotlib 内部には F11 でも潜らない（`core.py` の `SKIP`）
