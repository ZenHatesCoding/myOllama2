import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class ConversationManager:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.base_dir = base_dir
        self.conversations_dir = os.path.join(base_dir, "conversations")
        self.assets_dir = os.path.join(base_dir, "assets")
        self.vector_stores_dir = os.path.join(base_dir, "vector_stores", "history")
        self.index_path = os.path.join(self.conversations_dir, "index.json")
        
        self._ensure_directories()
        self.index = self._load_or_create_index()
    
    def _ensure_directories(self):
        os.makedirs(self.conversations_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)
        os.makedirs(self.vector_stores_dir, exist_ok=True)
    
    def _load_or_create_index(self) -> Dict:
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        return {
            "version": "1.0",
            "conversations": []
        }
    
    def _save_index(self):
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
    
    def _get_md_path(self, conversation_id: str) -> str:
        return os.path.join(self.conversations_dir, f"{conversation_id}.md")
    
    def _get_assets_path(self, conversation_id: str) -> str:
        return os.path.join(self.assets_dir, conversation_id)
    
    def _parse_frontmatter(self, content: str) -> tuple:
        if content.startswith("---\n"):
            parts = content.split("---\n", 2)
            if len(parts) >= 3:
                frontmatter_str = parts[1]
                body = parts[2]
                
                frontmatter = {}
                for line in frontmatter_str.strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        frontmatter[key.strip()] = value.strip()
                
                return frontmatter, body
        
        return {}, content
    
    def _format_frontmatter(self, metadata: Dict) -> str:
        lines = ["---"]
        for key, value in metadata.items():
            lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)
    
    def create_conversation(self, conversation_id: str = None, name: str = "新对话", model: str = "qwen3.5:9b") -> Dict:
        if conversation_id is None:
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        
        now = datetime.now().isoformat()
        
        metadata = {
            "id": conversation_id,
            "name": name,
            "created": now,
            "updated": now,
            "model": model,
            "message_count": 0
        }
        
        content = self._format_frontmatter(metadata)
        content += "# 对话记录\n\n"
        
        md_path = self._get_md_path(conversation_id)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        index_entry = {
            "id": conversation_id,
            "name": name,
            "created": now,
            "updated": now,
            "message_count": 0,
            "has_images": False,
            "has_document": False
        }
        self.index["conversations"].append(index_entry)
        self._save_index()
        
        return {
            "id": conversation_id,
            "name": name,
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "images": [],
            "document_file": None,
            "summary": None
        }
    
    def load_conversation(self, conversation_id: str) -> Optional[Dict]:
        md_path = self._get_md_path(conversation_id)
        
        if not os.path.exists(md_path):
            return None
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata, body = self._parse_frontmatter(content)
            
            messages = self._parse_messages(body)
            
            assets_path = self._get_assets_path(conversation_id)
            images = []
            if os.path.exists(assets_path):
                for filename in os.listdir(assets_path):
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                        img_path = os.path.join(assets_path, filename)
                        with open(img_path, 'rb') as f:
                            import base64
                            img_data = base64.b64encode(f.read()).decode('utf-8')
                            images.append({
                                "name": filename,
                                "data": img_data
                            })
            
            return {
                "id": metadata.get("id", conversation_id),
                "name": metadata.get("name", "新对话"),
                "created_at": metadata.get("created", ""),
                "updated_at": metadata.get("updated", ""),
                "model": metadata.get("model", "qwen3.5:4b"),
                "document_file": metadata.get("document"),
                "message_count": int(metadata.get("message_count", 0)),
                "messages": messages,
                "images": images,
                "summary": metadata.get("summary")
            }
        except Exception as e:
            print(f"加载对话失败: {str(e)}")
            return None
    
    def _parse_messages(self, body: str) -> List[Dict]:
        messages = []
        current_role = None
        current_content = []
        
        for line in body.split("\n"):
            if line.startswith("## User"):
                if current_role and current_content:
                    messages.append({
                        "role": current_role,
                        "content": "\n".join(current_content).strip()
                    })
                current_role = "user"
                current_content = []
            elif line.startswith("## Assistant"):
                if current_role and current_content:
                    messages.append({
                        "role": current_role,
                        "content": "\n".join(current_content).strip()
                    })
                current_role = "assistant"
                current_content = []
            elif current_role:
                current_content.append(line)
        
        if current_role and current_content:
            messages.append({
                "role": current_role,
                "content": "\n".join(current_content).strip()
            })
        
        return messages
    
    def append_message(self, conversation_id: str, role: str, content: str, images: List[Dict] = None):
        md_path = self._get_md_path(conversation_id)
        
        if not os.path.exists(md_path):
            return False
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            metadata, body = self._parse_frontmatter(file_content)
            
            role_label = "User" if role == "user" else "Assistant" if role == "assistant" else "System"
            message_text = f"\n## {role_label}\n{content}\n"
            
            if images:
                assets_path = self._get_assets_path(conversation_id)
                os.makedirs(assets_path, exist_ok=True)
                
                for i, img in enumerate(images):
                    img_name = f"img_{len(os.listdir(assets_path)) + 1}.jpg"
                    img_path = os.path.join(assets_path, img_name)
                    
                    import base64
                    img_data = img.get("data", "")
                    if img_data:
                        with open(img_path, 'wb') as f:
                            f.write(base64.b64decode(img_data))
            
            with open(md_path, 'a', encoding='utf-8') as f:
                f.write(message_text)
            
            metadata["updated"] = datetime.now().isoformat()
            metadata["message_count"] = int(metadata.get("message_count", 0)) + 1
            
            new_frontmatter = self._format_frontmatter(metadata)
            new_content = new_frontmatter + body + message_text
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self._update_index_entry(conversation_id, {
                "updated": metadata["updated"],
                "message_count": metadata["message_count"],
                "has_images": images is not None and len(images) > 0
            })
            
            return True
        except Exception as e:
            print(f"追加消息失败: {str(e)}")
            return False
    
    def update_conversation_name(self, conversation_id: str, name: str):
        md_path = self._get_md_path(conversation_id)
        
        if not os.path.exists(md_path):
            return False
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata, body = self._parse_frontmatter(content)
            metadata["name"] = name
            metadata["updated"] = datetime.now().isoformat()
            
            new_content = self._format_frontmatter(metadata) + body
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self._update_index_entry(conversation_id, {
                "name": name,
                "updated": metadata["updated"]
            })
            
            return True
        except Exception as e:
            print(f"更新对话名称失败: {str(e)}")
            return False
    
    def update_summary(self, conversation_id: str, summary: str):
        md_path = self._get_md_path(conversation_id)
        
        if not os.path.exists(md_path):
            return False
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata, body = self._parse_frontmatter(content)
            metadata["summary"] = summary
            metadata["updated"] = datetime.now().isoformat()
            
            new_content = self._format_frontmatter(metadata) + body
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self._update_index_entry(conversation_id, {
                "updated": metadata["updated"]
            })
            
            return True
        except Exception as e:
            print(f"更新摘要失败: {str(e)}")
            return False
    
    def delete_conversation(self, conversation_id: str) -> bool:
        md_path = self._get_md_path(conversation_id)
        assets_path = self._get_assets_path(conversation_id)
        
        try:
            if os.path.exists(md_path):
                os.remove(md_path)
            
            if os.path.exists(assets_path):
                shutil.rmtree(assets_path)
            
            self.index["conversations"] = [
                c for c in self.index["conversations"] 
                if c["id"] != conversation_id
            ]
            self._save_index()
            
            return True
        except Exception as e:
            print(f"删除对话失败: {str(e)}")
            return False
    
    def _update_index_entry(self, conversation_id: str, updates: Dict):
        for entry in self.index["conversations"]:
            if entry["id"] == conversation_id:
                entry.update(updates)
                break
        self._save_index()
    
    def validate_index(self) -> List[Dict]:
        valid_conversations = []
        
        for entry in self.index["conversations"]:
            md_path = self._get_md_path(entry["id"])
            if os.path.exists(md_path):
                valid_conversations.append(entry)
            else:
                print(f"对话 {entry['id']} 的文件已丢失，从索引移除")
        
        self.index["conversations"] = valid_conversations
        self._save_index()
        
        return valid_conversations
    
    def get_all_conversations(self) -> List[Dict]:
        return sorted(
            self.index["conversations"], 
            key=lambda x: x.get("updated", ""), 
            reverse=True
        )
    
    def conversation_exists(self, conversation_id: str) -> bool:
        md_path = self._get_md_path(conversation_id)
        return os.path.exists(md_path)
    
    def set_document(self, conversation_id: str, document_file: str):
        md_path = self._get_md_path(conversation_id)
        
        if not os.path.exists(md_path):
            return False
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata, body = self._parse_frontmatter(content)
            metadata["document"] = document_file
            metadata["updated"] = datetime.now().isoformat()
            
            new_content = self._format_frontmatter(metadata) + body
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self._update_index_entry(conversation_id, {
                "has_document": document_file is not None,
                "updated": metadata["updated"]
            })
            
            return True
        except Exception as e:
            print(f"设置文档失败: {str(e)}")
            return False


conversation_manager = ConversationManager()
