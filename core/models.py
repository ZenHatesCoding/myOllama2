from datetime import datetime
import uuid
import copy
import threading
import queue
from storage.conversation import conversation_manager
from config.manager import load_config


class Message:
    def __init__(self, role, content, images=None):
        self.role = role
        self.content = content
        self.images = images or []
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            'role': self.role,
            'content': self.content,
            'images': self.images,
            'timestamp': self.timestamp.isoformat()
        }


class Conversation:
    def __init__(self, conversation_id=None, from_persisted=None):
        if from_persisted:
            self.id = from_persisted.get("id", str(uuid.uuid4()))
            self.name = from_persisted.get("name", "新对话")
            self.created_at = datetime.fromisoformat(from_persisted["created_at"]) if from_persisted.get("created_at") else datetime.now()
            self.updated_at = datetime.fromisoformat(from_persisted["updated_at"]) if from_persisted.get("updated_at") else datetime.now()
            self.document_file = from_persisted.get("document_file")
            self.document_summary = from_persisted.get("document_summary")
            self.images = from_persisted.get("images", [])
            self.summary = from_persisted.get("summary")
            
            self.messages = []
            for msg in from_persisted.get("messages", []):
                message = Message(msg["role"], msg["content"])
                self.messages.append(message)
        else:
            self.id = conversation_id or str(uuid.uuid4())
            self.name = "新对话"
            self.created_at = datetime.now()
            self.updated_at = datetime.now()
            self.vector_store = None
            self.document_file = None
            self.document_summary = None
            self.document_chunks = []
            self.images = []
            self.messages = []
            self.summary = None
        
        self.vector_store = None
        self.document_chunks = []

    def add_message(self, role, content, images=None):
        message = Message(role, content, images)
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message

    def get_total_turns(self):
        return len(self.messages) // 2

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'document_file': self.document_file,
            'images': self.images,
            'message_count': len(self.messages),
            'summary': self.summary
        }


class AppState:
    def __init__(self):
        config = load_config()
        
        self.conversations = {}
        self.current_conversation_id = None
        self.max_context_turns = config.get("max_context_turns", 5)
        self.speech_recognition_lang = config.get("speech_recognition_lang", "zh-CN")
        self.speech_synthesis_lang = config.get("speech_synthesis_lang", "zh-CN")
        self.max_recording_time = config.get("max_recording_time", 30)
        self.is_generating = False
        self.should_stop = False
        self.response_queue = queue.Queue()
        
        self.llm_provider = config.get("llm_provider", "ollama")
        self.ollama_base_url = config.get("ollama_base_url", "http://localhost:11434")

        self.openai_endpoints = config.get("openai_endpoints", [])
        self.openai_current_endpoint = config.get("openai_current_endpoint", "")
        self.openai_current_model = config.get("openai_current_model", "")

        self.anthropic_endpoints = config.get("anthropic_endpoints", [])
        self.anthropic_current_endpoint = config.get("anthropic_current_endpoint", "")
        self.anthropic_current_model = config.get("anthropic_current_model", "")

        self._load_from_persistence()

    def get_current_openai_endpoint(self):
        for ep in self.openai_endpoints:
            if ep.get("name") == self.openai_current_endpoint:
                return ep
        return None

    def get_openai_base_url(self):
        ep = self.get_current_openai_endpoint()
        return ep.get("base_url", "") if ep else ""

    def get_openai_api_key(self):
        ep = self.get_current_openai_endpoint()
        return ep.get("api_key", "") if ep else ""

    def get_current_anthropic_endpoint(self):
        for ep in self.anthropic_endpoints:
            if ep.get("name") == self.anthropic_current_endpoint:
                return ep
        return None

    def get_anthropic_base_url(self):
        ep = self.get_current_anthropic_endpoint()
        return ep.get("base_url", "") if ep else ""

    def get_anthropic_api_key(self):
        ep = self.get_current_anthropic_endpoint()
        return ep.get("api_key", "") if ep else ""

    def _load_from_persistence(self):
        conversation_manager.validate_index()
        
        persisted_convs = conversation_manager.get_all_conversations()
        
        for conv_meta in persisted_convs:
            conv_id = conv_meta["id"]
            conv_data = conversation_manager.load_conversation(conv_id)
            
            if conv_data:
                conv = Conversation(from_persisted=conv_data)
                self.conversations[conv_id] = conv
        
        if persisted_convs:
            self.current_conversation_id = persisted_convs[0]["id"]
        
        if self.llm_provider == "ollama":
            from storage.history_rag import history_rag
            history_rag.build_all_index()

    def create_conversation(self):
        conv_data = conversation_manager.create_conversation()
        conv_id = conv_data["id"]
        
        conv = Conversation(conversation_id=conv_id)
        conv.name = conv_data["name"]
        conv.created_at = datetime.fromisoformat(conv_data["created_at"])
        conv.updated_at = datetime.fromisoformat(conv_data["updated_at"])
        
        self.conversations[conv_id] = conv
        if self.current_conversation_id is None:
            self.current_conversation_id = conv_id
        
        return conv

    def get_current_conversation(self):
        if self.current_conversation_id is None:
            return self.create_conversation()
        return self.conversations.get(self.current_conversation_id)

    def delete_conversation(self, conversation_id):
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            
            conversation_manager.delete_conversation(conversation_id)
            if self.llm_provider == "ollama":
                from storage.history_rag import history_rag
                history_rag.delete_conversation_index(conversation_id)
            
            if self.current_conversation_id == conversation_id:
                if self.conversations:
                    self.current_conversation_id = list(self.conversations.keys())[0]
                else:
                    self.create_conversation()
            return True
        return False

    def fork_conversation(self, source_id):
        if source_id not in self.conversations:
            return None
        source = self.conversations[source_id]
        
        new_conv_data = conversation_manager.create_conversation(
            name=f"{source.name} (副本)"
        )
        new_conv_id = new_conv_data["id"]
        new_conv = Conversation(conversation_id=new_conv_id)
        new_conv.name = new_conv_data["name"]
        new_conv.images = copy.deepcopy(source.images)
        
        for msg in source.messages:
            new_conv.add_message(msg.role, msg.content, msg.images if hasattr(msg, 'images') else None)
        
        self.conversations[new_conv_id] = new_conv
        
        return new_conv

    def persist_message(self, role: str, content: str, images=None):
        conv = self.get_current_conversation()
        conversation_manager.append_message(conv.id, role, content, images)

    def persist_conversation_name(self, name: str):
        if self.current_conversation_id:
            conversation_manager.update_conversation_name(self.current_conversation_id, name)

    def persist_summary(self, summary: str):
        if self.current_conversation_id:
            conversation_manager.update_summary(self.current_conversation_id, summary)

    def switch_conversation(self, conversation_id: str):
        if conversation_id in self.conversations:
            self.current_conversation_id = conversation_id
            return True
        return False
