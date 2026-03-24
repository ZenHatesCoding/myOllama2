# myOllama2 Skill 支持 PRD

## 1. 背景与目标

### 1.1 现状
myOllama2 是一个基于 Flask + LangGraph 的智能对话助手，支持：
- 多模型（Ollama / OpenAI / Anthropic 兼容 API）
- 文档问答（RAG）
- 新闻获取（MCP 工具）
- 截图识别、语音交互

现有工具系统基于 LangChain `@tool` 装饰器，工具需要手动注册，能力局限于"读取/处理"而非"执行/写"。

### 1.2 目标
让 myOllama2 支持**标准格式的 Skill**（参考 Claude Code / OpenCode 规范），实现：
- Skill 目录放置后**自动注册**，无需修改代码
- Skill 通过**渐进式披露**机制注入上下文
- 复用现有的 **LangGraph 工作流**和**前端界面**
- 支持**读写文件、执行脚本**等操作（通过内置工具）

### 1.3 核心设计理念

**Skill 的本质是"教 AI 怎么做事的说明书"，不是可执行代码，也不是工具调用手册。**

Claude Code 的设计哲学：
1. **内置工具（Read/Write/Bash 等）是模型天生就知道的** - 就像人类程序员知道"写文件用文本编辑器"一样
2. **SKILL.md 是工作流指南** - 告诉 AI 在什么场景下做什么事、怎么做，而不是告诉 AI 用什么工具
3. **模型自主决定工具调用** - AI 根据 SKILL.md 的指引和可用工具的 schema，自己判断何时调用什么工具

| 层级 | Claude Code 设计 | myOllama2 实现 |
|------|------------------|----------------|
| **知识层** | SKILL.md - 工作流指南 | 保持一致 |
| **工具层** | Read/Edit/Bash 等内置工具（始终可用） | 内置工具始终对模型可用 |
| **连接层** | LangGraph | 复用 |

### 1.4 与旧设计的核心区别

| 维度 | 旧设计 | 新设计 |
|------|--------|--------|
| 工具来源 | Skill 专属工具，需在 SKILL.md 中声明 | 内置工具始终可用 |
| SKILL.md 内容 | 包含"内置工具表"和使用指引 | 纯工作流指南，不提及具体工具 |
| 工具调用 | 显式映射（"使用 Write 工具创建文件"） | 模型自主决定 |
| 编写方式 | "调用 XX 工具执行 XX" | "创建 XX 文件，内容是..." |

---

## 2. Skill 格式规范

### 2.1 目录结构

```
skill-name/                    # 目录名必须与 SKILL.md 中的 name 一致
├── SKILL.md                   # 必须：核心文件
├── scripts/                   # 可选：可执行脚本
│   ├── process.py
│   └── validate.sh
├── references/                # 可选：参考文档（按需加载）
│   ├── api-guide.md
│   └── examples/
└── assets/                    # 可选：模板等资源
    └── template.md
```

### 2.2 SKILL.md 格式

采用 **Markdown + YAML Frontmatter** 标准格式。

**关键原则**：SKILL.md 只描述工作流，不提及具体工具名称。工具调用由模型根据上下文自主决定。

```yaml
---
name: pdf-to-org
description: 将 PDF 论文转换为 Org 格式进行分析。当你需要分析论文、整理研究笔记或生成阅读报告时使用。
---

# PDF to Org 转换

## 何时使用
当你需要将 PDF 论文转换为 Org 格式进行阅读和分析时，使用这个 Skill。

## 工作流程

### 步骤 1：读取 PDF 文件
找到并读取你要分析的 PDF 文件。如果文件是扫描件或无法直接读取，先用 OCR 或其他方式转换为文本。

### 步骤 2：规划 Org 文档结构
根据论文内容，规划 Org 文档结构：
- 一级标题：论文标题
- 二级标题：作者信息、摘要、关键发现、方法论、结论
- 可以添加个人笔记和思考

### 步骤 3：生成 Org 文件
按照以下格式生成 Org 文件：
- 使用 `*` 表示标题层级，`**` 表示二级标题
- 代码块使用 `#BEGIN_SRC` ... `#END_SRC`
- 重要结论用 `**粗体**` 标记

