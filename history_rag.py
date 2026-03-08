import os
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

from conversation_manager import conversation_manager


embedding_model = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")


class HistoryRAG:
    def __init__(self):
        self.vector_store = None
        self.conversation_blocks = {}
        self.vector_store_path = os.path.join(
            conversation_manager.vector_stores_dir, 
            "history_index"
        )
    
    MAX_BLOCK_LENGTH = 2000
    
    def _split_into_blocks(self, messages: List[Dict]) -> List[Dict]:
        blocks = []
        i = 0
        while i < len(messages):
            if messages[i]["role"] == "user":
                user_content = messages[i]["content"]
                if len(user_content) > self.MAX_BLOCK_LENGTH:
                    user_content = user_content[:self.MAX_BLOCK_LENGTH]
                
                assistant_content = ""
                if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                    assistant_content = messages[i + 1]["content"]
                    if len(assistant_content) > self.MAX_BLOCK_LENGTH:
                        assistant_content = assistant_content[:self.MAX_BLOCK_LENGTH]
                    i += 2
                else:
                    i += 1
                
                blocks.append({
                    "user_content": user_content,
                    "assistant_content": assistant_content,
                    "user_idx": i
                })
            else:
                i += 1
        return blocks
    
    def _block_to_text(self, block: Dict) -> str:
        text = f"用户: {block['user_content']}\n"
        if block['assistant_content']:
            text += f"助手: {block['assistant_content']}"
        return text
    
    def build_index(self, conversation_id: str) -> bool:
        conv_data = conversation_manager.load_conversation(conversation_id)
        if not conv_data:
            return False
        
        messages = conv_data.get("messages", [])
        if not messages:
            return False
        
        blocks = self._split_into_blocks(messages)
        if not blocks:
            return False
        
        documents = []
        for i, block in enumerate(blocks):
            text = self._block_to_text(block)
            doc = Document(
                page_content=text,
                metadata={
                    "conversation_id": conversation_id,
                    "block_idx": i,
                    "user_idx": block["user_idx"],
                    "source": "history"
                }
            )
            documents.append(doc)
        
        try:
            if documents:
                new_store = FAISS.from_documents(documents, embedding_model)
                
                if self.vector_store is None:
                    self.vector_store = new_store
                else:
                    self.vector_store.merge_from(new_store)
                
                self.conversation_blocks[conversation_id] = blocks
                
                return True
        except Exception as e:
            print(f"构建向量索引失败: {str(e)}")
            return False
        
        return False
    
    def build_all_index(self):
        conversations = conversation_manager.get_all_conversations()
        
        all_documents = []
        
        for conv in conversations:
            conv_id = conv["id"]
            conv_data = conversation_manager.load_conversation(conv_id)
            
            if conv_data and conv_data.get("messages"):
                blocks = self._split_into_blocks(conv_data["messages"])
                
                for i, block in enumerate(blocks):
                    text = self._block_to_text(block)
                    doc = Document(
                        page_content=text,
                        metadata={
                            "conversation_id": conv_id,
                            "block_idx": i,
                            "user_idx": block["user_idx"],
                            "source": "history"
                        }
                    )
                    all_documents.append(doc)
                
                self.conversation_blocks[conv_id] = blocks
        
        if all_documents:
            try:
                if len(all_documents) > 100:
                    batches = [all_documents[i:i+100] for i in range(0, len(all_documents), 100)]
                    for batch in batches:
                        batch_store = FAISS.from_documents(batch, embedding_model)
                        if self.vector_store is None:
                            self.vector_store = batch_store
                        else:
                            self.vector_store.merge_from(batch_store)
                else:
                    self.vector_store = FAISS.from_documents(all_documents, embedding_model)
                print(f"历史对话索引构建完成，共 {len(all_documents)} 个块")
            except Exception as e:
                print(f"构建全部索引失败: {str(e)}")
    
    def search(self, query: str, k: int = 5) -> List[Dict]:
        if self.vector_store is None:
            return []
        
        try:
            results = self.vector_store.similarity_search(query, k=k)
            
            formatted_results = []
            for doc in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "conversation_id": doc.metadata.get("conversation_id"),
                    "block_idx": doc.metadata.get("block_idx"),
                    "source": doc.metadata.get("source")
                })
            
            return formatted_results
        except Exception as e:
            print(f"搜索失败: {str(e)}")
            return []
    
    def get_context_for_query(self, query: str, max_blocks: int = 3) -> str:
        results = self.search(query, k=max_blocks)
        
        if not results:
            return ""
        
        context_parts = ["以下是相关的历史对话片段：\n"]
        for i, result in enumerate(results, 1):
            context_parts.append(f"--- 片段 {i} ---")
            context_parts.append(result["content"])
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def remove_conversation(self, conversation_id: str):
        if conversation_id in self.conversation_blocks:
            del self.conversation_blocks[conversation_id]
    
    def save_index(self):
        if self.vector_store is not None:
            try:
                self.vector_store.save_local(self.vector_store_path)
                return True
            except Exception as e:
                print(f"保存索引失败: {str(e)}")
                return False
        return False
    
    def load_index(self) -> bool:
        if os.path.exists(self.vector_store_path):
            try:
                self.vector_store = FAISS.load_local(
                    self.vector_store_path, 
                    embedding_model,
                    allow_dangerous_deserialization=True
                )
                return True
            except Exception as e:
                print(f"加载索引失败: {str(e)}")
                return False
        return False


history_rag = HistoryRAG()
