from datetime import datetime
import uuid
import copy
import threading
import queue


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
    def __init__(self, conversation_id=None):
        self.id = conversation_id or str(uuid.uuid4())
        self.name = "新对话"
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.vector_store = None
        self.document_file = None
        self.images = []
        self.messages = []
        self.summary = None

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
        self.conversations = {}
        self.current_conversation_id = None
        self.max_context_turns = 5
        self.speech_recognition_lang = 'zh-CN'
        self.speech_synthesis_lang = 'zh-CN'
        self.max_recording_time = 30
        self.is_generating = False
        self.should_stop = False
        self.response_queue = queue.Queue()

    def create_conversation(self):
        conv = Conversation()
        self.conversations[conv.id] = conv
        if self.current_conversation_id is None:
            self.current_conversation_id = conv.id
        return conv

    def get_current_conversation(self):
        if self.current_conversation_id is None:
            return self.create_conversation()
        return self.conversations.get(self.current_conversation_id)

    def delete_conversation(self, conversation_id):
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
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
        new_conv = Conversation()
        new_conv.name = f"{source.name} (副本)"
        new_conv.vector_store = source.vector_store
        new_conv.document_file = source.document_file
        new_conv.images = copy.deepcopy(source.images)
        new_conv.messages = copy.deepcopy(source.messages)
        new_conv.summary = source.summary
        self.conversations[new_conv.id] = new_conv
        self.current_conversation_id = new_conv.id
        return new_conv

    def switch_conversation(self, conversation_id):
        if conversation_id in self.conversations:
            self.current_conversation_id = conversation_id
            return True
        return False


state = AppState()
