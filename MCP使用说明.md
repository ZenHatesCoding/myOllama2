# 新闻获取MCP功能使用说明

## 功能概述

在myOllama2项目中集成了基于聚合数据API的新闻获取MCP功能，支持智能识别用户意图并自动调用新闻工具。

## 核心功能

1. **获取头条新闻**: 获取最新头条新闻
2. **按类型获取新闻**: 支持社会、国内、国际、娱乐、体育、科技、财经等分类
3. **搜索新闻**: 根据关键词搜索相关新闻
4. **智能意图识别**: 自动判断用户是否需要调用新闻工具
5. **演示数据模式**: 无需API密钥即可测试功能

## 文件结构

```
myOllama2/
├── mcp/
│   ├── __init__.py       # MCP模块初始化
│   ├── base.py          # MCP基类和工具schema定义
│   ├── manager.py       # MCP管理器，负责意图识别和工具调用
│   └── news_mcp.py     # 新闻MCP实现（基于聚合数据）
├── test_mcp.py         # 测试脚本
├── utils.py            # 已集成MCP功能
├── routes.py           # 已支持异步调用
└── requirements.txt     # 已添加httpx和pydantic依赖
```

## 使用方法

### 方法1: 通过Web界面使用

1. 启动应用：
```bash
cd myOllama2
python app.py
```

2. 打开浏览器访问 http://localhost:5000

3. 在输入框中输入以下示例：
   - "获取头条新闻"
   - "获取今天的科技新闻"
   - "搜索关于人工智能的新闻"
   - "获取最新的体育新闻"
   - "获取财经新闻"

### 方法2: 通过测试脚本使用

```bash
cd myOllama2
python test_mcp.py
```

## 配置真实API密钥

### 申请聚合数据API密钥

1. 访问 https://www.juhe.cn/
2. 注册账号
3. 进入个人中心 → 数据中心
4. 申请"新闻头条"API
5. 获取API Key

### 配置API密钥

在 `utils.py` 中修改：

```python
# 原来的代码（使用演示数据）
mcp_manager = MCPManager()
mcp_manager.register_mcp(NewsMCP())

# 修改为（使用真实API）
mcp_manager = MCPManager()
mcp_manager.register_mcp(NewsMCP(api_key="your_juhe_api_key_here"))
```

## 支持的新闻类型

- `top` - 头条
- `shehui` - 社会
- `guonei` - 国内
- `guoji` - 国际
- `yule` - 娱乐
- `tiyu` - 体育
- `keji` - 科技
- `caijing` - 财经

## 工作原理

1. 用户输入问题
2. MCPManager使用LLM进行意图识别
3. 判断是否需要调用新闻工具
4. 如果需要，自动调用对应的新闻工具
5. 获取新闻数据并格式化
6. 返回给用户

## 演示数据模式

如果没有配置API密钥，系统会自动使用演示数据模式，返回模拟的新闻数据。

优点：
- 无需API密钥即可测试
- 验证MCP功能是否正常
- 检查意图识别是否准确

注意：
- 演示数据是固定的，不会实时更新
- 要获取真实新闻，请配置API密钥

## 缓存机制

新闻数据默认缓存10分钟，避免频繁请求API。

可以调整缓存时间：

```python
from datetime import timedelta

news_mcp = NewsMCP(api_key="your_key")
news_mcp.cache_duration = timedelta(minutes=30)  # 30分钟缓存
```

## 常见问题

### Q: 为什么返回演示数据？

A: 没有配置API密钥时，系统会自动使用演示数据。请按照上述步骤申请API密钥并配置。

### Q: API请求失败怎么办？

A: 
1. 检查API密钥是否正确
2. 检查是否超出免费额度（聚合数据每天100次）
3. 检查网络连接
4. 查看错误日志

### Q: 意图识别不准确怎么办？

A: 可以调整MCPManager中的system_prompt，或者使用更强大的模型进行意图识别。

### Q: 如何添加更多MCP工具？

A: 
1. 继承BaseMCP类
2. 实现get_tools和execute_tool方法
3. 在MCPManager中注册

## 技术栈

- **HTTP客户端**: httpx（异步，性能好）
- **数据验证**: pydantic
- **新闻API**: 聚合数据 (juhe.cn)
- **意图识别**: LangChain + Ollama

## 下一步

1. 申请聚合数据API密钥
2. 配置到项目中
3. 测试真实新闻数据
4. 扩展更多MCP工具（天气、股票、翻译等）

## 许可证

MIT License
