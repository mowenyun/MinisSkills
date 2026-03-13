---
name: self-improving-agent
description: "自我改进记录与闭环：当命令/操作失败、用户纠错、发现知识过时、外部 API 失败、或出现可复用更优方案时触发。重要任务前可回顾历史 learnings。避免在普通闲聊、无需记录的临时失误或用户已明确不需要记录时触发。"
metadata:
  language: zh-CN
  scope: minis
---

# 自我改进技能（Minis 版）

本技能用于在 Minis 环境内**记录错误、纠正与可复用的最佳实践**，形成可追踪的学习闭环。

## Minis 目录约定

- **工作目录**：`/var/minis/workspace/`
- **学习日志目录**：`/var/minis/workspace/.learnings/`
- **学习日志文件**：
  - `LEARNINGS.md`（纠错、知识缺口、最佳实践）
  - `ERRORS.md`（命令失败、异常输出）
  - `FEATURE_REQUESTS.md`（用户提出的新能力）

> 仅当用户明确需要跨项目沉淀时，再考虑同步到 Minis 记忆系统。

## 快速参考（Quick Reference）

| 情景 | 动作 |
|-----------|--------|
| 命令/操作失败 | 记录到 `.learnings/ERRORS.md` |
| 用户纠正你 | 记录到 `.learnings/LEARNINGS.md`，类别 `correction` |
| 用户需要缺失能力 | 记录到 `.learnings/FEATURE_REQUESTS.md` |
| 外部 API/工具失败 | 记录到 `.learnings/ERRORS.md`，包含集成细节 |
| 知识过时 | 记录到 `.learnings/LEARNINGS.md`，类别 `knowledge_gap` |
| 发现更优方案 | 记录到 `.learnings/LEARNINGS.md`，类别 `best_practice` |
| 简化/强化复用模式 | 记录/更新 `.learnings/LEARNINGS.md`，带 `Source: simplify-and-harden` 与稳定 `Pattern-Key` |
| 与已有条目类似 | 用 `**See Also**` 链接，并考虑提升优先级 |
| 广泛适用的经验 | 提升到 Minis 记忆（见下方“提升到 Minis 记忆”） |

## 自动初始化 + 自动记录（Minis）

提供脚本：`scripts/minis_auto_log.sh`

用法示例：
```bash
# 初始化目录与文件
/var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh init

# 记录学习
/var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh learning "修复了下载超时" "使用分片与重试"

# 记录错误
/var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh error "curl 请求失败" "HTTP 429"

# 记录需求
/var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh feature "支持批量导出" "运营需要日报"
```


## 记录格式（Logging Format）

### Learning 记录

追加到 `.learnings/LEARNINGS.md`：

```markdown
## [LRN-YYYYMMDD-XXX] category

**记录时间**: ISO-8601 时间戳
**优先级**: low | medium | high | critical
**状态**: pending
**领域**: frontend | backend | infra | tests | docs | config

### 摘要
一行描述所学内容

### 详情
完整上下文：发生了什么、哪里错了、正确做法

### 建议动作
具体可执行的改进或修复

### 元数据
- 来源: conversation | error | user_feedback
- 关联文件: path/to/file.ext
- 标签: tag1, tag2
- 相关条目: LRN-20250110-001（如有关联）
- 模式键: simplify.dead_code | harden.input_validation（可选，复发模式追踪）
- 复发次数: 1（可选）
- 首次出现: 2025-01-15（可选）
- 最近出现: 2025-01-15（可选）

---
```

### Error 记录

追加到 `.learnings/ERRORS.md`：

```markdown
## [ERR-YYYYMMDD-XXX] skill_or_command_name

**记录时间**: ISO-8601 时间戳
**优先级**: high
**状态**: pending
**领域**: frontend | backend | infra | tests | docs | config

### 摘要
简要描述失败内容

### Error
```
实际错误信息或输出
```

### Context
- 尝试的命令/操作
- 输入或参数
- 环境细节（如相关）

### 建议修复
如可识别，给出可能的解决方案

### 元数据
- 可复现: yes | no | unknown
- 关联文件: path/to/file.ext
- 相关条目: ERR-20250110-001（如复发）

---
```

### Feature Request 记录

追加到 `.learnings/FEATURE_REQUESTS.md`：

```markdown
## [FEAT-YYYYMMDD-XXX] capability_name

**记录时间**: ISO-8601 时间戳
**优先级**: medium
**状态**: pending
**领域**: frontend | backend | infra | tests | docs | config

### 需求能力
用户想实现的能力

### 用户背景
为什么需要、在解决什么问题

### 复杂度评估
simple | medium | complex

### 建议实现
可能的实现方式与扩展点

### 元数据
- 频次: first_time | recurring
- 关联功能: existing_feature_name

---
```

