from flask import Blueprint, jsonify
from extensions import state

conversations_bp = Blueprint('conversations', __name__)

@conversations_bp.route('', methods=['GET'])
def get_conversations():
    conversations_list = [conv.to_dict() for conv in state.conversations.values()]
    return jsonify({
        'conversations': sorted(conversations_list, key=lambda x: x['updated_at'], reverse=True),
        'current_id': state.current_conversation_id
    })

@conversations_bp.route('', methods=['POST'])
def create_conversation():
    conv = state.create_conversation()
    state.current_conversation_id = conv.id
    return jsonify({'success': True, 'conversation': conv.to_dict()})

@conversations_bp.route('/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    if state.delete_conversation(conversation_id):
        return jsonify({'success': True, 'current_id': state.current_conversation_id})
    return jsonify({'error': '对话不存在'}), 404

@conversations_bp.route('/<conversation_id>/fork', methods=['POST'])
def fork_conversation(conversation_id):
    new_conv = state.fork_conversation(conversation_id)
    if new_conv:
        return jsonify({'success': True, 'conversation': new_conv.to_dict()})
    return jsonify({'error': '源对话不存在'}), 404

@conversations_bp.route('/<conversation_id>/switch', methods=['POST'])
def switch_conversation(conversation_id):
    if state.switch_conversation(conversation_id):
        conv = state.get_current_conversation()
        return jsonify({'success': True, 'conversation': conv.to_dict()})
    return jsonify({'error': '对话不存在'}), 404

@conversations_bp.route('/<conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    if conversation_id not in state.conversations:
        return jsonify({'error': '对话不存在'}), 404
    conv = state.conversations[conversation_id]
    return jsonify({
        'messages': [msg.to_dict() for msg in conv.messages],
        'document_file': conv.document_file
    })
