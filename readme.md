# MyOllama

基于 Flask、LangGraph 和 Ollama（或 OpenAI/Anthropic 兼容 API）的智能对话助手。

## 功能特性

- **QA/Agent 双模式**：问答模式和智能体模式切换
- **文档渐进式披露问答**：根据问题类型智能决定披露层级（摘要/相关片段/完整内容）
- **Skill 支持**：标准格式的 Skill 系统，即插即用
- **多模型支持**：Ollama、OpenAI、Anthropic
- **多端点支持**：OpenAI 和 Anthropic 模式均支持配置多个 API 端点
- **流式输出**：实时显示生成内容
- **语音交互**：语音识别和朗读

## 快速开始

### 环境要求

- Python 3.8+
- Ollama 服务（Ollama 模式）或 API Key（API 模式）

### 安装

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 拉取模型（Ollama 模式）
ollama pull nomic-embed-text
ollama pull qwen3.5:9b
```

### 启动

```bash
python app.py
```

访问 http://localhost:5000

## 项目结构

```
myOllama/
├── app.py                    # Flask 应用入口
├── routes.py                 # 路由注册
├── api/                      # API 模块
│   ├── __init__.py
│   ├── conversations.py      # 对话管理
│   ├── documents.py          # 文档上传/删除
│   ├── images.py             # 图片上传/删除/截图
│   ├── chat.py               # 消息生成/停止/流式传输/状态
│   ├── skills.py             # 技能管理
│   └── config.py             # 配置管理
├── agent/                    # Agent 模块
│   ├── __init__.py
│   ├── intent.py             # 意图检测
│   ├── nodes.py              # 节点函数
│   ├── graph.py              # 图构建
│   └── stream.py             # 流式接口
├── tools/                    # 工具模块
│   ├── __init__.py
│   ├── builtin.py            # 内置工具（Read/Write/Bash/Glob/Grep）
│   ├── news.py               # 新闻工具
│   ├── document.py           # 文档工具
│   └── skill.py              # Skill 工具
├── core/                     # 核心模块
│   ├── __init__.py           # 状态管理
│   ├── models.py             # 数据模型（Message, Conversation, AppState）
│   └── graph.py              # GraphState 定义
├── config/                   # 配置模块
│   ├── manager.py            # 配置加载/保存
│   └── context.py            # 模型上下文配置
├── storage/                  # 存储模块
│   ├── conversation.py       # 对话持久化
│   ├── history_rag.py        # 历史 RAG 检索
│   └── retriever.py          # 文档检索器
├── document/                  # 文档模块
│   └── loader.py             # 文档加载/处理
├── llm/                      # LLM 模块
│   ├── factory.py            # LLM 工厂
│   └── helpers.py            # LLM 辅助函数
├── resources/                # 资源模块
│   ├── base.py               # 资源基类
│   └── skills.py             # Skill 注册表
├── utils/                    # 工具模块
│   ├── image.py              # 图像处理
│   ├── messages.py           # 消息准备
│   ├── conversation.py       # 对话工具
│   ├── answer.py             # 生成回答
│   └── screenshot.py         # 截图功能
├── static/                   # 静态资源
│   ├── css/
│   └── js/
├── templates/                # HTML 模板
├── skills/                   # Skill 目录
├── conversations/            # 对话存储
└── doc/                      # 文档
    ├── 开发记录.md
    ├── Skill工作流程.md
    ├── PRD_Skill支持.md
    ├── MCP使用说明.md
    └── debug.md
```

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Flask Web Server                      │
│                   (app.py / routes.py)                   │
└─────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────┐
│                LangGraph Agent (agent/)                  │
│                                                          │
│            stream_graph(query, mode)                     │
│                     │                                    │
│         ┌───────────┴───────────┐                        │
│         ▼                       ▼                         │
│   ┌─────────────┐         ┌─────────────┐                │
│   │  QA Graph   │         │ Agent Graph │                │
│   │build_qa_    │         │build_agent_ │                │
│   │  graph()    │         │  graph()    │                │
│   └─────────────┘         └─────────────┘                │
│         │                       │                         │
│         ▼                       ▼                         │
│  classify_intent ──────→ match_skill                     │
│         │                       │                         │
│         ▼                       ▼                         │
│  retrieve_docs           activate_skill                  │
│         │                       │                         │
│         ▼                       ▼                         │
│  retrieve_history       generate_response                │
│         │                       │                         │
│         ▼                       │                         │
│  generate_response ◀──────────┘                         │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────┐                                        │
│  │  SSE Stream  │                                        │
│  └──────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

### LangGraph 工作流

项目采用 **LangGraph** 实现状态化的工作流，通过**两个独立的 Graph** 分别处理 QA 模式和 Agent 模式：

```python
# QA 模式 Graph
def build_qa_graph():
    graph = StateGraph(GraphState)
    graph.add_node("classify_intent", node_classify_intent)
    graph.add_node("retrieve_docs", node_retrieve_docs)
    graph.add_node("retrieve_history", node_retrieve_history)
    graph.add_node("generate_response", node_generate_response)
    graph.set_entry_point("classify_intent")
    # ... QA 模式边
    return graph.compile()

