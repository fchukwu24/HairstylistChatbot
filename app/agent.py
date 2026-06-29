"""
Agent runner for the haircare salon chatbot.

This file controls the full agent:

1. Receive the user's message.
2. Ask GROQAgentCore to decide the next action.
3. If the action is "finish", return the final answer.
4. If the action is a tool, execute it through tools.execute_tool() and return the final answer.

GROQAgentCore decides.
tools.py executes.
"""

from __future__ import annotations

from agent_dates import normalize_action_dates
from agent_core import AgentAction, GROQAgentCore
from tools import execute_tool
from agent_debug import debug_action, debug_result
from agent_guards import (
    user_message_confirms,
    recent_assistant_asked_confirmation,
    write_action_succeeded,
)

from agent_formatters import (
    blocked_write_action_answer,
    format_write_action_success,
    format_write_action_error,
    tool_result_is_error,
    tool_result_to_text,
)

MAX_DECISION_ROUNDS = 4



def run_turn(llm, tokenizer, history: list[dict[str, str]], user_message: str) -> str:
    """
    Run one chatbot turn.

    history is a list of {"role": ..., "content": ...} dictionaries.
    main.py keeps this list across the full terminal conversation.

    This function mutates history in place and returns the assistant's reply.
    """
    
    core = GROQAgentCore(llm, tokenizer)

    def commit_and_return(answer: str) -> str:
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": answer})
        return answer
    
    action = core.decide(history=history, user_message=user_message,)
    print("Raw action")
    debug_action(action)
    
    action = normalize_action_dates(action, user_message)
    print("Normalized action")
    debug_action(action)
    match action.tool:
        case "finish": 
            answer = action.arguments.get("answer")
            return commit_and_return(answer.strip())
        case "book_appointment"| "modify_appointment"| "cancel_appointment":
            # If confirmation sequence occurred
            if not (user_message_confirms(user_message) and recent_assistant_asked_confirmation(history)):
                return commit_and_return(blocked_write_action_answer(action, user_message))
            else:
                result = execute_tool(action.tool, action.arguments)
                debug_result(result)
                
                if write_action_succeeded(action.tool, result):
                    answer = format_write_action_success(action.tool, result)
                else:
                    answer = format_write_action_error(action.tool, result)
                return commit_and_return(answer)
        case "search_haircare_knowledge"| "get_booking_info":
            result = execute_tool(action.tool, action.arguments)
            print("Debug result")
            debug_result(result)
            if (not tool_result_is_error(result)):
                answer = _generate_final_answer_from_tool_result( llm=llm, tokenizer=tokenizer, user_message=user_message, tool_name=action.tool, tool_result=result,)
                history.append({"role": "assistant", "content": answer})
                return commit_and_return(answer)
            else:
                error = result.get("error") or result.get("blocked_tool")
                return commit_and_return(f"I couldn't look that up: {error}")
        case _: 
            print("Hit the fallback")
            fallback = (
            "Sorry, I’m having trouble completing that request. "
            "Could you rephrase your haircare, salon policy, or appointment question?"
                )
            return commit_and_return(fallback)
    

def _generate_final_answer_from_tool_result(
    llm,
    tokenizer,
    user_message: str,
    tool_name: str,
    tool_result,
) -> str:
    tool_result_text = tool_result_to_text(tool_result)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful haircare and salon assistant.\n"
                "Answer the user's question using the provided tool result.\n"
                "Do not call another tool.\n"
                "Do not output JSON.\n"
                "Do not mention internal tool names.\n"
                "\n"
                "Important accuracy rules:\n"
                "- Do not invent services, prices, durations, stylists, dates, or policies.\n"
                "- Do not contradict the tool result.\n"
                "- If the tool result contains a list and the user asks for everything, all services, "
                "a full list, complete list, or service menu, include every item from the list.\n"
                "- Do not shorten a full list unless the user asked for a summary.\n"
                "- If the tool result contains services, include each service name, duration, and price/range when available.\n"
                "- If the tool result says a service/category was not found, say that clearly and ask what they want to check instead.\n"
                "\n"

                "If the user asked for haircare advice, give direct practical advice.\n"
                "If the user asked about salon booking info, summarize the booking info clearly.\n"
                "Only ask a follow-up question if it is naturally needed."
                "Style rules:\n"
                "- Be concise and customer-friendly.\n"
                "- Use bullet points for service lists.\n"
                "- Only ask a follow-up question if it is naturally needed."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User question:\n{user_message}\n\n"
                f"Tool used:\n{tool_name}\n\n"
                f"Tool result:\n{tool_result_text}\n\n"
                "Write the final assistant response."
            ),
        },
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    return llm.invoke(prompt).strip()
