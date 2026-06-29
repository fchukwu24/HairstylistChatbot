"""Google Calendar-backed appointment backend.

This module replaces the old in-memory mock booking system.

It uses:
- Google Calendar API for real appointment events
- a shared booking calendar from GOOGLE_CALENDAR_ID
- business hours from booking_config.py
- stylists from booking_config.py
- services, durations, and prices from booking_config.py
"""

import os
from datetime import datetime, date as date_cls, time as time_cls, timedelta
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from booking_config import (
    STYLIST_SERVICE_CATEGORIES,
    TIMEZONE,
    BUSINESS_HOURS,
    SLOT_INTERVAL_MINUTES,
    STYLISTS,
    STYLIST_EMAILS,
    SERVICES,
    SERVICE_DURATIONS_MINUTES,
    SERVICE_DISPLAY_NAMES,
    SERVICE_PRICES,
    SERVICE_CATEGORIES
)

def _normalize_category(category: str | None) -> str | None:
    if not category:
        return None

    return " ".join(category.strip().lower().split())


def build_generic_service_categories(min_services: int = 2) -> dict[str, list[str]]:
    generic_categories: dict[str, list[str]] = {}

    for service, category in SERVICE_CATEGORIES.items():
        display_name = SERVICE_DISPLAY_NAMES.get(service, service.title())

        generic_categories.setdefault(category, []).append(display_name)

    return {
        category: sorted(display_names)
        for category, display_names in generic_categories.items()
        if len(display_names) >= min_services
    }


GENERIC_SERVICE_CATEGORIES = build_generic_service_categories()

def get_generic_service_options(service: str | None) -> list[str] | None:
    """
    Return service options for a broad/generic service category.

    Example:
    "braids" -> ["Box Braids", "Crochet Braids", ...]
    """
    category = _normalize_category(service)

    if not category:
        return None

    return GENERIC_SERVICE_CATEGORIES.get(category)

def _render_generic_service_names() -> str:
        return ", ".join(GENERIC_SERVICE_CATEGORIES.keys())
    
SCOPES = ["https://www.googleapis.com/auth/calendar"]

BASE_DIR = os.path.dirname(__file__)
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

# Shared calendar ID from .env. Falls back to primary for testing.
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")


def _get_calendar_service():
    """Build and return an authenticated Google Calendar service."""
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(
            "Google Calendar token.json was not found. "
            "Run the Google Calendar auth test first."
        )

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _normalize_stylist(stylist: str | None) -> str | None:
    """Match stylist names case-insensitively."""
    if not stylist:
        return None

    stylist = stylist.strip()

    for valid_stylist in STYLISTS:
        if stylist.lower() == valid_stylist.lower():
            return valid_stylist

    return None


def _normalize_service(service: str | None) -> str | None:
    """Match service names case-insensitively."""
    if not service:
        return None

    service = service.strip()

    for valid_service in SERVICES:
        if service.lower() == valid_service.lower():
            return valid_service

    return None


def _parse_date(date_str: str) -> date_cls:
    """Parse YYYY-MM-DD into a date object."""
    year, month, day = map(int, date_str.split("-"))
    return date_cls(year, month, day)


def _parse_time(time_str: str) -> time_cls:
    """Parse HH:MM into a time object."""
    hour, minute = map(int, time_str.split(":"))
    return time_cls(hour, minute)


def _parse_start_datetime(date_str: str, time_str: str) -> datetime:
    """Turn YYYY-MM-DD + HH:MM into a timezone-aware datetime."""
    return datetime.combine(
        _parse_date(date_str),
        _parse_time(time_str),
        tzinfo=ZoneInfo(TIMEZONE),
    )

def _parse_google_datetime(value: str) -> datetime:
    """Parse Google Calendar dateTime values safely."""
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")

    return datetime.fromisoformat(value).astimezone(ZoneInfo(TIMEZONE))

