# Shipped UI persistence (seed memory) for GitHub CORE + HF mirror.
# Keep in sync with .gitignore allow-list under workspace/.
#
# Dot-source:
#   . (Join-Path $PSScriptRoot "workspace_shipped_memory.ps1")

$script:ShippedWorkspaceMemoryFiles = @(
    "load_preview_ui_state.json",
    "region_wobble_mask.png"
)

$script:ShippedWorkspaceMemoryGlobs = @(
    "region_wobble_mask_*.png"
)

$script:ShippedWorkspaceMemoryDirs = @(
    "basic_layers"
)

function Get-ShippedWorkspaceMemoryNames {
    return @(
        $script:ShippedWorkspaceMemoryFiles +
        $script:ShippedWorkspaceMemoryDirs
    )
}

function Test-IsShippedWorkspaceMemoryName([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) { return $false }
    if ($script:ShippedWorkspaceMemoryFiles -contains $Name) { return $true }
    if ($script:ShippedWorkspaceMemoryDirs -contains $Name) { return $true }
    foreach ($glob in $script:ShippedWorkspaceMemoryGlobs) {
        if ($Name -like $glob) { return $true }
    }
    return $false
}

function Copy-ShippedWorkspaceMemory {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$DestRoot
    )

    $srcWorkspace = Join-Path $SourceRoot "workspace"
    $dstWorkspace = Join-Path $DestRoot "workspace"
    if (-not (Test-Path $srcWorkspace)) {
        Write-Warning "No source workspace: $srcWorkspace"
        return
    }
    if (-not (Test-Path $dstWorkspace)) {
        New-Item -ItemType Directory -Force -Path $dstWorkspace | Out-Null
    }

    $copied = @()
    foreach ($name in $script:ShippedWorkspaceMemoryFiles) {
        $src = Join-Path $srcWorkspace $name
        if (Test-Path $src) {
            Copy-Item -Force $src (Join-Path $dstWorkspace $name)
            $copied += $name
        }
    }
    foreach ($glob in $script:ShippedWorkspaceMemoryGlobs) {
        Get-ChildItem -Path $srcWorkspace -File -Filter $glob -ErrorAction SilentlyContinue |
            ForEach-Object {
                Copy-Item -Force $_.FullName (Join-Path $dstWorkspace $_.Name)
                $copied += $_.Name
            }
    }
    foreach ($dirName in $script:ShippedWorkspaceMemoryDirs) {
        $src = Join-Path $srcWorkspace $dirName
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $dstWorkspace $dirName
        if (Test-Path $dst) {
            Remove-Item -LiteralPath $dst -Recurse -Force -ErrorAction SilentlyContinue
        }
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        robocopy $src $dst /E /NFL /NDL /NJH /NJS /NC /NS /NP /XD __pycache__ |
            Out-Null
        if ($LASTEXITCODE -ge 8) {
            throw "robocopy failed copying workspace\$dirName (exit=$LASTEXITCODE)"
        }
        $copied += "$dirName/"
    }

    if ($copied.Count -gt 0) {
        Write-Host "Shipped workspace memory -> $dstWorkspace : $($copied -join ', ')"
    } else {
        Write-Warning "No shipped workspace memory found under $srcWorkspace"
    }
}