## ID 生成规则

格式：`TYPE-YYYYMMDD-XXX`
- TYPE: `LRN` (learning), `ERR` (error), `FEAT` (feature)
- YYYYMMDD: 当前日期
- XXX: 顺序号或随机 3 位（如 `001`, `A7B`）

示例：`LRN-20250115-001`、`ERR-20250115-A3F`、`FEAT-20250115-002`

## 条目解决

当问题修复后，更新条目：

1. 将 `**状态**: pending` → `**状态**: resolved`
2. 在元数据后添加解决块：

```markdown
### 解决记录
- **解决时间**: 2025-01-16T09:00:00Z
- **提交/PR**: abc123 或 #42
- **说明**: 简要描述做了什么
```

其他状态：
- `in_progress` - 正在处理
- `wont_fix` - 决定不修（在解决记录中写原因）
- `promoted` - 已提升到 Minis 记忆

## 提升到 Minis 记忆

当某条学习具有广泛适用性（不是一次性修复），应提升到 Minis 记忆系统。

### 何时提升

- 学习跨多个文件/功能适用
- 任何贡献者（人/AI）都应知道
- 防止重复犯错
- 记录项目约定

### 提升目标（Minis）

- **日记忆**：`/var/minis/memory/YYYY-MM-DD.md`（通过 `memory_write` 写入）
- **全局记忆**：`/var/minis/memory/GLOBAL.md`（只读，需要用户在设置中维护）
- **项目笔记**：建议写入 `/var/minis/workspace/PROJECT_NOTES.md`

### 如何提升

1. **提炼**：把学习浓缩成简洁规则或事实
2. **写入**：使用 `memory_write` 写入日记忆，必要时同步到项目笔记
3. **回写**：更新原条目：
   - `**状态**: pending` → `**状态**: promoted`
   - 添加 `**已提升**: YYYY-MM-DD.md` 或 `PROJECT_NOTES.md`

## 复发模式检测

如果记录内容与已有条目相似：

1. **先搜索**：`grep -r "keyword" /var/minis/workspace/.learnings/`
2. **建立关联**：在元数据中添加 `**See Also**: ERR-20250110-001`
3. **提升优先级**：如果问题反复出现
4. **考虑系统性修复**：反复出现通常意味着：
   - 文档缺失（→ 写入 PROJECT_NOTES.md 或日记忆）
   - 自动化缺失（→ 加入脚本或工具链）
   - 架构问题（→ 建立技术债任务）

## Simplify & Harden Feed

用于 ingest `simplify-and-harden` 技能中的复发模式，并将其转化为持久化的提示规则。

### Ingestion Workflow

1. 从任务摘要读取 `simplify_and_harden.learning_loop.candidates`。
2. 对每个候选项使用 `pattern_key` 作为稳定去重键。
3. 在 `.learnings/LEARNINGS.md` 搜索是否已存在：
   - `grep -n "Pattern-Key: <pattern_key>" /var/minis/workspace/.learnings/LEARNINGS.md`
4. 若已存在：
   - 递增 `Recurrence-Count`
   - 更新 `Last-Seen`
   - 添加 `See Also` 关联
5. 若不存在：
   - 新建 `LRN-...` 条目
   - 设置 `Source: simplify-and-harden`
   - 设置 `Pattern-Key`、`Recurrence-Count: 1` 与 `First-Seen`/`Last-Seen`

### 提升规则（系统提示反馈）

当满足以下条件时，把复发模式提升到 Minis 记忆：

- `Recurrence-Count >= 3`
- 至少出现在 2 个不同任务
- 在 30 天内发生

提升后的规则应是**短而明确的预防规则**（做事前/做事时的动作），而不是冗长的事故复盘。

## 周期性回顾

在自然节点回顾 `.learnings/`：

### 何时回顾
- 开始新的重要任务前
- 完成一个功能后
- 进入曾有 learnings 的领域时
- 活跃开发期间每周一次

### 快速状态检查
```bash
# Count pending items
grep -h "状态\*\*: pending" /var/minis/workspace/.learnings/*.md | wc -l

# List pending high-priority items
grep -B5 "优先级\*\*: high" /var/minis/workspace/.learnings/*.md | grep "^## \["

# Find learnings for a specific area
grep -l "领域\*\*: backend" /var/minis/workspace/.learnings/*.md
```
