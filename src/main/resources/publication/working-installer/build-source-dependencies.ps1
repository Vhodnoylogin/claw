param(
    [Parameter(Mandatory=$true)][string]$WorkDir,
    [string]$SourceRoot = [IO.Directory]::GetParent([IO.Directory]::GetParent([IO.Directory]::GetParent($PSScriptRoot).FullName).FullName).FullName,
    [string]$CMakeExe,
    [int]$Parallel = 8
)
$ErrorActionPreference = 'Stop'
$clawSourceRoot = [IO.Path]::GetFullPath($SourceRoot)
$clawWorkRoot = [IO.Path]::GetFullPath($WorkDir)
if (Test-Path -LiteralPath $clawWorkRoot) { throw 'Use a fresh external WorkDir.' }
if ($clawWorkRoot.StartsWith($clawSourceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'WorkDir must be outside the source snapshot.'
}
if (($clawWorkRoot -split '[\\/]') | Where-Object { $_ -in @('Data','mods','overwrite','downloads') }) {
    throw 'Live game, manager and download destinations are refused.'
}
$clawAncestor = $clawWorkRoot
while ($clawAncestor) {
    if (Test-Path -LiteralPath (Join-Path $clawAncestor '.git')) { throw 'WorkDir cannot be in Git.' }
    $clawParent = [IO.Directory]::GetParent($clawAncestor)
    if (!$clawParent) { break }; $clawAncestor = $clawParent.FullName
}
if (!(Test-Path -LiteralPath (Join-Path $clawSourceRoot 'upstream/CommonLibSSE-NG-0c95630.zip'))) {
    throw 'SourceRoot must be the extracted corresponding-source archive.'
}
if (!$CMakeExe) {
    $clawCommand = Get-Command cmake -ErrorAction SilentlyContinue
    if ($clawCommand) { $CMakeExe = $clawCommand.Source }
    else {
        $clawVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
        $clawVS = & $clawVsWhere -latest -property installationPath
        $CMakeExe = Join-Path $clawVS 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
    }
}
$clawPrefix = Join-Path $clawWorkRoot 'prefix'
$null = New-Item -ItemType Directory -Path $clawWorkRoot
$clawProjects = @(
    @{Name='directxmath'; Options=@('-DBUILD_XDSP=OFF','-DBUILD_SHMATH=OFF')},
    @{Name='directxtk'; Options=@('-DBUILD_TOOLS=OFF')},
    @{Name='fmt'; Options=@('-DFMT_DOC=OFF','-DFMT_TEST=OFF','-DFMT_FUZZ=OFF','-DFMT_INSTALL=ON')},
    @{Name='nlohmann-json'; Options=@('-DJSON_BuildTests=OFF','-DJSON_CI=OFF','-DJSON_Install=ON')},
    @{Name='rapidcsv'; Options=@('-DRAPIDCSV_BUILD_TESTS=OFF')},
    @{Name='simpleini'; Options=@()},
    @{Name='spdlog'; Options=@('-DSPDLOG_FMT_EXTERNAL=ON','-DSPDLOG_BUILD_ALL=OFF','-DSPDLOG_BUILD_EXAMPLE=OFF','-DSPDLOG_BUILD_EXAMPLE_HO=OFF','-DSPDLOG_BUILD_TESTS=OFF','-DSPDLOG_BUILD_TESTS_HO=OFF','-DSPDLOG_BUILD_BENCH=OFF','-DSPDLOG_INSTALL=ON','-DSPDLOG_NO_TZ_OFFSET=ON')},
    @{Name='toml11'; Options=@('-DTOML11_BUILD_TESTS=OFF','-DTOML11_BUILD_TOML_TESTS=OFF','-DTOML11_BUILD_EXAMPLES=OFF','-DTOML11_INSTALL=ON')},
    @{Name='xbyak'; Options=@()},
    @{Name='pugixml-1.15'; Options=@('-DPUGIXML_BUILD_TESTS=OFF','-DPUGIXML_INSTALL=ON')}
)
$clawReceipts = @()
foreach ($clawProject in $clawProjects) {
    $clawName = $clawProject.Name
    $clawSource = Join-Path $clawSourceRoot ('upstream/' + $clawName)
    $clawBuild = Join-Path $clawWorkRoot ('build-' + $clawName)
    $clawConfigure = @('-S',$clawSource,'-B',$clawBuild,'-G','Visual Studio 18 2026','-A','x64',
        '-DBUILD_SHARED_LIBS=OFF','-DBUILD_TESTING=OFF','-DCMAKE_POLICY_VERSION_MINIMUM=3.10',
        '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL',"-DCMAKE_PREFIX_PATH=$clawPrefix", "-DCMAKE_INSTALL_PREFIX=$clawPrefix") + $clawProject.Options
    & $CMakeExe @clawConfigure 2>&1 | Tee-Object -FilePath (Join-Path $clawWorkRoot ($clawName+'-configure.log'))
    if ($LASTEXITCODE) { throw "Dependency configuration failed: $clawName" }
    & $CMakeExe --build $clawBuild --config Release --target install --parallel $Parallel 2>&1 |
        Tee-Object -FilePath (Join-Path $clawWorkRoot ($clawName+'-build-install.log'))
    if ($LASTEXITCODE) { throw "Dependency build/install failed: $clawName" }
    $clawReceipts += @{name=$clawName; configured=$true; builtAndInstalled=$true; configureArguments=$clawConfigure}
}
@{sourceRoot=$clawSourceRoot; prefix=$clawPrefix; libraries=$clawReceipts; gameStarted=$false; installedIntoGame=$false} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $clawWorkRoot 'dependency-closure.json') -Encoding utf8
Write-Output "Dependency prefix: $clawPrefix"
