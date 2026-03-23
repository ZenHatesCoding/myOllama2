import json
from typing import Optional, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from tools.news import get_all_tools
from tools.document import document_tools
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