# Agent 模式 Graph
def build_agent_graph():
    graph = StateGraph(GraphState)
    graph.add_node("match_skill", node_match_skill)
    graph.add_node("activate_skill", node_activate_skill)
    graph.add_node("generate_response", node_generate_response)
    graph.set_entry_point("match_skill")
    # ... Agent 模式边
    return graph.compile()

# stream_graph 根据 mode 动态选择
def stream_graph(query, model_name, images, mode):
    if mode == "qa":
        executor = build_qa_graph()
    else:
        executor = build_agent_graph()
    # ...
```

**模式说明**：

| 模式 | 入口节点 | 流程 | 工具绑定 |
|------|----------|------|----------|
| **QA** | `classify_intent` | `→ retrieve_docs → retrieve_history → generate_response` | ❌ 不绑定 |
| **Agent** | `match_skill` | `→ activate_skill → generate_response` | ✅ 绑定内置工具 |

**节点说明**：

| 节点 | 功能 | 所属模式 |
|------|------|----------|
| `classify_intent` | 检测是否需要 MCP 工具 | QA |
| `match_skill` | 检测 Skill 意图 | Agent |
| `activate_skill` | 加载 Skill 上下文 | Agent |
| `retrieve_docs` | 文档检索 | QA |
| `retrieve_history` | 历史检索 | QA |
| `generate_response` | 生成回答 | 共用 |

**Agent 模式特点**：
- 绑定内置工具（Read/Write/Bash/Glob/Grep）
- 支持模型自主工具调用循环
- Skill 上下文按需注入

> **⚠️ 模型要求**：Agent 模式依赖模型的 **Tool Calling** 能力。请使用支持工具调用的模型（如 OpenAI GPT-4、Anthropic Claude、MiniMax 等）。部分本地部署模型可能不支持。

### 渐进式披露设计

项目的核心创新：根据问题类型动态决定文档内容的披露层级。

```
用户提问 "总结文档"
       │
       ▼
┌──────────────────────┐
│  decide_disclosure   │  ← 分析问题关键词
│    Level(query)      │
└──────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                    披露层级决策                               │
├──────────────────────────────────────────────────────────────┤
│  "总结/概括/摘要"  ──▶  disclosure_level = "summary"        │
│       │                              │                        │
│       │                              ▼                        │
│       │                     n_chunks = 30                    │
│       │                     返回30个块给LLM生成摘要          │
│       │                                                      │
│  "详细/完整/全部" ──▶  disclosure_level = "full"            │
│       │                              │                        │
│       │                              ▼                        │
│       │                     n_chunks = 100                   │
│       │                     返回100个块（完整内容）           │
│       │                                                      │
│  其他问题 ──▶  disclosure_level = "relevant"                │
│       │                              │                        │
│       │                              ▼                        │
│       │                     k = 8 (FAISS检索/直接取块)       │
│       │                     返回8个最相关片段                 │
└──────────────────────────────────────────────────────────────┘
```

**实现代码** (graph.py)：

```python
DISCLOSURE_LEVELS = {
    "summary": {"n_chunks": 30, "description": "摘要"},
    "relevant": {"k": 8, "description": "相关片段"},
    "full": {"n_chunks": 100, "description": "完整内容"}
}

def decide_disclosure_level(query: str) -> str:
    query_lower = query.lower()

    if any(kw in query_lower for kw in ["总结", "概括", "摘要", "summary"]):
        return "summary"
    elif any(kw in query_lower for kw in ["详细", "完整", "全部", "full"]):
        return "full"
    else:
        return "relevant"
