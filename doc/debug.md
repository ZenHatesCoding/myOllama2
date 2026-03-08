# myOllama2 问题调试记录

## 问题 1：上传文档后界面不更新

### 问题描述
上传文档触发生成摘要时，进度条走完，但界面不会显示上传的文档名称，也不会显示问答结果，需要手动刷新页面(F5)才会显示。

### 问题分析

#### 第一层分析：SSE 协议不一致
- **后端** (`routes.py` 第 389 行)：发送 chunk 消息时直接发送内容
  ```python
  if msg_type == "chunk":
      yield f"data: {content}\n\n"
  ```
- **前端** (`app.js` 第 704 行)：期望收到 `[chunk]` 前缀
  ```javascript
  } else if (data.startsWith('[chunk]')) {
      const chunk = data.substring(7);
      appendChunk(chunk);
  }
  ```
- **结果**：前端无法识别 chunk 消息，消息内容丢失

#### 第二层分析：loadMessages 调用问题
即使 SSE 协议修复后，消息仍然不显示。进一步排查发现：

- **前端** (`app.js` 第 730、748 行)：`loadMessages()` 调用时没有传对话 ID 参数
  ```javascript
  loadMessages();  // ❌ 没有传 conversationId 参数
  ```
- **函数定义** (`app.js` 第 340 行)：
  ```javascript
  function loadMessages(conversationId) {
      fetch(`/api/conversations/${conversationId}/messages`)
  ```
- **结果**：请求变成 `/api/conversations/undefined/messages`，返回 404

### 修复方案

#### 修复 1：后端 SSE 添加前缀
**文件**: `routes.py`
```python
# 修改前
if msg_type == "chunk":
    yield f"data: {content}\n\n"

# 修改后
if msg_type == "chunk":
    yield f"data: [chunk]{content}\n\n"
```

#### 修复 2：前端传对话 ID
**文件**: `app.js`
```javascript
// 修改前
loadMessages();
loadMessages();

// 修改后
loadMessages(currentConversationId);
loadMessages(currentConversationId);
```

### 修复后状态
- ✅ 文档上传后进度条正常显示
- ✅ 流式输出内容正常显示
- ✅ [DONE] 信号收到后正确调用 loadMessages 加载消息
- ✅ 界面正确显示文档名称和问题/答案
- ✅ 无需手动刷新页面

### 修复时间
2026-03-08

---

## Token 限制问题汇总

### 问题 1：历史对话索引构建失败

**问题描述**
构建历史对话索引时报错：`the input length exceeds the context length (status code: 400)`

**问题分析**
- embedding 模型 `nomic-embed-text` 对输入长度有限制
- 历史对话消息过长导致超出限制

**修复方案**
- `history_rag.py` 中添加分块长度限制
- `_split_into_blocks` 方法中截断每条消息到 2000 字符
- 分批构建索引（每批 100 个块）并合并

---

### 问题 2：文档摘要被截断

**问题描述**
上传文档生成摘要时，输出被截断

**问题分析**
- LLM 默认的 `num_predict` 参数限制输出长度
- 长文档摘要需要更长的输出

**修复方案**
- `agent.py` 的 `node_generate` 中增加 `num_predict=8000`
- 统一使用当前选中的模型（不再硬编码 qwen3.5:4b）
- 默认模型改为 qwen3.5:9b

---

### 修改的文件

- `history_rag.py`: 添加 MAX_BLOCK_LENGTH=2000，分批构建索引
- `agent.py`: num_predict=8000，统一使用选中模型
- `routes.py`: 默认模型改为 qwen3.5:9b
- `templates/index.html`: 默认选项改为 qwen3.5:9b

### 修复时间
2026-03-08

---

## 问题 2 补充：System Prompt 优化

### 问题描述
LLM 生成回答时，会把 system prompt 中的指令描述也当作需要处理的内容，导致输出包含不必要的解释性内容。

### 修复方案

1. **agent.py - 文档问答**：优化 system prompt，明确要求 LLM 直接输出答案

2. **agent.py - 普通问答**：增加具体指导

3. **utils.py - 对话摘要**：优化摘要生成 prompt

### 修改内容

