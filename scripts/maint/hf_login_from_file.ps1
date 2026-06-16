param(
    [Parameter(Mandatory = $true)]
    [string]$TokenFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $TokenFile)) {
    throw "Token file not found: $TokenFile"
}

$token = (Get-Content -LiteralPath $TokenFile -Raw -Encoding UTF8).Trim()
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Token file is empty: $TokenFile"
}
if ($token -match "[\x00-\x08\x0B\x0C\x0E-\x1F]") {
    throw @"
Token contains invalid control characters (e.g. NUL bytes).
Do NOT paste binary data or copy from Word/PDF.
Create a new token at https://huggingface.co/settings/tokens
Save ONLY the token string (starts with hf_) in Notepad as UTF-8, one line.
"@
}
if ($token -notmatch '^hf_') {
    throw "Token should start with hf_. Re-copy from https://huggingface.co/settings/tokens"
}

Remove-Item Env:HF_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:HUGGING_FACE_HUB_TOKEN -ErrorAction SilentlyContinue

Write-Host "Logging in to Hugging Face (token from file, not echoed) ..."
& python -m huggingface_hub.cli.hf auth login --token $token
if ($LASTEXITCODE -ne 0) {
    throw "hf auth login failed (exit $LASTEXITCODE)"
}

& python -m huggingface_hub.cli.hf auth whoami
if ($LASTEXITCODE -ne 0) {
    throw "hf auth whoami failed after login"
}

Write-Host "[OK] Hugging Face login verified."
