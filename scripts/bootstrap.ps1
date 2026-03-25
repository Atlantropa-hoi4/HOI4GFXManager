param(
    [string]$PythonExe = "",
    [switch]$IncludeDev
)

$ErrorActionPreference = "Stop"

function Resolve-PythonSpec {
    param([string]$OverrideExe)

    if ($OverrideExe) {
        return [pscustomobject]@{
            Command = $OverrideExe
            Args = @()
        }
    }

    $candidates = @(
        @{ Command = "py"; Args = @("-3.13") },
        @{ Command = "py"; Args = @("-3") },
        @{ Command = "python" ; Args = @() },
        @{ Command = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        if (Get-Command $candidate.Command -ErrorAction SilentlyContinue) {
            return [pscustomobject]@{
                Command = $candidate.Command
                Args = $candidate.Args
            }
        }
    }

    throw "Python 3.13 executable not found. Install Python 3.13 x64 or pass -PythonExe C:\Path\To\python.exe."
}

function Get-PythonVersion {
    param($PythonSpec)

    $version = & $PythonSpec.Command @($PythonSpec.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"))
    return $version.Trim()
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PythonSpec = Resolve-PythonSpec -OverrideExe $PythonExe
$DetectedVersion = Get-PythonVersion -PythonSpec $PythonSpec

if (-not $DetectedVersion.StartsWith("3.13.")) {
    throw "Unsupported Python version detected: $DetectedVersion. This repository currently targets Python 3.13.x."
}

$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

Push-Location $RepoRoot
try {
    if (-not (Test-Path $VenvPython)) {
        & $PythonSpec.Command @($PythonSpec.Args + @("-m", "venv", ".venv"))
    }

    & $VenvPython -m pip install --upgrade pip setuptools wheel

    $InstallTarget = if ($IncludeDev) { ".[dev]" } else { "." }
    & $VenvPython -m pip install -e $InstallTarget

    Write-Host ""
    Write-Host "Bootstrap complete."
    Write-Host "Run the app with:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1"
    Write-Host ""
    Write-Host "Run the baseline checks with:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1"
}
finally {
    Pop-Location
}
