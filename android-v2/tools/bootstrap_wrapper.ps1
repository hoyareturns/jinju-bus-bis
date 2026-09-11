$ErrorActionPreference = 'Stop'
$projectDirectory = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$wrapper = Join-Path $projectDirectory 'android/gradle/wrapper/gradle-wrapper.jar'
$expectedHash = '497C8C2A7E5031F6AA847F88104AA80A93532EC32EE17BDB8D1D2F67A194A9C7'
if (Test-Path -LiteralPath $wrapper) {
    if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash -eq $expectedHash) {
        Write-Output 'Gradle 9.5.0 Wrapper already verified.'
        exit 0
    }
    throw 'Existing wrapper has a different hash; inspect it before replacing it.'
}
$temporary = "$wrapper.download"
try {
    Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/gradle/gradle/v9.5.0/gradle/wrapper/gradle-wrapper.jar' -OutFile $temporary
    if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $expectedHash) {
        throw 'Official Gradle Wrapper checksum mismatch.'
    }
    Move-Item -LiteralPath $temporary -Destination $wrapper
    Write-Output 'Gradle 9.5.0 Wrapper downloaded and verified.'
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
}
