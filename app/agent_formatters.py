
import json

from agent_core import AgentAction
from agent_guards import BOOK_REQUIRED_FIELDS, MODIFY_CHANGE_FIELDS, missing_fields


def blocked_write_action_answer(action: AgentAction, user_message: str) -> str:
    arguments = action.arguments or {}

    if action.tool == "book_appointment":
        missing = missing_fields(arguments, BOOK_REQUIRED_FIELDS)

        if missing:
            return (
                "I can help book that. I still need: "
                f"{', '.join(missing)}."
            )

        return (
            "I have the appointment details:\n\n"
            f"- Service: {arguments['service']}\n"
            f"- Stylist: {arguments['stylist']}\n"
            f"- Date: {arguments['date']}\n"
            f"- Time: {arguments['time']}\n"
            f"- Name: {arguments['customer_name']}\n"
            f"{_format_optional_line('Email', arguments.get('customer_email'))}"
            "\nPlease confirm: should I book this appointment?"
        )

    if action.tool == "modify_appointment":
        appointment_id = arguments.get("appointment_id")

        if not appointment_id:
            return (
                "I can help modify that appointment. "
                "I still need the appointment ID."
            )

        requested_changes = {
            label: arguments.get(key)
            for key, label in MODIFY_CHANGE_FIELDS.items()
            if arguments.get(key)
        }

        if not requested_changes:
            return (
                f"I can help modify appointment {appointment_id}. "
                "What would you like to change — date, time, stylist, or service?"
            )

        change_lines = "".join(
            f"- {label}: {value}\n"
            for label, value in requested_changes.items()
        )

        return (
            "I have the modification details:\n\n"
            f"- Appointment ID: {appointment_id}\n"
            f"{change_lines}"
            "\nPlease confirm: should I update this appointment?"
        )

    if action.tool == "cancel_appointment":
        appointment_id = arguments.get("appointment_id")

        if not appointment_id:
            return (
                "I can help cancel an appointment. "
                "I still need the appointment ID."
            )

        return (
            "I have the cancellation details:\n\n"
            f"- Appointment ID: {appointment_id}\n\n"
            "Please confirm: should I cancel this appointment?"
        )

    return "Please confirm the details before I make that change."


def _format_optional_line(label: str, value) -> str:
    if value in (None, ""):
        return ""

    return f"- {label}: {value}\n"


def format_write_action_success(tool_name: str, result: dict) -> str:
    if tool_name == "book_appointment":
        return (
            "You're booked!\n\n"
            f"- Confirmation ID: {result.get('id')}\n"
            f"- Service: {result.get('service_display_name', result.get('service'))}\n"
            f"- Stylist: {result.get('stylist')}\n"
            f"- Date: {result.get('date')}\n"
            f"- Time: {result.get('time')}\n"
            f"- Name: {result.get('customer_name')}\n"
            f"- Email: {result.get('customer_email') or 'Not provided'}"
        )

    if tool_name == "modify_appointment":
        return (
            "Your appointment has been updated.\n\n"
            f"- Confirmation ID: {result.get('id')}\n"
            f"- Service: {result.get('service_display_name', result.get('service'))}\n"
            f"- Stylist: {result.get('stylist')}\n"
            f"- Date: {result.get('date')}\n"
            f"- Time: {result.get('time')}"
        )

    if tool_name == "cancel_appointment":
        cancelled = result.get("cancelled", {})

        return (
            "Your appointment has been cancelled.\n\n"
            f"- Appointment ID: {cancelled.get('id')}\n"
            f"- Summary: {cancelled.get('summary')}"
        )

    return "Done."

def format_write_action_error(tool_name: str, result: dict) -> str:
    error = result.get("error", "That action could not be completed.")

    if tool_name == "book_appointment":
        return f"I couldn't book that appointment: {error}"

    if tool_name == "modify_appointment":
        return f"I couldn't update that appointment: {error}"

    if tool_name == "cancel_appointment":
        return f"I couldn't cancel that appointment: {error}"

    return error

def tool_result_is_error(result) -> bool:
    if isinstance(result, dict):
        return "error" in result or "blocked_tool" in result
    return False

def tool_result_to_text(result) -> str:
    if isinstance(result, str):
        return result

    return json.dumps(result, indent=2)