def _day_bounds(date_str: str) -> tuple[datetime, datetime]:
    """Return start/end datetime for a calendar day."""
    start = datetime.combine(
        _parse_date(date_str),
        time_cls(0, 0),
        tzinfo=ZoneInfo(TIMEZONE),
    )

    end = start + timedelta(days=1)
    return start, end


def _service_duration(service: str | None) -> int:
    """Return service duration in minutes.

    If service is not provided, assume 60 minutes for general availability checks.
    """
    if not service:
        return 60

    return SERVICE_DURATIONS_MINUTES.get(service, 60)


def _service_display_name(service: str) -> str:
    """Return display name for a service."""
    return SERVICE_DISPLAY_NAMES.get(service, service.title())


def _service_price(service: str) -> dict:
    """Return price info for a service."""
    return SERVICE_PRICES.get(service, {})


def _format_price(service: str) -> str:
    """Create readable price text for calendar event descriptions."""
    price = _service_price(service)

    if not price:
        return "Price: Not listed"

    starting = price.get("starting_at_usd")
    price_range = price.get("range_usd")
    note = price.get("note")

    lines = []

    if starting is not None:
        lines.append(f"Starting at: ${starting}")

    if price_range and len(price_range) == 2:
        lines.append(f"Estimated range: ${price_range[0]}-${price_range[1]}")

    if note:
        lines.append(f"Price note: {note}")

    return "\n".join(lines) if lines else "Price: Not listed"


def _get_events_for_date(date_str: str) -> list[dict]:
    """Fetch all events from the shared booking calendar for one date."""
    calendar_service = _get_calendar_service()
    start, end = _day_bounds(date_str)

    response = calendar_service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return response.get("items", [])


def _event_stylist(event: dict) -> str | None:
    """Get stylist from event extended properties or event title."""
    private_props = event.get("extendedProperties", {}).get("private", {})
    stylist = private_props.get("stylist")

    if stylist:
        return stylist

    summary = event.get("summary", "")

    for valid_stylist in STYLISTS:
        if valid_stylist.lower() in summary.lower():
            return valid_stylist

    return None


def _event_overlaps_slot(event: dict, slot_start: datetime, slot_end: datetime) -> bool:
    """Return True if a calendar event overlaps an appointment slot."""
    if event.get("status") == "cancelled":
        return False

    start_data = event.get("start", {})
    end_data = event.get("end", {})

    # Timed event
    if "dateTime" in start_data and "dateTime" in end_data:
        event_start = _parse_google_datetime(start_data["dateTime"])
        event_end = _parse_google_datetime(end_data["dateTime"])

        return event_start < slot_end and event_end > slot_start

    # All-day event blocks the whole day.
    if "date" in start_data and "date" in end_data:
        event_start = date_cls.fromisoformat(start_data["date"])
        event_end = date_cls.fromisoformat(end_data["date"])
        slot_date = slot_start.date()

        return event_start <= slot_date < event_end

    return False

 # Booking Management Methods

