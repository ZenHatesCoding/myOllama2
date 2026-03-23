import json
from typing import Optional, Dict, Any, List
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool

from graph import GraphState, create_initial_state
from tools.news import get_all_tools, news_toolkit
from tools import get_builtin_tools
from tools.document import document_tools, get_document_summary, get_document_outline
from extensions import state
from llm_factory import create_llm
from skill_registry import skill_registry


def build_skills_schema() -> str:
    skills = skill_registry.get_all_skills()
    if not skills:
        return "无可用的 Skill"
    schema = "可用 Skill 列表：\n\n"
    for skill in skills:
        schema += f"Skill 名称: {skill.name}\n"
        schema += f"描述: {skill.description}\n\n"
    return schema


def detect_skill_intent(llm, query: str, skills_schema: str) -> Optional[Dict[str, Any]]:
    system_prompt = f"""你是一个智能助手，负责判断用户是否需要使用某个 Skill 来完成任务。

{skills_schema}

请分析用户的输入，判断用户意图：
1. 如果用户要求执行某个 Skill（如"帮我审查代码"、"用 pdf-to-org 读 PDF"），返回：
{{
    "need_skill": true,
    "skill_name": "Skill名称"
}}

2. 如果用户只是询问有哪些 Skill 可用（如"你有什么 skill"、"列出所有 skill"），返回：
{{
    "list_skills": true
}}

3. 如果用户只是在正常聊天，不需要使用任何 Skill，返回：
{{
    "need_skill": false
}}

只返回JSON，不要有其他内容。"""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ])

        content = response.content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    text_parts.append(part.get('text', ''))
                elif isinstance(part, str):
                    text_parts.append(part)
            result_text = ''.join(text_parts)
        else:
            result_text = str(content)

        result_text = result_text.strip()
        result_text = result_text.replace('```json', '').replace('```', '').strip()

        try:
            result = json.loads(result_text)
            return result
        except json.JSONDecodeError:
            return None
    except Exception as e:
        print(f"检测 Skill 意图失败: {str(e)}")
        return None


def detect_tool_intent(llm, query: str, tools_schema: str) -> Optional[Dict[str, Any]]:
    system_prompt = f"""你是一个智能助手，负责判断用户是否需要使用工具来完成任务。

{tools_schema}

请分析用户的输入，判断是否需要使用上述工具。
如果需要使用工具，请返回JSON格式：
{{
    "need_tool": true,
    "tool_name": "工具名称",
    "parameters": {{
        "参数名": "参数值"
    }}
}}

如果不需要使用工具，请返回：
{{
    "need_tool": false,
    "reason": "原因说明"
}}

只返回JSON，不要有其他内容。"""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ])

        content = response.content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    text_parts.append(part.get('text', ''))
                elif isinstance(part, str):
                    text_parts.append(part)
            result_text = ''.join(text_parts)
        else:
            result_text = str(content)

        result_text = result_text.strip()
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        try:
            result = json.loads(result_text)
            return result
        except json.JSONDecodeError:
            return None
    except Exception as e:
        print(f"检测工具意图失败: {str(e)}")
        return None


def build_tools_schema() -> str:
    tools = get_all_tools() + document_tools
    schema = "可用工具列表：\n\n"
    for tool in tools:
        schema += f"工具名称: {tool.name}\n"
        schema += f"描述: {tool.description}\n"
        if tool.args_schema:
            schema += "参数:\n"
            properties = tool.args_schema.schema().get("properties", {})
            required = tool.args_schema.schema().get("required", [])
            for param_name, param_info in properties.items():
                req = " (必需)" if param_name in required else " (可选)"
                desc = param_info.get("description", "")
                schema += f"  - {param_name}: {param_info.get('type', 'any')}{req} - {desc}\n"
        schema += "\n"
    return schema