## 格式规范
- Org 模式使用 `*` 表示标题层级
- 使用 `**` 表示二级标题，以此类推
- 可以添加 `:PROPERTIES:` 进行元数据管理
```

### 2.3 Frontmatter 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | Skill 名称，kebab-case，与目录名一致 |
| `description` | 是 | 功能描述 + 触发条件（影响 AI 何时加载），不超过 1024 字符 |

**注意**：不再需要 `tools` 字段声明可用工具，因为内置工具始终对模型可用。

### 2.4 渐进式披露机制

三级加载，减少 token 消耗：

| 级别 | 内容 | 加载时机 |
|------|------|---------|
| **第一级** | frontmatter 的 name + description | 始终加载（~50-100 tokens） |
| **第二级** | SKILL.md 正文（工作流指南） | 触发后加载（~1000-5000 tokens） |
| **第三级** | references/、scripts/ | 按需加载（AI 自行决定） |

---

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Flask Web Server                          │
│                      (routes.py / app.py)                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Skill Registry                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  skills/ 目录扫描 → SKILL.md 解析 → 自动注册             │ │
│  │  ┌────────────────────────────────────────────────────────┐│ │
│  │  │ Skill(name, description, content)                    ││ │
│  │  └────────────────────────────────────────────────────────┘│ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LangGraph Agent                             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    内置工具集（始终可用）                  │  │
│  │  ┌────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐       │  │
│  │  │ Read   │  │  Write  │  │  Bash   │  │  Glob  │ ...   │  │
│  │  └────────┘  └─────────┘  └─────────┘  └────────┘       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     模式路由                               │  │
│  │               根据 mode 决定后续流程                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                    /                    \                      │
│           ┌───────┴───────┐      ┌───────┴───────┐            │
│           │   QA 模式      │      │  Agent 模式    │            │
│           │               │      │               │            │
│           │ classify_intent│      │  match_skill   │            │
│           │       ↓        │      │       ↓        │            │
│           │generate_response│     │activate_skill  │            │
│           │  (无工具绑定)  │      │       ↓        │            │
│           │               │      │generate_response│            │
│           │               │      │(绑定内置工具)   │            │
│           └───────────────┘      └───────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心设计原则

1. **内置工具始终可用**
   - Read、Write、Bash、Glob、Grep 等内置工具对模型始终可用
   - 不需要在 SKILL.md 中声明
   - 模型根据工具的 schema（名称、参数、描述）自主决定调用

2. **SKILL.md 是工作流指南，不是工具手册**
   - 描述"做什么"和"怎么做"（工作流）
   - 不描述"用什么工具"
   - 模型自行根据上下文和可用工具决定

3. **Skill 触发后注入工作流上下文**
   - SKILL.md 内容作为 system prompt 的一部分
   - 模型结合工作流指南和内置工具，自主生成工具调用序列

### 3.3 组件职责

| 组件 | 职责 |
|------|------|
| **SkillRegistry** | 扫描 skills/ 目录、解析 SKILL.md、注册/管理 Skill |
| **Skill** | 封装单个 Skill 的元数据和工作流内容 |
| **内置工具集** | Read/Write/Bash/Glob/Grep 等，始终对模型可用 |
| **LangGraph 节点（QA）** | `classify_intent → generate_response` |
| **LangGraph 节点（Agent）** | `match_skill → activate_skill → generate_response` |

### 3.4 两种模式的 generate_response 区别

| 维度 | QA 模式 | Agent 模式 |
|------|---------|-----------|
| **工具绑定** | 不绑定工具 | 绑定内置工具 |
| **Skill 上下文** | 不注入 | 有则注入 |
| **工具调用循环** | 无 | 支持（模型自主调用工具） |
| **适用场景** | 文档问答、新闻获取、闲聊 | Skill 调试、文件操作 |

---

## 4. 功能需求

### 4.1 Skill 自动发现与注册

**描述**：系统启动或收到 reload 请求时，扫描 skills/ 目录，自动发现并注册所有有效 Skill。

**流程**：
1. 检查 skills/ 目录是否存在，不存在则创建
2. 遍历所有子目录
3. 检查是否存在 SKILL.md 文件
4. 解析 SKILL.md，提取 name 和 description
5. 注册到 SkillRegistry

**验收标准**：
- [ ] 启动时自动加载 skills/ 目录下的所有有效 Skill
- [ ] 支持手动触发重新扫描（API + 前端按钮）
- [ ] 无效目录（缺少 SKILL.md）不报错，静默跳过

### 4.2 Skill 触发检测

**描述**：用户输入时，LangGraph 判断是否需要触发某个 Skill。

**流程**：
1. 获取所有已注册 Skill 的 name + description
2. 构建触发检测 prompt
3. LLM 判断是否触发 Skill，返回 Skill 名称或 "none"
4. 如果触发，加载对应 Skill 的 SKILL.md 完整内容到上下文

**验收标准**：
- [ ] 仅当用户请求与 Skill description 匹配时才触发
- [ ] 触发后，将 SKILL.md 完整内容（工作流指南）注入到 context
- [ ] 支持多 Skill 场景（如需要多个 Skill 协同）

### 4.3 内置工具（始终可用）

**描述**：内置工具对模型始终可用，不受 Skill 影响。

| 工具名 | 功能 | 说明 |
|--------|------|------|
| `Read` | 读取文件 | 支持任意文本文件 |
| `Write` | 写入文件 | 支持创建/覆盖文件 |
| `Bash` | 执行脚本 | 支持 python/bash/node |
| `Glob` | 文件搜索 | 按模式匹配文件 |
| `Grep` | 内容搜索 | 在文件中搜索文本 |

**特点**：
- SKILL.md 中不需要（也不应该）声明可用工具
- 模型根据工具的 schema 自主决定调用
- 安全限制仍然生效（路径隔离、超时控制）

**SKILL.md 编写原则**：
- ✅ "创建 report.md 文件"
- ✅ "运行 convert.py 脚本"
- ✅ "查找所有 .py 文件"
- ❌ "使用 Write 工具创建文件"
- ❌ "调用 Bash 执行 scripts/convert.py"

### 4.4 references/ 和 scripts/ 按需加载

**描述**：Skill 的 references/ 和 scripts/ 目录内容按需加载。

**流程**：
1. AI 在执行过程中决定需要某个参考文件
2. AI 使用 Read 工具读取文件（如 `skills/pdf-to-org/scripts/convert.py`）
3. AI 使用 Bash 工具执行脚本（如 `python skills/pdf-to-org/scripts/convert.py ...`）

**验收标准**：
- [ ] AI 可以主动使用 Read 工具读取 references/ 目录文件
- [ ] AI 可以主动使用 Bash 工具执行 scripts/ 目录脚本
- [ ] 不需要显式声明，模型自行决定

### 4.5 Skill 执行结果处理

**描述**：Skill 执行后的结果如何传递给后续流程。

**流程**：
1. SKILL.md 工作流指导 AI 执行一系列工具调用
2. AI 根据工具调用结果生成最终回答
3. 结果存入 conversation history

---

## 5. API 设计

### 5.1 Skill 管理 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/skills` | GET | 获取所有已注册 Skill 列表 |
| `/api/skills/reload` | POST | 重新扫描并注册所有 Skill |

