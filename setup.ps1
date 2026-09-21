<#
 PyBP setup / repair script  (run from the repository root)

   .\setup.ps1                 # repair both Python side and VS Code extension
   .\setup.ps1 -PythonOnly     # Python side only
   .\setup.ps1 -ExtensionOnly  # extension side only
   .\setup.ps1 -Python C:\path\to\python.exe   # use a specific interpreter (same one as pybp.pythonPath)

 If blocked by execution policy:
   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#>
param(
  [string]$Python = "python",
  [switch]$PythonOnly,
  [switch]$ExtensionOnly
)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$PyDir = Join-Path $Root "pybp"
$ExtDir = Join-Path $Root "kakucho"

function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Run($exe, $argList) {
  & $exe @argList
  if ($LASTEXITCODE -ne 0) { throw "FAILED: $exe $($argList -join ' ') (exit $LASTEXITCODE)" }
}

# ------------------------------------------------------------------ Python side
if (-not $ExtensionOnly) {
  Step "Python: interpreter"
  Run $Python @("--version")
  Run $Python @("-c", "import sys; print(sys.executable)")

  Step "Python: remove stale install (old path / old version)"
  $ErrorActionPreference = "Continue"
  & $Python -m pip uninstall -y pybp 2>&1 | Out-Host
  $ErrorActionPreference = "Stop"
  # stale egg-info from the pre-move install (v0.1.0) can confuse pip; it is regenerated
  $egg = Join-Path $PyDir "pybp.egg-info"
  if (Test-Path $egg) { Remove-Item $egg -Recurse -Force }

  Step "Python: editable install from the new location"
  Run $Python @("-m", "pip", "install", "-e", "$PyDir[qt,web]")

  Step "Python: verify"
  Run $Python @("-c", "import pybp, pybp.core, pybp.webagg, IPython, ipdb, matplotlib, tornado; print('pybp loaded from:', pybp.__file__)")
}

# ------------------------------------------------------------------ Extension side
if (-not $PythonOnly) {
  Step "Extension: clean reinstall of node_modules (copied node_modules is unreliable)"
  Push-Location $ExtDir
  try {
    if (Test-Path "node_modules") { Remove-Item "node_modules" -Recurse -Force }
    if (Test-Path "out") { Remove-Item "out" -Recurse -Force }
    Run "npm" @("install")

    Step "Extension: compile"
    Run "npm" @("run", "compile")
    if (-not (Test-Path "out\extension.js")) { throw "out\extension.js was not produced" }

    Step "Extension: package vsix"
    Run "npx" @("--yes", "@vscode/vsce", "package", "--skip-license", "--allow-missing-repository", "--no-dependencies")
    $vsix = Get-ChildItem "*.vsix" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

    Step "Extension: reinstall into VS Code"
    $ErrorActionPreference = "Continue"   # "not installed" is not an error
    & code --uninstall-extension local.pybp 2>&1 | Out-Host
    $ErrorActionPreference = "Stop"
    Run "code" @("--install-extension", $vsix.FullName, "--force")
    Write-Host "Installed $($vsix.Name)"
  } finally { Pop-Location }
}

Write-Host "`nDONE. Fully quit and restart VS Code (Ctrl+Shift+P -> 'Developer: Reload Window' is not enough for a removed/reinstalled extension)." -ForegroundColor Green
