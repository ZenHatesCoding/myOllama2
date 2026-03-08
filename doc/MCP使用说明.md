# MCP 功能使用说明

## 功能概述

在 myOllama 项目中集成了 **MCP (Model Context Protocol)** 架构的外部工具系统，支持新闻获取、文档问答等功能。

MCP 采用 LLM 意图识别 + 自动工具调用的模式工作。

## 核心功能

1. **新闻获取**（基于聚合数据 API）
   - 获取头条新闻
   - 按分类获取新闻（社会/国内/国际/娱乐/体育/科技/财经）
   - 关键词搜索新闻
2. **文档问答**（内置工具）
   - 获取文档摘要
   - 语义检索文档
   - 获取文档大纲
3. **智能意图识别**：自动判断用户是否需要调用工具
4. **演示数据模式**：无需 API 密钥即可测试功能

## 文件结构

```
myOllama2/
├── mcp/
│   ├── __init__.py       # MCP 模块初始化，导出公共接口
│   ├── base.py          # MCP 基类和工具 schema 定义
│   ├── manager.py       # MCP 管理器，负责意图识别和工具调用
│   └── news_mcp.py     # 新闻 MCP 实现（基于聚合数据）
├── document_tools.py    # 文档工具（LangChain @tool）
├── agent.py            # LangGraph Agent，集成 MCP 工具调用
└── test_mcp.py         # MCP 测试脚本
```

## 工作原理

### 1. MCP 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Manager                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  意图识别：使用 LLM 判断用户是否需要工具             │    │
│  │  → 分析问题 → 选择工具 → 提取参数                   │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                   │
│         ┌─────────────────┼─────────────────┐               │
│         ▼                 ▼                 ▼                │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │  NewsMCP   │   │DocumentTool │   │  Future...  │       │
│  └─────────────┘   └─────────────┘   └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 2. LangGraph 与 MCP 的集成

MCP 工具通过 LangGraph 的 `node_detect_tool` 节点被调用：

```python
# agent.py - node_detect_tool 节点
def node_detect_tool(state: GraphState) -> dict:
    # 1. 构建工具 schema
    tools_schema = build_tools_schema()
    
    # 2. LLM 意图识别
    intent = detect_tool_intent(llm, query, tools_schema)
    
    # 3. 如果需要工具，执行工具
    if intent and intent.get("need_tool"):
        tool_name = intent.get("tool_name")
        parameters = intent.get("parameters", {})
        
        # ... 执行 MCP 工具 ...
        result = execute_tool(tool_name, parameters)
        
        return {"mcp_result": result}
    
    return {"mcp_result": None}
```

### 3. 工作流程

```
用户输入 "获取今天的科技新闻"
       │
       ▼
┌──────────────────────────────┐
│  detect_tool 节点            │
│  ┌────────────────────────┐  │
│  │ LLM 意图识别          │  │
│  │ → need_tool: true    │  │
│  │ → tool_name: get_    │  │
│  │   news_by_type       │  │
│  │ → parameters:        │  │
│  │   {news_type: keji}  │  │
│  └────────────────────────┘  │
└──────────────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  执行 NewsMCP 工具           │
│  → 调用聚合数据 API          │
│  → 获取科技新闻              │
└──────────────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  generate 节点               │
│  → 格式化新闻结果            │
│  → 流式返回给用户            │
└──────────────────────────────┘
```

## 使用方法

### 通过 Web 界面使用

1. 启动应用：
```bash
python app.py
```

2. 打开浏览器访问 http://localhost:5000

3. 输入以下示例：
   - "获取头条新闻"
   - "获取今天的科技新闻"
   - "搜索关于人工智能的新闻"
   - "获取最新的体育新闻"

### 通过测试脚本使用

```bash
cd myOllama2
python test_mcp.py
```

## 配置真实 API 密钥

### 申请聚合数据 API 密钥

1. 访问 https://www.juhe.cn/
2. 注册账号
3. 进入个人中心 → 数据中心
4. 申请"新闻头条"API
5. 获取 API Key

