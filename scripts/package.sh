#!/usr/bin/env bash
# 打包「源码测试版」：生成可分发的 tar.gz / zip，供熟人小范围试用。
#
# 定位：**不要求安装方式**——对方解压后 `uv sync --extra dev` 就能用，
# 不需要 wheel 上架、不需要 PyPI。所以这里只打源码，不打 dist/。
#
# 用法：
#   bash scripts/package.sh            # 版本号取自 pyproject.toml
#   bash scripts/package.sh /tmp/out   # 指定输出目录
#
# 产物：<out>/docgen-<version>-src.tar.gz 与 .zip
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

version="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
if [ -z "$version" ]; then
  echo "无法从 pyproject.toml 读出版本号" >&2
  exit 1
fi

out="${1:-$root/release}"
mkdir -p "$out"
name="docgen-${version}-src"

# 只打这些内容：源码 + 文档 + 示例 + 测试 + 工程配置。
# 明确排除 .venv / 缓存 / 构建产物 / git 内部。
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
mkdir -p "$staging/$name"

for item in src tests docs examples scripts \
            README.md CHANGELOG.md QUICKSTART.md LIMITATIONS.md FEEDBACK.md \
            HANDOFF.md GIT.md \
            pyproject.toml uv.lock .gitignore; do
  [ -e "$item" ] && cp -r "$item" "$staging/$name/"
done
mkdir -p "$staging/$name/.github"
cp -r .github/workflows "$staging/$name/.github/" 2>/dev/null || true

# 清掉可能混进来的垃圾：缓存、示例的构建产物（跑示例就会重新生成，不该随包发）
find "$staging/$name" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$staging/$name" \( -name '*.pyc' -o -name '.coverage' \) -delete 2>/dev/null || true
rm -f "$staging/$name"/examples/*/output.html "$staging/$name"/examples/*/output.docx

# 自检：包里不该出现这些
leaked="$(cd "$staging/$name" && find . \( -name '__pycache__' -o -name '*.pyc' -o -name 'output.html' \
  -o -name 'output.docx' -o -name '.coverage' \) -print)"
if [ -n "$leaked" ]; then
  echo "打包自检失败，以下内容不该进包：" >&2
  echo "$leaked" >&2
  exit 1
fi

( cd "$staging" && tar -czf "$out/$name.tar.gz" "$name" )
( cd "$staging" && zip -qr "$out/$name.zip" "$name" )

echo "已生成："
echo "  $out/$name.tar.gz"
echo "  $out/$name.zip"
echo
echo "试用者解压后执行："
echo "  uv sync --extra dev && uv run docgen --help"