### 5.2 Skill 数据结构

```json
{
  "name": "pdf-to-org",
  "description": "将 PDF 论文转换为 Org 格式进行分析...",
  "has_scripts": true,
  "has_references": true
}
```

---

## 6. 前端改造

### 6.1 Skill 配置区域

在设置面板增加 Skill 管理区域：

| 元素 | 说明 |
|------|------|
| Skill 列表 | 显示已注册的 Skill 名称和描述 |
| 重新加载按钮 | 触发 /api/skills/reload |
| 提示信息 | 说明如何安装新 Skill |

### 6.2 Skill 使用

用户无感知，Skill 在对话中自动生效。内置工具对所有对话始终可用。

---

## 7. 改造文件清单

| 文件 | 类型 | 改动说明 |
|------|------|---------|
| `skill_registry.py` | 改造 | 简化元数据解析（去掉 tools 字段） |
| `skill_tools.py` | 重命名 | 重命名为 `builtin_tools.py`，作为通用内置工具 |
| `agent.py` | 改造 | 根据 mode 决定流程：QA 模式不绑定工具，Agent 模式绑定内置工具 |
| `graph.py` | 改造 | GraphState 新增 `mode` 字段；`create_initial_state` 支持 mode 参数 |
| `routes.py` | 改造 | Skill 管理 API；`run_graph`/`stream_graph` 支持 mode 参数 |
| `app.py` | 改造 | 启动时初始化 Skill 注册 |
| `templates/index.html` | 改造 | 添加 QA/Agent 模式切换 UI |
| `static/js/app.js` | 改造 | 模式切换交互、Skill 列表加载 |

