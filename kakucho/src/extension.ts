/**
 * PyBP — MATLAB ライクな Python 実行環境
 *
 *  - エディタの赤丸を .vscode/py_breakpoints.json に書き出す（Python 側が読む）
 *  - F5 で IPython セッションを起動 / 2回目以降は同セッションへ %pybp を送る
 *  - Python 側が書く .vscode/py_debug_state.json を監視して停止行をハイライト
 *  - 停止中は F5/F10/F11 などを pdb コマンドとしてターミナルへ送る
 *  - Python 側が書く .vscode/py_figures.json を監視して figure ごとにタブを開く
 *  - Figure タブの 📋 で、その figure の PNG を Windows のクリップボードへ入れる
 */
import * as vscode from "vscode";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as http from "http";
import { execFile } from "child_process";

const BP_NAME = "py_breakpoints.json";
const STATE_NAME = "py_debug_state.json";
const SESSION_NAME = "py_session.json";
const FIGURES_NAME = "py_figures.json";
const SAVE_REQUEST_NAME = "py_save_request.json";   // Python → 拡張 : 保存ダイアログ要求

// pybp 本体は同梱するが、これらは利用者の Python に入っている必要がある
const REQUIRED_MODULES = [
  { mod: "IPython", pip: "ipython" },
  { mod: "ipdb", pip: "ipdb" },
  { mod: "matplotlib", pip: "matplotlib" },
  { mod: "tornado", pip: "tornado" },
];

function workspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function vscodeDir(): string | undefined {
  const root = workspaceRoot();
  return root ? path.join(root, ".vscode") : undefined;
}

function removeQuiet(p: string) {
  try { fs.unlinkSync(p); } catch { /* ignore */ }
}

// ---- 拡張の動作ログ（不具合報告用。セッション起動のたびに書き直される） ------------
const EXT_LOG_NAME = "py_ext_log.txt";

function extLogPath(): string | undefined {
  const dir = vscodeDir();
  return dir ? path.join(dir, EXT_LOG_NAME) : undefined;
}

function extLog(msg: string) {
  const p = extLogPath();
  if (!p) { return; }
  const d = new Date();
  const t = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
    + `:${String(d.getSeconds()).padStart(2, "0")}.${String(d.getMilliseconds()).padStart(3, "0")}`;
  try { fs.appendFileSync(p, `${t}  ${msg}\n`, "utf8"); } catch { /* ignore */ }
}

// ---- figure 画像のクリップボードコピー ---------------------------------------
/** webagg から画像を取得する（拡張ホストは Node なので CORS の制約を受けない） */
function fetchUrl(url: string, timeoutMs = 5000): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const req = http.get(url, res => {
      if (res.statusCode !== 200) {
        res.resume();
        reject(new Error(`HTTP ${res.statusCode} (${url})`));
        return;
      }
      const chunks: Buffer[] = [];
      res.on("data", (c: Buffer) => chunks.push(c));
      res.on("end", () => resolve(Buffer.concat(chunks)));
    });
    req.on("error", reject);
    req.setTimeout(timeoutMs, () =>
      req.destroy(new Error(`webagg (${url}) への接続がタイムアウトしました`)));
  });
}

// VS Code の clipboard API はテキスト専用なので、画像は PowerShell 経由で入れる。
//  -STA        : クリップボード API は STA スレッドを要求する
//  環境変数渡し : 日本語やスペースを含むパスのクォート崩れを避ける
const CLIP_PS =
  "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; " +
  "$i=[System.Drawing.Image]::FromFile($env:PYBP_CLIP_PNG); " +
  "[System.Windows.Forms.Clipboard]::SetImage($i); $i.Dispose()";

function setClipboardImage(pngPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    execFile(
      "powershell.exe",
      ["-STA", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", CLIP_PS],
      { env: { ...process.env, PYBP_CLIP_PNG: pngPath }, windowsHide: true },
      (err, _stdout, stderr) => {
        if (err) { reject(new Error(stderr?.trim() || err.message)); } else { resolve(); }
      },
    );
  });
}

