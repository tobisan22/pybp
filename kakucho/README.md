# PyBP — 変数も図も残る Python 実行環境

F5 で Python スクリプトを **常駐 IPython セッション**の中で実行します。エディタの赤丸（ブレークポイント）で
停止でき、**実行が終わっても変数と figure は生きたまま**残ります。MATLAB のコマンドウィンドウのような
使い心地で、実行後にそのまま変数を確認したり追加計算したりできます。

debugpy は使いません（内部は IPython + ipdb）。

## インストール

```
code --install-extension pybp-0.2.0.vsix
```

インストール後は **VS Code を完全に終了して再起動**してください（ウィンドウの再読み込みだけでは足りません）。
`.py` ファイルを開いて F5 で動きます。

## 必要なもの

使う Python に以下が入っている必要があります。

| パッケージ | 用途 |
|---|---|
| `ipython` | セッション本体 |
| `ipdb` | ブレークポイントでの停止 |
| `matplotlib` | 図の表示 |
| `tornado` | 既定の webagg バックエンド（図を VS Code のタブに出すのに必須） |

不足している場合は**初回起動時に拡張が検出して、インストールするか尋ねます**（`python -m pip install …` を実行）。
手動で入れるなら:

```
python -m pip install ipython ipdb matplotlib tornado
```

**`pybp` パッケージ自体はこの拡張に同梱されています。`pip install pybp` は不要です**
（設定 `pybp.useBundledPython` が既定で `true` のため、`PYTHONPATH` 経由で読み込まれます）。

## 使い方

| キー | 状態 | 動作 |
|---|---|---|
| F5 | 通常 | 初回: IPython セッション起動 + 実行 / 2回目以降: 同じセッションで再実行 |
| F5 | 停止中 | 続行 (`c`) |
| F10 | 停止中 | ステップオーバー (`n`) |
| F11 / Shift+F11 | 停止中 | ステップイン (`s`) / ステップアウト (`r`) |
| Shift+F5 | 停止中 | デバッガ終了 (`q`) → IPython プロンプトへ |
| Ctrl+Shift+F5 | 通常 | セッションを破棄して再起動 |
| Ctrl+C | Figure タブ | その figure の画像をクリップボードへコピー |

- 赤丸はエディタの行番号の左をクリック（VS Code の標準機能）
- 実行が終わってもセッションは生きています。ターミナル「PyBP」の IPython プロンプトでそのまま変数を確認できます
- `%reset` でワークスペースをクリア、`plt.close("all")` で figure を全て閉じる
- 自作モジュールは `autoreload` で編集が自動反映されます（挙動が怪しければ Ctrl+Shift+F5）

## 図について

matplotlib の figure は webagg バックエンドでノンブロッキング表示され、figure ごとに VS Code のタブが開きます。
実行後も残ります。

- タブ右上の 📋、またはグラフのツールバーの **Copy** で画像をクリップボードへコピーし、Word / PowerPoint に
  そのまま貼り付けられます（**Windows のみ**。VS Code のクリップボード API はテキスト専用のため PowerShell 経由で実装）
- ツールバーの **保存**（フロッピー）は VS Code の保存ダイアログを開きます。形式は隣のドロップダウン（png / svg / pdf など）に従います

## 設定

| 設定 | 既定 | 内容 |
|---|---|---|
| `pybp.pythonPath` | `python` | セッション起動に使う Python 実行ファイル |
| `pybp.webaggPort` | `8988` | matplotlib webagg のポート。セッション起動時に環境変数 `PYBP_PORT` として Python へ渡される |
| `pybp.useBundledPython` | `true` | 同梱の `pybp` を `PYTHONPATH` 経由で使う。**この拡張のソースを編集して開発する場合のみ `false`** にする |
| `pybp.autoOpenFigures` | `true` | figure が作られたら Figure タブを自動で開く |

環境変数 `PYBP_MPL` で matplotlib バックエンドを変更できます（既定 `webagg`。`qt` / `tk` / `inline` / `none`）。

## うまく動かないとき

| 症状 | 対処 |
|---|---|
| 依存パッケージの確認ダイアログが毎回出る | `pybp.pythonPath` が、依存を入れた Python と別のものを指しています。設定を確認してください |
| F5 が反応しない / コマンドが無い | VS Code を完全終了して再起動。それでも駄目なら `code --uninstall-extension local.pybp` → 再インストール |
| 図が出ない | `pybp.webaggPort` が他のアプリと衝突しています。別のポート番号に変更してください |
| Figure タブが空白 | パネルの境界をドラッグしてサイズを変えてください |

## 制約

- 赤丸がある実行は pdb トレースが入るため、純粋な数値計算は遅くなります（赤丸ゼロなら素の速度）
- 停止中の変数ホバー表示には未対応です（`ipdb>` プロンプトで変数名を打ってください）
- 標準ライブラリ・IPython・matplotlib の内部には F11 でも入りません
