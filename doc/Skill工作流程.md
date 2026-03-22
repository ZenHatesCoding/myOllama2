# Skill 工作流程详解

## 整体架构

Skill 系统基于 LangGraph 工作流，通过**意图分类**决定如何处理用户请求。

```
用户输入
    │
    ▼
┌─────────────────────────────────────┐
│        classify_intent               │
│    (分类用户意图：工具/Skill/聊天)    │
└─────────────────────────────────────┘
    │ 无 MCP 工具
    ▼
┌─────────────────────────────────────┐
│          match_skill                 │
│    (匹配 Skill / 询问列表)            │
└─────────────────────────────────────┘
    │
    ├─── 需要执行 Skill ────────────────→ activate_skill → generate_response
    │
    ├─── 询问 Skill 列表 ───────────────→ generate_response (直接返回列表)
    │
    └─── 普通聊天 ──────────────────────→ retrieve_docs → generate_response
```

---

## 三种处理场景

### 场景 A：询问 Skill 列表

**触发条件**：用户问"你有什么 skill"、"列出所有技能"等

```
用户输入："你有什么 skill"
    │
    ▼
match_skill:
  - LLM 判断：intent = {list_skills: true}
  - 或关键词 fallback：["什么skill", "什么技能", "列出", "list"]
    │
    ▼
返回 {target_skill: None, skill_context: "【可用Skill列表】..."}
    │
    ▼
should_use_skill:
  - skill_context 存在 → 返回 "generate_response"
    │
    ▼
generate_response:
  - skill_context 构建 system_prompt
  - 模型返回 Skill 列表给用户
```

---

### 场景 B：执行 Skill

**触发条件**：用户请求与某 Skill 描述相符（如"帮我审查代码"）

```
用户输入："帮我审查代码"
    │
    ▼
match_skill:
  - LLM 判断：intent = {need_skill: true, skill_name: "code-review"}
    │
    ▼
返回 {target_skill: "code-review", skill_context: None}
    │
    ▼
should_use_skill:
  - target_skill 存在 → 返回 "activate_skill"
    │
    ▼
activate_skill:
  - 从 skill_registry 获取 code-review 的完整内容
    │
    ▼
返回 {skill_context: "【激活Skill】..."}
    │
    ▼
should_use_skill:
  - skill_context 存在 → 返回 "generate_response"
    │
    ▼
generate_response:
  - skill_context 构建 system_prompt
  - 模型执行 Skill 定义的任务
```

---

### 场景 C：普通聊天

**触发条件**：用户正常聊天，无 Skill 相关意图

```
用户输入："今天天气怎么样"
    │
    ▼
match_skill:
  - LLM 判断：intent = {need_skill: false}
  - 关键词检测：不匹配
    │
    ▼
返回 {target_skill: None, skill_context: None}
    │
    ▼
should_use_skill:
  - target_skill = None ❌
  - skill_context = None ❌
  - 返回 "retrieve_docs"
    │
    ▼
retrieve_docs → retrieve_history → generate_response
  - 正常对话流程，无 Skill 干扰
```

---

## 节点说明

| 节点 | 函数 | 职责 |
|------|------|------|
| `classify_intent` | `node_classify_intent` | 检测是否需要 MCP 工具 |
| `match_skill` | `node_match_skill` | 检测 Skill 意图 / 列表查询 |
| `activate_skill` | `node_activate_skill` | 加载 Skill 上下文 |
| `retrieve_docs` | `node_retrieve_docs` | RAG 文档检索 |
| `retrieve_history` | `node_retrieve_history` | 历史对话检索 |
| `generate_response` | `node_generate_response` | 生成最终回答 |

---

## 核心函数说明

### detect_skill_intent

用 LLM 判断用户意图，返回三种结果：

```python
# 1. 需要执行某个 Skill
{"need_skill": true, "skill_name": "code-review"}

# 2. 询问 Skill 列表
{"list_skills": true}

# 3. 普通聊天
{"need_skill": false}
```

### node_match_skill

- 调用 `detect_skill_intent` 用 LLM 判断
- 提供关键词 fallback 机制，防止 LLM 判断不准确
- 根据判断结果设置 `target_skill` 和 `skill_context`

### should_use_skill

决策路由：

| target_skill | skill_context | 路由 |
|--------------|---------------|------|
| 有值 | - | `activate_skill` |
| None | 有值 | `generate_response` |
| None | None | `retrieve_docs` |

### node_activate_skill

- 根据 `target_skill` 从 `skill_registry` 获取 Skill 完整内容
- 设置 `skill_context` 供后续节点使用

---

## 与 MCP 工具的区别

| 维度 | MCP 工具 | Skill |
|------|----------|-------|
| 用途 | 获取外部数据（新闻等） | 指导模型执行任务 |
| 注入方式 | MCP 结果直接返回 | skill_context 注入 system prompt |
| 触发 | `classify_intent` | `match_skill` |
| 执行 | 同步调用后进入 generate_response | 先 activate_skill 再进入 generate_response |

---

## 配置变更记录

### 2026-03-22 优化

**问题**：原实现在 system_prompt 中预埋所有 Skill 列表，导致：
- 任何对话都会提及 Skill
- 几十个 Skill 时 prompt 爆炸
- 模型被训练成"主动提示用户有 Skill"

**优化方案**：
1. `match_skill` 改用 LLM 判断意图（与 `classify_intent` 一致）
2. 删除 system_prompt 预埋的 Skill 列表
3. 只在匹配到 Skill 时才加载对应上下文
4. 支持询问 Skill 列表的场景

**修改文件**：
- `agent.py`：重写 `node_match_skill`，新增 `detect_skill_intent`、`build_skills_schema`

### 2026-03-22 重命名

**优化节点命名**，提高可读性：

| 原名称 | 新名称 |
|--------|--------|
| `detect_tool` | `classify_intent` |
| `detect_skill` | `match_skill` |
| `load_skill` | `activate_skill` |
| `retrieve_document` | `retrieve_docs` |
| `generate` | `generate_response` |
