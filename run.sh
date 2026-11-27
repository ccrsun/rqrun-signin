#!/usr/bin/env bash
# RQrun 自动签到一键脚本
# 用法:
#   RQ_EMAIL=you@example.com RQ_PASSWORD=yourpass bash run.sh
# 依赖:
#   RQ_EMAIL / RQ_PASSWORD 通过环境变量传入（不要硬编码进本文件）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---- 校验账号环境变量 ----
if [ -z "${RQ_EMAIL:-}" ] || [ -z "${RQ_PASSWORD:-}" ]; then
  echo "错误: 请先设置环境变量 RQ_EMAIL 和 RQ_PASSWORD" >&2
  echo "示例: RQ_EMAIL=xxx@xxx.com RQ_PASSWORD=xxx bash run.sh" >&2
  exit 1
fi

# ---- 选择兼容 ddddocr/onnxruntime 的 Python (3.11/3.12 优先) ----
# 注意: 默认 python3 可能是 3.14，ddddocr 未必有对应 wheel。
PY=""
for cand in \
  /root/.pyenv/versions/3.12.15/bin/python3 \
  /root/.pyenv/versions/3.11.17/bin/python3; do
  if [ -x "$cand" ]; then
    PY="$cand"
    break
  fi
done

# 退回系统 python3（需为 3.11~3.13）
if [ -z "$PY" ]; then
  PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
  echo "错误: 未找到可用的 python3" >&2
  exit 1
fi
echo "使用 Python: $PY ($("$PY" --version 2>&1))"

# ---- 安装依赖（每次全新沙箱都需安装） ----
echo "安装依赖 ..."
"$PY" -m pip install -r requirements.txt --break-system-packages -q --disable-pip-version-check

# ---- 执行签到 ----
exec "$PY" rq_signin.py
