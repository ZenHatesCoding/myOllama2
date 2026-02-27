import threading
import os
import tempfile
from flask import request, jsonify, Response, render_template
from models import state
from utils import (
    load_document, process_document, generate_summary,
    process_image, encode_image_to_base64, prepare_messages,
    generate_answer, auto_name_conversation
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from utils import embedding_model


def register_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')


    @app.route('/api/conversations', methods=['GET'])
    def get_conversations():
        conversations_list = [conv.to_dict() for conv in state.conversations.values()]
        return jsonify({
            'conversations': sorted(conversations_list, key=lambda x: x['updated_at'], reverse=True),
            'current_id': state.current_conversation_id
        })


    @app.route('/api/conversations', methods=['POST'])
    def create_conversation():
        conv = state.create_conversation()
        state.current_conversation_id = conv.id
        return jsonify({'success': True, 'conversation': conv.to_dict()})


    @app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
    def delete_conversation(conversation_id):
        if state.delete_conversation(conversation_id):
            return jsonify({'success': True, 'current_id': state.current_conversation_id})
        return jsonify({'error': '对话不存在'}), 404


    @app.route('/api/conversations/<conversation_id>/fork', methods=['POST'])
    def fork_conversation(conversation_id):
        new_conv = state.fork_conversation(conversation_id)
        if new_conv:
            return jsonify({'success': True, 'conversation': new_conv.to_dict()})
        return jsonify({'error': '源对话不存在'}), 404


    @app.route('/api/conversations/<conversation_id>/switch', methods=['POST'])
    def switch_conversation(conversation_id):
        if state.switch_conversation(conversation_id):
            conv = state.get_current_conversation()
            return jsonify({'success': True, 'conversation': conv.to_dict()})
        return jsonify({'error': '对话不存在'}), 404


    @app.route('/api/conversations/<conversation_id>/messages', methods=['GET'])
    def get_messages(conversation_id):
        if conversation_id not in state.conversations:
            return jsonify({'error': '对话不存在'}), 404
        conv = state.conversations[conversation_id]
        return jsonify({
            'messages': [msg.to_dict() for msg in conv.messages],
            'document_file': conv.document_file
        })


    @app.route('/api/documents/upload', methods=['POST'])
    def upload_file():
        conversation = state.get_current_conversation()
        
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400

        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file_path = temp_file.name
            temp_file.close()
            file.save(temp_file_path)
            
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            
            docs = load_document(temp_file_path, file_ext)
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                length_function=len
            )
            document_chunks = text_splitter.split_documents(docs)
            
            conversation.vector_store = FAISS.from_documents(document_chunks, embedding_model)
            conversation.document_file = file.filename
            
            try:
                os.unlink(temp_file_path)
            except:
                pass
            
            return jsonify({
                'success': True,
                'message': f'{file_ext.upper()}文件解析完成，共生成 {len(document_chunks)} 个文本块',
                'document_file': file.filename
            })
        except Exception as e:
            try:
                if 'temp_file_path' in locals():
                    os.unlink(temp_file_path)
            except:
                pass
            return jsonify({'error': f'文件解析失败：{str(e)}'}), 500


    @app.route('/api/documents/remove', methods=['DELETE'])
    def remove_document():
        conversation = state.get_current_conversation()
        conversation.vector_store = None
        conversation.document_file = None
        return jsonify({'success': True, 'message': '文档已移除'})


    @app.route('/api/images/upload', methods=['POST'])
    def upload_image():
        conversation = state.get_current_conversation()
        
        data = request.json
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': '没有图片'}), 400
        
        try:
            image_path = process_image(image_data)
            if not image_path:
                return jsonify({'error': '图片处理失败'}), 500
            
            image_base64 = encode_image_to_base64(image_path)
            if not image_base64:
                return jsonify({'error': '图片编码失败'}), 500
            
            image_info = {
                'name': f'image_{len(conversation.images) + 1}',
                'data': image_base64
            }
            conversation.images.append(image_info)
            
            try:
                os.unlink(image_path)
            except:
                pass
            
            return jsonify({
                'success': True,
                'message': '图片上传成功',
                'images': conversation.images
            })
        except Exception as e:
            try:
                if 'image_path' in locals():
                    os.unlink(image_path)
            except:
                pass
            return jsonify({'error': f'图片上传失败：{str(e)}'}), 500


    @app.route('/api/images/remove', methods=['DELETE'])
    def remove_image():
        conversation = state.get_current_conversation()
        conversation.images = []
        return jsonify({'success': True, 'message': '图片已移除'})


    @app.route('/api/screenshot', methods=['POST'])
    def screenshot():
        import subprocess
        import sys
        
        conversation = state.get_current_conversation()
        
        try:
            script_path = os.path.join(os.path.dirname(__file__), 'screenshot.py')
            
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return jsonify({'error': f'截图失败：{result.stderr}'}), 500
            
            output = result.stdout.strip()
            
            if output == "CANCELLED":
                return jsonify({'error': '截图已取消'}), 400
            
            image_data = output
            
            try:
                image_path = process_image(f"data:image/png;base64,{image_data}")
            except:
                image_path = None
            
            if not image_path:
                image_info = {
                    'name': f'image_{len(conversation.images) + 1}',
                    'data': image_data
                }
                conversation.images.append(image_info)
                
                return jsonify({
                    'success': True,
                    'message': '截图成功',
                    'images': conversation.images
                })
            
            image_base64 = encode_image_to_base64(image_path)
            if not image_base64:
                return jsonify({'error': '图片编码失败'}), 500
            
            image_info = {
                'name': f'image_{len(conversation.images) + 1}',
                'data': image_base64
            }
            conversation.images.append(image_info)
            
            try:
                os.unlink(image_path)
            except:
                pass
            
            return jsonify({
                'success': True,
                'message': '截图成功',
                'images': conversation.images
            })
            
        except subprocess.TimeoutExpired:
            return jsonify({'error': '截图超时，请重试'}), 500
        except Exception as e:
            return jsonify({'error': f'截图失败：{str(e)}'}), 500


    @app.route('/api/images/remove/<int:index>', methods=['DELETE'])
    def remove_single_image(index):
        conversation = state.get_current_conversation()
        if 0 <= index < len(conversation.images):
            conversation.images.pop(index)
            return jsonify({'success': True, 'message': '图片已移除', 'images': conversation.images})
        return jsonify({'error': '无效的图片索引'}), 400


    @app.route('/api/messages', methods=['POST'])
    def generate():
        if state.is_generating:
            return jsonify({'error': '正在生成回答中，请稍候...'}), 400
        
        data = request.json
        query = data.get('query', '').strip()
        model_name = data.get('model', 'qwen3:8b')
        images = data.get('images', [])
        
        if not query and not images:
            return jsonify({'error': '请输入问题或上传图片'}), 400
        
        conversation = state.get_current_conversation()
        
        state.is_generating = True
        state.should_stop = False
        
        import asyncio
        
        def run_async_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(generate_answer(query, model_name))
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


    @app.route('/api/stop', methods=['POST'])
    def stop():
        if state.is_generating:
            state.should_stop = True
            return jsonify({'success': True, 'message': '正在中断操作...'})
        return jsonify({'error': '没有正在进行的操作'}), 400


    @app.route('/api/stream')
    def stream():
        import queue
        
        def event_stream():
            while True:
                try:
                    msg_type, content = state.response_queue.get(timeout=0.1)
                    if msg_type == "chunk":
                        yield f"data: {content}\n\n"
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


    @app.route('/api/status')
    def status():
        conv = state.get_current_conversation()
        return jsonify({
            'is_generating': state.is_generating,
            'has_document': conv.vector_store is not None,
            'current_document': conv.document_file,
            'message_count': len(conv.messages),
            'max_context_turns': state.max_context_turns
        })


    @app.route('/api/config', methods=['GET'])
    def get_config():
        return jsonify({
            'max_context_turns': state.max_context_turns,
            'speech_recognition_lang': state.speech_recognition_lang,
            'speech_synthesis_lang': state.speech_synthesis_lang,
            'max_recording_time': state.max_recording_time
        })


    @app.route('/api/config', methods=['PUT'])
    def update_config():
        data = request.json
        max_turns = data.get('max_context_turns')
        speech_recognition_lang = data.get('speech_recognition_lang')
        speech_synthesis_lang = data.get('speech_synthesis_lang')
        max_recording_time = data.get('max_recording_time')
        
        if max_turns is not None and isinstance(max_turns, int) and max_turns > 0:
            state.max_context_turns = max_turns
        
        if speech_recognition_lang:
            state.speech_recognition_lang = speech_recognition_lang
        
        if speech_synthesis_lang:
            state.speech_synthesis_lang = speech_synthesis_lang
        
        if max_recording_time is not None and isinstance(max_recording_time, int) and 5 <= max_recording_time <= 120:
            state.max_recording_time = max_recording_time
        
        return jsonify({
            'success': True,
            'max_context_turns': state.max_context_turns,
            'speech_recognition_lang': state.speech_recognition_lang,
            'speech_synthesis_lang': state.speech_synthesis_lang,
            'max_recording_time': state.max_recording_time
        })
