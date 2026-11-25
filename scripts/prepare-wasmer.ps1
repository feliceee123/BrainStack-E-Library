$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sitePackages = Join-Path $repoRoot 'wasmer\site-packages'

if (-not (Get-Command wasmer -ErrorAction SilentlyContinue)) {
    throw 'Wasmer CLI was not found. Install it before preparing the package.'
}

if (Test-Path -LiteralPath $sitePackages) {
    Remove-Item -LiteralPath $sitePackages -Recurse -Force
}

New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null

Push-Location $repoRoot
try {
    & wasmer run --net --volume '.:/project' python/python@=3.13.18 -- `
        -m pip install `
        --target /project/wasmer/site-packages `
        --only-binary=:all: `
        -r /project/backend/requirements.txt

    if ($LASTEXITCODE -ne 0) {
        throw "Wasmer dependency preparation failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
