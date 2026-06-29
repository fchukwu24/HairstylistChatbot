"""
Loads the local Hugging Face model
"""
import os

from langchain_groq import ChatGroq


class SimpleChatFormatter:
    """
    Minimal replacement for Hugging Face tokenizer.apply_chat_template().

    Your agent_core.py currently expects a tokenizer object with
    apply_chat_template(), so this keeps the rest of your code working
    without needing a real Hugging Face tokenizer.
    """

    def apply_chat_template(
        self,
        messages,
        tokenize=False,
        add_generation_prompt=True,
    ):
        parts = []

        for message in messages:
            role = message["role"].upper()
            content = message["content"]
            parts.append(f"{role}:\n{content}")

        if add_generation_prompt:
            parts.append("ASSISTANT:")

        return "\n\n".join(parts)


class GroqTextAdapter:
    """
    Makes ChatGroq behave like the old HuggingFacePipeline object.

    Your current code expects:

        llm.invoke(prompt).strip()

    But ChatGroq returns an AIMessage object.
    This adapter returns only the message content as a string.
    """

    def __init__(self, chat_model):
        self.chat_model = chat_model

    def invoke(self, prompt: str) -> str:
        response = self.chat_model.invoke(prompt)

        if hasattr(response, "content"):
            return response.content

        return str(response)

def load_llm(max_new_tokens: int = 512):
    model_name = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    chat_model = ChatGroq(
        model=model_name,
        temperature=0,
        max_tokens=max_new_tokens,
    )
    
    llm = GroqTextAdapter(chat_model)
    tokenizer = SimpleChatFormatter()

    return llm, tokenizer
