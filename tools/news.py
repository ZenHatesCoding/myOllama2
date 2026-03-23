from typing import Optional, Dict, Any, List
from langchain_core.tools import tool
import httpx
from datetime import datetime, timedelta


class NewsToolKit:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ""
        self.base_url = "http://v.juhe.cn/toutiao"
        self.cache = {}
        self.cache_duration = timedelta(minutes=10)
    
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
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self.api_key:
            params["key"] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    
    def _format_news_list(self, articles: List[Dict], tool_name: str) -> str:
        if not articles:
            return "未找到相关新闻"
        
        formatted = []
        for i, article in enumerate(articles, 1):
            title = article.get("title", "无标题")
            url = article.get("url", "")
            date = article.get("date", "")
            source = article.get("author_name", "未知来源")
            
            formatted.append(f"{i}. {title}")
            formatted.append(f"   来源: {source} | 时间: {date}")
            if url:
                formatted.append(f"   链接: {url}")
            formatted.append("")
        
        return "\n".join(formatted)
    
    def get_headlines(self, page_size: int = 10) -> Dict[str, Any]:
        cache_key = self._get_cache_key("get_headlines", page_size=page_size)
        cached = self._check_cache(cache_key)
        if cached:
            return cached
        
        try:
            result = self._make_request("index", {"type": "top", "page_size": page_size})
            
            if result.get("error_code") == 0:
                articles = result.get("result", {}).get("data", [])
                formatted_text = self._format_news_list(articles, "get_headlines")
                data = {
                    "success": True,
                    "tool_name": "get_headlines",
                    "articles": articles,
                    "formatted_text": formatted_text
                }
                self._set_cache(cache_key, data)
                return data
            else:
                return {
                    "success": False,
                    "error": result.get("reason", "获取新闻失败")
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_news_by_type(self, news_type: str, page_size: int = 10) -> Dict[str, Any]:
        cache_key = self._get_cache_key("get_news_by_type", news_type=news_type, page_size=page_size)
        cached = self._check_cache(cache_key)
        if cached:
            return cached
        
        type_mapping = {
            "头条": "top", "社会": "shehui", "国内": "guonei", "国际": "guoji",
            "娱乐": "yule", "体育": "tiyu", "科技": "keji", "财经": "caijing"
        }
        
        api_type = type_mapping.get(news_type, news_type)
        
        try:
            result = self._make_request("index", {"type": api_type, "page_size": page_size})
            
            if result.get("error_code") == 0:
                articles = result.get("result", {}).get("data", [])
                formatted_text = self._format_news_list(articles, "get_news_by_type")
                data = {
                    "success": True,
                    "tool_name": "get_news_by_type",
                    "articles": articles,
                    "formatted_text": formatted_text
                }
                self._set_cache(cache_key, data)
                return data
            else:
                return {
                    "success": False,
                    "error": result.get("reason", "获取新闻失败")
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_news(self, keyword: str, page_size: int = 10) -> Dict[str, Any]:
        cache_key = self._get_cache_key("search_news", keyword=keyword, page_size=page_size)
        cached = self._check_cache(cache_key)
        if cached:
            return cached
        
        try:
            result = self._make_request("index", {"type": keyword, "page_size": page_size})
            
            if result.get("error_code") == 0:
                articles = result.get("result", {}).get("data", [])
                formatted_text = self._format_news_list(articles, "search_news")
                data = {
                    "success": True,
                    "tool_name": "search_news",
                    "articles": articles,
                    "formatted_text": formatted_text
                }
                self._set_cache(cache_key, data)
                return data
            else:
                return {
                    "success": False,
                    "error": result.get("reason", "获取新闻失败")
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


news_toolkit = NewsToolKit(api_key="f01f4e17ae8680f4ad7c16904e0a3d21")


@tool
def get_headlines(page_size: int = 10) -> str:
    """获取头条新闻
    
    Args:
        page_size: 返回新闻数量，1-50，默认10
    """
    result = news_toolkit.get_headlines(page_size)
    if result.get("success"):
        return result.get("formatted_text", "获取新闻失败")
    return f"获取新闻失败: {result.get('error', '未知错误')}"


@tool
def get_news_by_type(news_type: str, page_size: int = 10) -> str:
    """按类型获取新闻
    
    Args:
        news_type: 新闻类型，可选值：头条、社会、国内、国际、娱乐、体育、科技、财经
        page_size: 返回新闻数量，1-50，默认10
    """
    result = news_toolkit.get_news_by_type(news_type, page_size)
    if result.get("success"):
        return result.get("formatted_text", "获取新闻失败")
    return f"获取新闻失败: {result.get('error', '未知错误')}"


@tool
def search_news(keyword: str, page_size: int = 10) -> str:
    """根据关键词搜索新闻
    
    Args:
        keyword: 搜索关键词
        page_size: 返回新闻数量，1-50，默认10
    """
    result = news_toolkit.search_news(keyword, page_size)
    if result.get("success"):
        return result.get("formatted_text", "获取新闻失败")
    return f"获取新闻失败: {result.get('error', '未知错误')}"


def get_all_tools():
    return [get_headlines, get_news_by_type, search_news]