def book_appointment(
    date: str,
    time: str,
    stylist: str,
    service: str,
    customer_name: str,
    customer_email: str = None,
) -> dict:
    """Create a new appointment event on the shared Google Calendar."""
    normalized_stylist = _normalize_stylist(stylist)
    normalized_service = _normalize_service(service)

    if not normalized_stylist:
        return {"error": f"Invalid stylist. Choose one of: {STYLISTS}"}

    if not normalized_service:
        return {"error": f"Invalid service. Choose one of: {SERVICES}"}

    possible_slots = _generate_possible_slots_per_stylist(date, normalized_stylist, normalized_service)

    if time not in possible_slots:
        return {
            "error": (
                f"{time} is not a valid start time for "
                f"{_service_display_name(normalized_service)} on {date}. "
                "The full service must fit before closing."
            )
        }

    events = _get_events_for_date(date)

    if not _is_slot_available(
        date_str=date,
        time_str=time,
        stylist=normalized_stylist,
        service=normalized_service,
        events=events,
    ):
        return {
            "error": (
                f"{normalized_stylist} is not available for "
                f"{_service_display_name(normalized_service)} at {time} on {date}."
            )
        }

    start_time = _parse_start_datetime(date, time)
    duration_minutes = _service_duration(normalized_service)
    end_time = start_time + timedelta(minutes=duration_minutes)

    display_service = _service_display_name(normalized_service)
    price_info = _service_price(normalized_service)

    attendees = []

    stylist_email = STYLIST_EMAILS.get(normalized_stylist)
    if stylist_email:
        attendees.append({"email": stylist_email})

    if customer_email:
        attendees.append({"email": customer_email})

    event = {
        "summary": f"{display_service} with {normalized_stylist} for {customer_name}",
        "description": (
            "Appointment created by Haircare Assistant.\n\n"
            f"Customer: {customer_name}\n"
            f"Customer email: {customer_email or 'Not provided'}\n"
            f"Stylist: {normalized_stylist}\n"
            f"Service: {display_service}\n"
            f"Duration: {duration_minutes} minutes\n"
            f"{_format_price(normalized_service)}"
        ),
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": TIMEZONE,
        },
        "attendees": attendees,
        "extendedProperties": {
            "private": {
                "created_by": "haircare_assistant",
                "customer_name": customer_name,
                "customer_email": customer_email or "",
                "stylist": normalized_stylist,
                "service": normalized_service,
                "duration_minutes": str(duration_minutes),
            }
        },
    }

    calendar_service = _get_calendar_service()

    created_event = calendar_service.events().insert(
        calendarId=CALENDAR_ID,
        body=event,
        sendUpdates="all",
    ).execute()

    return {
        "id": created_event["id"],
        "date": date,
        "time": time,
        "stylist": normalized_stylist,
        "service": normalized_service,
        "service_display_name": display_service,
        "duration_minutes": duration_minutes,
        "price": price_info,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "calendar_link": created_event.get("htmlLink"),
    }

def modify_appointment(
    appointment_id: str,
    date: str = None,
    time: str = None,
    stylist: str = None,
    service: str = None,
) -> dict:
    """Update fields on an existing Google Calendar appointment."""
    calendar_service = _get_calendar_service()

    try:
        event = calendar_service.events().get(
            calendarId=CALENDAR_ID,
            eventId=appointment_id,
        ).execute()
    except Exception:
        return {"error": f"No appointment found with id {appointment_id}."}

    private_props = event.get("extendedProperties", {}).get("private", {})

    current_stylist = private_props.get("stylist")
    current_service = private_props.get("service")
    current_customer = private_props.get("customer_name", "customer")
    current_customer_email = private_props.get("customer_email", "")

    new_stylist = _normalize_stylist(stylist) if stylist else current_stylist
    new_service = _normalize_service(service) if service else current_service

    if not new_stylist:
        return {"error": f"Invalid stylist. Choose one of: {STYLISTS}"}

    if not new_service:
        return {"error": f"Invalid service. Choose one of: {SERVICES}"}

    if "dateTime" not in event.get("start", {}):
        return {"error": "This appointment does not have a timed start value."}

    old_start = _parse_google_datetime(event["start"]["dateTime"])

    new_date = date or old_start.date().isoformat()
    new_time = time or old_start.strftime("%H:%M")

    possible_slots = _generate_possible_slots_per_stylist(new_date, new_stylist, new_service)

    if new_time not in possible_slots:
        return {
            "error": (
                f"{new_time} is not a valid start time for "
                f"{_service_display_name(new_service)} on {new_date}. "
                "The full service must fit before closing."
            )
        }

    events = _get_events_for_date(new_date)

    if not _is_slot_available(
        date_str=new_date,
        time_str=new_time,
        stylist=new_stylist,
        service=new_service,
        events=events,
        ignore_event_id=appointment_id,
    ):
        return {
            "error": (
                f"{new_stylist} is not available for "
                f"{_service_display_name(new_service)} at {new_time} on {new_date}."
            )
        }

    start_time = _parse_start_datetime(new_date, new_time)
    duration_minutes = _service_duration(new_service)
    end_time = start_time + timedelta(minutes=duration_minutes)

    display_service = _service_display_name(new_service)

    event["summary"] = f"{display_service} with {new_stylist} for {current_customer}"
    event["description"] = (
        "Appointment updated by Haircare Assistant.\n\n"
        f"Customer: {current_customer}\n"
        f"Customer email: {current_customer_email or 'Not provided'}\n"
        f"Stylist: {new_stylist}\n"
        f"Service: {display_service}\n"
        f"Duration: {duration_minutes} minutes\n"
        f"{_format_price(new_service)}"
    )

    event["start"] = {
        "dateTime": start_time.isoformat(),
        "timeZone": TIMEZONE,
    }

    event["end"] = {
        "dateTime": end_time.isoformat(),
        "timeZone": TIMEZONE,
    }

    attendees = []

    stylist_email = STYLIST_EMAILS.get(new_stylist)
    if stylist_email:
        attendees.append({"email": stylist_email})

    if current_customer_email:
        attendees.append({"email": current_customer_email})

    event["attendees"] = attendees

    event["extendedProperties"] = {
        "private": {
            **private_props,
            "stylist": new_stylist,
            "service": new_service,
            "duration_minutes": str(duration_minutes),
        }
    }

    updated_event = calendar_service.events().update(
        calendarId=CALENDAR_ID,
        eventId=appointment_id,
        body=event,
        sendUpdates="all",
    ).execute()

    return {
        "id": updated_event["id"],
        "date": new_date,
        "time": new_time,
        "stylist": new_stylist,
        "service": new_service,
        "service_display_name": display_service,
        "duration_minutes": duration_minutes,
        "calendar_link": updated_event.get("htmlLink"),
    }

