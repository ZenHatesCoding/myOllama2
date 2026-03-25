from core import state


def auto_name_conversation(conversation):
    from llm.helpers import generate_summary

    if conversation.messages:
        user_assistant_pairs = 0
        for i in range(0, len(conversation.messages) - 1, 2):
            if (conversation.messages[i].role == "user" and
                i + 1 < len(conversation.messages) and
                conversation.messages[i + 1].role == "assistant"):
                user_assistant_pairs += 1

        if conversation.name == "新对话":
            for msg in conversation.messages:
                if msg.role == "user":
                    name = msg.content[:20] + ("..." if len(msg.content) > 20 else "")
                    conversation.name = name
                    state.persist_conversation_name(name)
                    break

        if user_assistant_pairs > 0 and user_assistant_pairs % 5 == 0:
            summary = generate_summary(conversation.messages)
            if summary:
                conversation.name = summary[:30] + ("..." if len(summary) > 30 else "")
                state.persist_conversation_name(conversation.name)
                state.persist_summary(summary)
