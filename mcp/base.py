from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: List[ToolParameter] = []


class BaseMCP(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def get_tools(self) -> List[ToolSchema]:
        pass
    
    @abstractmethod
    async def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tools": [tool.model_dump() for tool in self.get_tools()]
        }