def node_classify_intent(state: GraphState) -> dict:
    from extensions import state as app_state
    from graph import decide_disclosure_level, DISCLOSURE_LEVELS

    if state.get("should_stop"):
        return {}

    query = state.get("query", "")
    if not query:
        return {"mcp_result": None}

    disclosure_level = decide_disclosure_level(query)
    level_config = DISCLOSURE_LEVELS.get(disclosure_level, DISCLOSURE_LEVELS["relevant"])

    model_name = state.get("model_name", "qwen3.5:9b")
    provider = app_state.llm_provider if hasattr(app_state, 'llm_provider') else 'ollama'

    if provider == "ollama":
        llm = ChatOllama(
            model=model_name,
            base_url=app_state.ollama_base_url if hasattr(app_state, 'ollama_base_url') else "http://localhost:11434",
            temperature=0.3
        )
    elif provider == "openai":
        llm = create_llm(
            provider="openai",
            model=app_state.openai_current_model if hasattr(app_state, 'openai_current_model') and app_state.openai_current_model else model_name,
            base_url=app_state.get_openai_base_url() if hasattr(app_state, 'get_openai_base_url') else None,
            api_key=app_state.get_openai_api_key() if hasattr(app_state, 'get_openai_api_key') else None,
            temperature=0.3
        )
    elif provider == "anthropic":
        llm = create_llm(
            provider="anthropic",
            model=app_state.anthropic_current_model if hasattr(app_state, 'anthropic_current_model') and app_state.anthropic_current_model else model_name,
            base_url=app_state.get_anthropic_base_url() if hasattr(app_state, 'get_anthropic_base_url') else None,
            api_key=app_state.get_anthropic_api_key() if hasattr(app_state, 'get_anthropic_api_key') else None,
            temperature=0.3
        )
    else:
        llm = ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=0.3
        )
    
    tools_schema = build_tools_schema()
    intent = detect_tool_intent(llm, query, tools_schema)
    
    if intent and intent.get("need_tool"):
        tool_name = intent.get("tool_name")
        parameters = intent.get("parameters", {})
        
        result = None
        if tool_name == "get_headlines":
            result = news_toolkit.get_headlines(parameters.get("page_size", 10))
        elif tool_name == "get_news_by_type":
            result = news_toolkit.get_news_by_type(
                parameters.get("news_type", "头条"),
                parameters.get("page_size", 10)
            )
        elif tool_name == "search_news":
            result = news_toolkit.search_news(
                parameters.get("keyword", ""),
                parameters.get("page_size", 10)
            )
        elif tool_name == "get_document_summary":
            n_chunks = level_config.get("n_chunks", 30)
            result = {"success": True, "tool_name": tool_name, "formatted_text": get_document_summary.invoke({"n_chunks": n_chunks})}
        elif tool_name == "get_document_outline":
            result = {"success": True, "tool_name": tool_name, "formatted_text": get_document_outline.invoke({})}
        
        if result and result.get("success"):
            result["disclosure_level"] = disclosure_level
            return {"mcp_result": result, "disclosure_level": disclosure_level}
    
    return {"mcp_result": None, "disclosure_level": disclosure_level}


def node_retrieve_docs(state: GraphState) -> dict:
    from graph import DISCLOSURE_LEVELS
    from retriever import create_retriever
    
    if state.get("should_stop"):
        return {}
    
    query = state.get("query", "")
    disclosure_level = state.get("disclosure_level", "relevant")
    level_config = DISCLOSURE_LEVELS.get(disclosure_level, DISCLOSURE_LEVELS["relevant"])
    
    from extensions import state as app_state
    provider = app_state.llm_provider if hasattr(app_state, 'llm_provider') else 'ollama'
    
    conversation = state.get_current_conversation() if hasattr(state, 'get_current_conversation') else None
    
    if not conversation:
        conversation = app_state.get_current_conversation()
    
    if not conversation or not conversation.document_chunks:
        return {"has_document": False, "document_context": "", "disclosure_level": disclosure_level}
    
    retriever = create_retriever(conversation, provider)
    if not retriever:
        return {"has_document": False, "document_context": "", "disclosure_level": disclosure_level}
    
    k = level_config.get("k", 8)
    relevant_docs = retriever.retrieve(query, k=k)
    main_context = "\n\n".join([doc.page_content for doc in relevant_docs]) if relevant_docs else "无相关内容"
    
    outline = get_document_outline.invoke({})
    summary = get_document_summary.invoke({"n_chunks": 10})
    
    full_context = f"""【相关片段】
{main_context}

【文档大纲】
{outline}

【文档摘要】
{summary}
"""
    
    return {
        "has_document": True,
        "document_context": full_context,
        "disclosure_level": disclosure_level
    }


