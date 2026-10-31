#!/usr/bin/env pwsh
# 一键装依赖：依次尝试若干来源，**用真实同步来判断可用性**，哪个成功就用哪个。
#
# 这是 scripts/setup.sh 的 PowerShell 版（Windows 上不必装 Git Bash）。
# 两者行为一致：同样的候选来源、同样的短超时换源、同样带 --frozen。
#
# 为什么要有这个脚本：内外网状态会随时间变化（现实因素）。同一个索引，
# 在不同网络环境下可能直连可用、也可能需要代理或换镜像。把某一次探测结果
# 写成固定命令，过几天就会失效。所以这里不预设结论，改成运行期逐个尝试。
#
# 用法（与 setup.sh 一致；PowerShell 惯用的 -Dev 也支持）：
#   pwsh scripts/setup.ps1                       # 装运行时依赖
#   pwsh scripts/setup.ps1 --dev                 # 连开发工具（pytest/ruff/mypy）一起装
#   pwsh scripts/setup.ps1 --dev --index <URL>   # 手动指定来源，跳过自动尝试
#   pwsh scripts/setup.ps1 --dev --proxy <URL>
#
# Windows PowerShell 5.1 用同样参数：
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup.ps1 --dev
#
# 说明：不用 "先探测再同步" 那种两段式——探测（如 uv pip install --dry-run）本身
# 就依赖环境，容易假失败（实测踩到）。这里直接同步，靠短超时快速失败、换下一个来源。
#
# 同步一律带 `--frozen`：**不改写 uv.lock**。否则一旦用镜像同步，uv 会把锁文件里
# 500+ 处 URL 全部换成镜像地址（实测踩到）。`--frozen` 仍然会按 --index 去镜像
# 下载，只是不动锁文件。
#
# 为什么手工解析参数而不用 param()：实测 pwsh 里 `--dev` **不会**绑到 `[switch]$Dev`
# 上，而是被当成位置参数的值喂给下一个 string 形参（`--index` 会收到 `--dev`），
# 于是静默走错分支。为了与 bash 版的 `--dev` 写法一致，这里自己解析 $args。
#
# 兼容 Windows PowerShell 5.1 与 PowerShell 7（见 scripts/README.md）。
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$Dev = $false
$Index = ''
$Proxy = ''
$argv = @($args)
for ($i = 0; $i -lt $argv.Count; $i++) {
    switch -Regex ($argv[$i]) {
        '^(--dev|-Dev|--Dev)$' { $Dev = $true; continue }
        '^(--index|-Index|--Index)$' {
            if ($i + 1 -ge $argv.Count) {
                [Console]::Error.WriteLine('--index 后面缺少地址'); exit 2
            }
            $Index = $argv[++$i]; continue
        }
        '^(--proxy|-Proxy|--Proxy)$' {
            if ($i + 1 -ge $argv.Count) {
                [Console]::Error.WriteLine('--proxy 后面缺少地址'); exit 2
            }
            $Proxy = $argv[++$i]; continue
        }
        default {
            # 用 [Console] 直接写 stderr：Write-Error 会附带一大段 PowerShell
            # 调用栈噪音，对使用者没用
            [Console]::Error.WriteLine("未知参数：$($argv[$i])")
            [Console]::Error.WriteLine('用法：pwsh scripts/setup.ps1 [--dev] [--index <URL>] [--proxy <URL>]')
            exit 2
        }
    }
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$extra = @()
if ($Dev) { $extra = @('--extra', 'dev') }

# --- 找 uv ---------------------------------------------------------------
$uv = $env:UV
if (-not $uv) {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { $uv = $cmd.Source }
}
if (-not $uv) {
    # 常见安装位置兜底（安装脚本默认装在 ~/.local/bin）
    foreach ($candidate in @(
            (Join-Path $env:USERPROFILE '.local/bin/uv.exe'),
            (Join-Path $env:LOCALAPPDATA 'Microsoft/WinGet/Links/uv.exe')
        )) {
        if (Test-Path $candidate) { $uv = $candidate; break }
    }
}
if (-not $uv) {
    Write-Host '找不到 uv。请先安装：' -ForegroundColor Red
    Write-Host '  Windows:     powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Write-Host '  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh'
    Write-Host '（不想用 uv 也可以： python -m venv .venv; .venv\Scripts\pip install -e ".[dev]" -i <可用镜像>）'
    exit 1
}

$logFile = Join-Path ([System.IO.Path]::GetTempPath()) 'docgen-setup.log'

# 执行一次同步；返回退出码。输出重定向到日志文件，失败时供诊断。
function Invoke-Sync {
    param([string]$Index, [string]$ProxyAddr, [int]$Timeout, [Switch]$Quiet)
    $outFile = if ($Quiet) { $logFile } else { $null }
    # Start-Process 才能可靠拿到退出码并重定向输出（管道会吞掉退出码）
    $argList = @('sync', '--frozen') + $extra
    $env:UV_HTTP_TIMEOUT = "$Timeout"
    $env:UV_CONCURRENT_DOWNLOADS = '8'
    $env:UV_DEFAULT_INDEX = $Index
    if ($ProxyAddr) {
        $env:HTTP_PROXY = $ProxyAddr
        $env:HTTPS_PROXY = $ProxyAddr
    }
    try {
        if ($Quiet) {
            $p = Start-Process -FilePath $uv -ArgumentList $argList -NoNewWindow -Wait -PassThru `
                -RedirectStandardOutput $outFile -RedirectStandardError "$outFile.err"
        } else {
            $p = Start-Process -FilePath $uv -ArgumentList $argList -NoNewWindow -Wait -PassThru
        }
        return $p.ExitCode
    }
    finally {
        Remove-Item Env:UV_HTTP_TIMEOUT, Env:UV_CONCURRENT_DOWNLOADS, Env:UV_DEFAULT_INDEX `
            -ErrorAction SilentlyContinue
        if ($ProxyAddr) {
            Remove-Item Env:HTTP_PROXY, Env:HTTPS_PROXY -ErrorAction SilentlyContinue
        }
    }
}

$defaultIndex = 'https://pypi.org/simple'

# --- 手动指定来源时只试一次 ----------------------------------------------
if ($Index -or $Proxy) {
    $useIndex = if ($Index) { $Index } else { $defaultIndex }
    Write-Host "按指定来源同步（index=$useIndex proxy=$(if ($Proxy) { $Proxy } else { '无' })）"
    $rc = Invoke-Sync -Index $useIndex -ProxyAddr $Proxy -Timeout 60
    if ($rc -eq 0) { Write-Host '✅ 完成'; exit 0 }
    Write-Host '❌ 指定来源失败' -ForegroundColor Red
    exit $rc
}

# --- 自动尝试：从"最快/最省事"到"最兜底" ---------------------------------
# 代理地址与镜像都只是"候选"，不假定它们存在或不存在。
$candidates = @(
    @{ Label = '镜像（直连）'; Index = 'https://pypi.tuna.tsinghua.edu.cn/simple'; Proxy = '' },
    @{ Label = '直连 PyPI'; Index = $defaultIndex; Proxy = '' },
    @{ Label = '代理 127.0.0.1:7897 + PyPI'; Index = $defaultIndex; Proxy = 'http://127.0.0.1:7897' },
    @{ Label = '代理 127.0.0.1:7897 + 镜像'; Index = 'https://pypi.tuna.tsinghua.edu.cn/simple'; Proxy = 'http://127.0.0.1:7897' }
)

foreach ($c in $candidates) {
    Write-Host ("→ {0} ... " -f $c.Label) -NoNewline
    # 用 UV_HTTP_TIMEOUT 压低单次失败耗时，避免卡住
    $rc = Invoke-Sync -Index $c.Index -ProxyAddr $c.Proxy -Timeout 20 -Quiet
    if ($rc -eq 0) {
        Write-Host '成功'
        Write-Host ''
        Write-Host "✅ 依赖已装好（来源：$($c.Label)）"
        Write-Host '   验证： uv run docgen --help'
        exit 0
    }
    Write-Host '不可用'
}

Write-Host ''
Write-Host '❌ 所有候选来源都失败了。诊断线索：' -ForegroundColor Red
Write-Host "   - 完整日志：$logFile（与 $logFile.err）"
Write-Host '   - 若处于内网：确认代理地址（默认候选是 127.0.0.1:7897，可能不是你的）'
Write-Host '   - 手动指定任意可用源：'
Write-Host "       pwsh scripts/setup.ps1 $(if ($Dev) { '--dev ' })--index <你的索引> [--proxy <你的代理>]"
exit 1
