$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Virtual environment not found. Run .\scripts\bootstrap.ps1 first."
}

Push-Location $RepoRoot
try {
    & $PythonExe -m compileall main.py focusgfxshine.py
    & $PythonExe -m unittest discover -s tests -p "test_*.py"
}
finally {
    Pop-Location
}
