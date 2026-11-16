$ErrorActionPreference = "Stop"

$ProjectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectDirectory

$OutputDirectory = [System.IO.Path]::GetFullPath((Join-Path $ProjectDirectory "dist\ToDoX"))
$RunningFromOutput = Get-Process -Name "ToDoX" -ErrorAction SilentlyContinue | Where-Object {
    try {
        $ProcessPath = $_.Path
        $null -ne $ProcessPath -and
            [System.IO.Path]::GetFullPath($ProcessPath).StartsWith(
                $OutputDirectory,
                [System.StringComparison]::OrdinalIgnoreCase
            )
    } catch {
        $false
    }
}

if ($RunningFromOutput) {
    $ProcessIds = ($RunningFromOutput.Id | Sort-Object) -join ", "
    throw "O ToDoX ainda esta em execucao (processos: $ProcessIds). Encerre-o pela bandeja do Windows antes de compilar novamente."
}

& ".\.venv\Scripts\python.exe" ".\tools\generate_brand_assets.py"
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar os icones da marca."
}

npm run build --prefix frontend
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao compilar o frontend."
}

$PreviousPythonUserBase = $env:PYTHONUSERBASE
$env:PYTHONUSERBASE = Join-Path $ProjectDirectory ".python-user-base"
& ".\.venv\Scripts\python.exe" -s -m PyInstaller `
    --noconfirm `
    --clean `
    ListaDeTarefas.spec
$PyInstallerExitCode = $LASTEXITCODE
if ($null -eq $PreviousPythonUserBase) {
    Remove-Item Env:PYTHONUSERBASE -ErrorAction SilentlyContinue
} else {
    $env:PYTHONUSERBASE = $PreviousPythonUserBase
}

if ($PyInstallerExitCode -ne 0) {
    throw "Falha ao gerar o executável."
}

Write-Host ""
Write-Host "Executavel criado em: $ProjectDirectory\dist\ToDoX\ToDoX.exe"