def node_retrieve_history(state: GraphState) -> dict:
    from extensions import state as app_state
    
    provider = app_state.llm_provider if hasattr(app_state, 'llm_provider') else 'ollama'
    query = state.get("query", "")
    
    total_turns = 0
    conversation = None
    try:
        conversation = app_state.get_current_conversation() if hasattr(app_state, 'get_current_conversation') else None
        if conversation:
            total_turns = conversation.get_total_turns()
    except:
        pass
    
    if total_turns <= app_state.max_context_turns:
        return {"history_context": ""}
    
    from history_rag import history_rag
    
    llm = None
    if provider != "ollama":
        from llm_factory import create_llm
        if provider == "openai":
            llm = create_llm(
                provider="openai",
                model=app_state.openai_current_model if hasattr(app_state, 'openai_current_model') and app_state.openai_current_model else "gpt-4",
                base_url=app_state.get_openai_base_url() if hasattr(app_state, 'get_openai_base_url') else None,
                api_key=app_state.get_openai_api_key() if hasattr(app_state, 'get_openai_api_key') else None,
                temperature=0.3
            )
        elif provider == "anthropic":
            llm = create_llm(
                provider="anthropic",
                model=app_state.anthropic_current_model if hasattr(app_state, 'anthropic_current_model') and app_state.anthropic_current_model else "claude-3-sonnet-20240229",
                base_url=app_state.get_anthropic_base_url() if hasattr(app_state, 'get_anthropic_base_url') else None,
                api_key=app_state.get_anthropic_api_key() if hasattr(app_state, 'get_anthropic_api_key') else None,
                temperature=0.3
            )
    
    history_context = history_rag.get_context(query, provider=provider, llm=llm, k=3)
    
    return {"history_context": history_context or ""}


