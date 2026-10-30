# Configura o ambiente Conda, instala as dependências do projeto e configura o Jupyter/VS Code.
# Execute na pasta raiz do projeto ou coloque estes arquivos na raiz do projeto.

$ErrorActionPreference = "Stop"
$EnvName = "cgu-rag"
$PythonVersion = "3.11"
$DisplayName = "Python 3.11 (CGU RAG)"
$ProjectDir = $PSScriptRoot

function Write-Step($Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

try {
    Write-Step "Verificando a raiz do projeto"
    if (-not (Test-Path (Join-Path $ProjectDir "pyproject.toml"))) {
        throw "Não encontrei pyproject.toml em '$ProjectDir'. Coloque os arquivos configurar-cgu-rag.ps1 e configurar-cgu-rag.bat na raiz do projeto (a mesma pasta de pyproject.toml) e execute novamente."
    }

    Write-Step "Localizando o Conda"
    $CondaCandidates = @(
        "C:\ProgramData\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe"
    )

    $Conda = $CondaCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $Conda) {
        $Command = Get-Command conda -ErrorAction SilentlyContinue
        if ($Command) { $Conda = $Command.Source }
    }

    if (-not $Conda) {
        throw "Não encontrei o conda.exe. Verifique a instalação do Miniconda."
    }

    Write-Host "Conda encontrado: $Conda"

    Write-Step "Verificando se o ambiente '$EnvName' existe"
    & $Conda env list | Out-Host
    $EnvPath = Join-Path $env:USERPROFILE ".conda\envs\$EnvName"
    $EnvPathAlt = Join-Path (Split-Path (Split-Path $Conda -Parent) -Parent) "envs\$EnvName"

    if (-not (Test-Path (Join-Path $EnvPath "python.exe")) -and
        -not (Test-Path (Join-Path $EnvPathAlt "python.exe"))) {
        Write-Step "Criando ambiente Python $PythonVersion"
        & $Conda create -n $EnvName "python=$PythonVersion" pip -y
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao criar o ambiente. Verifique os Termos de Serviço dos canais Conda e tente novamente."
        }
    } else {
        Write-Host "Ambiente '$EnvName' já existe."
    }

    Write-Step "Instalando as dependências do projeto (pip install -e `".[notebook]`")"
    Push-Location $ProjectDir
    try {
        & $Conda run -n $EnvName python -m pip install -e ".[notebook]"
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao instalar as dependências do projeto. Confira o pyproject.toml e a conexão com a internet."
        }
    }
    finally {
        Pop-Location
    }

    Write-Step "Instalando/atualizando Jupyter e ipykernel no ambiente"
    & $Conda run -n $EnvName python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar o pip." }

    & $Conda run -n $EnvName python -m pip install --upgrade jupyterlab ipykernel
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar Jupyter/ipykernel." }

    Write-Step "Registrando o kernel Jupyter"
    & $Conda run -n $EnvName python -m ipykernel install --user --name $EnvName --display-name $DisplayName
    if ($LASTEXITCODE -ne 0) { throw "Falha ao registrar o kernel." }

    Write-Step "Configurando o interpretador padrão do VS Code para este projeto"
    $VscodeDir = Join-Path $ProjectDir ".vscode"
    New-Item -ItemType Directory -Path $VscodeDir -Force | Out-Null
    $SettingsPath = Join-Path $VscodeDir "settings.json"
    $PythonExe = (& $Conda run -n $EnvName python -c "import sys; print(sys.executable)").Trim()

    if (-not $PythonExe) { throw "Não foi possível descobrir o caminho do Python do ambiente." }

    $Settings = [ordered]@{
        "python.defaultInterpreterPath" = $PythonExe
        "jupyter.askForKernelRestart" = $false
    }

    $Settings | ConvertTo-Json -Depth 5 | Set-Content -Path $SettingsPath -Encoding UTF8

    Write-Step "Validando a configuração e as dependências"
    & $Conda run -n $EnvName python --version
    & $Conda run -n $EnvName python -c "import sys, ipykernel, jupyter, fitz, numpy, requests, sentence_transformers, openai; print('Interpretador:', sys.executable); print('Dependências principais: OK')"
    if ($LASTEXITCODE -ne 0) { throw "A validação do ambiente ou das dependências falhou." }

    Write-Host "`nCONFIGURAÇÃO CONCLUÍDA!" -ForegroundColor Green
    Write-Host "Ambiente: $EnvName"
    Write-Host "Kernel: $DisplayName"
    Write-Host "Python: $PythonExe"
    Write-Host "VS Code: $SettingsPath"
    Write-Host "`nPróximos passos:"
    Write-Host "1. Abra/recarregue esta pasta no VS Code."
    Write-Host "2. Abra o arquivo .ipynb e selecione 'Python 3.11 (CGU RAG)' em Select Kernel."
    Write-Host "3. O VS Code normalmente memoriza o kernel selecionado para esse notebook."
}
catch {
    Write-Host "`nERRO: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`nPressione Enter para fechar."
Read-Host | Out-Null
