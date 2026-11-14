$ErrorActionPreference = 'Stop'
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $base
$source = @(
    'cliente.py', 'servidor.py', 'jogo.py', 'motor.py',
    'README.md', 'INICIAR_DEMO_WINDOWS.bat',
    'MiniWormsLauncher.cs', 'GERAR_ENTREGA_WINDOWS.bat', 'EMPACOTAR_WINDOWS.ps1'
)
foreach ($file in $source) {
    if (-not (Test-Path -LiteralPath (Join-Path $base $file) -PathType Leaf)) {
        throw "Arquivo obrigatorio nao encontrado: $file"
    }
}
$exe = Join-Path $base 'MiniWorms.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw 'MiniWorms.exe nao encontrado. A compilacao nao foi concluida.'
}
$out = Join-Path $base 'ENTREGA'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$srcZip = Join-Path $out 'MiniWorms_SEM_EXECUTAVEL.zip'
$exeZip = Join-Path $out 'MiniWorms_COM_EXECUTAVEL.zip'
$sourcePaths = @($source | ForEach-Object { Join-Path $base $_ })
Compress-Archive -LiteralPath $sourcePaths -DestinationPath $srcZip -CompressionLevel Optimal -Force
Compress-Archive -LiteralPath ($sourcePaths + @($exe)) -DestinationPath $exeZip -CompressionLevel Optimal -Force
foreach ($zip in @($srcZip, $exeZip)) {
    $bytes = (Get-Item -LiteralPath $zip).Length
    Write-Host ("{0}: {1} bytes" -f (Split-Path -Leaf $zip), $bytes)
    if ($bytes -ge 10000000) {
        throw "O arquivo ultrapassa o limite de 10 MB: $zip"
    }
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
foreach ($zip in @($srcZip, $exeZip)) {
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zip)
    try {
        $names = @($archive.Entries | ForEach-Object { $_.Name })
        if ($names -contains 'MiniWorms_Servidor.exe' -or $names -contains 'MiniWorms_Cliente.exe') {
            throw "O ZIP contem executaveis antigos: $zip"
        }
        if (($zip -eq $exeZip) -and -not ($names -contains 'MiniWorms.exe')) {
            throw 'O ZIP com executavel nao contem MiniWorms.exe'
        }
        if (($zip -eq $srcZip) -and ($names -contains 'MiniWorms.exe')) {
            throw 'O ZIP sem executavel contem um EXE indevido'
        }
    }
    finally {
        $archive.Dispose()
    }
}
Write-Host 'Entrega gerada e verificada na pasta ENTREGA.'