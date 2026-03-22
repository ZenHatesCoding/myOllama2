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

Skill 的本质是**教 AI 怎么做事的说明书**，不是可执行代码：

| 层级 | 职责 | Claude Code | myOllama2 |
|------|------|-------------|-----------|
| **知识层** | 何时用、怎么用 | SKILL.md | 新增 |
| **工具层** | 实际执行操作 | Read/Edit/Bash 等内置工具 | 扩展现有 tools.py |
| **连接层** | 工具编排 | LangGraph | 复用 |

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

采用 **Markdown + YAML Frontmatter** 标准格式：

```yaml
---
name: pdf-to-org
description: 将 PDF 论文转换为 Org 格式进行分析。当你需要分析论文、整理研究笔记或生成阅读报告时使用。支持指定模板和输出格式。
---

# PDF to Org 转换

## 使用方法

### 步骤 1：读取 PDF
使用 Read 工具读取 PDF 文件内容...

### 步骤 2：执行转换脚本

调用 scripts/convert.py 进行转换：

bash
python3 scripts/convert.py --input {pdf_path} --output {output_path} --template {template}
```

### 2.3 Frontmatter 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | Skill 名称，kebab-case，与目录名一致 |
| `description` | 是 | 功能描述 + 触发条件（影响 AI 何时加载），不超过 1024 字符 |
| `license` | 否 | 许可证类型 |
| `compatibility` | 否 | 环境要求说明 |
| `metadata` | 否 | 自定义元数据（author, version 等） |

### 2.4 渐进式披露机制

三级加载，减少 token 消耗：

| 级别 | 内容 | 加载时机 |
|------|------|---------|
| **第一级** | frontmatter 的 name + description | 始终加载（~50-100 tokens） |
| **第二级** | SKILL.md 正文 | 触发后加载（~1000-5000 tokens） |
| **第三级** | references/、scripts/ | 按需加载 |

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
│  │  │ Skill(name, description, content, references)       ││ │
│  │  └────────────────────────────────────────────────────────┘│ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LangGraph Agent                             │
│                                                                  │
│  ┌───────────────┐   ┌─────────────────┐   ┌───────────────┐   │
│  │ detect_intent │──▶│ skill_execute   │──▶│   generate   │   │
│  │ (判断是否触发) │   │ (加载 Skill 内容) │   │ (带 Skill 上下文) │ │
│  └───────────────┘   └─────────────────┘   └───────────────┘   │
│                              │                                   │
│                  ┌───────────┼───────────┐                     │
│                  ▼           ▼           ▼                     │
│             ┌────────┐  ┌─────────┐  ┌─────────┐              │
│             │ Read   │  │  Bash   │  │ Write   │              │
│             │ File   │  │ Script  │  │ File    │              │
│             └────────┘  └─────────┘  └─────────┘              │
│                 ↑                                               │
│           内置工具（扩展自 tools.py）                            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 组件职责

| 组件 | 职责 |
|------|------|
| **SkillRegistry** | 扫描 skills/ 目录、解析 SKILL.md、注册/管理 Skill |
| **Skill** | 封装单个 Skill 的元数据和内容 |
| **内置工具集** | 扩展 tools.py，提供 Read/Write/Bash/Glob 等标准工具 |
| **LangGraph 节点** | detect_intent → skill_execute → generate |

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
4. 如果触发，加载对应 Skill 的完整内容到上下文

**验收标准**：
- [ ] 仅当用户请求与 Skill description 匹配时才触发
- [ ] 触发后，将 SKILL.md 完整内容注入到 system prompt
- [ ] 支持多 Skill 并发（如果多个 Skill 都相关）

### 4.3 Skill 内容按需加载

**描述**：Skill 的 references/ 和 scripts/ 目录内容按需加载，不立即注入上下文。

**流程**：
1. AI 在执行过程中决定需要参考某个文件
2. 读取对应文件内容
3. 将内容注入到当前上下文

**验收标准**：
- [ ] references/ 目录文件可被 AI 主动读取
- [ ] scripts/ 目录脚本可被 Bash 工具执行

### 4.4 内置工具扩展

**描述**：扩展现有的 tools.py，提供 Claude Code 风格的内置工具。

**新增工具**：