### 配置 API 密钥

在 `mcp/__init__.py` 中修改：

```python
# 原来的代码（使用演示数据）
mcp_manager.register_mcp(NewsMCP())

# 修改为（使用真实 API）
mcp_manager.register_mcp(NewsMCP(api_key="your_juhe_api_key_here"))
```

## 支持的工具

### 新闻工具（NewsMCP）

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `get_headlines` | 获取头条新闻 | `page_size` (可选，默认 10) |
| `get_news_by_type` | 按分类获取新闻 | `news_type` (必需), `page_size` (可选) |
| `search_news` | 关键词搜索新闻 | `keyword` (必需), `page_size` (可选) |

### 新闻类型参数

- `top` - 头条
- `shehui` - 社会
- `guonei` - 国内
- `guoji` - 国际
- `yule` - 娱乐
- `tiyu` - 体育
- `keji` - 科技
- `caijing` - 财经

### 文档工具（内置）

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `get_document_summary` | 获取文档摘要 | `n_chunks` (可选) |
| `search_document` | 语义检索文档 | `query` (必需), `k` (可选) |
| `get_document_outline` | 获取文档大纲 | 无 |

## 演示数据模式

如果没有配置 API 密钥，系统会自动使用演示数据模式，返回模拟的新闻数据。

**优点**：
- 无需 API 密钥即可测试
- 验证 MCP 功能是否正常
- 检查意图识别是否准确

**注意**：
- 演示数据是固定的，不会实时更新
- 要获取真实新闻，请配置 API 密钥

## 缓存机制

新闻数据默认缓存 10 分钟，避免频繁请求 API。

```python
from datetime import timedelta
from mcp import NewsMCP

news_mcp = NewsMCP(api_key="your_key")
news_mcp.cache_duration = timedelta(minutes=30)  # 30 分钟缓存
```

## 添加新 MCP 工具

1. 继承 `BaseMCP` 类
2. 实现 `get_tools()` 和 `execute_tool()` 方法
3. 在 `MCPManager` 中注册

```python
# mcp/weather_mcp.py
from .base import BaseMCP, ToolSchema, ToolParameter

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
                parameters=[
                    ToolParameter(
                        name="city",
                        type="string",
                        description="城市名称",
                        required=True
                    )
                ]
            )
        ]
    
    def execute_tool(self, tool_name: str, parameters: dict):
        # 实现工具逻辑
        city = parameters.get("city")
        # 调用天气 API
        return {"success": True, "formatted_text": f"{city} 天气：晴，温度 25°C"}

# 注册
# mcp/__init__.py
from .weather_mcp import WeatherMCP

mcp_manager.register_mcp(WeatherMCP())
```

## 常见问题

### Q: 为什么返回演示数据？

A: 没有配置 API 密钥时，系统会自动使用演示数据。请按照上述步骤申请 API 密钥并配置。

### Q: API 请求失败怎么办？

A:
1. 检查 API 密钥是否正确
2. 检查是否超出免费额度（聚合数据每天 100 次）
3. 检查网络连接
4. 查看错误日志

### Q: 意图识别不准确怎么办？

A: 可以调整 `agent.py` 中的 `detect_tool_intent` 函数的 system_prompt，或者使用更强大的模型。

### Q: LangGraph 如何与 MCP 集成？

A: MCP 工具通过 `node_detect_tool` 节点被调用，使用 LLM 进行意图识别，然后执行相应的工具。具体见上文"LangGraph 与 MCP 的集成"部分。

## 技术栈

- **HTTP 客户端**: httpx
- **AI/LLM**: LangChain, LangGraph, Ollama
- **工具定义**: LangChain @tool
- **新闻 API**: 聚合数据 (juhe.cn)

## 更新日志

### v7.0.0
- MCP 工具集成到 LangGraph 工作流
- 新增文档工具（get_document_summary, search_document, get_document_outline）
- LLM 意图识别 + 自动工具调用
- 统一通过 agent.py 调用 MCP
