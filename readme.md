# MyOllama - 智能对话助手

基于 Flask、LangGraph 和 Ollama（或 OpenAI/Anthropic 兼容 API）的智能对话助手，支持文档渐进式披露问答、多模型选择、语音交互、截图识别等功能。

## 功能特性

### 核心功能
- **Skill 支持**：标准格式的 Skill 系统，自动注册，即插即用（详见 [Skill 工作流程](doc/Skill工作流程.md)）
- **文档渐进式披露问答**：上传文档后，系统根据问题类型智能决定披露层级（摘要/相关片段/完整内容）
- **多文档格式支持**：PDF、Word (.docx)、纯文本
- **图片上传**：支持图片上传和多模态问答，支持拖拽上传
- **截图识别**：支持屏幕截图和区域选择（快捷键 Alt+A）
- **拖拽上传**：支持将图片或文档直接拖拽到对话框区域上传
- **智能问答**：基于 LangGraph Agent 和 LLM（Ollama/OpenAI/Anthropic）的问答系统
- **流式输出**：实时显示生成内容，提供流畅的用户体验
- **中断操作**：可随时停止正在生成的回答
- **新闻获取**：集成聚合数据 API，支持头条新闻、分类新闻、新闻搜索

### 对话管理
- **本地记忆持久化**：对话历史自动保存为 Markdown 文件，重启服务后自动恢复
- **多对话支持**：创建和管理多个独立对话
- **对话分叉**：基于现有对话创建新的分支对话
- **智能命名**：AI 自动生成对话摘要作为标题（新对话首条消息自动命名，每 5 轮对话后自动刷新）
- **历史对话 RAG**：语义检索历史对话中的相关内容

### 语音功能
- **语音识别**：支持中英文语音输入，自动转换为文字
- **语音朗读**：支持中英文语音播放

### 模型选择
- **多模型支持**：qwen3:8b、qwen3:14b、deepseek-r1:8b、qwen3-vl:8b、qwen3.5 系列
- **默认模型**：qwen3.5:9b
- **自动切换**：上传图片或截图时自动切换到多模态模型
- **多 Provider 支持**：支持 Ollama、OpenAI 兼容 API、Anthropic 兼容 API
- **多端点支持**：OpenAI 和 Anthropic 模式均支持配置多个 API 端点，每个端点可注册多个模型，前端动态生成下拉菜单
- **API 配置注意**：Anthropic 兼容模式地址末尾是 `/anthropic`，`langchain_anthropic` 会自动加 `/v1/messages`

## 环境要求

- Python 3.8+
- **Ollama 模式**：Ollama 服务（运行在 http://localhost:11434）
- **API 模式**：OpenAI 或 Anthropic 兼容 API
- 推荐使用的 Ollama 模型：
  - 嵌入模型：`nomic-embed-text`（仅 Ollama 模式需要）
  - LLM 模型：`qwen3.5:9b`、`qwen3-vl:8b` 等

## 安装步骤

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 仅 Ollama 模式需要拉取模型
ollama pull nomic-embed-text
ollama pull qwen3.5:9b
ollama pull qwen3-vl:8b

# API 模式则需要在配置界面填写 API Key
```

## 启动应用

```bash
python app.py
```

应用将在 http://localhost:5000 启动

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Flask Web Server                         │
│                         (app.py / routes.py)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Agent (agent.py)                    │
│                                                                  │
│  ┌──────────────┐                                               │
│  │ detect_tool │ ←── 入口：检测是否需要 MCP 工具               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              should_use_tool 决策                         │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │    │
│  │  │ target_skill│  │  mcp_result │  │   其他        │   │    │
│  │  │   已设置     │  │   已设置     │  │              │   │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘   │    │
│  └─────────┼────────────────┼────────────────┼────────────┘    │
│            ▼                ▼                ▼                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ load_skill  │  │   generate   │  │ detect_skill │        │
│  │ (加载 Skill) │  │ (MCP 结果)   │  │ (检测 Skill) │        │
│  └──────┬───────┘  └──────────────┘  └──────┬───────┘        │
│         │                                      │                 │
│         │              ┌──────────────────────┼────────────┐    │
│         │              ▼                      ▼            │    │
│         │       ┌─────────────────────────────────────┐   │    │
│         │       │        should_use_skill 决策          │   │    │
│         │       │  ┌─────────────┐  ┌─────────────┐   │   │    │
│         │       │  │target_skill │  │   其他      │   │   │    │
│         │       │  │  已设置     │  │             │   │   │    │
│         │       │  └──────┬─────┘  └──────┬──────┘   │   │    │
│         │       └─────────┼───────────────┼──────────┘   │    │
│         │                 ▼               ▼                │    │
│         │          ┌────────────┐  ┌──────────────┐     │    │
│         │          │load_skill  │  │retrieve_doc  │     │    │
│         │          └─────┬──────┘  └──────┬───────┘     │    │
│         │                │                │              │    │
│         │                └────────┬───────┘              │    │
│         │                         ▼                      │    │
│         │                  ┌──────────────┐              │    │
│         │                  │retrieve_hist │              │    │
│         │                  └──────┬───────┘              │    │
│         │                         ▼                      │    │
│         │                  ┌──────────────┐              │    │
│         └─────────────────▶│   generate  │◀─────────────┘    │
│                            │ (Skill/MCP/ │                  │
│                            │  Doc/Chat)  │                  │
│                            └──────┬───────┘                  │
│                                   ▼                           │
│                            ┌──────────────┐                   │
│                            │  SSE Stream  │                   │
│                            └──────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### LangGraph 工作流

项目采用 **LangGraph** 实现状态化的工作流，每个请求都会经过以下节点：

```python
graph = StateGraph(GraphState)

