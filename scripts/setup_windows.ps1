$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $PSScriptRoot
Set-Location $AppDir

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExecutable = "py"
    $PythonPrefix = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonExecutable = "python"
    $PythonPrefix = @()
} else {
    Write-Error "Python was not found. Install Python 3.11 through 3.14 from python.org, select 'Add Python to PATH', then run setup again."
}

& $PythonExecutable @PythonPrefix -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "PMC requires Python 3.11 through 3.14. Python 3.14.6 is the natively validated version."
}

$VenvPython = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython -PathType Leaf)) {
    Write-Host "Creating an isolated .venv..."
    & $PythonExecutable @PythonPrefix -m venv (Join-Path $AppDir ".venv")
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Virtual-environment creation failed. Confirm that this folder is writable and your Python installation includes venv."
    }
} else {
    Write-Host "Reusing the existing local .venv."
}
& $VenvPython -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "The existing .venv uses an unsupported Python version. Remove only this application's .venv, then run setup again."
}

Write-Host "Installing PMC's declared dependencies..."
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $AppDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Dependency installation failed. Check your internet connection and the error above, then run setup again."
}

Write-Host "Setup complete. Start PMC with scripts\run_windows.ps1"
