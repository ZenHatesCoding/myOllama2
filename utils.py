import base64
import io
import os
import tempfile
import uuid
import asyncio
import time
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
from history_rag import history_rag

embedding_model = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")
llm_model = ChatOllama(
    model="qwen3.5:4b",
    base_url="http://localhost:11434",
    temperature=0.7
)


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
        
        history_context = history_rag.get_context_for_query(query, max_blocks=3)
        if history_context:
            messages.append(SystemMessage(content=history_context))
        
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
    from agent import stream_graph
    from tools import news_toolkit
    import json
    
    try:
        conversation = state.get_current_conversation()
        
        if model_name is None:
            model_name = "qwen3.5:4b"
        
        print(f"开始生成回答，模型: {model_name} (LangGraph)")
        
        llm_for_intent = ChatOllama(
            model="qwen3:8b",
            base_url="http://localhost:11434",
            temperature=0.3
        )
        
        tools_schema = """可用工具列表：

工具名称: get_headlines
描述: 获取头条新闻
参数:
  - page_size: integer (可选) - 返回新闻数量，1-50，默认10

工具名称: get_news_by_type
描述: 按类型获取新闻
参数:
  - news_type: string (必需) - 新闻类型，可选值：头条、社会、国内、国际、娱乐、体育、科技、财经
  - page_size: integer (可选) - 返回新闻数量，1-50，默认10

工具名称: search_news
描述: 根据关键词搜索新闻
参数:
  - keyword: string (必需) - 搜索关键词
  - page_size: integer (可选) - 返回新闻数量，1-50，默认10
"""
        
        system_prompt = f"""你是一个智能助手，负责判断用户是否需要使用工具来完成任务。

{tools_schema}

请分析用户的输入，判断是否需要使用上述工具。
如果需要使用工具，请返回JSON格式：
{{
    "need_tool": true,
    "tool_name": "工具名称",
    "parameters": {{
        "参数名": "参数值"
    }}
}}

如果不需要使用工具，请返回：
{{
    "need_tool": false,
    "reason": "原因说明"
}}

只返回JSON，不要有其他内容。"""
        
        mcp_result = None
        try:
            response = llm_for_intent.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ])
            result_text = response.content.strip()
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            intent = json.loads(result_text)
            
            if intent.get("need_tool"):
                tool_name = intent.get("tool_name")
                parameters = intent.get("parameters", {})
                
                if tool_name == "get_headlines":
                    mcp_result = news_toolkit.get_headlines(parameters.get("page_size", 10))
                elif tool_name == "get_news_by_type":
                    mcp_result = news_toolkit.get_news_by_type(
                        parameters.get("news_type", "头条"),
                        parameters.get("page_size", 10)
                    )
                elif tool_name == "search_news":
                    mcp_result = news_toolkit.search_news(
                        parameters.get("keyword", ""),
                        parameters.get("page_size", 10)
                    )
        except Exception as e:
            print(f"工具意图检测失败: {str(e)}")
        
        if mcp_result and mcp_result.get("success"):
            tool_name = mcp_result.get("tool_name", "")
            formatted_text = mcp_result.get("formatted_text", "")
            print(f"LangGraph Tool 调用成功: {tool_name}")
            
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
                    time.sleep(0.01)
                
                if not state.should_stop:
                    conversation.add_message("user", query)
                    conversation.add_message("assistant", full_text)
                    state.persist_message("user", query)
                    state.persist_message("assistant", full_text)
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
            state.persist_message("user", query)
            state.persist_message("assistant", output_content)
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
                    state.persist_conversation_name(name)
                    break
        
        if len(conversation.messages) >= 2:
            summary = generate_summary(conversation.messages)
            if summary:
                conversation.name = summary[:30] + ("..." if len(summary) > 30 else "")
                state.persist_conversation_name(conversation.name)
                state.persist_summary(summary)
