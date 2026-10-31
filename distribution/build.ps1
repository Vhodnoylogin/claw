param(
    [Parameter(Mandatory=$true)][string]$BuildDir,
    [Parameter(Mandatory=$true)][string]$CommonLibDir,
    [Parameter(Mandatory=$true)][string]$SkeeHeader,
    [string]$CMakeExe,
    [string]$Generator = 'Visual Studio 18 2026',
    [ValidateSet('UNIVERSAL')][string]$Runtime = 'UNIVERSAL',
    [string]$DependencyPrefix,
    [string]$ToolchainFile,
    [string]$PhysicsModelHeader,
    [string]$PhysicsFixtureHeader,
    [string]$OBodyHeader,
    [int]$Parallel = 8,
    [switch]$BuildTests,
    [hashtable]$FetchSources = @{}
)
$ErrorActionPreference = 'Stop'
$Runtime = $Runtime.ToUpperInvariant()
$clawSource = [IO.Path]::GetFullPath($PSScriptRoot)
$clawRepo = [IO.Directory]::GetParent($clawSource).FullName
$clawOutput = [IO.Path]::GetFullPath($BuildDir)
$clawCache = Join-Path $clawOutput 'CMakeCache.txt'
if (Test-Path -LiteralPath $clawCache) {
    $clawRuntimeEntry = Get-Content -LiteralPath $clawCache | Where-Object { $_ -match '^CLAW_RUNTIME:.*=' } | Select-Object -First 1
    $clawPreviousRuntime = if ($clawRuntimeEntry) { ($clawRuntimeEntry -split '=', 2)[1] } else { 'VR' }
    if ($clawPreviousRuntime -ne $Runtime) { throw 'Use a fresh universal BuildDir; preserve older SE/VR build trees.' }
}
$clawAllowedWork = [IO.Path]::Combine($clawRepo, 'work') + [IO.Path]::DirectorySeparatorChar
if ($clawOutput.Equals($clawRepo, [StringComparison]::OrdinalIgnoreCase) -or
    ($clawOutput.StartsWith($clawRepo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and
    !$clawOutput.StartsWith($clawAllowedWork, [StringComparison]::OrdinalIgnoreCase))) {
    throw 'BuildDir must be external or under ignored work/; source builds are refused.'
}
if (($clawOutput -split '[\\/]') | Where-Object { $_ -in @('Data','mods','overwrite','downloads') }) {
    throw 'BuildDir cannot be a live game, mod or archive destination.'
}
$clawAncestor = $clawOutput
while ($clawAncestor) {
    if (Test-Path -LiteralPath $clawAncestor) {
        $clawItem = Get-Item -LiteralPath $clawAncestor -Force
        if ($clawItem.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'BuildDir ancestry contains a link/junction.' }
    }
    $clawParent = [IO.Directory]::GetParent($clawAncestor)
    if (!$clawParent) { break }; $clawAncestor = $clawParent.FullName
}
if (!$CMakeExe) {
    $clawCommand = Get-Command cmake -ErrorAction SilentlyContinue
    if ($clawCommand) { $CMakeExe = $clawCommand.Source }
    else {
        $clawVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
        if (!(Test-Path -LiteralPath $clawVsWhere)) { throw 'Specify -CMakeExe or add cmake to PATH.' }
        $clawVS = & $clawVsWhere -latest -property installationPath
        $CMakeExe = Join-Path $clawVS 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
    }
}
$clawConfigure = @('-S', $clawSource, '-B', $clawOutput, '-G', $Generator, '-A', 'x64',
    "-DCLAW_RUNTIME=$Runtime",
    "-DCLAW_COMMONLIB_DIR=$([IO.Path]::GetFullPath($CommonLibDir))",
    "-DCLAW_SKEE_HEADER=$([IO.Path]::GetFullPath($SkeeHeader))",
    "-DCLAW_BUILD_TESTS=$($BuildTests.IsPresent.ToString().ToUpperInvariant())")
if ($DependencyPrefix) { $clawConfigure += "-DCMAKE_PREFIX_PATH=$([IO.Path]::GetFullPath($DependencyPrefix))" }
if ($ToolchainFile) { $clawConfigure += "-DCMAKE_TOOLCHAIN_FILE=$([IO.Path]::GetFullPath($ToolchainFile))" }
if ($PhysicsModelHeader) { $clawConfigure += "-DCLAW_PHYSICS_MODEL_HEADER=$([IO.Path]::GetFullPath($PhysicsModelHeader))" }
if ($PhysicsFixtureHeader) { $clawConfigure += "-DCLAW_PHYSICS_FIXTURE_HEADER=$([IO.Path]::GetFullPath($PhysicsFixtureHeader))" }
if ($OBodyHeader) { $clawConfigure += "-DCLAW_OBODY_HEADER=$([IO.Path]::GetFullPath($OBodyHeader))" }
foreach ($clawName in $FetchSources.Keys) {
    if ($clawName -notin @('PUGIXML')) { throw "Only PUGIXML is fetched here; supply modern SDK dependencies through DependencyPrefix/ToolchainFile: $clawName" }
    $clawConfigure += "-DFETCHCONTENT_SOURCE_DIR_$($clawName.ToUpperInvariant())=$([IO.Path]::GetFullPath($FetchSources[$clawName]))"
}
& $CMakeExe @clawConfigure
if ($LASTEXITCODE) { throw 'CMake configuration failed.' }
$clawTargets = @('CLAWDistribution','claw-preset-tool')
if ($BuildTests) { $clawTargets += 'claw-preset-tests','claw-matrix-tests','claw-runtime-tests','claw-physics-observer-tests','claw-physics-fit-tests','claw-source-bootstrap-tests' }
& $CMakeExe --build $clawOutput --config Release --target @clawTargets --parallel $Parallel
if ($LASTEXITCODE) { throw 'Native compilation failed.' }
Write-Output "Compiled into $clawOutput. This command never runs tests or installs files."