def node_generate_response(state: GraphState) -> dict:
    if state.get("should_stop"):
        return {"output_content": "操作已中断"}
    
    mcp_result = state.get("mcp_result")
    model_name = state.get("model_name", "qwen3.5:9b")
    query = state.get("query", "")
    images = state.get("images", [])
    has_document = state.get("has_document", False)
    document_context = state.get("document_context", "")
    history_context = state.get("history_context", "")
    skill_context = state.get("skill_context")
    
    news_tools = ["get_headlines", "get_news_by_type", "search_news"]
    document_tools_list = ["get_document_summary", "get_document_outline"]
    
    if mcp_result and mcp_result.get("success"):
        tool_name = mcp_result.get("tool_name", "")
        formatted_text = mcp_result.get("formatted_text", "")
        
        if tool_name in news_tools:
            tool_display_names = {
                "get_headlines": "头条新闻",
                "get_news_by_type": "分类新闻",
                "search_news": "新闻搜索"
            }
            tool_display_name = tool_display_names.get(tool_name, tool_name)
            full_text = f"📰 正在从{tool_display_name}获取信息...\n\n{formatted_text}"
            return {"output_content": full_text}
        
        if tool_name in document_tools_list:
            document_context = formatted_text
            has_document = True
    
    from extensions import state as app_state
    provider = app_state.llm_provider if hasattr(app_state, 'llm_provider') else 'ollama'
    
    conversation = app_state.get_current_conversation()
    builtin_tools = get_builtin_tools()
    mode = state.get("mode", "qa")

    if mode == "agent":
        if skill_context:
            system_prompt = f"""{skill_context}

你是一个专业的 AI 助手，可以使用内置工具（Read、Write、Bash、Glob、Grep）来完成用户任务。

当你需要读取文件时，使用 Read 工具。
当你需要创建或修改文件时，使用 Write 工具。
当你需要执行命令或脚本时，使用 Bash 工具。
当你需要搜索文件时，使用 Glob 工具。
当你需要在文件中搜索内容时，使用 Grep 工具。

请根据上述 Skill 指导完成任务。完成后向用户报告结果。

请开始回答："""
        else:
            system_prompt = """你是一个专业的 AI 助手，可以使用内置工具（Read、Write、Bash、Glob、Grep）来完成用户任务。

当你需要读取文件时，使用 Read 工具。
当你需要创建或修改文件时，使用 Write 工具。
当你需要执行命令或脚本时，使用 Bash 工具。
当你需要搜索文件时，使用 Glob 工具。
当你需要在文件中搜索内容时，使用 Grep 工具。

请根据用户需求自主决定何时调用工具。完成后向用户报告结果。

请开始回答："""
        
        if provider == "ollama":
            llm = ChatOllama(
                model=model_name,
                base_url=app_state.ollama_base_url if hasattr(app_state, 'ollama_base_url') else "http://localhost:11434",
                temperature=0.7,
                num_ctx=32000,
                num_predict=8000
            ).bind_tools(builtin_tools)
        elif provider == "openai":
            llm = create_llm(
                provider="openai",
                model=app_state.openai_current_model if hasattr(app_state, 'openai_current_model') and app_state.openai_current_model else model_name,
                base_url=app_state.get_openai_base_url() if hasattr(app_state, 'get_openai_base_url') else None,
                api_key=app_state.get_openai_api_key() if hasattr(app_state, 'get_openai_api_key') else None,
                temperature=0.7
            ).bind_tools(builtin_tools)
        elif provider == "anthropic":
            llm = create_llm(
                provider="anthropic",
                model=app_state.anthropic_current_model if hasattr(app_state, 'anthropic_current_model') and app_state.anthropic_current_model else model_name,
                base_url=app_state.get_anthropic_base_url() if hasattr(app_state, 'get_anthropic_base_url') else None,
                api_key=app_state.get_anthropic_api_key() if hasattr(app_state, 'get_anthropic_api_key') else None,
                temperature=0.7
            ).bind_tools(builtin_tools)
        else:
            llm = ChatOllama(
                model=model_name,
                base_url="http://localhost:11434",
                temperature=0.7,
                num_ctx=32000,
                num_predict=8000
            ).bind_tools(builtin_tools)
        
        from utils import prepare_messages
        messages = prepare_messages(conversation, query, system_prompt, images if images else None)
        
        output_content = ""
        tool_result_buffer = []
        
        for chunk in llm.stream(messages):
            if app_state.should_stop:
                output_content += "\n\n操作已中断"
                break
            
            if hasattr(chunk, 'content') and isinstance(chunk.content, list):
                for part in chunk.content:
                    if isinstance(part, dict):
                        if part.get('type') == 'text':
                            text = part.get('text', '')
                            output_content += text
                        elif part.get('type') == 'tool_use':
                            tool_name = part.get('name', '')
                            tool_input = part.get('input', {})
                            tool_id = part.get('id', '')
                            tool_result = _execute_builtin_tool(tool_name, tool_input)
                            tool_result_buffer.append({
                                'tool_call_id': tool_id,
                                'tool_name': tool_name,
                                'result': tool_result
                            })
                            output_content += f"\n[执行工具: {tool_name}]\n"
                    elif isinstance(part, str):
                        output_content += part
            else:
                chunk_text = str(getattr(chunk, 'content', chunk))
                output_content += chunk_text
            
            if tool_result_buffer:
                continue
        
        if tool_result_buffer:
            messages.append(AIMessage(content=output_content))
            for tr in tool_result_buffer:
                messages.append(HumanMessage(
                    content=f"工具 {tr['tool_name']} 返回结果: {tr['result']}"
                ))
            
            output_content = ""
            for chunk in llm.stream(messages):
                if app_state.should_stop:
                    output_content += "\n\n操作已中断"
                    break
                
                if hasattr(chunk, 'content') and isinstance(chunk.content, list):
                    for part in chunk.content:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            output_content += part.get('text', '')
                        elif isinstance(part, str):
                            output_content += part
                else:
                    output_content += str(getattr(chunk, 'content', chunk))
        
        return {"output_content": output_content}
    else:
        if provider == "ollama":
            llm = ChatOllama(
                model=model_name,
                base_url=app_state.ollama_base_url if hasattr(app_state, 'ollama_base_url') else "http://localhost:11434",
                temperature=0.7,
                num_ctx=32000,
                num_predict=8000
            )
        elif provider == "openai":
            llm = create_llm(
                provider="openai",
                model=app_state.openai_current_model if hasattr(app_state, 'openai_current_model') and app_state.openai_current_model else model_name,
                base_url=app_state.get_openai_base_url() if hasattr(app_state, 'get_openai_base_url') else None,
                api_key=app_state.get_openai_api_key() if hasattr(app_state, 'get_openai_api_key') else None,
                temperature=0.7
            )
        elif provider == "anthropic":
            llm = create_llm(
                provider="anthropic",
                model=app_state.anthropic_current_model if hasattr(app_state, 'anthropic_current_model') and app_state.anthropic_current_model else model_name,
                base_url=app_state.get_anthropic_base_url() if hasattr(app_state, 'get_anthropic_base_url') else None,
                api_key=app_state.get_anthropic_api_key() if hasattr(app_state, 'get_anthropic_api_key') else None,
                temperature=0.7
            )
        else:
            llm = ChatOllama(
                model=model_name,
                base_url="http://localhost:11434",
                temperature=0.7,
                num_ctx=32000,
                num_predict=8000
            )
        
        context_parts = []
        if has_document and document_context:
            context_parts.append(f"【文档内容】\n{document_context}")
        if history_context:
            context_parts.append(f"【历史对话上下文】\n{history_context}")
        context_str = "\n\n".join(context_parts) if context_parts else ""

        system_prompt = f"""你是一个专业、友好的AI助手。
请根据以下信息回答用户的问题。
{context_str}

【回答要求】
1. 用户用什么语言提问，你就用什么语言回答
2. 回答要简洁、有条理

请开始回答："""
        
        from utils import prepare_messages
        messages = prepare_messages(conversation, query, system_prompt, images if images else None)
        
        output_content = ""
        for chunk in llm.stream(messages):
            if app_state.should_stop:
                output_content += "\n\n操作已中断"
                break
            
            if hasattr(chunk, 'content') and isinstance(chunk.content, list):
                text_parts = []
                for part in chunk.content:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        text_parts.append(part.get('text', ''))
                    elif isinstance(part, str):
                        text_parts.append(part)
                chunk_text = ''.join(text_parts)
            else:
                chunk_text = str(chunk.content)
            
            output_content += chunk_text
        
        return {"output_content": output_content}


