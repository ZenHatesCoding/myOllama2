# Skill 工作流程详解

## 整体架构

Skill 系统基于 LangGraph 工作流，通过**两个独立的 Graph** 分别处理 QA 模式和 Agent 模式。

```
stream_graph(query, mode)
    │
    ├─── mode = "qa" ──────────→ build_qa_graph()
    │                              │
    │                              ▼
    │                         QA Graph
    │    classify_intent → retrieve_docs → retrieve_history → generate_response
    │
    └─── mode = "agent" ───────→ build_agent_graph()
                                   │
                                   ▼
                              Agent Graph
                match_skill → activate_skill → generate_response
```

---

## QA 模式 Graph

### 流程

```
用户输入 → classify_intent → retrieve_docs → retrieve_history → generate_response
```

### 特点

- 不注入 Skill 上下文
- 不绑定内置工具
- 使用新闻 MCP 和文档 RAG 工具
- `generate_response` 节点：无工具绑定版本

### 节点

| 节点 | 函数 | 职责 |
|------|------|------|
| `classify_intent` | `node_classify_intent` | 检测是否需要 MCP 工具（新闻/文档） |
| `retrieve_docs` | `node_retrieve_docs` | RAG 文档检索 |
| `retrieve_history` | `node_retrieve_history` | 历史对话检索 |
| `generate_response` | `node_generate_response` | 生成回答（无工具绑定） |

### 条件边

`classify_intent` 节点的 `should_use_tool_qa` 决策：

| 条件 | 下一节点 |
|------|----------|
| 有 MCP 结果 | `generate_response` |
| 否则 | `retrieve_docs` |

---

## Agent 模式 Graph

### 流程

```
用户输入 → match_skill → activate_skill → generate_response
```

### 特点

- 注入 Skill 上下文（如果有匹配）
- 绑定内置工具（Read/Write/Bash/Glob/Grep）
- 支持模型自主工具调用循环
- `generate_response` 节点：工具绑定版本

### 节点

| 节点 | 函数 | 职责 |
|------|------|------|
| `match_skill` | `node_match_skill` | 检测 Skill 意图 |
| `activate_skill` | `node_activate_skill` | 加载 Skill 上下文 |
| `generate_response` | `node_generate_response` | 生成回答（绑定内置工具） |

### 条件边

`match_skill` 节点的 `should_use_skill_agent` 决策：

| 条件 | 下一节点 |
|------|----------|
| `target_skill` 有值 | `activate_skill` |
| 其他 | `generate_response` |

### 工具调用循环

```
generate_response:
  1. 绑定内置工具（Read/Write/Bash/Glob/Grep）
  2. 模型生成文本或工具调用
  3. 执行工具，结果反馈给模型
  4. 循环直到模型输出最终回答
```

---

## 核心函数说明

### build_qa_graph()

构建 QA 模式的 LangGraph：

```python
def build_qa_graph():
    graph = StateGraph(GraphState)
    graph.add_node("classify_intent", node_classify_intent)
    graph.add_node("retrieve_docs", node_retrieve_docs)
    graph.add_node("retrieve_history", node_retrieve_history)
    graph.add_node("generate_response", node_generate_response)
    graph.set_entry_point("classify_intent")
    # ... 添加边
    return graph.compile(checkpointer=MemorySaver())
```

### build_agent_graph()

构建 Agent 模式的 LangGraph：

```python
def build_agent_graph():
    graph = StateGraph(GraphState)
    graph.add_node("match_skill", node_match_skill)
    graph.add_node("activate_skill", node_activate_skill)
    graph.add_node("generate_response", node_generate_response)
    graph.set_entry_point("match_skill")
    # ... 添加边
    return graph.compile(checkpointer=MemorySaver())
```

### stream_graph()

根据 mode 动态选择 Graph：

```python
def stream_graph(query, model_name, images, mode):
    initial_state = create_initial_state(query, model_name, images, mode)

    if mode == "qa":
        executor = build_qa_graph()
    else:
        executor = build_agent_graph()

    for event in executor.stream(initial_state, ...):
        # 处理事件
```

### node_generate_response()

内部通过 `mode` 字段判断使用哪个逻辑：

```python
def node_generate_response(state: GraphState) -> dict:
    mode = state.get("mode", "qa")

    if mode == "agent":
        # 工具绑定版本
        llm = llm.bind_tools(builtin_tools)
        # ... 工具调用循环
    else:
        # 无工具绑定版本
        # ... 直接生成回答
```

---

## 与 MCP 工具的区别

| 维度 | MCP 工具（QA 模式） | 内置工具（Agent 模式） |
|------|---------------------|------------------------|
| 用途 | 获取外部数据（新闻等） | 文件操作、脚本执行 |
| 触发 | `classify_intent` 检测 | 模型自主决定 |
| 调用方式 | 意图识别后执行 | Tool Calling 循环 |
| 注入方式 | MCP 结果直接返回 | 工具结果反馈给模型 |

---

## 配置变更记录

### 2026-03-22 两个独立 Graph 架构

**问题**：原方案使用单一 Graph + 条件路由，导致状态机混乱，无法正常工作。

**解决方案**：
1. 创建两个独立的 Graph：`build_qa_graph()` 和 `build_agent_graph()`
2. `stream_graph()` 根据 mode 动态选择使用哪个 Graph
3. 删除了 `route_by_mode` 节点和 `should_use_tool`/`should_use_skill` 的跨模式路由

**修改文件**：
- `agent.py`：新增 `build_qa_graph()` 和 `build_agent_graph()`，修改 `stream_graph()` 和 `run_graph()`

### 2026-03-22 QA/Agent 模式分离

**改动**：
1. 新增 `mode` 字段到 `GraphState`
2. QA 模式：跳过 Skill 相关节点，不绑定工具
3. Agent 模式：跳过 MCP 工具，不注入文档上下文
4. Agent 模式 `generate_response` 绑定内置工具，支持工具调用循环

**修改文件**：
- `graph.py`：新增 `mode` 字段
- `agent.py`：`generate_response` 根据 mode 选择逻辑
- `routes.py`：传递 `mode` 参数
- `utils.py`：`generate_answer` 支持 `mode` 参数

### 2026-03-22 Skill 本质重新定义

**核心理念**：Skill 的本质是"教 AI 怎么做事的说明书"，不是可执行代码，也不是工具调用手册。

| 层级 | Claude Code 设计 | myOllama2 实现 |
|------|------------------|----------------|
| **知识层** | SKILL.md - 工作流指南 | 保持一致 |
| **工具层** | Read/Edit/Bash 等内置工具 | 内置工具始终可用 |
| **连接层** | LangGraph | 复用 |
