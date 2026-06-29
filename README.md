# Haircare & appointment assistant


## Setup without docker

```
pip install -r requirements.txt
python main.py
```

## Setup with docker

```
docker compose build --nocache
docker compose run --rm haircare-chatbot
```

## Example interaction

```
You: how often should I wash my hair?
Assistant: Most hair types do well with washing every two to three days...

You: can I book a haircut with Jordan on 2026-06-20?
Assistant: Let me check what's open that day...
Assistant: Jordan has 10:00, 11:30, 13:00, 14:30, and 16:00 open on
2026-06-20. Which time works for you, and what name should I book it under?

You: 14:30, under Alex
Assistant: Just to confirm: a haircut with Jordan on 2026-06-20 at 14:30
for Alex. Should I book it?

You: yes
Assistant: You're booked! Confirmation id 4402e2cb.
```

## How it's organized

- `main.py` -- the terminal REPL loop
- `llm.py` -- loads the model/tokenizer and wraps it as a LangChain LLM
- `rag.py` -- chunks `data/*.md`, embeds with HuggingFaceEmbeddings, stores/searches with FAISS
- `booking.py` -- the mocked appointment backend (in-memory, resets each run)
- `tools.py` -- the tool registry (descriptions + the dispatcher that runs them)
- `agent.py` -- the loop that prompts the model, parses any `<tool_call>` it emits, runs it, and feeds the result back in
- `data/haircare_knowledge.md` -- sample content; add more `.md` files here for a bigger knowledge base
- `Dockerfile`, `docker-compose.yml`, `.dockerignore` -- containerized deployment

## Design notes

