from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from core import state


def prepare_messages(conversation, query, system_prompt, images=None):
    messages = [SystemMessage(content=system_prompt)]
    
    total_turns = conversation.get_total_turns()
    
    if total_turns > state.max_context_turns:
        if not conversation.summary:
            from llm.helpers import generate_summary
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