graph.add_node("detect_tool", node_detect_tool)      # 检测 MCP 工具
graph.add_node("detect_skill", node_detect_skill)    # 检测 Skill 意图
graph.add_node("load_skill", node_load_skill)        # 加载 Skill 上下文
graph.add_node("retrieve_document", node_retrieve_document)  # 文档检索
graph.add_node("retrieve_history", node_retrieve_history)    # 历史检索
graph.add_node("generate", node_generate)            # LLM 生成回答

graph.set_entry_point("detect_tool")

graph.add_conditional_edges("detect_tool", should_use_tool, {
    "load_skill": "load_skill",           # Skill 已触发
    "generate": "generate",               # MCP 工具结果
    "detect_skill": "detect_skill"       # 进入 Skill 检测
})

graph.add_conditional_edges("detect_skill", should_use_skill, {
    "load_skill": "load_skill",           # Skill 意图匹配
    "retrieve_document": "retrieve_document"  # 普通文档问答
})

graph.add_edge("load_skill", "generate")
graph.add_edge("retrieve_document", "retrieve_history")
graph.add_edge("retrieve_history", "generate")
graph.add_edge("generate", END)
```

**节点说明**：

| 节点 | 功能 | 说明 |
|------|------|------|
| `detect_tool` | 意图识别 | 检测是否需要 MCP 工具（新闻等） |
| `detect_skill` | Skill 检测 | 检测是否触发某个 Skill |
| `load_skill` | 加载 Skill | 加载 Skill 的完整内容和工具 |
| `retrieve_document` | 文档检索 | RAG 向量检索 + 渐进式披露 |
| `retrieve_history` | 历史检索 | 语义检索相关历史对话 |
| `generate` | 生成回答 | 整合 Skill/MCP/文档/历史上下文 |

**四种对话模式**：

| 模式 | 触发条件 | 上下文 |
|------|----------|--------|
| **Skill 模式** | 用户请求匹配 Skill description | Skill 内容 + 内置工具 |
| **MCP 模式** | 用户请求需要新闻等工具 | MCP 工具结果 |
| **文档模式** | 上传文档后的问答 | RAG 检索结果 + 渐进式披露 |
| **普通对话** | 其他情况 | 历史对话 + Skill 列表（始终可用） |

### 渐进式披露设计

项目的核心创新：根据问题类型动态决定文档内容的披露层级。

```
用户提问 "总结文档"
       │
       ▼
┌──────────────────────┐
│  decide_disclosure  │  ← 分析问题关键词
│    Level(query)     │
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
│  其他问题 ──▶  disclosure_level = "relevant"                 │
│       │                              │                        │
│       │                              ▼                        │
│       │                     k = 8 (FAISS检索/直接取块)                │
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
┌─────────────────────────────────────────────────────────────┐
│                      MCP Manager (manager.py)                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  意图识别：使用 LLM 判断用户是否需要工具             │    │
│  │  → 分析问题 → 选择工具 → 提取参数                   │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                   │
│         ┌─────────────────┼─────────────────┐               │
│         ▼                 ▼                 ▼                │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │  NewsMCP   │   │ DocumentTool│   │  Future...  │      │
│  │ (新闻获取)  │   │  (文档工具)  │   │  (扩展用)   │      │
│  └─────────────┘   └─────────────┘   └─────────────┘      │
└─────────────────────────────────────────────────────────────┘
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

