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