---

## 8. 安全机制

| 机制 | 实现 |
|------|------|
| **路径隔离** | 所有文件操作限制在项目目录（skills/、workspace/、conversations/） |
| **超时控制** | Bash 执行默认 60s 超时 |
| **输入验证** | Skill description 不允许 XML 标签（防注入） |

---

## 9. 非功能性需求

### 9.1 性能
- Skill 扫描应在 1 秒内完成（≤100 个 Skill）
- 触发检测延迟 < 500ms

### 9.2 兼容性
- 现有对话功能不受影响
- 现有 MCP 工具继续正常工作

### 9.3 可扩展性
- 支持未来新增 Skill 类型
- 支持 Skill 间的依赖声明

---

## 10. 示例 Skill

### 10.1 PDF to Org Skill

目录结构：
```
pdf-to-org/
├── SKILL.md
├── scripts/
│   └── convert.py
└── assets/
    └── default-template.org
```

SKILL.md 内容：
```yaml
---
name: pdf-to-org
description: 将 PDF 论文转换为 Org 格式进行分析。当你需要分析论文、整理研究笔记、生成阅读报告时使用。
---

# PDF to Org 转换

## 何时使用
当用户要求将 PDF 论文转换为 Org 格式、进行分析、整理研究笔记或生成阅读报告时，使用这个 Skill。

## 工作流程

### 步骤 1：读取 PDF 文件
找到并读取用户指定的 PDF 文件。如果文件是扫描件或无法直接读取，先用 OCR 或其他方式转换为文本。

### 步骤 2：规划 Org 文档结构
根据论文内容，规划 Org 文档结构：
- 一级标题：论文标题
- 二级标题：作者信息、摘要、关键发现、方法论、结论
- 三级标题：具体章节内容
- 添加"个人笔记"章节记录你的思考

### 步骤 3：生成 Org 文件
创建 .org 文件，包含：
- 标题层级使用 `*`（一级）、`**`（二级）、`***`（三级）
- 重要结论用 `**粗体**` 标记
- 代码块使用 `#BEGIN_SRC` ... `#END_SRC`
- 表格使用 Org 格式

## 格式规范
- Org 模式使用 `*` 表示标题层级
- 使用 `**` 表示二级标题，以此类推
- 可以添加 `:PROPERTIES:` 进行元数据管理
- 论文标题作为一级标题
- 每个主要章节作为二级标题
```

### 10.2 Code Review Skill

目录结构：
```
code-review/
├── SKILL.md
└── references/
    └── coding-standards.md
```

SKILL.md 内容：
```yaml
---
name: code-review
description: 对代码进行评审，提供改进建议。适用于代码审查、bug 修复建议、性能优化等场景。
---

