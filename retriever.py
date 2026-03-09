from abc import ABC, abstractmethod
from typing import List, Optional
from langchain_core.documents import Document


class DocumentRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, k: int) -> List[Document]:
        pass

    @abstractmethod
    def get_chunks_count(self) -> int:
        pass


class FAISSRetriever(DocumentRetriever):
    def __init__(self, vector_store, chunks: List[Document]):
        self.vector_store = vector_store
        self.chunks = chunks

    def retrieve(self, query: str, k: int) -> List[Document]:
        return self.vector_store.similarity_search(query, k=k)

    def get_chunks_count(self) -> int:
        return len(self.chunks)


class DirectChunkRetriever(DocumentRetriever):
    def __init__(self, chunks: List[Document]):
        self.chunks = chunks

    def retrieve(self, query: str, k: int) -> List[Document]:
        return self.chunks[:k]

    def get_chunks_count(self) -> int:
        return len(self.chunks)


def create_retriever(conversation, provider: str) -> Optional[DocumentRetriever]:
    if not conversation or not conversation.document_chunks:
        return None

    if provider == "ollama" and conversation.vector_store:
        return FAISSRetriever(conversation.vector_store, conversation.document_chunks)
    else:
        return DirectChunkRetriever(conversation.document_chunks)
