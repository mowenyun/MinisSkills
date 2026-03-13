#!/bin/sh
# self-improving-agent Minis 自动初始化 + 自动记录
set -e

BASE="/var/minis/workspace/.learnings"
LEARN="$BASE/LEARNINGS.md"
ERRS="$BASE/ERRORS.md"
FEAT="$BASE/FEATURE_REQUESTS.md"

init() {
  mkdir -p "$BASE"
  [ -f "$LEARN" ] || cat > "$LEARN" <<'EOF'
# Learnings
EOF
  [ -f "$ERRS" ] || cat > "$ERRS" <<'EOF'
# Errors
EOF
  [ -f "$FEAT" ] || cat > "$FEAT" <<'EOF'
# Feature Requests
EOF
}

log_learning() {
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  DATE=$(date -u +%Y%m%d)
  RAND=$(tr -dc A-Z0-9 </dev/urandom | head -c 3)
  ID="LRN-${DATE}-${RAND}"
  SUMMARY="$1"
  DETAILS="$2"
  cat >> "$LEARN" <<EOF
## [$ID] category

**记录时间**: $TS
**优先级**: medium
**状态**: pending
**领域**: docs

### 摘要
$SUMMARY

### 详情
${DETAILS:-（可选）}

### 建议动作
（待补充）

### 元数据
- 来源: conversation
- 关联文件: (可选)
- 标签: (可选)

---
EOF
  echo "已记录：$ID → $LEARN"
}

log_error() {
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  DATE=$(date -u +%Y%m%d)
  RAND=$(tr -dc A-Z0-9 </dev/urandom | head -c 3)
  ID="ERR-${DATE}-${RAND}"
  SUMMARY="$1"
  DETAILS="$2"
  cat >> "$ERRS" <<EOF
## [$ID] command

**记录时间**: $TS
**优先级**: high
**状态**: pending
**领域**: infra

### 摘要
$SUMMARY

### Error
```
${DETAILS:-（粘贴错误信息）}
```

### Context
- 尝试的命令/操作：
- 输入或参数：
- 环境细节：

### 建议修复
（待补充）

### 元数据
- 可复现: unknown
- 关联文件: (可选)

---
EOF
  echo "已记录：$ID → $ERRS"
}

log_feature() {
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  DATE=$(date -u +%Y%m%d)
  RAND=$(tr -dc A-Z0-9 </dev/urandom | head -c 3)
  ID="FEAT-${DATE}-${RAND}"
  SUMMARY="$1"
  DETAILS="$2"
  cat >> "$FEAT" <<EOF
## [$ID] capability

**记录时间**: $TS
**优先级**: medium
**状态**: pending
**领域**: docs

### 需求能力
$SUMMARY

### 用户背景
${DETAILS:-（可选）}

### 复杂度评估
medium

### 建议实现
（待补充）

### 元数据
- 频次: first_time
- 关联功能: (可选)

---
EOF
  echo "已记录：$ID → $FEAT"
}

usage() {
  echo "用法：$0 init | learning <摘要> [详情] | error <摘要> [错误] | feature <摘要> [背景]" >&2
  exit 1
}

case "$1" in
  init)
    init
    echo "已初始化：$BASE"
    ;;
  learning)
    init
    [ -n "$2" ] || usage
    log_learning "$2" "$3"
    ;;
  error)
    init
    [ -n "$2" ] || usage
    log_error "$2" "$3"
    ;;
  feature)
    init
    [ -n "$2" ] || usage
    log_feature "$2" "$3"
    ;;
  *)
    usage
    ;;
esac