```python
# agent.py - node_detect_tool 节点
def node_detect_tool(state: GraphState) -> dict:
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

#### 添加新 MCP 工具

1. 继承 `BaseMCP` 类
2. 实现 `get_tools()` 和 `execute_tool()` 方法
3. 在 `MCPManager` 中注册

```python
# 示例：添加天气 MCP
class WeatherMCP(BaseMCP):
    def __init__(self):
        super().__init__(
            name="weather_mcp",
            description="获取天气信息"
        )

    def get_tools(self):
        return [
            ToolSchema(
                name="get_weather",
                description="获取指定城市天气",
                parameters=[...]
            )
        ]

    def execute_tool(self, tool_name: str, parameters: dict):
        # 实现工具逻辑
        ...

# 注册
mcp_manager.register_mcp(WeatherMCP())
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
│                    上下文构建流程                             │
├─────────────────────────────────────────────────────────────┤
│  1. System Prompt (指定角色和回答规则)                      │
│  2. Skill 列表 (始终包含，模型自行判断是否触发)             │
│  3. 对话摘要 (对话轮数 > 5 时生成)                          │
│  4. 历史对话 RAG (语义检索相关片段)                         │
│  5. 文档上下文 (根据 disclosure_level 加载)                 │
│  6. 最近对话 (滑动窗口，默认 5 轮)                           │
│  7. 当前问题                                                │
└─────────────────────────────────────────────────────────────┘
```

| 来源 | 策略 | 参数 |
|------|------|------|
| Skill 列表 | 始终注入 | 模型自行判断触发 |
| 对话摘要 | LLM 压缩 | 轮数 > 5 时生成 |
| 历史 RAG | FAISS 检索 / LLM 选择 | Ollama: k=3, API: LLM 判断 |
| 文档 | 渐进式披露 | 根据问题类型 |

## 项目结构

```
myOllama/
├── app.py                 # Flask 应用入口
├── routes.py              # API 路由定义
├── agent.py               # LangGraph Agent 构建和节点定义
├── graph.py               # GraphState 定义和渐进式披露逻辑
├── document_tools.py      # 文档工具 (LangChain @tool)
├── mcp/
│   ├── __init__.py
│   ├── base.py           # MCP 基类定义
│   ├── manager.py        # MCP 管理器
│   └── news_mcp.py       # 新闻 MCP 实现
├── utils.py               # 工具函数（消息构建、摘要生成）
├── resources.py           # 资源注册表
├── conversation_manager.py # 对话持久化管理
├── history_rag.py         # 历史对话 RAG 检索
├── extensions.py          # 状态管理（解决循环依赖）
├── llm_factory.py         # LLM 工厂（多 Provider 支持）
├── conversations/         # 对话存储目录
├── vector_stores/         # 向量索引存储（仅 Ollama 模式）
└── templates/             # HTML 模板
```

## 技术栈

- **后端**: Flask
- **AI/ML**: LangChain, LangGraph, Ollama / OpenAI / Anthropic
- **向量存储**: FAISS（仅 Ollama 模式需要）
- **文档处理**: PyPDFLoader, python-docx
- **前端**: 原生 HTML/CSS/JavaScript

## 更新日志

### v8.0.0

- **Skill 系统**
  - 标准 Skill 格式支持（Markdown + YAML Frontmatter）
  - 自动发现与注册，无需修改代码
  - 内置文件读写、脚本执行工具（Read/Write/Bash/Glob/Grep）
  - Skill 触发检测与渐进式上下文注入
  - 所有对话模式统一 system_prompt，模型自行判断触发

- **前端 Skill 管理**
  - 配置面板显示已注册 Skill 列表
  - 手动重新加载 Skill

### v7.2.0
- **多端点支持**
  - OpenAI 和 Anthropic 模式均支持配置多个 API 端点
  - 每个端点可注册多个模型
  - 前端动态生成模型下拉菜单
  - 可在端点间快速切换模型

### v7.1.0
- **多 LLM Provider 支持**
  - 支持 Ollama、OpenAI 兼容 API、Anthropic 兼容 API
  - 可在配置界面切换不同的 LLM 服务商
  - API 模式下不构建向量索引

---

## 待办事项

### 方案一：动态拉取模型列表（未来探索）

**背景**：用户希望配置 URL + API Key 后，系统能自动发现服务器上可用的模型，而不是手动注册。

**实现难点**：
- **Anthropic 官方没有模型列表 API**，这是其设计理念（强调"不知道有什么模型"的简洁性）
- 第三方兼容服务（如 Minimax）可能有自定义端点，但需要服务商配合

**可能的实现方式**：
1. **探测式调用**：向 `/models` 或类似端点发送请求，根据响应判断可用模型
2. **服务商特定 API**：针对特定服务商（如 Minimax）实现其专有的模型发现接口
3. **手动 + 动态混合**：保留手动注册作为基础，动态发现作为增强功能

**前置条件**：
- 需要确定目标服务商的模型列表 API 规范
- 需要服务商支持跨域或提供 SDK

**状态**：待探索，需要用户确认目标服务商后实现

---

## API 模式实现

### 架构设计

项目采用统一的检索策略接口，同时支持 Ollama 和 API 模式：

```
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph 工作流                              │
│                                                                  │
│  query → detect_tool → retrieve_document → retrieve_history → │
│                               │                    │            │
│                               ▼                    ▼            │
│                    文档检索 (retriever)    历史 RAG            │
│                    - Ollama: FAISS         - Ollama: FAISS    │
│                    - API: 直接取块         - API: LLM 判断    │
│                               │                    │            │
│                               └────────┬───────────┘            │
│                                        ▼                         │
│                              generate (生成回答)                │
└─────────────────────────────────────────────────────────────────┘
```

### 1. 文档问答

#### 统一检索接口 (retriever.py)

```python
class DocumentRetriever(ABC):
    def retrieve(self, query: str, k: int) -> List[Document]:
        pass

