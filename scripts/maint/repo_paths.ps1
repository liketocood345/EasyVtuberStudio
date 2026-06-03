# Shared local repo path resolution (GitHub: easyvtuberstudio-develop / easyvtuberstudio-main).

$script:DevDirCandidates = @("easyvtuberstudio-develop", "tha4fork-develop")
$script:ForkDirCandidates = @("easyvtuberstudio-main", "tha4fork")

function Get-DevelopRootFromScript {
    param([string]$ScriptRoot = $PSScriptRoot)
    return (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
}

function Find-SiblingRepo {
    param(
        [string]$ParentDir,
        [string[]]$DirNames,
        [switch]$RequireGit
    )
    foreach ($name in $DirNames) {
        $candidate = Join-Path $ParentDir $name
        if (-not (Test-Path $candidate)) { continue }
        if ($RequireGit -and -not (Test-Path (Join-Path $candidate ".git"))) { continue }
        return (Resolve-Path $candidate).Path
    }
    return $null
}

function Resolve-DevelopForkRoots {
    param(
        [string]$DevRoot = "",
        [string]$ForkRoot = ""
    )
    if ($DevRoot) {
        $DevRoot = (Resolve-Path $DevRoot).Path
    } else {
        $DevRoot = Get-DevelopRootFromScript
    }
    $parent = Split-Path $DevRoot -Parent
    if (-not $ForkRoot) {
        $ForkRoot = Find-SiblingRepo -ParentDir $parent -DirNames $script:ForkDirCandidates -RequireGit
    } else {
        $ForkRoot = (Resolve-Path $ForkRoot).Path
    }
    if (-not $ForkRoot) {
        throw "Fork repo not found beside $DevRoot (tried: $($script:ForkDirCandidates -join ', '))"
    }
    return @{ DevRoot = $DevRoot; ForkRoot = $ForkRoot }
}

function Get-GitHubOriginUrl {
    param([ValidateSet("develop", "main")][string]$Repo = "main")
    return "https://github.com/liketocood345/easyvtuberstudio-$Repo.git"
}