def _execute_builtin_tool(tool_name: str, tool_input: dict) -> str:
    tool_map = {
        'Read': lambda inp: _tool_read(inp.get('path', ''), inp.get('encoding', 'utf-8')),
        'Write': lambda inp: _tool_write(inp.get('path', ''), inp.get('content', ''), inp.get('encoding', 'utf-8')),
        'Bash': lambda inp: _tool_bash(inp.get('command', ''), inp.get('timeout', 60)),
        'Glob': lambda inp: _tool_glob(inp.get('pattern', '')),
        'Grep': lambda inp: _tool_grep(inp.get('pattern', ''), inp.get('path', './'), inp.get('encoding', 'utf-8')),
    }
    
    func = tool_map.get(tool_name)
    if func:
        try:
            return func(tool_input)
        except Exception as e:
            return f"工具执行错误: {str(e)}"
    return f"未知工具: {tool_name}"


def _tool_read(path: str, encoding: str = "utf-8") -> str:
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).parent.resolve()
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / path
    if p.exists():
        return p.read_text(encoding=encoding)
    return f"文件不存在: {path}"


def _tool_write(path: str, content: str, encoding: str = "utf-8") -> str:
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).parent.resolve()
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding=encoding)
    return f"成功写入: {path}"


def _tool_bash(command: str, timeout: int = 60) -> str:
    import subprocess
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            return f"命令失败 (退出码 {result.returncode}):\n{result.stderr}"
        return result.stdout if result.stdout else "命令执行成功"
    except subprocess.TimeoutExpired:
        return f"命令超时 ({timeout}秒)"
    except Exception as e:
        return f"命令执行错误: {str(e)}"