# Code Review

## 何时使用
当用户要求审查代码、查找 bug、提出改进建议或进行代码质量评估时，使用这个 Skill。

## 工作流程

### 步骤 1：定位代码文件
如果用户指定了文件，直接使用。如果用户只说"审查代码"，先搜索项目中的代码文件。

### 步骤 2：阅读代码
仔细阅读代码，理解其逻辑、功能和结构。

### 步骤 3：分析问题
从以下维度分析代码：
1. **正确性**：代码是否按预期工作？是否有逻辑错误？
2. **安全性**：是否有潜在的安全风险（如注入、越权）？
3. **性能**：是否有性能瓶颈或资源浪费？
4. **可读性**：代码是否易于理解和维护？
5. **最佳实践**：是否符合该语言的编码规范？

### 步骤 4：生成评审报告
创建评审报告，包含：
- 代码位置和概述
- 发现的问题（按严重程度分类）
- 改进建议
- 总体评价

## 输出格式
评审报告应该结构清晰，包含：
- 总评（优秀/良好/需要改进）
- 问题列表（高危、中危、低危）
- 具体改进建议
```

---

## 11. SKILL.md 编写指南

### 11.1 推荐写法

**工作流导向**：
```markdown
## 工作流程

### 步骤 1：读取配置文件
找到并读取项目中的配置文件。

### 步骤 2：分析配置
检查配置是否合理，是否符合最佳实践。

### 步骤 3：生成报告
创建配置审计报告，包含发现的问题和建议。
```

**自然语言描述**：
```markdown
当需要进行代码重构时：
1. 先理解现有代码的结构和依赖
2. 制定重构计划，确保小步前进
3. 每完成一个小步骤，运行测试验证
4. 重构完成后审查代码
```

### 11.2 不推荐写法

**显式工具调用**（不推荐）：
```markdown
### 步骤 1：使用 Read 工具读取文件
调用 Read(path="config.json")

### 步骤 2：使用 Write 工具创建报告
调用 Write(path="report.md", content="...")
```

**工具声明**（不需要）：
```markdown
## 可用工具
- Read：读取文件
- Write：写入文件
- Bash：执行命令

