import threading
import os
import tempfile
import queue
from flask import request, jsonify, Response, render_template
from extensions import state
from skill_registry import skill_registry
from utils import (
    load_document, process_document, generate_summary,
    process_image, encode_image_to_base64, prepare_messages,
    generate_answer, auto_name_conversation, get_embedding_model, get_llm_model
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from config_manager import load_config, save_config


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
        if state.is_generating:
            return jsonify({'error': '正在处理中，请稍候...'}), 400
        
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
            
            state.is_generating = True
            state.should_stop = False
            state.response_queue = queue.Queue()
            
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            filename = file.filename
            
            def process_document_async():
                try:
                    state.response_queue.put(("progress", "正在解析文档..."))
                    
                    if state.should_stop:
                        state.response_queue.put(("error", "操作已中断"))
                        return
                    
                    docs = load_document(temp_file_path, file_ext)
                    
                    state.response_queue.put(("progress", f"文档已解析，正在分块..."))
                    
                    if state.should_stop:
                        state.response_queue.put(("error", "操作已中断"))
                        return
                    
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=500,
                        chunk_overlap=50,
                        length_function=len
                    )
                    document_chunks = text_splitter.split_documents(docs)
                    
                    total_chunks = len(document_chunks)
                    state.response_queue.put(("progress", f"已分块 {total_chunks} 个，正在建立索引..."))
                    
                    if state.should_stop:
                        state.response_queue.put(("error", "操作已中断"))
                        return
                    
                    for i, chunk in enumerate(document_chunks):
                        chunk.metadata["chunk_index"] = i
                    
                    if state.llm_provider == "ollama":
                        embedding = get_embedding_model(state.ollama_base_url)
                        conversation.vector_store = FAISS.from_documents(document_chunks, embedding)
                    conversation.document_file = filename
                    conversation.document_chunks = document_chunks
                    conversation.document_summary = None
                    
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass
                    
                    state.response_queue.put(("progress", "正在生成摘要..."))
                    
                    from agent import stream_graph
                    query = "请总结这个文档的主要内容"
                    
                    summary_text = ""
                    for chunk in stream_graph(query, model_name="qwen3.5:9b", mode="qa"):
                        if state.should_stop:
                            break
                        summary_text += chunk
                        state.response_queue.put(("chunk", chunk))
                    
                    if not state.should_stop:
                        conversation.document_summary = summary_text
                        conversation.add_message("user", f"上传文档《{filename}》，请总结")
                        conversation.add_message("assistant", summary_text)
                        state.persist_message("user", f"上传文档《{filename}》，请总结")
                        state.persist_message("assistant", summary_text)
                        state.response_queue.put(("done", f"{file_ext.upper()}文件解析完成，共生成 {total_chunks} 个文本块"))
                    else:
                        state.response_queue.put(("stopped", "操作已中断，文档已加载，可正常问答"))
                    
                except Exception as e:
                    state.response_queue.put(("error", f"处理失败：{str(e)}"))
                finally:
                    state.is_generating = False
            
            thread = threading.Thread(target=process_document_async)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': '开始解析文档',
                'conversation_id': conversation.id
            })
            
        except Exception as e:
            return jsonify({'error': f'上传失败：{str(e)}'}), 500
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
        conversation.summary = None
        conversation.document_chunks = []
        
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
        model_name = data.get('model', 'qwen3.5:9b')
        images = data.get('images', [])
        mode = data.get('mode', 'qa')
        
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
        config = load_config()
        return jsonify({
            'llm_provider': state.llm_provider,
            'ollama_base_url': state.ollama_base_url,
            'openai_endpoints': state.openai_endpoints,
            'openai_current_endpoint': state.openai_current_endpoint,
            'openai_current_model': state.openai_current_model,
            'anthropic_endpoints': state.anthropic_endpoints,
            'anthropic_current_endpoint': state.anthropic_current_endpoint,
            'anthropic_current_model': state.anthropic_current_model,
            'max_context_turns': state.max_context_turns,
            'speech_recognition_lang': state.speech_recognition_lang,
            'speech_synthesis_lang': state.speech_synthesis_lang,
            'max_recording_time': state.max_recording_time
        })


    @app.route('/api/config', methods=['PUT'])
    def update_config():
        data = request.json

        llm_provider = data.get('llm_provider')
        ollama_base_url = data.get('ollama_base_url')
        openai_endpoints = data.get('openai_endpoints')
        openai_current_endpoint = data.get('openai_current_endpoint')
        openai_current_model = data.get('openai_current_model')
        anthropic_endpoints = data.get('anthropic_endpoints')
        anthropic_current_endpoint = data.get('anthropic_current_endpoint')
        anthropic_current_model = data.get('anthropic_current_model')
        max_turns = data.get('max_context_turns')
        speech_recognition_lang = data.get('speech_recognition_lang')
        speech_synthesis_lang = data.get('speech_synthesis_lang')
        max_recording_time = data.get('max_recording_time')

        if llm_provider:
            state.llm_provider = llm_provider

        if ollama_base_url:
            state.ollama_base_url = ollama_base_url

        if openai_endpoints is not None:
            state.openai_endpoints = openai_endpoints
        if openai_current_endpoint is not None:
            state.openai_current_endpoint = openai_current_endpoint
        if openai_current_model is not None:
            state.openai_current_model = openai_current_model

        if anthropic_endpoints is not None:
            state.anthropic_endpoints = anthropic_endpoints
        if anthropic_current_endpoint is not None:
            state.anthropic_current_endpoint = anthropic_current_endpoint
        if anthropic_current_model is not None:
            state.anthropic_current_model = anthropic_current_model

        if max_turns is not None and isinstance(max_turns, int) and max_turns > 0:
            state.max_context_turns = max_turns

        if speech_recognition_lang:
            state.speech_recognition_lang = speech_recognition_lang

        if speech_synthesis_lang:
            state.speech_synthesis_lang = speech_synthesis_lang

        if max_recording_time is not None and isinstance(max_recording_time, int) and 5 <= max_recording_time <= 120:
            state.max_recording_time = max_recording_time

        config = load_config()
        config['llm_provider'] = state.llm_provider
        config['ollama_base_url'] = state.ollama_base_url
        config['openai_endpoints'] = state.openai_endpoints
        config['openai_current_endpoint'] = state.openai_current_endpoint
        config['openai_current_model'] = state.openai_current_model
        config['anthropic_endpoints'] = state.anthropic_endpoints
        config['anthropic_current_endpoint'] = state.anthropic_current_endpoint
        config['anthropic_current_model'] = state.anthropic_current_model
        config['max_context_turns'] = state.max_context_turns
        config['speech_recognition_lang'] = state.speech_recognition_lang
        config['speech_synthesis_lang'] = state.speech_synthesis_lang
        config['max_recording_time'] = state.max_recording_time
        save_config(config)

        return jsonify({
            'success': True,
            'max_context_turns': state.max_context_turns,
            'speech_recognition_lang': state.speech_recognition_lang,
            'speech_synthesis_lang': state.speech_synthesis_lang,
            'max_recording_time': state.max_recording_time
        })


    @app.route('/api/openai/endpoints', methods=['GET'])
    def get_openai_endpoints():
        return jsonify({
            'endpoints': state.openai_endpoints,
            'current_endpoint': state.openai_current_endpoint,
            'current_model': state.openai_current_model
        })


    @app.route('/api/openai/endpoints', methods=['POST'])
    def add_openai_endpoint():
        data = request.json
        name = data.get('name', '').strip()
        base_url = data.get('base_url', '').strip()
        api_key = data.get('api_key', '').strip()
        models = data.get('models', [])

        if not name:
            return jsonify({'success': False, 'error': '端点名称不能为空'}), 400
        if not base_url:
            return jsonify({'success': False, 'error': 'API 地址不能为空'}), 400

        for ep in state.openai_endpoints:
            if ep.get('name') == name:
                return jsonify({'success': False, 'error': '端点名称已存在'}), 400

        endpoint = {
            'name': name,
            'base_url': base_url,
            'api_key': api_key,
            'models': models
        }
        state.openai_endpoints.append(endpoint)

        config = load_config()
        config['openai_endpoints'] = state.openai_endpoints
        save_config(config)

        return jsonify({'success': True, 'endpoint': endpoint})


    @app.route('/api/openai/endpoints/<endpoint_name>', methods=['PUT'])
    def update_openai_endpoint(endpoint_name):
        data = request.json

        for i, ep in enumerate(state.openai_endpoints):
            if ep.get('name') == endpoint_name:
                if 'base_url' in data:
                    ep['base_url'] = data['base_url'].strip()
                if 'api_key' in data:
                    ep['api_key'] = data['api_key'].strip()
                if 'models' in data:
                    ep['models'] = data['models']
                if 'name' in data and data['name'] != endpoint_name:
                    new_name = data['name'].strip()
                    for other_ep in state.openai_endpoints:
                        if other_ep.get('name') == new_name and other_ep.get('name') != endpoint_name:
                            return jsonify({'success': False, 'error': '新名称已存在'}), 400
                    ep['name'] = new_name
                    if state.openai_current_endpoint == endpoint_name:
                        state.openai_current_endpoint = new_name

                config = load_config()
                config['openai_endpoints'] = state.openai_endpoints
                config['openai_current_endpoint'] = state.openai_current_endpoint
                save_config(config)

                return jsonify({'success': True, 'endpoint': ep})

        return jsonify({'success': False, 'error': '端点不存在'}), 404


    @app.route('/api/openai/endpoints/<endpoint_name>', methods=['DELETE'])
    def delete_openai_endpoint(endpoint_name):
        for i, ep in enumerate(state.openai_endpoints):
            if ep.get('name') == endpoint_name:
                state.openai_endpoints.pop(i)
                if state.openai_current_endpoint == endpoint_name:
                    state.openai_current_endpoint = state.openai_endpoints[0]['name'] if state.openai_endpoints else ''

                config = load_config()
                config['openai_endpoints'] = state.openai_endpoints
                config['openai_current_endpoint'] = state.openai_current_endpoint
                save_config(config)

                return jsonify({'success': True})

        return jsonify({'success': False, 'error': '端点不存在'}), 404


    @app.route('/api/openai/switch', methods=['POST'])
    def switch_openai_endpoint():
        data = request.json
        endpoint_name = data.get('endpoint_name')
        model = data.get('model')

        for ep in state.openai_endpoints:
            if ep.get('name') == endpoint_name:
                state.openai_current_endpoint = endpoint_name
                if model:
                    state.openai_current_model = model

                config = load_config()
                config['openai_current_endpoint'] = state.openai_current_endpoint
                config['openai_current_model'] = state.openai_current_model
                save_config(config)

                return jsonify({
                    'success': True,
                    'endpoint': ep,
                    'current_model': state.openai_current_model
                })

        return jsonify({'success': False, 'error': '端点不存在'}), 404


    @app.route('/api/anthropic/endpoints', methods=['GET'])
    def get_anthropic_endpoints():
        return jsonify({
            'endpoints': state.anthropic_endpoints,
            'current_endpoint': state.anthropic_current_endpoint,
            'current_model': state.anthropic_current_model
        })


    @app.route('/api/anthropic/endpoints', methods=['POST'])
    def add_anthropic_endpoint():
        data = request.json
        name = data.get('name', '').strip()
        base_url = data.get('base_url', '').strip()
        api_key = data.get('api_key', '').strip()
        models = data.get('models', [])

        if not name:
            return jsonify({'success': False, 'error': '端点名称不能为空'}), 400
        if not base_url:
            return jsonify({'success': False, 'error': 'API 地址不能为空'}), 400

        for ep in state.anthropic_endpoints:
            if ep.get('name') == name:
                return jsonify({'success': False, 'error': '端点名称已存在'}), 400

        endpoint = {
            'name': name,
            'base_url': base_url,
            'api_key': api_key,
            'models': models
        }
        state.anthropic_endpoints.append(endpoint)

        config = load_config()
        config['anthropic_endpoints'] = state.anthropic_endpoints
        save_config(config)

        return jsonify({'success': True, 'endpoint': endpoint})


    @app.route('/api/anthropic/endpoints/<endpoint_name>', methods=['PUT'])
    def update_anthropic_endpoint(endpoint_name):
        data = request.json

        for i, ep in enumerate(state.anthropic_endpoints):
            if ep.get('name') == endpoint_name:
                if 'base_url' in data:
                    ep['base_url'] = data['base_url'].strip()
                if 'api_key' in data:
                    ep['api_key'] = data['api_key'].strip()
                if 'models' in data:
                    ep['models'] = data['models']
                if 'name' in data and data['name'] != endpoint_name:
                    new_name = data['name'].strip()
                    for other_ep in state.anthropic_endpoints:
                        if other_ep.get('name') == new_name and other_ep.get('name') != endpoint_name:
                            return jsonify({'success': False, 'error': '新名称已存在'}), 400
                    ep['name'] = new_name
                    if state.anthropic_current_endpoint == endpoint_name:
                        state.anthropic_current_endpoint = new_name

                config = load_config()
                config['anthropic_endpoints'] = state.anthropic_endpoints
                config['anthropic_current_endpoint'] = state.anthropic_current_endpoint
                save_config(config)

                return jsonify({'success': True, 'endpoint': ep})

        return jsonify({'success': False, 'error': '端点不存在'}), 404


    @app.route('/api/anthropic/endpoints/<endpoint_name>', methods=['DELETE'])
    def delete_anthropic_endpoint(endpoint_name):
        for i, ep in enumerate(state.anthropic_endpoints):
            if ep.get('name') == endpoint_name:
                state.anthropic_endpoints.pop(i)
                if state.anthropic_current_endpoint == endpoint_name:
                    state.anthropic_current_endpoint = state.anthropic_endpoints[0]['name'] if state.anthropic_endpoints else ''

                config = load_config()
                config['anthropic_endpoints'] = state.anthropic_endpoints
                config['anthropic_current_endpoint'] = state.anthropic_current_endpoint
                save_config(config)

                return jsonify({'success': True})

        return jsonify({'success': False, 'error': '端点不存在'}), 404


    @app.route('/api/anthropic/switch', methods=['POST'])
    def switch_anthropic_endpoint():
        data = request.json
        endpoint_name = data.get('endpoint_name')
        model = data.get('model')

        for ep in state.anthropic_endpoints:
            if ep.get('name') == endpoint_name:
                state.anthropic_current_endpoint = endpoint_name
                if model:
                    state.anthropic_current_model = model

                config = load_config()
                config['anthropic_current_endpoint'] = state.anthropic_current_endpoint
                config['anthropic_current_model'] = state.anthropic_current_model
                save_config(config)

                return jsonify({
                    'success': True,
                    'endpoint': ep,
                    'current_model': state.anthropic_current_model
                })

        return jsonify({'success': False, 'error': '端点不存在'}), 404


    @app.route('/api/skills', methods=['GET'])
    def get_skills():
        skills = skill_registry.get_all_skills()
        return jsonify({
            'skills': [skill.to_dict() for skill in skills],
            'count': len(skills)
        })


    @app.route('/api/skills/reload', methods=['POST'])
    def reload_skills():
        try:
            skill_registry.reload()
            skills = skill_registry.get_all_skills()
            return jsonify({
                'success': True,
                'message': f'成功加载 {len(skills)} 个 Skill',
                'skills': [skill.to_dict() for skill in skills]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/skills/<skill_name>', methods=['GET'])
    def get_skill_detail(skill_name):
        skill = skill_registry.get_skill(skill_name)
        if not skill:
            return jsonify({'error': 'Skill 不存在'}), 404

        return jsonify({
            'name': skill.name,
            'description': skill.description,
            'has_scripts': skill.has_scripts(),
            'has_references': skill.has_references(),
            'content': skill.get_full_content()
        })
