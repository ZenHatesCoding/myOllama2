from langchain_core.tools import tool
from models import state


@tool
def get_document_summary() -> str:
    """获取当前文档的摘要信息。
    
    返回文档的主题、主要章节结构和关键信息点。
    当需要了解文档整体内容时调用此工具。
    """
    conversation = state.get_current_conversation()
    
    if not conversation.document_file:
        return "当前没有上传文档。"
    
    if conversation.document_summary:
        return f"文档《{conversation.document_file}》摘要：\n{conversation.document_summary}"
    
    return f"文档《{conversation.document_file}》，共 {len(conversation.document_chunks)} 个文本块。"


@tool
def search_document(query: str, k: int = 4) -> str:
    """在文档中搜索与问题相关的内容片段。
    
    Args:
        query: 搜索关键词或问题
        k: 返回片段数量，默认4，范围1-10
    
    返回与查询最相关的文档片段。
    """
    conversation = state.get_current_conversation()
    
    if not conversation.vector_store:
        return "当前没有上传文档，无法搜索。"
    
    k = max(1, min(10, k))
    
    try:
        results = conversation.vector_store.similarity_search(query, k=k)
        
        if not results:
            return "未找到相关内容。"
        
        output = f"找到 {len(results)} 个相关片段：\n\n"
        for i, doc in enumerate(results, 1):
            chunk_idx = doc.metadata.get("chunk_index", "?")
            output += f"--- 片段 {i} (索引:{chunk_idx}) ---\n"
            output += doc.page_content[:500]
            if len(doc.page_content) > 500:
                output += "..."
            output += "\n\n"
        
        return output
    except Exception as e:
        return f"搜索失败：{str(e)}"


@tool
def expand_context(chunk_id: int, direction: str = "both") -> str:
    """获取指定片段的前后扩展内容。
    
    Args:
        chunk_id: 片段索引
        direction: 扩展方向，"before"(前)、"after"(后)、"both"(前后)，默认"both"
    
    返回扩展后的上下文内容。
    """
    conversation = state.get_current_conversation()
    
    if not conversation.document_chunks:
        return "当前没有上传文档。"
    
    chunks = conversation.document_chunks
    total = len(chunks)
    
    if chunk_id < 0 or chunk_id >= total:
        return f"无效的片段索引 {chunk_id}，有效范围 0-{total-1}。"
    
    result_chunks = []
    
    if direction == "before":
        start = max(0, chunk_id - 1)
        end = chunk_id + 1
    elif direction == "after":
        start = chunk_id
        end = min(total, chunk_id + 2)
    else:
        start = max(0, chunk_id - 1)
        end = min(total, chunk_id + 2)
    
    output = f"扩展上下文（片段 {start} 到 {end-1}）：\n\n"
    
    for i in range(start, end):
        chunk = chunks[i]
        output += f"--- 片段 {i} ---\n"
        output += chunk.page_content[:800]
        if len(chunk.page_content) > 800:
            output += "..."
        output += "\n\n"
    
    return output


@tool
def get_document_outline() -> str:
    """获取文档的结构大纲。
    
    返回文档的章节结构和每个章节的简要描述。
    当需要了解文档整体结构时调用。
    """
    conversation = state.get_current_conversation()
    
    if not conversation.document_chunks:
        return "当前没有上传文档。"
    
    chunks = conversation.document_chunks
    total = len(chunks)
    
    output = f"文档《{conversation.document_file}》结构：\n"
    output += f"共 {total} 个文本块\n\n"
    
    sample_size = min(10, total)
    step = max(1, total // sample_size)
    
    for i in range(0, total, step):
        chunk = chunks[i]
        content = chunk.page_content[:100].replace("\n", " ")
        output += f"[块 {i}] {content}...\n"
    
    if total > sample_size:
        output += f"\n... 还有 {total - sample_size * step} 个文本块 ..."
    
    return output


document_tools = [get_document_summary, search_document, expand_context, get_document_outline]
