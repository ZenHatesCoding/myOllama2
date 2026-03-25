import asyncio


async def generate_answer(query, model_name=None, mode="qa"):
    from agent import stream_graph
    from core import state
    from utils.conversation import auto_name_conversation
    
    try:
        conversation = state.get_current_conversation()
        
        if model_name is None:
            model_name = "qwen3.5:4b"
        
        print(f"开始生成回答，模型: {model_name}，模式: {mode} (LangGraph工作流)")
        
        conversation.add_message("user", query)
        
        images = conversation.images
        
        full_response = ""
        
        for chunk in stream_graph(query, model_name, images, mode):
            if state.should_stop:
                full_response += "\n\n操作已中断"
                state.response_queue.put(("chunk", "\n\n操作已中断"))
                break
            
            full_response += chunk
            state.response_queue.put(("chunk", chunk))
        
        if not state.should_stop:
            conversation.add_message("assistant", full_response)
            state.persist_message("user", query)
            state.persist_message("assistant", full_response)
            auto_name_conversation(conversation)
            state.response_queue.put(("done", ""))
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
