import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio

from .base import BaseMCP, ToolSchema, ToolParameter


class NewsMCP(BaseMCP):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="news_mcp",
            description="新闻获取工具，基于聚合数据API，支持获取最新新闻、搜索新闻等功能"
        )
        self.api_key = api_key or ""
        self.base_url = "http://v.juhe.cn/toutiao"
        self.cache = {}
        self.cache_duration = timedelta(minutes=10)
    
    def get_tools(self) -> List[ToolSchema]:
        return [
            ToolSchema(
                name="get_headlines",
                description="获取头条新闻",
                parameters=[
                    ToolParameter(
                        name="page_size",
                        type="integer",
                        description="返回新闻数量，1-50",
                        required=False,
                        default=10
                    )
                ]
            ),
            ToolSchema(
                name="get_news_by_type",
                description="按类型获取新闻",
                parameters=[
                    ToolParameter(
                        name="news_type",
                        type="string",
                        description="新闻类型：top(头条), shehui(社会), guonei(国内), guoji(国际), yule(娱乐), tiyu(体育), keji(科技), caijing(财经)",
                        required=True
                    ),
                    ToolParameter(
                        name="page_size",
                        type="integer",
                        description="返回新闻数量，1-50",
                        required=False,
                        default=10
                    )
                ]
            ),
            ToolSchema(
                name="search_news",
                description="根据关键词搜索新闻",
                parameters=[
                    ToolParameter(
                        name="keyword",
                        type="string",
                        description="搜索关键词",
                        required=True
                    ),
                    ToolParameter(
                        name="page_size",
                        type="integer",
                        description="返回新闻数量，1-50",
                        required=False,
                        default=10
                    )
                ]
            )
        ]
    
    def _get_cache_key(self, tool_name: str, **kwargs) -> str:
        return f"{tool_name}_{hash(str(sorted(kwargs.items())))}"
    
    def _check_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < self.cache_duration:
                return cached_data
            del self.cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, data: Dict[str, Any]):
        self.cache[cache_key] = (data, datetime.now())
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self.api_key:
            params["key"] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    
    def _format_news_list(self, articles: List[Dict], tool_name: str) -> str:
        if not articles:
            return "未找到相关新闻"
        
        result = f"## {tool_name}\n\n"
        for i, article in enumerate(articles, 1):
            result += f"### {i}. {article.get('title', '无标题')}\n"
            result += f"**来源**: {article.get('source', '未知')}\n"
            result += f"**时间**: {article.get('time', '未知')}\n"
            result += f"**描述**: {article.get('digest', '无描述')}\n"
            result += f"**链接**: {article.get('url', '')}\n\n"
        
        return result
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        try:
            cache_key = self._get_cache_key(tool_name, **kwargs)
            cached_result = self._check_cache(cache_key)
            if cached_result:
                return cached_result
            
            if tool_name == "get_headlines":
                result = await self._get_headlines(**kwargs)
            elif tool_name == "get_news_by_type":
                result = await self._get_news_by_type(**kwargs)
            elif tool_name == "search_news":
                result = await self._search_news(**kwargs)
            else:
                return {
                    "success": False,
                    "error": f"未知的工具: {tool_name}"
                }
            
            self._set_cache(cache_key, result)
            return result
            
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP错误: {e.response.status_code}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"执行失败: {str(e)}"
            }
    
    async def _get_headlines(self, page_size: int = 10) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "success": True,
                "tool_name": "get_headlines",
                "formatted_text": self._get_mock_headlines(page_size),
                "data": self._get_mock_headlines_data(page_size)
            }
        
        params = {
            "type": "top",
            "page_size": min(page_size, 50)
        }
        
        data = await self._make_request("index", params)
        
        if data.get("error_code") != 0:
            return {
                "success": False,
                "error": data.get("reason", "获取头条失败")
            }
        
        articles = data.get("result", {}).get("data", [])
        formatted_text = self._format_news_list(articles, "头条新闻")
        
        return {
            "success": True,
            "tool_name": "get_headlines",
            "formatted_text": formatted_text,
            "data": articles
        }
    
    async def _get_news_by_type(self, news_type: str, page_size: int = 10) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "success": True,
                "tool_name": "get_news_by_type",
                "formatted_text": self._get_mock_news_by_type(news_type, page_size),
                "data": self._get_mock_news_by_type_data(news_type, page_size)
            }
        
        params = {
            "type": news_type,
            "page_size": min(page_size, 50)
        }
        
        data = await self._make_request("index", params)
        
        if data.get("error_code") != 0:
            return {
                "success": False,
                "error": data.get("reason", "获取新闻失败")
            }
        
        articles = data.get("result", {}).get("data", [])
        type_names = {
            "top": "头条", "shehui": "社会", "guonei": "国内", 
            "guoji": "国际", "yule": "娱乐", "tiyu": "体育",
            "keji": "科技", "caijing": "财经"
        }
        type_name = type_names.get(news_type, news_type)
        formatted_text = self._format_news_list(articles, f"{type_name}新闻")
        
        return {
            "success": True,
            "tool_name": "get_news_by_type",
            "formatted_text": formatted_text,
            "data": articles
        }
    
    async def _search_news(self, keyword: str, page_size: int = 10) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "success": True,
                "tool_name": "search_news",
                "formatted_text": self._get_mock_search_news(keyword, page_size),
                "data": self._get_mock_search_news_data(keyword, page_size)
            }
        
        params = {
            "q": keyword,
            "page_size": min(page_size, 50)
        }
        
        data = await self._make_request("content", params)
        
        if data.get("error_code") != 0:
            return {
                "success": False,
                "error": data.get("reason", "搜索新闻失败")
            }
        
        articles = data.get("result", {}).get("data", [])
        formatted_text = self._format_news_list(articles, f"搜索结果: {keyword}")
        
        return {
            "success": True,
            "tool_name": "search_news",
            "formatted_text": formatted_text,
            "data": articles
        }
    
    def _get_mock_headlines(self, page_size: int) -> str:
        mock_articles = self._get_mock_headlines_data(page_size)
        return self._format_news_list(mock_articles, "头条新闻（演示数据）")
    
    def _get_mock_headlines_data(self, page_size: int) -> List[Dict]:
        mock_data = [
            {
                "title": "头条新闻示例 1 - 这是一条演示新闻标题",
                "source": "示例媒体",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "digest": "这是一条演示新闻的描述内容。在实际使用中，这里会显示真实的新闻摘要。",
                "url": "https://example.com/news/1"
            },
            {
                "title": "头条新闻示例 2 - 另一条演示新闻",
                "source": "示例媒体2",
                "time": (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                "digest": "这是第二条演示新闻的描述内容。您可以申请聚合数据的API密钥来获取真实新闻。",
                "url": "https://example.com/news/2"
            },
            {
                "title": "头条新闻示例 3 - 更多演示内容",
                "source": "示例媒体3",
                "time": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
                "digest": "这是第三条演示新闻。聚合数据提供每天100次免费请求，足够个人使用。",
                "url": "https://example.com/news/3"
            }
        ]
        
        return mock_data[:min(page_size, len(mock_data))]
    
    def _get_mock_news_by_type(self, news_type: str, page_size: int) -> str:
        mock_articles = self._get_mock_news_by_type_data(news_type, page_size)
        type_names = {
            "top": "头条", "shehui": "社会", "guonei": "国内", 
            "guoji": "国际", "yule": "娱乐", "tiyu": "体育",
            "keji": "科技", "caijing": "财经"
        }
        type_name = type_names.get(news_type, news_type)
        return self._format_news_list(mock_articles, f"{type_name}新闻（演示数据）")
    
    def _get_mock_news_by_type_data(self, news_type: str, page_size: int) -> List[Dict]:
        type_names = {
            "top": "头条", "shehui": "社会", "guonei": "国内", 
            "guoji": "国际", "yule": "娱乐", "tiyu": "体育",
            "keji": "科技", "caijing": "财经"
        }
        type_name = type_names.get(news_type, news_type)
        
        mock_data = [
            {
                "title": f"{type_name}新闻示例 1 - 这是一条{type_name}新闻",
                "source": "示例媒体",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "digest": f"这是一条{type_name}新闻的描述内容。",
                "url": f"https://example.com/news/{news_type}/1"
            },
            {
                "title": f"{type_name}新闻示例 2 - 另一条{type_name}新闻",
                "source": "示例媒体2",
                "time": (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                "digest": f"这是第二条{type_name}新闻的描述内容。",
                "url": f"https://example.com/news/{news_type}/2"
            }
        ]
        
        return mock_data[:min(page_size, len(mock_data))]
    
    def _get_mock_search_news(self, keyword: str, page_size: int) -> str:
        mock_articles = self._get_mock_search_news_data(keyword, page_size)
        return self._format_news_list(mock_articles, f"搜索结果: {keyword}（演示数据）")
    
    def _get_mock_search_news_data(self, keyword: str, page_size: int) -> List[Dict]:
        mock_data = [
            {
                "title": f"关于'{keyword}'的搜索结果 1",
                "source": "搜索结果媒体",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "digest": f"这是关于'{keyword}'的搜索结果描述。实际使用时会显示真实的搜索结果。",
                "url": f"https://example.com/search/{keyword}/1"
            },
            {
                "title": f"关于'{keyword}'的搜索结果 2",
                "source": "搜索结果媒体2",
                "time": (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                "digest": f"这是关于'{keyword}'的第二个搜索结果。",
                "url": f"https://example.com/search/{keyword}/2"
            }
        ]
        
        return mock_data[:min(page_size, len(mock_data))]
