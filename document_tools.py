from langchain_core.tools import tool
from resources import ResourceRegistry


@tool
def get_document_summary(n_chunks: int = 10) -> str:
    """获取文档内容用于生成摘要。
    
    当用户要求总结、概括、概述文档主要内容时调用此工具。
    返回文档前N个块的完整内容，供LLM生成摘要。
    
    Args:
        n_chunks: 加载的文本块数量，默认10块约5000字
    """
    resource = ResourceRegistry.get("document")
    if not resource or not resource.is_available():
        return "当前没有上传文档"
    
    result = resource.load("summary", {"n_chunks": n_chunks})
    return result.content


@tool
def search_document(query: str, k: int = 4, expand: bool = True) -> str:
    """在文档中搜索内容。
    
    当用户查找特定信息、搜索关键词时调用此工具。
    支持相似度检索和上下文扩展。
    
    Args:
        query: 搜索查询或关键词
        k: 返回片段数量，默认4
        expand: 是否扩展上下文（包含前后相邻块），默认True
    """
    resource = ResourceRegistry.get("document")
    if not resource or not resource.is_available():
        return "当前没有上传文档"
    
    strategy = "search" if expand else "specific"
    result = resource.load(strategy, {"query": query, "k": k})
    return result.content


@tool
def get_document_outline() -> str:
    """获取文档结构大纲。
    
    当用户询问文档结构、目录、章节组织时调用此工具。
    返回文档各部分的采样预览。
    """
    resource = ResourceRegistry.get("document")
    if not resource or not resource.is_available():
        return "当前没有上传文档"
    
    result = resource.load("structure", {})
    return result.content


document_tools = [get_document_summary, search_document, get_document_outline]
