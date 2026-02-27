import asyncio
from typing import Dict, List, Optional, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
import json

from .base import BaseMCP, ToolSchema


class MCPManager:
    def __init__(self):
        self.mcps: Dict[str, BaseMCP] = {}
        self.llm = ChatOllama(
            model="qwen3:8b",
            base_url="http://localhost:11434",
            temperature=0.3
        )
    
    def register_mcp(self, mcp: BaseMCP):
        self.mcps[mcp.name] = mcp
    
    def get_all_tools(self) -> List[ToolSchema]:
        tools = []
        for mcp in self.mcps.values():
            tools.extend(mcp.get_tools())
        return tools
    
    def get_tools_schema(self) -> str:
        tools = self.get_all_tools()
        schema = "可用工具列表：\n\n"
        for tool in tools:
            schema += f"工具名称: {tool.name}\n"
            schema += f"描述: {tool.description}\n"
            if tool.parameters:
                schema += "参数:\n"
                for param in tool.parameters:
                    required = " (必需)" if param.required else " (可选)"
                    schema += f"  - {param.name}: {param.type}{required} - {param.description}\n"
            schema += "\n"
        return schema
    
    async def detect_intent_and_execute(self, user_query: str) -> Optional[Dict[str, Any]]:
        tools_schema = self.get_tools_schema()
        
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
            response = await asyncio.to_thread(
                self.llm.invoke,
                [SystemMessage(content=system_prompt), HumanMessage(content=user_query)]
            )
            
            result_text = response.content.strip()
            
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                return None
            
            if not result.get("need_tool"):
                return None
            
            tool_name = result.get("tool_name")
            parameters = result.get("parameters", {})
            
            for mcp in self.mcps.values():
                tools = mcp.get_tools()
                for tool in tools:
                    if tool.name == tool_name:
                        return await mcp.execute_tool(tool_name, **parameters)
            
            return None
            
        except Exception as e:
            print(f"意图检测失败: {str(e)}")
            return None