def cancel_appointment(appointment_id: str) -> dict:
    """Cancel/delete an existing Google Calendar appointment."""
    calendar_service = _get_calendar_service()

    try:
        event = calendar_service.events().get(
            calendarId=CALENDAR_ID,
            eventId=appointment_id,
        ).execute()

        calendar_service.events().delete(
            calendarId=CALENDAR_ID,
            eventId=appointment_id,
            sendUpdates="all",
        ).execute()

        return {
            "cancelled": {
                "id": appointment_id,
                "summary": event.get("summary"),
            }
        }
    
    except HttpError as e:
        if e.resp.status == 404:
            return {"error": f"No appointment found with id {appointment_id}."}
    raise

# Booking Info Methods
# Main Tool Call
def get_booking_info(
    request_type: str = "auto",
    date: str | None = None,
    stylist: str | None = None,
    service: str | None = None,
    category: str | None = None,) -> dict:
    #  """
    # Read-only booking info helper.

    # Handles:
    # - salon hours
    # - service list
    # - category/service options
    # - service checks
    # - stylist capability checks
    # - availability checks
    # """
    request_type = (request_type or "auto").strip().lower()

    if request_type == "hours":
        if not date:
            return {"error": "date is required for hours."}

        return get_salon_hours(date)

    if request_type in {"services", "service_catalog", "catalog"}:
        return {
            "services": [
                {
                    "service": service_key,
                    "display_name": _service_display_name(service_key),
                    "category": SERVICE_CATEGORIES.get(service_key),
                    "duration_minutes": _service_duration(service_key),
                    "price": _service_price(service_key),
                }
                for service_key in SERVICES
            ],
            "generic_service_categories": GENERIC_SERVICE_CATEGORIES,
        }

    if request_type in {"category_options", "service_options"}:
        requested_category = category or service
        options = get_generic_service_options(requested_category)

        if not options:
            return {
                "category": requested_category,
                "services": [],
                "message": "No multi-service category found for that request.",
            }

        return {
            "category": _normalize_category(requested_category),
            "services": options,
        }

    if request_type in {"service_check", "offers", "offered"}:
        normalized_service = _normalize_service(service)
        requested_category = _normalize_category(category or service)

        if normalized_service:
            return {
                "offered": True,
                "match_type": "exact_service",
                "service": normalized_service,
                "display_name": _service_display_name(normalized_service),
                "category": SERVICE_CATEGORIES.get(normalized_service),
                "duration_minutes": _service_duration(normalized_service),
                "price": _service_price(normalized_service),
            }

        if requested_category in GENERIC_SERVICE_CATEGORIES:
            return {
                "offered": True,
                "match_type": "category",
                "category": requested_category,
                "services": GENERIC_SERVICE_CATEGORIES[requested_category],
            }

        return {
            "offered": False,
            "requested_service": service,
            "requested_category": category,
            "message": "The salon does not list that service or category.",
        }

    if request_type in {"stylist_capabilities", "capabilities"}:
        normalized_stylist = _normalize_stylist(stylist)

        if stylist and not normalized_stylist:
            return {"error": f"Invalid stylist. Choose one of: {STYLISTS}."}

        stylists_to_check = [normalized_stylist] if normalized_stylist else STYLISTS

        normalized_service = _normalize_service(service)
        requested_category = _normalize_category(category or service)

        results = {}

        for stylist_name in stylists_to_check:
            stylist_categories = STYLIST_SERVICE_CATEGORIES.get(stylist_name, [])

            if normalized_service:
                results[stylist_name] = {
                    "can_perform": can_perform_service(stylist_name, normalized_service),
                    "service": normalized_service,
                    "display_name": _service_display_name(normalized_service),
                    "category": SERVICE_CATEGORIES.get(normalized_service),
                }
            elif requested_category:
                results[stylist_name] = {
                    "can_perform": requested_category in stylist_categories,
                    "category": requested_category,
                    "stylist_categories": stylist_categories,
                }
            else:
                results[stylist_name] = {
                    "service_categories": stylist_categories,
                }

        return {"stylists": results}

    if request_type == "availability":
        if not date:
            return {"error": "date is required for availability."}

        normalized_service = _normalize_service(service)

        if service and not normalized_service:
            requested_category = _normalize_category(service)

            if requested_category in GENERIC_SERVICE_CATEGORIES:
                return {
                    "error": (
                        f"'{service}' is a category, not a specific service. "
                        f"Choose one of: {', '.join(GENERIC_SERVICE_CATEGORIES[requested_category])}."
                    )
                }

            return {"error": f"Invalid service '{service}'. Choose one of: {SERVICES}."}

        return check_availability(
            date=date,
            stylist=stylist,
            service=normalized_service,
        )

    if request_type == "auto":
        if date:
            return check_availability(
                date=date,
                stylist=stylist,
                service=_normalize_service(service),
            )

        if service or category:
            return get_booking_info(
                request_type="service_check",
                service=service,
                category=category,
            )

        return get_booking_info(request_type="services")

    return {
        "error": (
            f"Unknown request_type '{request_type}'. "
            "Choose one of: auto, hours, services, service_check, "
            "category_options, stylist_capabilities, availability."
        )
    }
