#!/usr/bin/env pwsh
# 打包「源码测试版」：生成可分发的 tar.gz / zip，供熟人小范围试用。
#
# 这是 scripts/package.sh 的 PowerShell 版（Windows 上不必装 Git Bash）。
# 两者行为一致：同样的内容清单、同样的打包自检、同样的产物名。
#
# 定位：**不要求安装方式**——对方解压后 `setup` 就能用，
# 不需要 wheel 上架、不需要 PyPI。所以这里只打源码，不打 dist/。
#
# 用法：
#   pwsh scripts/package.ps1                  # 版本号取自 pyproject.toml
#   pwsh scripts/package.ps1 -OutDir C:\out   # 指定输出目录
#
# 产物：<out>/docgen-<version>-src.tar.gz 与 .zip
#
# 兼容 Windows PowerShell 5.1 与 PowerShell 7（见 scripts/README.md）。
#Requires -Version 5.1
[CmdletBinding()]
param(
    # 输出目录（默认 <仓库根>/release）
    [string]$OutDir
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root


function Get-BsdTar {
    # 找**能处理 Windows 路径**的 tar（bsdtar）。
    #
    # 为什么要挑：PATH 里可能先命中 GNU tar（Git Bash / MSYS2 / Cygwin 的
    # /usr/bin/tar），它会把 C:\... 当成远程主机名，报
    # "Cannot connect to C: resolve failed"，于是 tar.gz 静默失败。
    # Windows 10+ 自带的 %SystemRoot%\System32\tar.exe 是 bsdtar，优先用它；
    # 其余候选要用 --version 验证确实是 bsdtar（含 libarchive）才可用。
    $candidates = @()
    if ($env:SystemRoot) {
        $candidates += (Join-Path $env:SystemRoot 'System32\tar.exe')
    }
    $found = Get-Command tar -ErrorAction SilentlyContinue
    if ($found -and $found.Source) { $candidates += $found.Source }

    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $version = (& $candidate --version 2>&1 | Select-Object -First 1)
        if ($version -match 'bsdtar|libarchive') { return $candidate }
    }
    return $null
}

# Windows PowerShell 5.1 不会自动加载压缩程序集（pwsh 7 会），显式来一次
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
} catch {
    Write-Warning "未能加载压缩程序集，打包可能失败：$_"
}

# --- 版本号取自 pyproject.toml（唯一真源）---------------------------------
$versionLine = Select-String -Path 'pyproject.toml' -Pattern '^version = "(.*)"' |
    Select-Object -First 1
if (-not $versionLine) {
    Write-Error '无法从 pyproject.toml 读出版本号'
    exit 1
}
$version = $versionLine.Matches[0].Groups[1].Value
$name = "docgen-$version-src"

if (-not $OutDir) { $OutDir = Join-Path $root 'release' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# --- 只打这些内容：源码 + 文档 + 示例 + 测试 + 工程配置 -------------------
# 明确排除 .venv / 缓存 / 构建产物 / git 内部。
$items = @(
    'src', 'tests', 'docs', 'examples', 'scripts',
    'README.md', 'CHANGELOG.md', 'QUICKSTART.md', 'LIMITATIONS.md', 'FEEDBACK.md',
    'HANDOFF.md',
    'pyproject.toml', 'uv.lock', '.gitignore'
)

$staging = Join-Path ([System.IO.Path]::GetTempPath()) ("docgen-pkg-" + [guid]::NewGuid().ToString('N'))
$dest = Join-Path $staging $name
New-Item -ItemType Directory -Force -Path $dest | Out-Null

try {
    foreach ($item in $items) {
        if (-not (Test-Path $item)) { continue }
        $target = Join-Path $dest (Split-Path -Leaf $item)
        if ((Get-Item $item).PSIsContainer) {
            Copy-Item -Recurse -Force $item $target
        } else {
            Copy-Item -Force $item $target
        }
    }
    $wf = Join-Path $dest '.github/workflows'
    if (Test-Path '.github/workflows') {
        New-Item -ItemType Directory -Force -Path $wf | Out-Null
        Copy-Item -Recurse -Force '.github/workflows/*' $wf
    }

    # --- 清掉可能混进来的垃圾 -------------------------------------------
    Get-ChildItem -Path $dest -Recurse -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @('__pycache__') -or $_.Name -like '*.egg-info' } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $dest -Recurse -File -Include '*.pyc', '.coverage' -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path (Join-Path $dest 'examples') -Recurse -File -Include 'output.html', 'output.docx' `
        -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

    # --- 自检：包里不该出现这些 -----------------------------------------
    $leaked = Get-ChildItem -Path $dest -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -in @('__pycache__', '.coverage', 'output.html', 'output.docx') -or
            $_.Name -like '*.egg-info' -or
            $_.Extension -eq '.pyc'
        }
    if ($leaked) {
        Write-Error ("打包自检失败，以下内容不该进包：`n" + (($leaked | ForEach-Object { $_.FullName }) -join "`n"))
        exit 1
    }

    # --- 出包（不依赖外部 zip；tar.gz 优先用 tar 命令，退回 .NET API）----
    $tarPath = Join-Path $OutDir "$name.tar.gz"
    $zipPath = Join-Path $OutDir "$name.zip"
    Remove-Item $tarPath, $zipPath -ErrorAction SilentlyContinue

    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $dest, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $true)

    # 压缩包内的顶层目录名要与 zip 一致
    $tarRoot = Join-Path $staging 'tarroot'
    New-Item -ItemType Directory -Force -Path $tarRoot | Out-Null
    Copy-Item -Recurse -Force $dest (Join-Path $tarRoot $name)

    $tarMade = $false
    $tarExe = Get-BsdTar
    if ($tarExe) {
        & $tarExe -czf $tarPath -C $tarRoot $name
        $tarMade = ($LASTEXITCODE -eq 0)
    }
    if (-not $tarMade) {
        try {
            # .NET 的 tar 在 System.Formats.Tar（只有 PowerShell 7 / .NET 7+ 才有）
            Add-Type -AssemblyName System.Formats.Tar -ErrorAction Stop
            [System.Formats.Tar.TarFile]::CreateFromDirectory(
                $tarRoot, $tarPath, $true, $false)
            $tarMade = $true
        } catch {
            Write-Warning ("没找到可用的 bsdtar，也没有 .NET TarFile（Windows PowerShell 5.1 没有），" +
                "只生成了 zip。要 tar.gz 请确认 $env:SystemRoot\System32\tar.exe 存在，" +
                "或用 pwsh 7 / Git Bash 运行。")
        }
    }

    Write-Host '已生成：'
    if ($tarMade) { Write-Host "  $tarPath" }
    Write-Host "  $zipPath"
    Write-Host ''
    Write-Host '试用者解压后执行（任选其一）：'
    Write-Host '  pwsh scripts/setup.ps1 --dev                  # PowerShell 7'
    Write-Host '  powershell -File scripts\setup.ps1 --dev      # Windows PowerShell 5.1'
    Write-Host '  scripts\setup.cmd --dev                       # cmd'
    Write-Host '  bash scripts/setup.sh --dev                   # Git Bash / macOS / Linux'
}
finally {
    Remove-Item -Recurse -Force $staging -ErrorAction SilentlyContinue
}