def _tool_glob(pattern: str) -> str:
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).parent.resolve()
    ALLOWED_DIRS = [
        PROJECT_ROOT / "skills",
        PROJECT_ROOT / "workspace",
        PROJECT_ROOT / "conversations",
        PROJECT_ROOT / "output",
    ]
    results = []
    for base_dir in ALLOWED_DIRS:
        if base_dir.exists():
            for f in base_dir.glob(pattern):
                if f.is_file():
                    results.append(str(f.relative_to(PROJECT_ROOT)))
    return "\n".join(results) if results else f"没有找到匹配 {pattern} 的文件"


def _tool_grep(pattern: str, path: str = "./", encoding: str = "utf-8") -> str:
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).parent.resolve()
    ALLOWED_DIRS = [
        PROJECT_ROOT / "skills",
        PROJECT_ROOT / "workspace",
        PROJECT_ROOT / "conversations",
        PROJECT_ROOT / "output",
    ]
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / path
    
    matches = []
    for base_dir in ALLOWED_DIRS:
        if str(p).startswith(str(base_dir)) and base_dir.exists():
            for f in base_dir.rglob("*.py"):
                try:
                    content = f.read_text(encoding=encoding)
                    for i, line in enumerate(content.splitlines(), 1):
                        if pattern in line:
                            matches.append(f"{f.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")
                except:
                    pass
            break
    
    return "\n".join(matches[:50]) if matches else f"没有找到匹配 {pattern} 的内容"


def route_by_mode(state: GraphState) -> str:
    mode = state.get("mode", "qa")
    
    if mode == "agent":
        target_skill = state.get("target_skill")
        if target_skill:
            return "activate_skill"
        return "match_skill"
    
    return "classify_intent"


def should_use_tool(state: GraphState) -> str:
    mode = state.get("mode", "qa")
    target_skill = state.get("target_skill")
    mcp_result = state.get("mcp_result")

    if target_skill:
        return "activate_skill"
    elif mcp_result and mcp_result.get("success"):
        return "generate_response"
    
    if mode == "qa":
        return "retrieve_docs"
    return "match_skill"


def should_use_skill(state: GraphState) -> str:
    mode = state.get("mode", "qa")
    target_skill = state.get("target_skill")
    skill_context = state.get("skill_context")

    if target_skill:
        return "activate_skill"
    if skill_context:
        return "generate_response"
    if mode == "agent":
        return "generate_response"
    return "retrieve_docs"


def should_use_skill_agent(state: GraphState) -> str:
    target_skill = state.get("target_skill")
    skill_context = state.get("skill_context")

    if target_skill:
        return "activate_skill"
    if skill_context:
        return "generate_response"
    return "generate_response"