```

### MCP 工具系统

项目使用 **MCP (Model Context Protocol)** 架构管理外部工具，与 LangGraph 的 Tool Calling 集成。

#### MCP 架构

```
┌────────────────────────────────────────────────────────────┐
│                    MCP Manager (manager.py)                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  意图识别：使用 LLM 判断用户是否需要工具             │   │
│  │  → 分析问题 → 选择工具 → 提取参数                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│         ┌─────────────────┼─────────────────┐              │
│         ▼                 ▼                 ▼               │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │  NewsMCP   │   │ DocumentTool│   │  Future...  │      │
│  │ (新闻获取)  │   │  (文档工具)  │   │  (扩展用)   │      │
│  └─────────────┘   └─────────────┘   └─────────────┘      │
└────────────────────────────────────────────────────────────┘
```

#### 已集成的工具

| 工具 | 来源 | 功能 |
|------|------|------|
| `get_headlines` | NewsMCP | 获取头条新闻 |
| `get_news_by_type` | NewsMCP | 按分类获取新闻 |
| `search_news` | NewsMCP | 关键词搜索新闻 |
| `get_document_summary` | DocumentTool | 获取文档摘要 |
| `get_document_outline` | DocumentTool | 获取文档大纲 |

#### LangGraph 与 MCP 的集成

MCP 工具集成在 **QA 模式**的 `classify_intent` 节点中：

```python
# agent/nodes.py - classify_intent 节点（QA 模式）
def node_classify_intent(state: GraphState) -> dict:
    # 1. 分析问题意图
    tools_schema = build_tools_schema()
    intent = detect_tool_intent(llm, query, tools_schema)

    # 2. 如果需要工具，执行工具
    if intent and intent.get("need_tool"):
        tool_name = intent.get("tool_name")
        # ... 执行 MCP 工具 ...
        result = {"success": True, "formatted_text": ...}
        return {"mcp_result": result}

    return {"mcp_result": None}
```

### Skill 系统

项目支持 **标准格式的 Skill**（参考 Claude Code / OpenCode 规范），实现 Skill 的即插即用。

#### Skill 目录结构

```
skills/                      # Skill 根目录
├── skill-name/              # Skill 目录（必须与 SKILL.md 中的 name 一致）
│   ├── SKILL.md             # 核心文件（必须）
│   ├── scripts/             # 可选：可执行脚本
│   ├── references/          # 可选：参考文档
│   └── assets/              # 可选：模板等资源
└── another-skill/
    └── SKILL.md
```

#### SKILL.md 格式

采用 **Markdown + YAML Frontmatter** 标准格式：

```yaml
---
name: pdf-to-org
description: 将 PDF 论文转换为 Org 格式进行分析。当你需要分析论文时使用。
---

# PDF to Org 转换

## 使用方法

### 步骤 1：读取 PDF
使用 Read 工具读取 PDF 文件...

### 步骤 2：执行转换
...
```

#### 内置 Skill 工具

> **注意**：内置工具仅在 Agent 模式下可用

| 工具 | 功能 |
|------|------|
| `Read` | 读取文件内容 |
| `Write` | 写入文件 |
| `Bash` | 执行脚本 |
| `Glob` | 文件搜索 |
| `Grep` | 内容搜索 |

#### 添加新 Skill

将 Skill 文件夹放入 `skills/` 目录，系统启动时自动注册。无需修改代码。

### 上下文加载策略

```
用户提问
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    上下文构建流程                            │
├─────────────────────────────────────────────────────────────┤
│  1. System Prompt (指定角色和回答规则)                     │
│  2. Skill 列表 (始终包含，模型自行判断是否触发)             │
│  3. 对话摘要 (对话轮数 > 5 时生成)                          │
│  4. 历史对话 RAG (语义检索相关片段)                         │
│  5. 文档上下文 (根据 disclosure_level 加载)                 │
│  6. 最近对话 (滑动窗口，默认 5 轮)                          │
│  7. 当前问题                                               │
└─────────────────────────────────────────────────────────────┘
```

| 来源 | 策略 | 参数 |
|------|------|------|
| Skill 列表 | 始终注入 | 模型自行判断触发 |
| 对话摘要 | LLM 压缩 | 轮数 > 5 时生成 |
| 历史 RAG | FAISS 检索 / LLM 选择 | Ollama: k=3, API: LLM 判断 |
| 文档 | 渐进式披露 | 根据问题类型 |

## 技术栈

- **后端**: Flask
- **AI/ML**: LangChain, LangGraph, Ollama / OpenAI / Anthropic
- **向量存储**: FAISS
- **文档处理**: PyPDFLoader, python-docx
- **前端**: 原生 HTML/CSS/JavaScript

## 文档

- [开发记录](doc/开发记录.md) - 详细的技术实现和架构设计
- [Skill 工作流程](doc/Skill工作流程.md) - Skill 系统使用说明
- [PRD_Skill支持](doc/PRD_Skill支持.md) - Skill 需求文档
- [MCP使用说明](doc/MCP使用说明.md) - MCP 工具系统说明
- [debug.md](doc/debug.md) - 调试指南

## 许可证

MIT
