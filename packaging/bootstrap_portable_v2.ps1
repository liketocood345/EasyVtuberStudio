param([string]$PortableRoot='', [switch]$Quiet, [switch]$ForceRebuildRuntime,
      [switch]$MouseStudentOnly, [switch]$Tha3Only)
# Compatibility entrypoint: keep dependency selection in one implementation.
& (Join-Path $PSScriptRoot 'bootstrap_portable.ps1') @PSBoundParameters
