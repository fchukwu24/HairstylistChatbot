"""
Local agent core for the haircare salon chatbot.

This copies the STRUCTURE of the GroqAgentCore notebook pattern,
but it does NOT use Groq.

It uses the same local Hugging Face model already loaded by llm.py.

Main idea:
- AgentCore plans the next action.
- It does not execute tools.
- agent.py will execute tools through tools.execute_tool().
"""

from __future__ import annotations

import json
import re

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from booking_config import TIMEZONE
from booking import _render_generic_service_names
from tools import TOOLS

@dataclass
class AgentAction:
    """
    A structured decision from the agent core.

    Example:
    AgentAction(
        tool="check_availability",
        arguments={"date": "2026-06-27", "stylist": "Jordan"},
        reason="The user asked for open appointment times."
    )
    """

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class GROQAgentCore:

    def __init__(self, llm, tokenizer, allowed_tools: set[str] | None = None):
        self.llm = llm
        self.tokenizer = tokenizer
        self.allowed_tools = allowed_tools or self._default_allowed_tools()

    def decide(
        self,
        history: list[dict[str, str]],
        user_message: str,
    ) -> AgentAction:
        # """
        # Choose the next action.

        # This should return one of:
        # - search_haircare_knowledge
        # - check_availability
        # - book_appointment
        # - modify_appointment
        # - cancel_appointment
        # - get_salon_hours
        # - finish

        # The tool is NOT executed here.
        # """

        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {
                "role": "user",
                "content": self._build_decision_prompt(
                    history=history,
                    user_message=user_message,
                ),
            },
        ]
        raw_reply = self._generate(messages)
        try:
            return self._parse_action(raw_reply)
        except Exception as e:
            return AgentAction(
                tool="finish",
                arguments={
                    "answer": (
                        "Sorry, I had trouble deciding how to handle that. "
                        "Could you rephrase your haircare, salon policy, or appointment question?"
                    )
                },
                reason=f"Decision core returned invalid JSON: {e}",
            )

    def _generate(self, messages: list[dict[str, str]]) -> str:
        """
        Generate text with the existing local model.
        """
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        return self.llm.invoke(prompt).strip()

    def _build_system_prompt(self) -> str:
        now = datetime.now(ZoneInfo(TIMEZONE))

        return f"""
You are the planning core for a hair salon chatbot.

You do not answer normally unless you choose the "finish" tool.
Your job is to choose exactly one next action.

Current salon date/time:
{now.strftime("%A, %Y-%m-%d %H:%M")} ({TIMEZONE})

Available tools:
{self._render_tools()}

You may also choose this special tool:
- finish(arguments: {{"answer": "customer-facing answer"}})

Return ONLY valid JSON.
Do not use markdown.
Do not use code fences.
Do not add explanation outside the JSON.

Required JSON format:
{{
  "tool": "tool_name_here",
  "arguments": {{}},
  "reason": "short reason here"
}}

Date handling rules:
- If the user gives an exact date in YYYY-MM-DD format, use the date argument.
- If the user gives a vague or relative date phrase, do not calculate the final date yourself.
- For vague or relative dates, copy the user's phrase exactly into date_text.
- If the user gives a vague time period instead of a specific day, such as "next week" or "this weekend", choose finish and ask which specific date they want.
- Do not guess dates like 2026-07-03 for "next Saturday". Use date_text instead.
- Examples:
    - "today" -> date_text: "today"
    - "tomorrow" -> date_text: "tomorrow"
    - "next Saturday" -> date_text: "next Saturday"
    - "this Friday" -> date_text: "this Friday"
    - "July 4" -> date_text: "July 4"
    - "next week" -> date_text: "next week"
    

Routing rules:
- If you choose finish, arguments must include {{"answer": "..."}}.
- Never return finish with empty arguments.
- If the latest user message is only a greeting like "hi", "hello", "hey", or "how are you", choose finish and greet the user. Do not call a tool.
- If the user says something unrelated to haircare, salon policies, or appointments, choose finish and briefly say you can help with haircare, salon policies, and appointments.
- Never invent appointment details. Do not invent dates, times, stylists, services, customer names, emails, or appointment ids. If required details are missing, choose finish and ask for the missing details.
- Use only details the user actually gave in the conversation or details returned by a tool.
- For tools that require a date, date_text counts as the date detail when the user gave a vague or relative date. Python will convert date_text into date before the tool runs.
- If the user asks for a broad service like {_render_generic_service_names()} ask which specific service they want before booking.
- Do not say an appointment was booked, modified, or cancelled unless the tool result clearly shows success.
- Use get_booking_info for salon hours, service lists, service categories, service checks, stylist capabilities, and availability.
- If the assistant recently asked the user to confirm appointment details and the user changes one of those details with words like "actually", "wait", "instead", "change", or "make it", treat it as an update to the pending appointment.
- Do not use search_haircare_knowledge when the user is changing a pending appointment service.
- If the user asks for all services, everything, the full list, the complete list, or "what services do you offer", use get_booking_info with request_type="services".
- Use request_type="category_options" only when the user names a specific broad category like braids, locs, twists, installs, natural styles, or treatments.
- If the user changes the service, use get_booking_info with request_type="availability" to re-check availability for the same date, stylist, and new service.
- Do not use search_haircare_knowledge for service catalog questions like "what braid styles do you do"; use get_booking_info.
- Use get_booking_info with request_type="category_options" when the user asks what styles/services exist inside a broad category like braids, locs, twists, or installs.
- Use get_booking_info with request_type="availability" when the user asks for open times, slots, or appointments.
- Use get_booking_info with request_type="hours" when the user asks when the salon opens, closes, or whether it is open.
- Use search_haircare_knowledge for haircare questions and salon policy questions.
- Use book_appointment only after the user has clearly confirmed the service, stylist, date or date_text, time, and customer name.
- Use modify_appointment only after the user has clearly confirmed the appointment id and the requested changes.
- If the assistant recently asked for a missing booking detail and the user provides only that missing detail, combine it with the previous booking request.
- Example:
  Assistant: "What time would you like?"
  User: "11:00 am"
  Use the previous service, stylist, date/date_text, and customer details from conversation history.
- Do not answer salon hours when the user is providing a missing booking detail.
- Use cancel_appointment only after the user has clearly confirmed the appointment id and cancellation.
- If you are unsure whether the user confirmed a booking, modification, or cancellation, do not choose book_appointment, modify_appointment, or cancel_appointment. Choose finish and ask for confirmation.
""".strip()

    def _build_decision_prompt(
        self,
        history: list[dict[str, str]],
        user_message: str,
    ) -> str:
        recent_history = history[-8:]

        return f"""
                Recent conversation:
                {json.dumps(recent_history, indent=2)}

                Latest user message:
                {user_message}

                Choose the next action now.
                Return only the JSON object.
                """.strip()


    
                
    def _render_tools(self) -> str:
        lines = []

        for tool in TOOLS:
            name = tool["name"]

            if name not in self.allowed_tools:
                continue

            params = ", ".join(
                f"{key}: {value}"
                for key, value in tool.get("parameters", {}).items()
            )

            lines.append(
                f"- {name}({params}) - {tool.get('description', '')}"
            )

        return "\n".join(lines)

    def _default_allowed_tools(self) -> set[str]:
        return {tool["name"] for tool in TOOLS} | {"finish"}

    def _parse_action(self, content: str) -> AgentAction:
        data = self._loads_json_object(content)

        tool = data.get("tool")
        arguments = data.get("arguments", {})
        reason = data.get("reason", "")

        if tool not in self.allowed_tools:
            return AgentAction(
                tool="finish",
                arguments={
                    "answer": (
                        "I can help with haircare questions, salon policies, "
                        "and appointments."
                    )
                },
                reason=f"Model chose an invalid or disallowed tool: {tool}",
            )

        if not isinstance(arguments, dict):
            arguments = {"input": arguments}

        return AgentAction(
            tool=tool,
            arguments=arguments,
            reason=reason,
        )

    def _loads_json_object(self, content: str) -> dict[str, Any]:
        """
        Parse JSON even if the model accidentally adds extra text.
        """
        cleaned = content.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)

            if not match:
                raise

            data = json.loads(match.group(0))

        if not isinstance(data, dict):
            raise ValueError("Decision core response must be a JSON object.")

        return data