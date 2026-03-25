from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class LoadResult:
    success: bool
    content: str
    metadata: Dict[str, Any] = None


class BaseResource(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
    
    @abstractmethod
    def load(self, strategy: str, params: Dict[str, Any]) -> LoadResult:
        pass


class DocumentResource(BaseResource):
    @property
    def name(self) -> str:
        return "document"
    
    def is_available(self) -> bool:
        from core import state
        conversation = state.get_current_conversation()
        return bool(conversation and conversation.document_chunks)
    
    def load(self, strategy: str, params: Dict[str, Any]) -> LoadResult:
        from core import state
        conversation = state.get_current_conversation()
        
        if not conversation or not conversation.document_chunks:
            return LoadResult(False, "当前没有上传文档")
        
        chunks = conversation.document_chunks
        total = len(chunks)
        
        if strategy == "summary":
            n_chunks = min(params.get("n_chunks", 10), total)
            content_parts = []
            for i in range(n_chunks):
                content_parts.append(f"--- 文本块 {i} ---\n{chunks[i].page_content}")
            content = "\n\n".join(content_parts)
            return LoadResult(
                True, 
                f"文档《{conversation.document_file}》前 {n_chunks} 个文本块（共 {total} 块）：\n\n{content}",
                {"n_chunks": n_chunks, "total": total}
            )
        
        elif strategy == "structure":
            sample_rate = params.get("sample_rate", 10)
            step = max(1, total // sample_rate)
            sampled = []
            for i in range(0, total, step):
                preview = chunks[i].page_content[:150].replace("\n", " ")
                sampled.append(f"[块 {i}] {preview}...")
            return LoadResult(
                True,
                f"文档《{conversation.document_file}》结构采样（共 {total} 块）：\n\n" + "\n".join(sampled),
                {"total": total}
            )
        
        elif strategy == "search":
            query = params.get("query", "")
            k = params.get("k", 4)
            
            if not conversation.vector_store:
                return LoadResult(False, "文档索引不可用")
            
            docs = conversation.vector_store.similarity_search(query, k=k)
            if not docs:
                return LoadResult(False, "未找到相关内容")
            
            results = []
            for doc in docs:
                chunk_idx = doc.metadata.get("chunk_index", 0)
                start = max(0, chunk_idx - 1)
                end = min(total, chunk_idx + 2)
                expanded_parts = []
                for i in range(start, end):
                    expanded_parts.append(f"[块 {i}] {chunks[i].page_content}")
                expanded = "\n".join(expanded_parts)
                results.append(f"--- 相关片段（块 {start}-{end-1}）---\n{expanded}")
            
            return LoadResult(
                True,
                f"找到 {len(results)} 个相关片段：\n\n" + "\n\n".join(results),
                {"k": k, "found": len(results)}
            )
        
        elif strategy == "specific":
            query = params.get("query", "")
            k = params.get("k", 4)
            
            if not conversation.vector_store:
                return LoadResult(False, "文档索引不可用")
            
            docs = conversation.vector_store.similarity_search(query, k=k)
            if not docs:
                return LoadResult(False, "未找到相关内容")
            
            results = []
            for doc in docs:
                chunk_idx = doc.metadata.get("chunk_index", "?")
                results.append(f"--- 片段 {chunk_idx} ---\n{doc.page_content}")
            
            return LoadResult(
                True,
                f"找到 {len(results)} 个相关片段：\n\n" + "\n\n".join(results),
                {"k": k, "found": len(results)}
            )
        
        return LoadResult(False, f"未知策略: {strategy}")


class ResourceRegistry:
    _resources: Dict[str, BaseResource] = {}
    
    @classmethod
    def register(cls, resource: BaseResource):
        cls._resources[resource.name] = resource
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseResource]:
        return cls._resources.get(name)
    
    @classmethod
    def get_available(cls) -> List[BaseResource]:
        return [r for r in cls._resources.values() if r.is_available()]


ResourceRegistry.register(DocumentResource())