# get_salon_hours(date) - checks salon hours for a day
def get_salon_hours(date: str) -> dict:
    """Return salon open/close information for a specific date."""
    hours = _get_business_hours_for_date(date)

    if not hours:
        return {
            "date": date,
            "closed": True,
            "message": "The salon is closed on this date.",
        }

    return {
        "date": date,
        "closed": False,
        "open": hours["open"],
        "close": hours["close"],
        "timezone": TIMEZONE,
    }

def _get_business_hours_for_date(date_str: str) -> dict | None:
    """Return business hours for a date, or None if the salon is closed."""
    weekday = _parse_date(date_str).strftime("%A").lower()
    hours = BUSINESS_HOURS.get(weekday)

    if not hours:
        return None

    if hours.get("closed"):
        return None

    if "open" not in hours or "close" not in hours:
        return None

    return hours

def check_availability(date: str, stylist: str = None, service: str = None) -> dict:
    """Return open slots for a date.

    If stylist is provided, only that stylist is checked.
    If service is provided, the service duration controls which slots fit.
    """
    normalized_stylist = _normalize_stylist(stylist)
    normalized_service = _normalize_service(service)

    if stylist and not normalized_stylist:
        return {"error": f"Invalid stylist. Choose one of: {STYLISTS}"}

    if service and not normalized_service:
        return {"error": f"Invalid service. Choose one of: {SERVICES}"}

    if not _get_business_hours_for_date(date):
        return {
            "date": date,
            "service": normalized_service,
            "duration_minutes": _service_duration(normalized_service),
            "availability": {},
            "message": "The salon is closed on this date.",
        }

    stylists_to_check = [normalized_stylist] if normalized_stylist else STYLISTS
    possible_slots = {}
    for stylist in stylists_to_check:
        possible_slots[stylist] = _generate_possible_slots_per_stylist(date, stylist, normalized_service)
    events = _get_events_for_date(date)

    availability = {}

    for stylist_name in stylists_to_check:
        open_slots = []

        for slot in possible_slots[stylist_name]:
            if _is_slot_available(
                date_str=date,
                time_str=slot,
                stylist=stylist_name,
                service=normalized_service,
                events=events,
            ):
                open_slots.append(slot)

        availability[stylist_name] = open_slots

    return {
        "date": date,
        "service": normalized_service,
        "duration_minutes": _service_duration(normalized_service),
        "availability": availability,
    }

