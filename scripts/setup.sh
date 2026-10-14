#!/usr/bin/env bash
# 一键装依赖：依次尝试若干来源，**用真实同步来判断可用性**，哪个成功就用哪个。
#
# 为什么要有这个脚本：内外网状态会随时间变化（现实因素）。同一个索引，
# 在不同网络环境下可能直连可用、也可能需要代理或换镜像。把某一次探测结果
# 写成固定命令，过几天就会失效。所以这里不预设结论，改成运行期逐个尝试。
#
# 用法：
#   bash scripts/setup.sh              # 装运行时依赖
#   bash scripts/setup.sh --dev        # 连开发工具（pytest/ruff/mypy）一起装
#   bash scripts/setup.sh --dev --index <URL> [--proxy <URL>]   # 手动指定，跳过自动尝试
#
# 说明：不用 "先探测再同步" 那种两段式——探测（如 uv pip install --dry-run）本身
# 就依赖环境，容易假失败（实测踩到）。这里直接同步，靠短超时快速失败、换下一个来源。
#
# 同步一律带 `--frozen`：**不改写 uv.lock**。否则一旦用镜像同步，uv 会把锁文件里
# 500+ 处 URL 全部换成镜像地址（实测踩到），谁再提交一次就把镜像带到仓库里了。
# `--frozen` 仍然会按 --index 去镜像下载，只是不动锁文件。
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

extra=""
index=""
proxy=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dev) extra="--extra dev"; shift ;;
    --index) index="${2:-}"; shift 2 ;;
    --proxy) proxy="${2:-}"; shift 2 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

UV="${UV:-uv}"
if ! command -v "$UV" >/dev/null 2>&1; then
  echo "找不到 uv。请先安装：" >&2
  echo "  Windows:     powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"" >&2
  echo "  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "（不想用 uv 也可以： python -m venv .venv && pip install -e \".[dev]\" -i <可用镜像>）" >&2
  exit 1
fi

# 手动指定时只试一次
if [ -n "$index" ] || [ -n "$proxy" ]; then
  echo "按指定来源同步（index=${index:-默认} proxy=${proxy:-无}）"
  if [ -n "$proxy" ]; then
    UV_HTTP_TIMEOUT=60 UV_DEFAULT_INDEX="${index:-https://pypi.org/simple}" \
      http_proxy="$proxy" https_proxy="$proxy" "$UV" sync --frozen $extra
  else
    UV_HTTP_TIMEOUT=60 UV_DEFAULT_INDEX="${index:-https://pypi.org/simple}" \
      "$UV" sync --frozen $extra
  fi
  rc=$?
  [ $rc -eq 0 ] && echo "✅ 完成" && exit 0
  echo "❌ 指定来源失败" >&2; exit $rc
fi

# 自动尝试的候选顺序：从"最快/最省事"到"最兜底"。
# 用 UV_HTTP_TIMEOUT 压低单次失败耗时，避免卡住。
try() {
  local label="$1" idx="$2" px="$3"
  printf '→ %s ... ' "$label"
  local rc=0
  if [ -n "$px" ]; then
    UV_HTTP_TIMEOUT=20 UV_CONCURRENT_DOWNLOADS=8 UV_DEFAULT_INDEX="$idx" \
      http_proxy="$px" https_proxy="$px" "$UV" sync --frozen $extra >/tmp/docgen-setup.log 2>&1 || rc=$?
  else
    UV_HTTP_TIMEOUT=20 UV_CONCURRENT_DOWNLOADS=8 UV_DEFAULT_INDEX="$idx" \
      "$UV" sync --frozen $extra >/tmp/docgen-setup.log 2>&1 || rc=$?
  fi
  if [ $rc -eq 0 ]; then
    echo "成功"
    echo
    echo "✅ 依赖已装好（来源：$label）"
    echo "   验证： $UV run docgen --help"
    return 0
  fi
  echo "不可用"
  return 1
}

# 候选清单：代理地址与镜像都只是"候选"，不假定它们存在或不存在
for candidate in \
  "镜像（直连）|https://pypi.tuna.tsinghua.edu.cn/simple|" \
  "直连 PyPI|https://pypi.org/simple|" \
  "代理 127.0.0.1:7897 + PyPI|https://pypi.org/simple|http://127.0.0.1:7897" \
  "代理 127.0.0.1:7897 + 镜像|https://pypi.tuna.tsinghua.edu.cn/simple|http://127.0.0.1:7897"
do
  IFS='|' read -r label idx px <<< "$candidate"
  try "$label" "$idx" "$px" && exit 0
done

echo
echo "❌ 所有候选来源都失败了。诊断线索：" >&2
echo "   - 完整日志：/tmp/docgen-setup.log" >&2
echo "   - 若处于内网：确认代理地址（默认候选是 127.0.0.1:7897，可能不是你的）" >&2
echo "   - 手动指定任意可用源：" >&2
echo "       bash scripts/setup.sh $extra --index <你的索引> [--proxy <你的代理>]" >&2
exit 1