def node_match_skill(state: GraphState) -> dict:
    if state.get("should_stop"):
        return {}

    query = state.get("query", "")
    if not query:
        return {"target_skill": None}

    skills = skill_registry.get_all_skills()
    if not skills:
        return {"target_skill": None}

    from extensions import state as app_state
    provider = app_state.llm_provider if hasattr(app_state, 'llm_provider') else 'ollama'
    model_name = state.get("model_name", "qwen3.5:9b")

    if provider == "ollama":
        llm = ChatOllama(
            model=model_name,
            base_url=app_state.ollama_base_url if hasattr(app_state, 'ollama_base_url') else "http://localhost:11434",
            temperature=0.3
        )
    elif provider == "openai":
        llm = create_llm(
            provider="openai",
            model=app_state.openai_current_model if hasattr(app_state, 'openai_current_model') and app_state.openai_current_model else model_name,
            base_url=app_state.get_openai_base_url() if hasattr(app_state, 'get_openai_base_url') else None,
            api_key=app_state.get_openai_api_key() if hasattr(app_state, 'get_openai_api_key') else None,
            temperature=0.3
        )
    elif provider == "anthropic":
        llm = create_llm(
            provider="anthropic",
            model=app_state.anthropic_current_model if hasattr(app_state, 'anthropic_current_model') and app_state.anthropic_current_model else model_name,
            base_url=app_state.get_anthropic_base_url() if hasattr(app_state, 'get_anthropic_base_url') else None,
            api_key=app_state.get_anthropic_api_key() if hasattr(app_state, 'get_anthropic_api_key') else None,
            temperature=0.3
        )
    else:
        llm = ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=0.3
        )

    skills_schema = build_skills_schema()
    intent = detect_skill_intent(llm, query, skills_schema)

    query_lower = query.lower()
    list_keywords = ["什么skill", "什么技能", "有哪些skill", "有哪些技能", "列出", "list", "skill列表", "技能列表"]
    is_list_query = any(kw in query_lower for kw in list_keywords)

    if intent and intent.get("need_skill"):
        skill_name = intent.get("skill_name")
        return {"target_skill": skill_name}

    if intent and intent.get("list_skills"):
        skills = skill_registry.get_all_skills()
        skill_list_text = "\n".join([f"- **{skill.name}**: {skill.description}" for skill in skills])
        skill_context = f"【可用 Skill 列表】\n\n{skill_list_text}\n\n请向用户介绍这些 Skill。"
        return {"target_skill": None, "skill_context": skill_context}

    if is_list_query and not intent:
        skills = skill_registry.get_all_skills()
        skill_list_text = "\n".join([f"- **{skill.name}**: {skill.description}" for skill in skills])
        skill_context = f"【可用 Skill 列表】\n\n{skill_list_text}\n\n请向用户介绍这些 Skill。"
        return {"target_skill": None, "skill_context": skill_context}

    return {"target_skill": None}


def node_activate_skill(state: GraphState) -> dict:
    if state.get("should_stop"):
        return {}
    
    target_skill = state.get("target_skill")
    if not target_skill:
        return {"skill_context": None}
    
    skill = skill_registry.get_skill(target_skill)
    if not skill:
        return {"skill_context": None}
    
    skill_content = skill.get_full_content()
    skill_context = f"【激活 Skill: {skill.name}】\n\n{skill_content}"
    
    return {"skill_context": skill_context}


_qa_graph = None
_agent_graph = None


def should_use_tool_qa(state: GraphState) -> str:
    mcp_result = state.get("mcp_result")
    if mcp_result and mcp_result.get("success"):
        return "generate_response"
    return "retrieve_docs"


def build_qa_graph():
    global _qa_graph
    if _qa_graph is None:
        graph = StateGraph(GraphState)

        graph.add_node("classify_intent", node_classify_intent)
        graph.add_node("retrieve_docs", node_retrieve_docs)
        graph.add_node("retrieve_history", node_retrieve_history)
        graph.add_node("generate_response", node_generate_response)

        graph.set_entry_point("classify_intent")

        graph.add_conditional_edges(
            "classify_intent",
            should_use_tool_qa,
            {
                "generate_response": "generate_response",
                "retrieve_docs": "retrieve_docs"
            }
        )

        graph.add_edge("retrieve_docs", "retrieve_history")
        graph.add_edge("retrieve_history", "generate_response")
        graph.add_edge("generate_response", END)

        _qa_graph = graph.compile(checkpointer=MemorySaver())
    return _qa_graph