def _is_slot_available(
    date_str: str,
    time_str: str,
    stylist: str,
    service: str | None,
    events: list[dict],
    ignore_event_id: str | None = None,
) -> bool:
    """Check whether a stylist is free for a specific service slot."""
    slot_start = _parse_start_datetime(date_str, time_str)
    slot_end = slot_start + timedelta(minutes=_service_duration(service))

    for event in events:
        if ignore_event_id and event.get("id") == ignore_event_id:
            continue

        booked_stylist = _event_stylist(event)

        # If the event has a stylist, it only blocks that stylist.
        # If no stylist is found, treat it as blocking everyone.
        stylist_matches = booked_stylist is None or booked_stylist == stylist

        if stylist_matches and _event_overlaps_slot(event, slot_start, slot_end):
            return False

    return True

# Helper function to generate all possible slots that a service can be done by a stylist in the salon,
# or if no service is specified then all available times
def _generate_possible_slots_per_stylist(date_str: str, stylist: str, service: str | None = None) -> list[str]:
    """Generate possible appointment start times from business hours.

    A slot is only returned if the full service duration fits before closing.
    """
    hours = _get_business_hours_for_date(date_str)

    if (service and not _can_perform_service(stylist=stylist,service=service)) or not hours:
        return []

    duration_minutes = _service_duration(service)

    open_dt = _parse_start_datetime(date_str, hours["open"])
    close_dt = _parse_start_datetime(date_str, hours["close"])

    slots = []
    current = open_dt

    while current + timedelta(minutes=duration_minutes) <= close_dt:
        
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=SLOT_INTERVAL_MINUTES)

    return slots

# External function wrapper
def can_perform_service(stylist: str, service: str) -> bool:
    norm_stylist = _normalize_service(stylist)
    norm_service = _normalize_service(service)
    if not norm_stylist or not norm_service:
        return False
    else: 
        return _can_perform_service(norm_stylist, norm_service)
    
def _can_perform_service(stylist: str, service: str) -> bool:
    
    if not service:
        return True
    
    service_category = SERVICE_CATEGORIES.get(service)
    
    if not service_category:
        return True
    
    stylist_categories = STYLIST_SERVICE_CATEGORIES.get(stylist, []) # List of categories offered by stylist
    
    return service_category in stylist_categories


