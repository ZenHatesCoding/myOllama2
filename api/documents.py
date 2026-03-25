import threading
import os
import tempfile
import queue
from flask import Blueprint, request, jsonify
from core import state
from utils import load_document, get_embedding_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

documents_bp = Blueprint('documents', __name__)

@documents_bp.route('/upload', methods=['POST'])
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


@documents_bp.route('/remove', methods=['DELETE'])
def remove_document():
    conversation = state.get_current_conversation()
    conversation.vector_store = None
    conversation.document_file = None
    conversation.summary = None
    conversation.document_chunks = []

    return jsonify({'success': True, 'message': '文档已移除'})
