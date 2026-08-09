$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $PSScriptRoot
Set-Location $AppDir
$VenvPython = Join-Path $AppDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython -PathType Leaf)) {
    Write-Error "PMC is not set up. Run scripts\setup_windows.ps1 first."
}
& $VenvPython -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "The PMC virtual environment uses an unsupported Python version. Remove .venv and run setup_windows.ps1 again with Python 3.11 through 3.14."
}
& $VenvPython -c "import openai, pandas, streamlit"
if ($LASTEXITCODE -ne 0) {
    Write-Error "PMC dependencies are missing or incomplete. Run scripts\setup_windows.ps1 again."
}

$SessionKeyAdded = $false
if (-not $env:OPENAI_API_KEY) {
    $KeyChoice = Read-Host "Configure the optional OpenAI API key for this PowerShell session? [y/N]"
    if ($KeyChoice -match "^[Yy]$") {
        $SecureKey = Read-Host "OpenAI API key (input hidden)" -AsSecureString
        $Credential = [System.Management.Automation.PSCredential]::new("PMC", $SecureKey)
        $env:OPENAI_API_KEY = $Credential.GetNetworkCredential().Password
        $SessionKeyAdded = $true
    }
}

try {
    Write-Host "Starting Product Manager Central. Press Control-C in this window to stop."
    & $VenvPython -m streamlit run (Join-Path $AppDir "app.py")
} finally {
    if ($SessionKeyAdded) {
        Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    }
}