class FAISSRetriever(DocumentRetriever):
    def retrieve(self, query: str, k: int):
        return self.vector_store.similarity_search(query, k=k)

class DirectChunkRetriever(DocumentRetriever):
    def retrieve(self, query: str, k: int):
        return self.chunks[:k]  # 直接取前 k 个块

def create_retriever(conversation, provider: str):
    if provider == "ollama" and conversation.vector_store:
        return FAISSRetriever(conversation.vector_store, conversation.document_chunks)
    else:
        return DirectChunkRetriever(conversation.document_chunks)
```

#### 渐进式披露 + MCP 协同

```python
def node_retrieve_document(state: GraphState) -> dict:
    retriever = create_retriever(conversation, provider)
    k = level_config.get("k", 8)
    relevant_docs = retriever.retrieve(query, k=k)
    
    outline = get_document_outline.invoke({})
    summary = get_document_summary.invoke({"n_chunks": 10})
    
    full_context = f"""【相关片段】
{main_context}

【文档大纲】
{outline}

【文档摘要】
{summary}
"""
```

### 2. 历史对话 RAG

#### 统一上下文接口 (history_rag.py)

```python
class HistoryRAG:
    def get_context(self, query: str, provider: str, llm=None, k: int = 3):
        if provider == "ollama" and self.vector_store:
            return self._get_context_with_faiss(query, k)
        else:
            return self._get_context_with_llm(query, llm, k)
    
    def _get_context_with_faiss(self, query: str, k: int):
        results = self.search(query, k=k)
        return format_results(results)
    
    def _get_context_with_llm(self, query: str, llm, k: int):
        # 1. 获取所有对话元信息
        conversations = conversation_manager.get_all_conversations()
        
        # 2. LLM 判断哪些历史对话相关
        prompt = f"""当前问题：{query}
历史对话列表：{conv_list}
请选择最相关的 {k} 个对话ID（用逗号分隔）。"""
        
        selected_ids = llm.invoke(prompt).content.split(",")
        
        # 3. 读取选中对话内容并返回
        return load_selected_conversations(selected_ids)
```

#### LangGraph 集成

```python
def node_retrieve_history(state: GraphState) -> dict:
    provider = app_state.llm_provider
    
    if total_turns > max_context_turns:
        llm = create_llm(provider) if provider != "ollama" else None
        history_context = history_rag.get_context(query, provider, llm, k=3)
    
    return {"history_context": history_context or ""}
```

### 3. 复用设计

| 模块 | Ollama 模式 | API 模式 |
|------|------------|----------|
| 文档检索 | FAISS 向量检索 | DirectChunkRetriever 直接取块 |
| 历史 RAG | FAISS 向量检索 | LLM 判断选择 |
| MCP 工具 | Ollama LLM | API LLM |
| LLM 调用 | ChatOllama | ChatOpenAI / ChatAnthropic |

通过统一的接口 + provider 参数切换，实现最大程度的代码复用。

---

### v7.0.0

- **LangGraph 重构**
  - 使用 StateGraph 实现状态化工作流
  - 条件边实现动态流程控制
  - MemorySaver 实现对话状态记忆
- **渐进式披露升级**
  - 根据问题类型自动选择披露层级
  - summary / relevant / full 三级披露
  - 关键词驱动的智能决策
- **MCP 工具集成**
  - MCP Manager 统一管理外部工具
  - LLM 意图识别 + 自动工具调用
  - 支持新闻获取、文档问答等
- **默认模型升级**
  - 对话默认模型改为 qwen3.5:9b
  - 统一使用当前选中模型
- **Token 限制优化**
  - 历史对话分块截断
  - LLM 输出长度扩展

### v6.1.0

- 文档上传异步处理 + 进度条
- 摘要流式生成
- 中断操作支持

### v6.0.0

- 文档渐进式问答
- 上下文窗口自适应
