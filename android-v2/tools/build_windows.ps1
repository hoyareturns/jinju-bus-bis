param(
    [string]$ToolRoot = 'D:/CodexBuildTools/jinju-bus-20260911',
    [switch]$LiveApiCheck
)
$ErrorActionPreference = 'Stop'
$projectDirectory = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$buildAlias = Join-Path $ToolRoot 'project'
if (-not (Test-Path -LiteralPath $buildAlias)) {
    New-Item -ItemType Junction -Path $buildAlias -Target $projectDirectory | Out-Null
}
if ((Get-Item -LiteralPath $buildAlias).Target -ne $projectDirectory) {
    throw 'Build junction points to a different project.'
}
$env:JAVA_HOME = Join-Path $ToolRoot 'jdk/jdk-17.0.20.1+1'
$env:ANDROID_HOME = Join-Path $ToolRoot 'sdk'
$env:GRADLE_USER_HOME = Join-Path $ToolRoot 'gradle-home'
$env:TAGO_LIVE_CHECK = if ($LiveApiCheck) { 'true' } else { 'false' }
foreach ($required in @($env:JAVA_HOME, $env:ANDROID_HOME)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Build tool missing: $required" }
}
Push-Location (Join-Path $buildAlias 'android')
try {
    & ./gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:lintDebug "-PJINJU_BUILD_ROOT=$ToolRoot/build-output" --project-cache-dir "$ToolRoot/project-cache" --console=plain
    if ($LASTEXITCODE -ne 0) { throw "Gradle failed: $LASTEXITCODE" }
    Get-Item -LiteralPath "$ToolRoot/build-output/app/outputs/apk/debug/app-debug.apk" | Select-Object FullName, Length
} finally { Pop-Location }
