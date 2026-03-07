import base64
import io
import os
import tempfile
import uuid
import asyncio
from PIL import Image
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama
from langchain_ollama import OllamaEmbeddings
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from models import state
from mcp import MCPManager, NewsMCP


embedding_model = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")
llm_model = ChatOllama(
    model="qwen3:8b",
    base_url="http://localhost:11434",
    temperature=0.7
)

mcp_manager = MCPManager()
mcp_manager.register_mcp(NewsMCP(api_key="f01f4e17ae8680f4ad7c16904e0a3d21"))


def load_document(file_path, file_type):
    if file_type == "pdf":
        loader = PyPDFLoader(file_path)
        return loader.load()
    elif file_type == "docx":
        doc = DocxDocument(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return [Document(page_content=text, metadata={"source": file_path})]
    elif file_type == "txt":
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return [Document(page_content=text, metadata={"source": file_path})]
    return []


def process_document(documents):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    texts = text_splitter.split_documents(documents)
    vector_store = FAISS.from_documents(texts, embedding_model)
    return vector_store


def generate_summary(messages):
    try:
        prompt = "请用一句话总结以下对话的主要内容：\n\n"
        for msg in messages:
            prompt += f"{msg.role}: {msg.content}\n"
        prompt += "\n摘要："
        
        response = llm_model.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        print(f"生成摘要失败：{str(e)}")
        return None


def process_image(image_data):
    try:
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        max_size = (512, 512)
        image.thumbnail(max_size, Image.LANCZOS)
        
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"temp_{uuid.uuid4()}.jpg")
        image.save(temp_path, 'JPEG', quality=70)
        
        return temp_path
    except Exception as e:
        print(f"图像处理失败: {str(e)}")
        return None


def encode_image_to_base64(image_path):
    try:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"图像编码失败: {str(e)}")
        return None


def prepare_messages(conversation, query, system_prompt, images=None):
    messages = [SystemMessage(content=system_prompt)]
    
    total_turns = conversation.get_total_turns()
    
    if total_turns > state.max_context_turns:
        if not conversation.summary:
            early_messages = conversation.messages[:state.max_context_turns * 2]
            summary = generate_summary(early_messages)
            if summary:
                conversation.summary = summary
        
        if conversation.summary:
            messages.append(SystemMessage(content=f"之前的对话摘要：{conversation.summary}"))
        
        recent_messages = conversation.messages[-state.max_context_turns * 2:]
        for msg in recent_messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
    else:
        for msg in conversation.messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
    
    if images and len(images) > 0:
        image_contents = []
        for img in images:
            image_url = f"data:image/jpeg;base64,{img['data']}"
            print(f"图片URL长度: {len(image_url)}")
            print(f"图片数据长度: {len(img['data'])}")
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": image_url
                }
            })
        
        content = [
            {"type": "text", "text": query}
        ] + image_contents
        
        messages.append(HumanMessage(content=content))
    else:
        messages.append(HumanMessage(content=query))
    
    return messages


async def generate_answer(query, model_name=None):
    from langchain_ollama import ChatOllama
    
    try:
        conversation = state.get_current_conversation()
        
        if model_name is None:
            model_name = "qwen3.5:4b"
        
        print(f"开始生成回答，模型: {model_name}")
        
        mcp_result = await mcp_manager.detect_intent_and_execute(query)
        if mcp_result and mcp_result.get("success"):
            tool_name = mcp_result.get("tool_name", "")
            formatted_text = mcp_result.get("formatted_text", "")
            print(f"MCP工具调用成功: {tool_name}")
            
            tool_display_names = {
                "get_headlines": "头条新闻",
                "get_news_by_type": "分类新闻",
                "search_news": "新闻搜索"
            }
            tool_display_name = tool_display_names.get(tool_name, tool_name)
            
            state.response_queue.put(("chunk", f"📰 正在从{tool_display_name}获取信息...\n\n"))
            
            if not state.should_stop:
                full_text = f"📰 正在从{tool_display_name}获取信息...\n\n{formatted_text}"
                
                for i in range(0, len(formatted_text), 10):
                    if state.should_stop:
                        break
                    chunk = formatted_text[i:i+10]
                    state.response_queue.put(("chunk", chunk))
                    import time
                    time.sleep(0.01)
                
                if not state.should_stop:
                    conversation.add_message("user", query)
                    conversation.add_message("assistant", full_text)
                    auto_name_conversation(conversation)
                    state.response_queue.put(("done", ""))
                else:
                    state.response_queue.put(("error", "操作已中断"))
            else:
                state.response_queue.put(("error", "操作已中断"))
            return
        
        llm = ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=0.7
        )
        
        if conversation.vector_store:
            relevant_docs = conversation.vector_store.similarity_search(query, k=4)
            context = "\n\n".join([doc.page_content for doc in relevant_docs]) if relevant_docs else "无相关内容"
            system_prompt = f"你是一个文档问答助手。仅基于以下内容回答问题：\n\n{context}"
        else:
            system_prompt = "你是一个乐于助人的助手"
        
        if state.should_stop:
            state.response_queue.put(("error", "操作已中断"))
            return
        
        images = conversation.images
        print(f"图片数量: {len(images) if images else 0}")
        
        messages = prepare_messages(conversation, query, system_prompt, images)
        print(f"消息数量: {len(messages)}")
        
        output_content = ""
        for chunk in llm.stream(messages):
            if state.should_stop:
                output_content += "\n\n操作已中断"
                state.response_queue.put(("chunk", "\n\n操作已中断"))
                break
            
            chunk_text = str(chunk.content)
            output_content += chunk_text
            state.response_queue.put(("chunk", chunk_text))

        if not state.should_stop:
            conversation.add_message("user", query)
            conversation.add_message("assistant", output_content)
            auto_name_conversation(conversation)
            state.response_queue.put(("done", output_content))
        else:
            state.response_queue.put(("error", "操作已中断"))

    except Exception as e:
        print(f"生成回答失败: {str(e)}")
        import traceback
        traceback.print_exc()
        state.response_queue.put(("error", f"生成失败：{str(e)}"))
    finally:
        state.is_generating = False
        state.should_stop = False


def auto_name_conversation(conversation):
    if conversation.messages:
        if conversation.name == "新对话":
            for msg in conversation.messages:
                if msg.role == "user":
                    name = msg.content[:20] + ("..." if len(msg.content) > 20 else "")
                    conversation.name = name
                    break
        
        if len(conversation.messages) >= 2:
            summary = generate_summary(conversation.messages)
            if summary:
                conversation.name = summary[:30] + ("..." if len(summary) > 30 else "")