| 工具名 | 功能 | 说明 |
|--------|------|------|
| `Read` | 读取文件 | 支持任意文本文件 |
| `Write` | 写入文件 | 支持创建/覆盖文件 |
| `Bash` | 执行脚本 | 支持 python/bash/node |
| `Glob` | 文件搜索 | 按模式匹配文件 |
| `Grep` | 内容搜索 | 在文件中搜索文本 |

**安全限制**：
- 所有文件操作限制在项目目录内
- Bash 执行有超时限制
- 禁止访问系统敏感目录

### 4.5 Skill 执行结果处理

**描述**：Skill 执行后的结果如何传递给后续流程。

**流程**：
1. Skill 指令指导 AI 执行一系列内置工具调用
2. AI 根据结果生成最终回答
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
  "description": "将 PDF 论文转换为 Org 格式...",
  "category": "文档处理",
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

用户无感知，Skill 在对话中自动生效。

---

## 7. 改造文件清单

| 文件 | 类型 | 改动说明 |
|------|------|---------|
| `skill_registry.py` | **新增** | Skill 注册中心 |
| `tools.py` | **改造** | 扩展内置工具（Read/Write/Bash/Glob/Grep） |
| `agent.py` | **改造** | Skill 触发检测、上下文注入 |
| `graph.py` | **改造** | GraphState 增加 skill 相关字段 |
| `models.py` | **改造** | AppState 增加 skill_registry |
| `routes.py` | **改造** | Skill 管理 API |
| `app.py` | **改造** | 启动时初始化 Skill 注册 |
| `templates/index.html` | **改造** | Skill 配置 UI |
| `static/js/app.js` | **改造** | Skill 列表加载、reload 功能 |

---

## 8. 安全机制

| 机制 | 实现 |
|------|------|
| **路径隔离** | 所有文件操作限制在项目目录（skills/、workspace/、conversations/） |
| **超时控制** | Bash 执行默认 60s 超时 |
| **输入验证** | Skill description 不允许 XML 标签（防注入） |
| **只读偏好** | references/ 可读，scripts/ 执行需明确授权 |

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
description: 将 PDF 论文转换为 Org 格式。当你需要分析论文、整理研究笔记、生成阅读报告或转换为 Emacs Org 模式时使用。支持指定模板。
---

# PDF to Org 转换

## 使用方法

### 步骤 1：读取 PDF
使用 Read 工具读取 PDF 文件内容。

### 步骤 2：提取内容
调用 convert.py 进行转换：

bash
python3 scripts/convert.py --input {pdf_path} --output {output_path}

### 步骤 3：验证输出
检查生成的 .org 文件内容是否完整。

## 模板

支持的模板：
- `default`：标准论文格式
- `research`：研究笔记格式
- `reading-log`：阅读日志格式

## 注意事项

- PDF 路径必须是绝对路径
- 输出目录必须存在
- 转换可能需要几秒钟，请耐心等待
```

convert.py 示例：
```python
#!/usr/bin/env python3
import sys
import argparse

def main(params, workspace):
    args = argparse.Namespace(
        input=params.get('pdf_path'),
        output=params.get('output_path', 'output.org'),
        template=params.get('template', 'default')
    )
    # PDF 读取和转换逻辑
    # ...
    return f"转换完成: {args.output}"

if __name__ == '__main__':
    print(main({}, None))
```

---

## 11. 后续规划

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | Skill 自动发现与注册 | 核心功能 |
| P0 | 内置工具扩展 | Read/Write/Bash |
| P0 | Skill 触发检测 | 集成到 LangGraph |
| P1 | references/ 按需加载 | 增强 Skill 能力 |
| P1 | Skill 搜索与过滤 | 前端体验优化 |
| P2 | Skill 依赖管理 | 支持 Skill 间引用 |
| P2 | Skill 市场 | 分享与安装社区 Skill |

---

## 12. 术语表

| 术语 | 说明 |
|------|------|
| Skill | 一组指令（SKILL.md），教 AI 如何处理特定任务 |
| Frontmatter | SKILL.md 开头的 YAML 元数据 |
| 渐进式披露 | 三级加载机制，控制 token 消耗 |
| 内置工具 | 系统提供的基础能力（Read/Write/Bash 等） |
| Trigger | 触发条件，决定何时加载某个 Skill |
