param(
    [Parameter(Mandatory=$true)][string]$BuildDir,
    [Parameter(Mandatory=$true)][string]$CommonLibDir,
    [Parameter(Mandatory=$true)][string]$SkeeHeader,
    [string]$CMakeExe,
    [string]$Generator = 'Visual Studio 18 2026',
    [int]$Parallel = 8,
    [switch]$BuildTests,
    [hashtable]$FetchSources = @{}
)
$ErrorActionPreference = 'Stop'
$clawSource = [IO.Path]::GetFullPath($PSScriptRoot)
$clawRepo = [IO.Directory]::GetParent($clawSource).FullName
$clawOutput = [IO.Path]::GetFullPath($BuildDir)
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
    "-DCLAW_COMMONLIB_DIR=$([IO.Path]::GetFullPath($CommonLibDir))",
    "-DCLAW_SKEE_HEADER=$([IO.Path]::GetFullPath($SkeeHeader))",
    "-DCLAW_BUILD_TESTS=$($BuildTests.IsPresent.ToString().ToUpperInvariant())")
foreach ($clawName in $FetchSources.Keys) {
    if ($clawName -notin @('PUGIXML','FMT','SPDLOG','RAPIDCSV')) { throw "Unknown external dependency: $clawName" }
    $clawConfigure += "-DFETCHCONTENT_SOURCE_DIR_$($clawName.ToUpperInvariant())=$([IO.Path]::GetFullPath($FetchSources[$clawName]))"
}
& $CMakeExe @clawConfigure
if ($LASTEXITCODE) { throw 'CMake configuration failed.' }
$clawTargets = @('CLAWDistribution','claw-preset-tool')
if ($BuildTests) { $clawTargets += 'claw-preset-tests' }
& $CMakeExe --build $clawOutput --config Release --target @clawTargets --parallel $Parallel
if ($LASTEXITCODE) { throw 'Native compilation failed.' }
Write-Output "Compiled into $clawOutput. This command never runs tests or installs files."