def build_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        graph = StateGraph(GraphState)

        graph.add_node("match_skill", node_match_skill)
        graph.add_node("activate_skill", node_activate_skill)
        graph.add_node("generate_response", node_generate_response)

        graph.set_entry_point("match_skill")

        graph.add_conditional_edges(
            "match_skill",
            should_use_skill_agent,
            {
                "activate_skill": "activate_skill",
                "generate_response": "generate_response"
            }
        )

        graph.add_edge("activate_skill", "generate_response")
        graph.add_edge("generate_response", END)

        _agent_graph = graph.compile(checkpointer=MemorySaver())
    return _agent_graph


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("route_by_mode", lambda state: state)
    graph.add_node("classify_intent", node_classify_intent)
    graph.add_node("match_skill", node_match_skill)
    graph.add_node("activate_skill", node_activate_skill)
    graph.add_node("retrieve_docs", node_retrieve_docs)
    graph.add_node("retrieve_history", node_retrieve_history)
    graph.add_node("generate_response", node_generate_response)

    graph.set_entry_point("route_by_mode")

    graph.add_conditional_edges(
        "route_by_mode",
        route_by_mode,
        {
            "qa": "classify_intent",
            "agent": "match_skill"
        }
    )

    graph.add_conditional_edges(
        "classify_intent",
        should_use_tool,
        {
            "activate_skill": "activate_skill",
            "generate_response": "generate_response",
            "match_skill": "match_skill"
        }
    )

    graph.add_conditional_edges(
        "match_skill",
        should_use_skill,
        {
            "activate_skill": "activate_skill",
            "generate_response": "generate_response"
        }
    )

    graph.add_edge("activate_skill", "generate_response")
    graph.add_edge("retrieve_docs", "retrieve_history")
    graph.add_edge("retrieve_history", "generate_response")
    graph.add_edge("generate_response", END)
    
    return graph.compile(checkpointer=MemorySaver())


graph_executor = None


def get_graph_executor():
    global graph_executor
    if graph_executor is None:
        graph_executor = build_graph()
    return graph_executor


def run_graph(query: str, model_name: str = "qwen3.5:4b", images: List[dict] = None, mode: str = "qa") -> str:
    initial_state = create_initial_state(query, model_name, images, mode)
    
    if mode == "qa":
        executor = build_qa_graph()
    else:
        executor = build_agent_graph()
    
    result = executor.invoke(initial_state, config={"configurable": {"thread_id": "default"}})
    
    return result.get("output_content", "")


def stream_graph(query: str, model_name: str = "qwen3.5:4b", images: List[dict] = None, mode: str = "qa"):
    from extensions import state as app_state
    
    initial_state = create_initial_state(query, model_name, images, mode)
    
    if mode == "qa":
        executor = build_qa_graph()
    else:
        executor = build_agent_graph()
    
    mcp_result = None
    
    for event in executor.stream(initial_state, config={"configurable": {"thread_id": "default"}}):
        if app_state.should_stop:
            yield "操作已中断"
            return
        
        for node_name, node_output in event.items():
            if node_name == "classify_intent":
                mcp_result = node_output.get("mcp_result")
                if mcp_result and mcp_result.get("success"):
                    tool_name = mcp_result.get("tool_name", "")
                    tool_display_names = {
                        "get_headlines": "头条新闻",
                        "get_news_by_type": "分类新闻",
                        "search_news": "新闻搜索",
                        "get_document_summary": "文档摘要",
                        "get_document_outline": "文档大纲"
                    }
                    tool_display_name = tool_display_names.get(tool_name, tool_name)
                    yield f"📰 正在从{tool_display_name}获取信息...\n\n"
            
            elif node_name == "generate_response":
                output = node_output.get("output_content", "")
                yield output
