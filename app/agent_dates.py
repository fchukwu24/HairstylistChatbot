import dateparser
import re
from dateparser.search import search_dates
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from agent_core import AgentAction
from booking_config import TIMEZONE

def normalize_action_dates(action: AgentAction, user_message: str) -> AgentAction:
    """
    Convert vague dates like 'today', 'tomorrow', 'this Friday',
    or 'next Saturday' into YYYY-MM-DD before tool execution.

    If the user used a relative date phrase, trust Python/dateparser over the LLM.
    """
    if not isinstance(action.arguments, dict):
        return action

    arguments = dict(action.arguments)

    date_text = arguments.get("date_text")
    existing_date = arguments.get("date")

    # Best path: LLM copied the user's raw date phrase.
    if date_text:
        parsed_date = _parse_customer_date(date_text)

        if parsed_date:
            arguments["date"] = parsed_date

        arguments.pop("date_text", None)

        return AgentAction(
            tool=action.tool,
            arguments=arguments,
            reason=action.reason,
        )

    # Fallback: if the user clearly used relative words but the model gave a date,
    # override the model's date with Python parsing.
    if _contains_relative_date_phrase(user_message):
        parsed_date = _parse_customer_date(user_message)

        if parsed_date:
            arguments["date"] = parsed_date

        arguments.pop("date_text", None)

        return AgentAction(
            tool=action.tool,
            arguments=arguments,
            reason=action.reason,
        )

    # If model already gave a clean exact date, keep it.
    if _looks_like_iso_date(existing_date):
        arguments.pop("date_text", None)

        return AgentAction(
            tool=action.tool,
            arguments=arguments,
            reason=action.reason,
        )

    # Last fallback: try parsing existing date or the whole user message.
    parsed_date = _parse_customer_date(existing_date or user_message)

    if parsed_date:
        arguments["date"] = parsed_date

    arguments.pop("date_text", None)

    return AgentAction(
        tool=action.tool,
        arguments=arguments,
        reason=action.reason,
    )


def _looks_like_iso_date(value) -> bool:
    if not isinstance(value, str):
        return False

    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _parse_customer_date(text: str | None) -> str | None:
    if not text:
        return None

    manual_date = _parse_common_relative_date(text)

    if manual_date:
        return manual_date

    now = datetime.now(ZoneInfo(TIMEZONE))

    settings = {
        "RELATIVE_BASE": now.replace(tzinfo=None),
        "TIMEZONE": TIMEZONE,
        "RETURN_AS_TIMEZONE_AWARE": False,
        "PREFER_DATES_FROM": "future",
    }

    found_dates = search_dates(text, settings=settings)

    if found_dates:
        return found_dates[0][1].date().isoformat()

    parsed = dateparser.parse(text, settings=settings)

    if parsed:
        return parsed.date().isoformat()

    return None


def _parse_common_relative_date(text: str) -> str | None:
    """
    Manually handle common salon-style date phrases.

    This avoids weird cases like an LLM or parser turning
    'next Saturday' into a Friday.
    """
    text = text.lower()
    today = datetime.now(ZoneInfo(TIMEZONE)).date()

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    after_match = re.search(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+after\s+(.+)",
        text,
    )
    
    if after_match:
        target_weekday_name = after_match.group(1)
        anchor_text = after_match.group(2)

        anchor_date_text = _parse_common_relative_date(anchor_text)

        if anchor_date_text:
            anchor_date = datetime.strptime(anchor_date_text, "%Y-%m-%d").date()
            target_weekday = weekdays[target_weekday_name]

            days_ahead = (target_weekday - anchor_date.weekday()) % 7

            # "Tuesday after Saturday" should mean the following Tuesday,
            # not the same day if weekdays somehow match.
            if days_ahead == 0:
                days_ahead = 7

            return (anchor_date + timedelta(days=days_ahead)).isoformat()

    if "today" in text:
        return today.isoformat()

    if "tomorrow" in text:
        return (today + timedelta(days=1)).isoformat()
    
    
    
    for weekday_name, target_weekday in weekdays.items():
        if weekday_name not in text:
            continue

        days_ahead = (target_weekday - today.weekday()) % 7

        # If today is Saturday and user says "next Saturday",
        # they almost certainly mean 7 days from now, not today.
        if f"next {weekday_name}" in text and days_ahead == 0:
            days_ahead = 7

        return (today + timedelta(days=days_ahead)).isoformat()

    return None


def _contains_relative_date_phrase(text: str) -> bool:
    text = text.lower()

    relative_markers = [
        "today",
        "tomorrow",
        "tonight",
        "this ",
        "next ",
        "coming ",
        "weekend",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    return any(marker in text for marker in relative_markers)