以上工具均可使用，不需要在 Skill 中声明。
```

### 11.3 为什么这样设计

1. **模型知道工具是什么**
   - 内置工具的 schema（名称、参数、描述）对模型始终可见
   - 模型不需要 SKILL.md 告诉它"用 Write 创建文件"

2. **SKILL.md 专注于工作流**
   - 什么场景做什么事
   - 做事的一般步骤
   - 输出格式和质量标准

3. **更自然的交互**
   - 用户说"帮我把这个 PDF 转成 Org"
   - AI 看到 Skill 的工作流指引
   - AI 自主决定用 Read 读 PDF，用 Write 创建 org 文件

---

## 12. QA 模式与 Agent 模式

### 12.1 设计背景

系统中存在两种不同的使用场景：

| 场景 | 特点 | 典型需求 |
|------|------|---------|
| **问答（QA）** | 快速回答、文档理解、新闻获取 | 不需要读写文件、执行脚本 |
| **智能体（Agent）** | 复杂任务执行、Skill 驱动 | 需要读写文件、执行脚本、调用工具 |

为了保持架构简洁，将两种场景拆分为**独立模式**，互不干扰。

### 12.2 两种模式对比

| 维度 | QA 模式 | Agent 模式 |
|------|---------|-----------|
| **流程** | `classify_intent → generate_response` | `match_skill → activate_skill → generate_response` |
| **工具绑定** | 新闻/文档 MCP 工具 | 内置工具（Read/Write/Bash/Glob/Grep） |
| **Skill 注入** | ❌ 不注入 | ✅ 有则注入 |
| **适用场景** | 文档问答、新闻查询、闲聊 | Skill 调试、文件操作、脚本执行 |

### 12.3 实现架构：两个独立 Graph

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

**核心函数**：
- `build_qa_graph()`：构建 QA 模式专用 Graph
- `build_agent_graph()`：构建 Agent 模式专用 Graph
- `stream_graph()`：根据 mode 动态选择 Graph

### 12.4 QA 模式流程

```
用户输入 → classify_intent（判断是否需要新闻/文档工具）→ generate_response（无工具绑定）
```

- **classify_intent**：判断用户是否需要新闻 MCP 或文档 RAG
- **retrieve_docs/retrieve_history**：RAG 检索
- **generate_response**：普通 LLM 调用，不绑定任何工具
- **适用场景**：原有文档问答、图片问答、新闻获取等

### 12.5 Agent 模式流程

```
用户输入 → match_skill（检测是否触发 Skill）→ activate_skill（注入工作流）→ generate_response（绑定内置工具）
```

- **match_skill**：判断用户意图是否匹配某个 Skill
- **activate_skill**：将 SKILL.md 内容注入上下文
- **generate_response**：绑定 Read/Write/Bash/Glob/Grep 工具，模型自主决定工具调用
- **适用场景**：Skill 调试、文件操作、脚本执行

> **⚠️ 模型要求**：Agent 模式依赖模型的 **Tool Calling（工具调用）** 能力。模型需要在训练阶段具备工具调用能力，并返回标准化的结构化数据（包含 `type: "tool_use"` 等字段）。
>
> - **支持的模型**：OpenAI GPT-4/3.5、Anthropic Claude、MiniMax 等具备 Tool Calling 能力的模型
> - **不支持的模型**：部分本地部署的模型（如某些 Ollama 模型）可能不具备工具调用能力，使用这些模型时 Agent 模式将无法正常工作
>
> 如遇 Agent 模式问题，请确认当前 provider 使用的模型是否支持 Tool Calling。

### 12.6 Agent 模式下的工具调用

Agent 模式下，LLM 绑定内置工具后，模型自主决定何时调用工具：

```
模型生成文本/工具调用 → 执行工具 → 结果反馈 → 模型继续生成 → ... → 最终回答
```

**示例**：
用户："用 code-review skill 审查这个项目的代码"
1. match_skill 检测到 code-review Skill
2. activate_skill 注入 SKILL.md 工作流
3. generate_response 绑定内置工具，模型自主决定：
   - 用 Glob 搜索代码文件
   - 用 Read 读取代码
   - 用 Write 创建评审报告

### 12.7 前端交互

前端添加模式切换 UI：

| 元素 | 说明 |
|------|------|
| 模式切换 | QA / Agent 两个选项 |
| 模式指示 | 当前所在模式的可视化提示 |

默认使用 **QA 模式**，保持原有体验。切换到 **Agent 模式**后，进入 Skill 调试模式。

---

## 13. 后续规划

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | Skill 自动发现与注册 | 核心功能 |
| P0 | 内置工具（始终可用） | Read/Write/Bash |
| P0 | Skill 触发检测 | 集成到 LangGraph |
| P0 | QA/Agent 模式分离 | 架构解耦 |
| P1 | references/ 按需加载 | AI 主动读取参考文档 |
| P1 | Skill 搜索与过滤 | 前端体验优化 |
| P2 | Skill 依赖管理 | 支持 Skill 间引用 |
| P2 | Skill 市场 | 分享与安装社区 Skill |

---

## 13. 术语表

| 术语 | 说明 |
|------|------|
| Skill | 一组工作流指南（SKILL.md），教 AI 如何处理特定任务 |
| Frontmatter | SKILL.md 开头的 YAML 元数据 |
| 渐进式披露 | 三级加载机制，控制 token 消耗 |
| 内置工具 | 系统提供的基础能力（Read/Write/Bash 等），始终对模型可用 |
| Trigger | 触发条件，决定何时加载某个 Skill |
| 工作流指南 | SKILL.md 的核心内容，指导 AI 如何完成特定任务 |
