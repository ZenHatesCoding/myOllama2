from flask import Blueprint, jsonify, Response, request
from core import state
import threading
import asyncio

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/messages', methods=['POST'])
def generate():
    if state.is_generating:
        return jsonify({'error': '正在生成回答中，请稍候...'}), 400

    data = request.json
    query = data.get('query', '').strip()
    model_name = data.get('model', 'qwen3.5:9b')
    images = data.get('images', [])
    mode = data.get('mode', 'qa')

    if not query and not images:
        return jsonify({'error': '请输入问题或上传图片'}), 400

    conversation = state.get_current_conversation()

    state.is_generating = True
    state.should_stop = False

    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from utils import generate_answer
            loop.run_until_complete(generate_answer(query, model_name, mode))
        finally:
            loop.close()

    thread = threading.Thread(target=run_async_task)
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'message': '开始生成回答',
        'conversation_id': conversation.id
    })


@chat_bp.route('/stop', methods=['POST'])
def stop():
    if state.is_generating:
        state.should_stop = True
        return jsonify({'success': True, 'message': '正在中断操作...'})
    return jsonify({'error': '没有正在进行的操作'}), 400


@chat_bp.route('/stream')
def stream():
    import queue

    def event_stream():
        while True:
            try:
                msg_type, content = state.response_queue.get(timeout=0.1)
                if msg_type == "chunk":
                    yield f"data: [chunk]{content}\n\n"
                elif msg_type == "progress":
                    yield f"data: [PROGRESS]{content}\n\n"
                elif msg_type == "done":
                    yield f"data: [DONE]\n\n"
                    break
                elif msg_type == "error":
                    yield f"data: [ERROR]{content}\n\n"
                    break
            except queue.Empty:
                if not state.is_generating:
                    yield f"data: [DONE]\n\n"
                    break
                continue

    return Response(event_stream(), mimetype='text/event-stream')


@chat_bp.route('/status')
def status():
    conv = state.get_current_conversation()
    return jsonify({
        'is_generating': state.is_generating,
        'has_document': conv.vector_store is not None if conv else False,
        'current_document': conv.document_file if conv else None,
        'message_count': len(conv.messages) if conv else 0,
        'max_context_turns': state.max_context_turns
    })