// ---- 赤丸の書き出し ----------------------------------------------------------
function dumpBreakpoints() {
  const dir = vscodeDir();
  if (!dir) { return; }
  const bps = vscode.debug.breakpoints
    .filter((b): b is vscode.SourceBreakpoint => b instanceof vscode.SourceBreakpoint)
    .filter(b => b.location.uri.fsPath.endsWith(".py"))
    .map(b => ({
      file: b.location.uri.fsPath,
      line: b.location.range.start.line + 1,   // 0-based → 1-based
      enabled: b.enabled,
      condition: b.condition ?? null,
    }));
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, BP_NAME), JSON.stringify(bps, null, 2), "utf8");
}

export function activate(context: vscode.ExtensionContext) {
  // ---- 状態 ----
  let runTerminal: vscode.Terminal | undefined;
  let current: { file: string; line: number } | undefined;
  const figurePanels = new Map<number, vscode.WebviewPanel>();   // figure 番号 → タブ
  let activeFigure: number | undefined;                          // 最後にフォーカスされた figure

  const config = () => vscode.workspace.getConfiguration("pybp");

  // ---- 図の表示先 ----
  //  tab    : webagg + figure ごとに VS Code のタブを自動で開く（既定）
  //  manual : webagg だがタブは自動で開かない（📈 で開く）
  //  window : Qt / Tk の別ウィンドウ。webagg サーバーは起動しない
  type FigureDisplay = "tab" | "manual" | "window";

  /** ユーザーが明示的に設定した値だけを拾う（既定値は無視する） */
  const explicitly = <T>(key: string): T | undefined => {
    const i = config().inspect<T>(key);
    return i?.workspaceFolderValue ?? i?.workspaceValue ?? i?.globalValue;
  };

  const figureDisplay = (): FigureDisplay => {
    const v = explicitly<FigureDisplay>("figureDisplay");
    if (v) { return v; }
    // 旧 pybp.autoOpenFigures: false との下位互換
    if (explicitly<boolean>("autoOpenFigures") === false) { return "manual"; }
    return config().get<FigureDisplay>("figureDisplay", "tab");
  };

  // window モードでは Figure タブ関連の UI を隠す。
  // 未設定＝false として評価されるよう、否定形のキーにしてある。
  const updateFigureWindowContext = () =>
    vscode.commands.executeCommand(
      "setContext", "pybp.figureWindow", figureDisplay() === "window");

  const setStopped = (v: boolean) =>
    vscode.commands.executeCommand("setContext", "pybp.stopped", v);

  // ---- ステータスバー ----
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  status.command = "pybp.continue";
  context.subscriptions.push(status);

  const updateStatus = () => {
    if (current) {
      status.text = `$(debug-pause) PyBP: ${path.basename(current.file)}:${current.line}`;
      status.tooltip = "ブレークポイントで停止中（クリックで続行）";
      status.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground");
      status.show();
    } else if (runTerminal) {
      status.text = "$(terminal) PyBP session";
      status.tooltip = "IPython セッション稼働中";
      status.backgroundColor = undefined;
      status.show();
    } else {
      status.hide();
    }
  };

  // ---- 停止行ハイライト ----
  const decoration = vscode.window.createTextEditorDecorationType({
    isWholeLine: true,
    backgroundColor: new vscode.ThemeColor("editor.stackFrameHighlightBackground"),
    overviewRulerColor: new vscode.ThemeColor("editor.stackFrameHighlightBackground"),
    overviewRulerLane: vscode.OverviewRulerLane.Full,
  });
  context.subscriptions.push(decoration);

  const applyHighlight = () => {
    for (const ed of vscode.window.visibleTextEditors) {
      const hit = !!current &&
        ed.document.uri.fsPath.toLowerCase() === current.file.toLowerCase();
      ed.setDecorations(
        decoration,
        hit ? [new vscode.Range(current!.line - 1, 0, current!.line - 1, 0)] : []
      );
    }
  };

  // 停止解除・セッション終了などで共通に呼ぶ
  const clearStopped = () => {
    current = undefined;
    setStopped(false);
    applyHighlight();
    updateStatus();
  };

  // ---- figure タブ ----
  const closeAllFigurePanels = () => {
    for (const p of [...figurePanels.values()]) { p.dispose(); }
    figurePanels.clear();
  };

  // Figure タブが前面にあるかを自前のコンテキストキーで持つ。
  // 組み込みの activeWebviewPanelId は当環境で editor/title に効かなかったため
  // （pybp.stopped と同じ、この拡張で実績のある方式に揃える）。
  const updateFigureContext = () => {
    const active = [...figurePanels.values()].some(p => p.active);
    vscode.commands.executeCommand("setContext", "pybp.figureActive", active);
  };

  const openFigurePanel = (base: string, num: number) => {
    const existing = figurePanels.get(num);
    if (existing) { existing.reveal(undefined, true); return; }

    const panel = vscode.window.createWebviewPanel(
      "pybpFigure", `Figure ${num}`,
      { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
      { enableScripts: true, retainContextWhenHidden: true }
    );
    const figureHtml = () => `<!DOCTYPE html><html><head>
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; frame-src ${base}; style-src 'unsafe-inline';">
<style>
  html, body { margin:0; padding:0; width:100%; height:100%; overflow:hidden; }
  iframe { position:absolute; inset:0; width:100%; height:100%; border:0; }
</style>
</head><body><iframe src="${base}/${num}"></iframe>
<!-- ${Date.now()}-${Math.random().toString(36).slice(2)} --></body></html>`;
    panel.webview.html = figureHtml();

    // 背面タブが空白になる問題は Python 側（pybp.webagg）で対処している。
    // ブラウザは canvas のリサイズで中身を捨てるため、resize には必ずフル画像を返す。
    panel.onDidChangeViewState(e => {
      if (e.webviewPanel.active) { activeFigure = num; }
      updateFigureContext();
    });
    panel.onDidDispose(() => {
      figurePanels.delete(num);
      if (activeFigure === num) { activeFigure = undefined; }
      updateFigureContext();
    });
    figurePanels.set(num, panel);
  };

  const readFigures = (): { url: string; figures: number[] } | undefined => {
    const dir = vscodeDir();
    if (!dir) { return undefined; }
    try {
      return JSON.parse(fs.readFileSync(path.join(dir, FIGURES_NAME), "utf8"));
    } catch {
      return undefined;
    }
  };

  // ---- 保存ダイアログ（ツールバーの Download を押すと Python が要求ファイルを書く） ----
  // webview は window.open もダウンロードもブロックするため、保存は拡張側で行う。
  const handleSaveRequest = async () => {
    const dir = vscodeDir();
    if (!dir) { return; }
    const reqPath = path.join(dir, SAVE_REQUEST_NAME);
    let req: { figure: number; format: string };
    try {
      req = JSON.parse(fs.readFileSync(reqPath, "utf8"));
    } catch {
      return;
    }
    removeQuiet(reqPath);            // 一度きりの要求として消す
    const fmt = (req.format || "png").replace(/[^a-z0-9]/gi, "").toLowerCase() || "png";

    const uri = await vscode.window.showSaveDialog({
      defaultUri: vscode.Uri.file(
        path.join(workspaceRoot() ?? os.homedir(), `figure${req.figure}.${fmt}`)),
      filters: { [fmt.toUpperCase()]: [fmt] },
    });
    if (!uri) { return; }
    const port = config().get<number>("webaggPort", 8988);
    const base = readFigures()?.url ?? `http://127.0.0.1:${port}`;
    try {
      const data = await fetchUrl(`${base}/${req.figure}/download.${fmt}`);
      fs.writeFileSync(uri.fsPath, data);
      vscode.window.setStatusBarMessage(
        `PyBP: ${path.basename(uri.fsPath)} を保存しました`, 2500);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      extLog(`SAVE  失敗: ${msg}`);
      vscode.window.showErrorMessage(`PyBP: 保存に失敗しました — ${msg}`);
    }
  };

  const syncFigurePanels = (info: { url: string; figures: number[] }) => {
    for (const n of info.figures) { openFigurePanel(info.url, n); }
    for (const [n, p] of [...figurePanels]) {      // plt.close された figure のタブは閉じる
      if (!info.figures.includes(n)) { p.dispose(); }
    }
  };

  // ---- セッション ----
  const sessionAlive = () => {
    const dir = vscodeDir();
    return !!runTerminal && !!dir && fs.existsSync(path.join(dir, SESSION_NAME));
  };

  // セッションに渡す環境変数。
  //  PYBP_PORT  : 渡さないと Python は既定の 8988 で待ち受け、拡張だけが設定値の
  //               ポートを見にいって figure タブが空になる
  //  PYBP_MPL   : matplotlib バックエンド。pybp.figureDisplay から決まる。
  //               "auto" は Python 側が Qt → Tk → webagg の順に解決する
  //  PYTHONPATH : 同梱した pybp を pip install 無しで import できるようにする
  const sessionEnv = (): { [k: string]: string } => {
    const env: { [k: string]: string } = {
      PYBP_PORT: String(config().get<number>("webaggPort", 8988)),
      PYBP_MPL: figureDisplay() === "window"
        ? config().get<string>("windowBackend", "auto")
        : "webagg",
    };
    if (config().get<boolean>("useBundledPython", true)) {
      const bundled = path.join(context.extensionPath, "python");
      if (fs.existsSync(bundled)) {
        const existing = process.env.PYTHONPATH;
        env.PYTHONPATH = existing ? `${bundled}${path.delimiter}${existing}` : bundled;
      } else {
        extLog(`SESSION 同梱 Python が見つからない: ${bundled}`);
      }
    }
    return env;
  };

  /**
   * 起動に使う Python を調べる。
   *
   * exe は解決済みの絶対パス。ターミナルでは必ずこれを使う。拡張ホストとターミナルでは
   * PATH が異なることがあり（conda / venv の自動アクティベート）、`python` のまま
   * 送ると「診断した処理系」と「実際に動く処理系」がずれて、依存は揃っているのに
   * ModuleNotFoundError になる。
   * pybp 自身も見る — 同梱版を PYTHONPATH で通しているので、ここが null なら
   * ターミナルは必ず `No module named pybp` で落ちる。
   */
  type Probe = { exe: string; missing: string[]; pybp: string | null };

  const PROBE_CODE = [
    "import json, sys",
    "import importlib.util as u",
    "def where(name):",
    "    try:",
    "        s = u.find_spec(name)",
    "    except Exception as e:",
    "        return '<error: %s>' % e",
    "    if s is None:",
    "        return None",
    "    return s.origin or next(iter(s.submodule_search_locations or []), None)",
    "print(json.dumps({",
    "    'exe': sys.executable,",
    "    'missing': [m for m in sys.argv[1:] if where(m) is None],",
    "    'pybp': where('pybp'),",
    "}))",
  ].join("\n");

  const probePython = (python: string, env: { [k: string]: string }):
    Promise<Probe | { error: string }> =>
    new Promise(resolve => {
      execFile(python, ["-c", PROBE_CODE, ...REQUIRED_MODULES.map(r => r.mod)],
        { env: { ...process.env, ...env }, windowsHide: true },
        (err, stdout, stderr) => {
          if (err) {
            resolve({ error: (stderr || err.message).trim() });
            return;
          }
          try {
            resolve(JSON.parse(stdout.trim().split(/\r?\n/).pop() ?? "") as Probe);
          } catch {
            resolve({ error: `診断出力を解釈できません: ${stdout.trim().slice(0, 200)}` });
          }
        });
    });

  const installDeps = (python: string, pkgs: string[], env: { [k: string]: string }) =>
    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `PyBP: ${pkgs.join(", ")} をインストールしています…`,
      },
      () => new Promise<boolean>(resolve => {
        execFile(python, ["-m", "pip", "install", ...pkgs],
          { env: { ...process.env, ...env }, windowsHide: true, maxBuffer: 16 * 1024 * 1024 },
          (err, _stdout, stderr) => {
            if (err) {
              const msg = (stderr || err.message).trim();
              extLog(`DEPS  pip install 失敗: ${msg.slice(0, 400)}`);
              vscode.window.showErrorMessage(
                `PyBP: インストールに失敗しました — ${msg.split("\n").pop()?.slice(0, 200)}`);
              resolve(false);
              return;
            }
            extLog(`DEPS  pip install 成功: ${pkgs.join(", ")}`);
            resolve(true);
          });
      }));

  const startSession = async (scriptPath?: string) => {
    const lp = extLogPath();
    if (lp) { try { fs.writeFileSync(lp, ""); } catch { /* ignore */ } }
    extLog("SESSION start");

    const python = config().get<string>("pythonPath", "python");
    const bundled = config().get<boolean>("useBundledPython", true);
    const env = sessionEnv();
    extLog(`SESSION pythonPath=${python} useBundledPython=${bundled}`);
    extLog(`SESSION figureDisplay=${figureDisplay()} PYBP_MPL=${env.PYBP_MPL}`);
    extLog(`SESSION PYTHONPATH=${env.PYTHONPATH ?? "(未設定)"}`);

    const probe = await probePython(python, env);
    if ("error" in probe) {
      extLog(`PROBE python を実行できない: ${probe.error.slice(0, 300)}`);
      vscode.window.showErrorMessage(
        `PyBP: Python を実行できません（${python}）。設定 pybp.pythonPath を確認してください`);
      return;
    }
    extLog(`PROBE exe=${probe.exe}`);
    extLog(`PROBE pybp=${probe.pybp ?? "(import できない)"}`);
    extLog(`PROBE 不足モジュール: ${probe.missing.join(", ") || "なし"}`);

    if (probe.missing.length > 0) {
      const pkgs = probe.missing.map(
        m => REQUIRED_MODULES.find(r => r.mod === m)?.pip ?? m);
      const pick = await vscode.window.showWarningMessage(
        `PyBP: 依存パッケージが不足しています（${pkgs.join(", ")}）`,
        "インストール", "あとで");
      if (pick === "インストール" && !await installDeps(probe.exe, pkgs, env)) {
        return;
      }
      // 「あとで」でもセッションは起動する。診断の誤検出で操作不能になるのを避けるため。
    }

    // pybp 本体が見えなければ、起動しても必ず ModuleNotFoundError で落ちる。
    // 心当たりを添えてここで止める（ターミナルの一瞬のエラーより分かりやすい）。
    if (!probe.pybp) {
      const hint = bundled
        ? `同梱版に PYTHONPATH が通っていません（${env.PYTHONPATH ?? "未設定"}）`
        : "設定 pybp.useBundledPython が false です。pip install -e ./pybp を実行するか true に戻してください";
      extLog(`PROBE 中止: pybp を import できない — ${hint}`);
      vscode.window.showErrorMessage(`PyBP: pybp を import できません — ${hint}`);
      return;
    }

    // 前セッションの残骸（強制終了時など）を掃除
    const dir = vscodeDir();
    if (dir) {
      removeQuiet(path.join(dir, SESSION_NAME));
      removeQuiet(path.join(dir, STATE_NAME));
      removeQuiet(path.join(dir, FIGURES_NAME));
      removeQuiet(path.join(dir, SAVE_REQUEST_NAME));
    }
    closeAllFigurePanels();
    if (runTerminal) { runTerminal.dispose(); }

    // シェルを挟まず Python 自身をターミナルのプロセスにする。
    //  - 診断した処理系（probe.exe）と実際に動く処理系が必ず一致する
    //  - パスに空白があってもクォート（PowerShell の & 演算子）を気にしなくてよい
    //  - PowerShell プロファイルや conda の自動アクティベートが割り込まない
    // ターミナルへの sendText は pty 経由で IPython / ipdb の標準入力に届くので、
    // 停止中のコマンド送信や %pybp での再実行はこれまで通り動く。
    const args = ["-m", "pybp", ...(scriptPath ? [scriptPath] : [])];
    extLog(`SESSION launch ${probe.exe} ${args.join(" ")}`);
    runTerminal = vscode.window.createTerminal({
      name: "PyBP", shellPath: probe.exe, shellArgs: args, env,
    });
    runTerminal.show(true);
    updateStatus();
  };

  // ---- 赤丸 ----
  dumpBreakpoints();
  context.subscriptions.push(vscode.debug.onDidChangeBreakpoints(dumpBreakpoints));

  // ---- コマンド: 実行系 ----
  context.subscriptions.push(
    vscode.commands.registerCommand("pybp.run", async () => {
      const doc = vscode.window.activeTextEditor?.document;
      if (!doc || doc.languageId !== "python") {
        vscode.window.showWarningMessage("PyBP: Python ファイルを開いてください");
        return;
      }
      await doc.save();
      if (sessionAlive()) {
        runTerminal!.show(true);
        runTerminal!.sendText(`%pybp "${doc.uri.fsPath}"`);   // 既存セッションで再実行
      } else {
        await startSession(doc.uri.fsPath);                    // 新規セッション
      }
    }),

    vscode.commands.registerCommand("pybp.restart", async () => {
      const doc = vscode.window.activeTextEditor?.document;
      if (runTerminal) {
        runTerminal.dispose();
        runTerminal = undefined;
      }
      await startSession(doc?.languageId === "python" ? doc.uri.fsPath : undefined);
    }),

    vscode.commands.registerCommand("pybp.openFigures", async () => {
      if (figureDisplay() === "window") {
        vscode.window.showInformationMessage(
          "PyBP: 設定 pybp.figureDisplay が window のため、図は別ウィンドウに出ています");
        return;
      }
      const info = readFigures();
      if (info && info.figures.length > 0) {
        syncFigurePanels(info);
        return;
      }
      // figure 情報が無い → webagg の一覧ページを Simple Browser で開く
      const port = config().get<number>("webaggPort", 8988);
      return vscode.commands.executeCommand(
        "simpleBrowser.api.open",
        vscode.Uri.parse(info?.url ?? `http://127.0.0.1:${port}`),
        { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true }
      );
    }),

    vscode.commands.registerCommand("pybp.copyFigure", async () => {
      if (process.platform !== "win32") {
        vscode.window.showWarningMessage("PyBP: 画像のクリップボードコピーは Windows のみ対応です");
        return;
      }
      // アイコンを押した時点でフォーカスされているタブを優先し、無ければ直近のものを使う
      const focused = [...figurePanels].find(([, p]) => p.active)?.[0];
      const num = focused ?? activeFigure;
      if (num === undefined) {
        vscode.window.showWarningMessage("PyBP: コピーする Figure タブがありません");
        return;
      }
      const port = config().get<number>("webaggPort", 8988);
      const base = readFigures()?.url ?? `http://127.0.0.1:${port}`;
      const tmp = path.join(os.tmpdir(), `pybp-fig${num}-${Date.now()}.png`);
      try {
        const png = await fetchUrl(`${base}/${num}/download.png`);
        fs.writeFileSync(tmp, png);
        await setClipboardImage(tmp);
        vscode.window.setStatusBarMessage(`PyBP: Figure ${num} をコピーしました`, 2000);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        extLog(`COPY  失敗: ${msg}`);
        vscode.window.showErrorMessage(`PyBP: Figure ${num} のコピーに失敗しました — ${msg}`);
      } finally {
        removeQuiet(tmp);
      }
    }),
  );

  // ---- コマンド: 停止中の pdb 操作 ----
  const send = (cmd: string) => () => {
    const term = runTerminal ?? vscode.window.activeTerminal;
    term?.sendText(cmd);
  };
  context.subscriptions.push(
    vscode.commands.registerCommand("pybp.continue", send("c")),
    vscode.commands.registerCommand("pybp.stepOver", send("n")),
    vscode.commands.registerCommand("pybp.stepInto", send("s")),
    vscode.commands.registerCommand("pybp.stepOut",  send("r")),
    vscode.commands.registerCommand("pybp.stop",     send("q")),
    vscode.window.onDidCloseTerminal(t => {
      if (t === runTerminal) {
        runTerminal = undefined;
        closeAllFigurePanels();
        clearStopped();
      }
    }),
  );

  // ---- 停止位置の監視 ----
  const onStateChanged = async (uri: vscode.Uri) => {
    try {
      const raw = await vscode.workspace.fs.readFile(uri);
      current = JSON.parse(Buffer.from(raw).toString("utf8"));
      setStopped(true);
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(current!.file));
      const ed = await vscode.window.showTextDocument(doc, { preserveFocus: true, preview: false });
      ed.revealRange(
        new vscode.Range(current!.line - 1, 0, current!.line - 1, 0),
        vscode.TextEditorRevealType.InCenterIfOutsideViewport
      );
    } catch {
      current = undefined;
      setStopped(false);
    }
    applyHighlight();
    updateStatus();
  };

  const stateWatcher = vscode.workspace.createFileSystemWatcher(`**/.vscode/${STATE_NAME}`);
  stateWatcher.onDidCreate(onStateChanged);
  stateWatcher.onDidChange(onStateChanged);
  stateWatcher.onDidDelete(clearStopped);
  context.subscriptions.push(
    stateWatcher,
    vscode.window.onDidChangeVisibleTextEditors(applyHighlight),
  );

  // ---- figure タブの自動オープン ----
  const onFigures = async () => {
    if (figureDisplay() !== "tab") { return; }
    const info = readFigures();
    if (info) { syncFigurePanels(info); }
  };
  const figWatcher = vscode.workspace.createFileSystemWatcher(`**/.vscode/${FIGURES_NAME}`);
  figWatcher.onDidCreate(onFigures);
  figWatcher.onDidChange(onFigures);
  context.subscriptions.push(figWatcher);

  // ---- 保存要求の監視 ----
  const saveWatcher = vscode.workspace.createFileSystemWatcher(`**/.vscode/${SAVE_REQUEST_NAME}`);
  saveWatcher.onDidCreate(handleSaveRequest);
  saveWatcher.onDidChange(handleSaveRequest);
  context.subscriptions.push(saveWatcher);

  // ---- 設定変更への追従 ----
  // バックエンドはセッション起動時に決まるので、走っている間は作り直さないと変わらない。
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(async e => {
      if (!e.affectsConfiguration("pybp.figureDisplay")
        && !e.affectsConfiguration("pybp.windowBackend")
        && !e.affectsConfiguration("pybp.autoOpenFigures")) { return; }
      updateFigureWindowContext();
      if (!runTerminal) { return; }
      const pick = await vscode.window.showInformationMessage(
        "PyBP: 図の表示先が変わりました。セッションを作り直すと反映されます",
        "再起動");
      if (pick === "再起動") {
        await vscode.commands.executeCommand("pybp.restart");
      }
    }),
  );

  setStopped(false);
  updateFigureWindowContext();
  updateStatus();
}

export function deactivate() {}