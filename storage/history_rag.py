import os
from typing import List, Dict, Optional
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

from storage.conversation import conversation_manager


def get_embedding_model(base_url: str):
    return OllamaEmbeddings(
        model="nomic-embed-text",
        base_url=base_url
    )


class HistoryRAG:
    def __init__(self):
        self.vector_store = None
        self.conversation_blocks = {}
        self.vector_store_path = os.path.join(
            conversation_manager.vector_stores_dir, 
            "history"
        )

    def build_index(self, conversation_id: str) -> bool:
        conv_data = conversation_manager.load_conversation(conversation_id)
        
        if not conv_data or not conv_data.get("messages"):
            return False
        
        messages = conv_data["messages"]
        
        documents = []
        for idx, msg in enumerate(messages):
            if msg.get("role") == "user":
                user_content = msg.get("content", "")
                
                assistant_content = ""
                for a_idx in range(idx + 1, len(messages)):
                    if messages[a_idx].get("role") == "assistant":
                        assistant_content = messages[a_idx].get("content", "")
                        break
                
                if user_content:
                    block = {
                        "conversation_id": conversation_id,
                        "user_idx": idx,
                        "content": f"用户: {user_content}\n助手: {assistant_content}"
                    }
                    
                    doc = Document(
                        page_content=block["content"],
                        metadata={
                            "conversation_id": conversation_id,
                            "user_idx": idx,
                            "source": "history"
                        }
                    )
                    documents.append(doc)
        
        try:
            if documents:
                base_url = "http://localhost:11434"
                embedding = get_embedding_model(base_url)
                new_store = FAISS.from_documents(documents, embedding)
                
                if self.vector_store is None:
                    self.vector_store = new_store
                else:
                    self.vector_store.merge_from(new_store)
                
                self.conversation_blocks[conversation_id] = documents
                
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
            
            if not conv_data or not conv_data.get("messages"):
                continue
            
            messages = conv_data["messages"]
            conv_documents = []
            
            for idx, msg in enumerate(messages):
                if msg.get("role") == "user":
                    user_content = msg.get("content", "")
                    
                    assistant_content = ""
                    for a_idx in range(idx + 1, len(messages)):
                        if messages[a_idx].get("role") == "assistant":
                            assistant_content = messages[a_idx].get("content", "")
                            break
                    
                    if user_content:
                        block = {
                            "conversation_id": conv_id,
                            "user_idx": idx,
                            "content": f"用户: {user_content}\n助手: {assistant_content}"
                        }
                        
                        doc = Document(
                            page_content=block["content"],
                            metadata={
                                "conversation_id": conv_id,
                                "user_idx": idx,
                                "source": "history"
                            }
                        )
                        all_documents.append(doc)
                        conv_documents.append(doc)
            
            if conv_documents:
                self.conversation_blocks[conv_id] = conv_documents
        
        if all_documents:
            try:
                base_url = "http://localhost:11434"
                embedding = get_embedding_model(base_url)
                if len(all_documents) > 100:
                    batches = [all_documents[i:i+100] for i in range(0, len(all_documents), 100)]
                    for batch in batches:
                        batch_store = FAISS.from_documents(batch, embedding)
                        if self.vector_store is None:
                            self.vector_store = batch_store
                        else:
                            self.vector_store.merge_from(batch_store)
                else:
                    self.vector_store = FAISS.from_documents(all_documents, embedding)
                print(f"历史对话索引构建完成，共 {len(all_documents)} 个块")
            except Exception as e:
                print(f"构建全部索引失败: {str(e)}")
    
    def search(self, query: str, k: int = 5) -> List[Dict]:
        if self.vector_store is None:
            return []
        
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            results = []
            for doc in docs:
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata
                })
            return results
        except Exception as e:
            print(f"搜索失败: {str(e)}")
            return []
    
    def clear(self):
        self.vector_store = None
        self.conversation_blocks = {}

    def delete_conversation_index(self, conversation_id: str) -> bool:
        try:
            if conversation_id in self.conversation_blocks:
                del self.conversation_blocks[conversation_id]
            return True
        except Exception as e:
            print(f"删除对话索引失败: {str(e)}")
            return False

    def save_index(self) -> bool:
        if self.vector_store is None:
            return False

        try:
            os.makedirs(self.vector_store_path, exist_ok=True)
            self.vector_store.save_local(self.vector_store_path)
            return True
        except Exception as e:
            print(f"保存索引失败: {str(e)}")
            return False

    def load_index(self) -> bool:
        if os.path.exists(self.vector_store_path):
            try:
                base_url = "http://localhost:11434"
                embedding = get_embedding_model(base_url)
                self.vector_store = FAISS.load_local(
                    self.vector_store_path,
                    embedding,
                    allow_dangerous_deserialization=True
                )
                return True
            except Exception as e:
                print(f"加载索引失败: {str(e)}")
                return False
        return False

    def get_context(self, query: str, provider: str, llm=None, k: int = 3) -> Optional[str]:
        if provider == "ollama" and self.vector_store:
            return self._get_context_with_faiss(query, k)
        else:
            return self._get_context_with_llm(query, llm, k)

    def _get_context_with_faiss(self, query: str, k: int = 3) -> Optional[str]:
        results = self.search(query, k=k)
        if not results:
            return None

        context_parts = []
        for r in results:
            context_parts.append(f"[历史对话 {r['conversation_id']}]\n{r['content']}")

        return "以下是历史对话中与当前问题相关的内容：\n\n" + "\n\n".join(context_parts)

    def _get_context_with_llm(self, query: str, llm, k: int = 3) -> Optional[str]:
        if not llm:
            return None

        conversations = conversation_manager.get_all_conversations()
        if not conversations:
            return None

        conv_list = []
        for c in conversations:
            conv_list.append(f"- ID: {c['id']}, 名称: {c['name']}, 摘要: {c.get('summary', '无')}")

        conv_list_str = "\n".join(conv_list[:20])

        prompt = f"""当前问题：{query}

历史对话列表：
{conv_list_str}

请选择与当前问题最相关的最多{k}个对话，返回对话ID列表（用逗号分隔）。只返回ID，不要有其他内容。"""

        try:
            response = llm.invoke(prompt)
            selected_ids = [s.strip() for s in response.content.split(",") if s.strip()]
            selected_ids = selected_ids[:k]
        except Exception as e:
            print(f"LLM 选择历史对话失败: {str(e)}")
            return None

        context_parts = []
        for conv_id in selected_ids:
            conv_data = conversation_manager.load_conversation(conv_id)
            if conv_data and conv_data.get("messages"):
                messages = conv_data["messages"][-6:]
                content = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in messages if m.get("content")])
                context_parts.append(f"[历史对话 {conv_data.get('name', conv_id)}]\n{content}")

        if not context_parts:
            return None

        return "以下是历史对话中与当前问题相关的内容：\n\n" + "\n\n".join(context_parts)


history_rag = HistoryRAG()
