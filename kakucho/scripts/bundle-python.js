/**
 * pybp/pybp/ を拡張の python/ 配下へコピーして .vsix に同梱する。
 * vsce package（vscode:prepublish）から実行される。
 * コピー先はビルド生成物なので .gitignore 済み — 編集しても意味がない。
 */
const fs = require("fs");
const path = require("path");

const src = path.resolve(__dirname, "..", "..", "pybp", "pybp");
const dest = path.resolve(__dirname, "..", "python", "pybp");

if (!fs.existsSync(src)) {
  console.error(`bundle-python: コピー元が見つかりません: ${src}`);
  process.exit(1);
}

fs.rmSync(dest, { recursive: true, force: true });
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.cpSync(src, dest, {
  recursive: true,
  filter: (p) => !p.split(path.sep).includes("__pycache__") && !p.endsWith(".pyc"),
});

const files = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { walk(p); } else { files.push(path.relative(dest, p)); }
  }
})(dest);

if (!files.includes("__main__.py")) {
  console.error("bundle-python: __main__.py が見つかりません。コピーに失敗しています");
  process.exit(1);
}
console.log(`bundle-python: ${files.length} ファイルを同梱`);
for (const f of files) { console.log("   ", f); }
