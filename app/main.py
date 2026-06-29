import logging
from dotenv import load_dotenv

load_dotenv()

from llm import load_llm
from agent import run_turn
import rag

def main():
    print("Loading model...")
    llm, tokenizer = load_llm()

    print("Building/loading the haircare knowledge index...")
    rag.load_vector_db()

    print("\nHaircare & booking assistant ready. Type 'quit' to exit.\n")
    history = []

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"quit", "exit"}:
            break
        if not user_input:
            continue

        reply = run_turn(llm, tokenizer, history, user_input)
        print(f"\nAssistant: {reply}\n")


if __name__ == "__main__":
    main()