- `agent.py`: 更新文档问答和普通问答的 system prompt
- `utils.py`: 更新对话摘要生成的 prompt

### 修复时间
2026-03-08

---

## 问题 2：文档摘要质量差 + 渐进式加载

### 问题描述
1. 上传文档后自动摘要质量很差，显示的是原始文档块而非 LLM 生成的摘要
2. 中断后手动提问"总结文档"，同样返回原始文档块
3. 返回块数太少（默认10块约5000字），无法覆盖长文档

### 问题分析

#### 问题 1 根因
- `stream_graph()` 中对文档工具有特殊处理，直接输出原始文档内容
- 工具结果没有让 LLM 再处理生成摘要

#### 问题 2 根因
- 工具默认只返回 10 个块
- 没有根据问题类型调整返回内容粒度

### 修复方案

#### 方案 A：修复 Tool Calling 流程
1. 移除 `stream_graph()` 中对文档工具的特殊处理
2. 让 `node_generate()` 正确将文档内容作为上下文，让 LLM 生成回答

#### 方案 C：实现渐进式加载
1. 在 `graph.py` 中定义披露层级配置
```python
DISCLOSURE_LEVELS = {
    "summary": {"n_chunks": 30, "description": "摘要"},
    "relevant": {"k": 8, "description": "相关片段"},
    "full": {"n_chunks": 100, "description": "完整内容"}
}
```

2. 添加披露层级判断函数
```python
def decide_disclosure_level(query: str) -> str:
    # 根据问题关键词判断需要什么粒度的内容
    if "总结" in query or "概括" in query:
        return "summary"
    elif "详细" in query or "完整" in query:
        return "full"
    else:
        return "relevant"
```

3. 修改 `node_detect_tool` 根据披露层级调用工具
4. 修改 `node_retrieve_document` 根据披露层级调整检索数量

### 修改的文件

- `graph.py`: 添加 `disclosure_level` 字段和 `DISCLOSURE_LEVELS`、`decide_disclosure_level`
- `agent.py`: 
  - 移除 `stream_graph` 中文档工具的特殊处理
  - `node_detect_tool` 根据披露层级设置工具参数
  - `node_retrieve_document` 根据披露层级调整 k 值

### 修复后效果

| 问题类型 | 触发关键词 | 返回内容 |
|---------|-----------|---------|
| 总结/概括 | "总结"、"abstract" | 30 个块摘要，让 LLM 生成总结 |
| 一般问答 | 默认 | 8 个相关片段 |
| 详细/完整 | "详细"、"完整" | 100 个块 |

### 修复时间
2026-03-08

---

## 问题 3：循环依赖风险

### 问题描述
`from models import state` 在多个文件中重复导入（app.py, routes.py, utils.py, agent.py, resources.py），形成循环依赖风险，可能导致初始化顺序问题。

### 问题分析

**涉及的文件**：
- `app.py` - `from models import state`
- `routes.py` - `from models import state`
- `utils.py` - `from models import state`
- `agent.py` - `from models import state` (多处)
- `resources.py` - `from models import state` (在函数内部导入)

**风险点**：
- 初始化顺序不确定，可能导致 state 未初始化就被访问
- 单元测试困难，无法单独测试某个模块
- 维护困难，牵一发而动全身

### 修复方案

采用**方案 A：依赖注入**，创建 `extensions.py` 统一管理 state 访问。

#### 新建 extensions.py
```python
from models import AppState

_state = None


def init_state():
    global _state
    _state = AppState()
    return _state


def get_state():
    global _state
    if _state is None:
        _state = AppState()
    return _state


state = get_state()
```

#### 修改各文件导入
将 `from models import state` 改为 `from extensions import state`

**修改的文件**：
- `app.py`
- `routes.py`
- `utils.py`
- `agent.py` (4处)
- `resources.py` (2处)

### 修复后状态
- ✅ 所有模块统一从 extensions.py 获取 state
- ✅ 解耦 models.py 和其他模块的直接依赖
- ✅ 支持延迟初始化，get_state() 首次调用时才创建实例
- ✅ 不绑定框架，纯 Python 实现

### 修复时间
2026-03-08
