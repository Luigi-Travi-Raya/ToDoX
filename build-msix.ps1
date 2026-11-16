$ErrorActionPreference = "Stop"

$ProjectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectDirectory

& ".\build.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar a distribuicao portatil do ToDoX."
}

$BuildRoot = [System.IO.Path]::GetFullPath((Join-Path $ProjectDirectory "build"))
$StageDirectory = [System.IO.Path]::GetFullPath((Join-Path $BuildRoot "msix-layout"))
if (-not $StageDirectory.StartsWith($BuildRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Diretorio temporario do MSIX fora da pasta build."
}

if (Test-Path -LiteralPath $StageDirectory) {
    Remove-Item -LiteralPath $StageDirectory -Recurse -Force
}
New-Item -ItemType Directory -Path $StageDirectory | Out-Null

Copy-Item -Path ".\dist\ToDoX\*" -Destination $StageDirectory -Recurse
Copy-Item -LiteralPath ".\msix\AppxManifest.xml" -Destination $StageDirectory
& ".\.venv\Scripts\python.exe" ".\tools\generate_msix_assets.py" (Join-Path $StageDirectory "Assets")

$MakeAppxCommand = Get-Command "makeappx.exe" -ErrorAction SilentlyContinue
if ($null -ne $MakeAppxCommand) {
    $MakeAppxPath = $MakeAppxCommand.Source
} else {
    $MakeAppxFile = Get-ChildItem `
        -LiteralPath "C:\Program Files (x86)\Windows Kits\10\bin" `
        -Filter "makeappx.exe" `
        -Recurse `
        -File `
        -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    $MakeAppxPath = if ($null -ne $MakeAppxFile) { $MakeAppxFile.FullName } else { $null }
}
if ($null -eq $MakeAppxPath) {
    throw "MakeAppx nao encontrado. Instale o Windows SDK ou o MSIX Packaging Tool."
}

[xml]$PackageManifest = Get-Content -LiteralPath ".\msix\AppxManifest.xml" -Raw
$PackageVersion = $PackageManifest.Package.Identity.Version
$Output = Join-Path $ProjectDirectory ("dist\ToDoX_{0}_x64.msix" -f $PackageVersion)
if (Test-Path -LiteralPath $Output) {
    Remove-Item -LiteralPath $Output -Force
}

& $MakeAppxPath pack /d $StageDirectory /p $Output /o
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar o pacote MSIX."
}

Write-Host ""
Write-Host "MSIX criado em: $Output"
