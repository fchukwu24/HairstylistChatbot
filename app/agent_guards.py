BOOK_REQUIRED_FIELDS = {
    "date": "date",
    "time": "time",
    "stylist": "stylist",
    "service": "service",
    "customer_name": "customer name",
}

MODIFY_CHANGE_FIELDS = {
    "date": "new date",
    "time": "new time",
    "stylist": "new stylist",
    "service": "new service",
}


def user_message_confirms(user_message: str) -> bool:
    """
    Check whether the latest user message is an explicit confirmation.
    """
    text = user_message.strip().lower()

    confirmation_phrases = {
        "yes",
        "yeah",
        "yep",
        "correct",
        "confirm",
        "confirmed",
        "that's right",
        "that is right",
        "looks good",
        "go ahead",
        "book it",
        "cancel it",
        "reschedule it",
        "make the change",
        "do it",
    }

    if text in confirmation_phrases:
        return True

    return any(phrase in text for phrase in confirmation_phrases)


def recent_assistant_asked_confirmation(history: list[dict[str, str]]) -> bool:
    """
    Check whether the recent assistant message asked the user to confirm.

    This prevents the model from booking/canceling/modifying immediately from
    a first request like:
        "Book me with Jordan tomorrow at 10."

    Instead, the assistant should first summarize the details and ask for
    confirmation.
    """
    for message in reversed(history[-6:]):
        if message.get("role") != "assistant":
            continue

        content = message.get("content", "").lower()

        confirmation_markers = [
            "confirm",
            "should i book",
            "should i cancel",
            "should i reschedule",
            "should i modify",
            "is that correct",
            "does that look right",
            "please confirm",
            "just to confirm",
        ]

        return any(marker in content for marker in confirmation_markers)

    return False

def is_missing_value(value) -> bool:
    if value in (None, ""):
        return True

    if not isinstance(value, str):
        return False

    placeholder_values = {
        "user-provided",
        "customer",
        "customer name",
        "name",
        "unknown",
        "not provided",
        "n/a",
        "none",
    }

    return value.strip().lower() in placeholder_values


def missing_fields(arguments: dict, required_fields: dict[str, str]) -> list[str]:
    missing = []

    for key, label in required_fields.items():
        if is_missing_value(arguments.get(key)):
            missing.append(label)

    return missing

def write_action_succeeded(tool_name: str, result: dict) -> bool:
    if not isinstance(result, dict):
        return False

    if result.get("error"):
        return False

    if tool_name in {"book_appointment", "modify_appointment"}:
        return bool(result.get("id"))

    if tool_name == "cancel_appointment":
        return bool(result.get("cancelled"))

    return False
