"""Tools for the agent loop. Each tool has a name, description, and
parameter spec that gets rendered into the system prompt, plus the actual
Python function that runs when the model calls it."""

import booking
import rag

TOOLS = [
    {
        "name": "search_haircare_knowledge",
        "description": "Search the haircare knowledge base. Use for any question about hair care, products, or technique -- not for booking.",
        "parameters": {"query": "string -- the haircare question or topic"},
    },
    {
        "name": "book_appointment",
        "description": "Book a new appointment. Only call this after the customer has confirmed every detail.",
        "parameters": {
            "date": "string -- required, YYYY-MM-DD",
            "date_text": "string -- optional. Copy the user's date phrase exactly if they used a relative or vague date.",
            "time": "string -- required, HH:MM",
            "stylist": f"string -- required, one of {booking.STYLISTS}",
            "service": f"string -- required, one of {booking.SERVICES}",
            "customer_name": "string -- required",
            "customer_email": "string -- optional",
        },
    },
    {
        "name": "modify_appointment",
        "description": "Change the date, time, stylist, or service on an existing appointment. Only call this after the customer has confirmed the appointment id and the requested change.",
        "parameters": {
            "appointment_id": "string -- required",
            "date": "string -- optional, YYYY-MM-DD",
            "date_text": "string -- optional. Copy the user's date phrase exactly if they used a relative or vague date.",
            "time": "string -- optional, HH:MM",
            "stylist": f"string -- optional, one of {booking.STYLISTS}",
            "service": f"string -- optional, one of {booking.SERVICES}",
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing appointment. Only call this after the customer has explicitly confirmed the appointment id and cancellation",
        "parameters": {
            "appointment_id": "string -- required"
        },
    },
    {
    "name": "get_booking_info",
    "description": (
        "Get read-only salon booking information. Use for salon hours, "
        "service lists, service categories, whether the salon offers a service, "
        "stylist capabilities, and appointment availability. "
        "Do not use this to book, modify, or cancel appointments."
    ),
    "parameters": {
        "request_type": (
            "string -- optional, one of: auto, hours, services, "
            "service_check, category_options, stylist_capabilities, availability"
        ),
        "date": "string -- optional, YYYY-MM-DD. Use only if the user gave an exact date or the date is already known.",
        "date_text": "string -- optional. Copy the user's date phrase exactly if they used a relative or vague date, such as today, tomorrow, next Saturday, this Friday, July 4, or next week.",
        "stylist": "string -- optional",
        "service": "string -- optional, exact service or broad category",
        "category": "string -- optional, broad service category",
    },
    },
]

REQUIRED_ARGS = {
    "search_haircare_knowledge": {"query"},
    "check_availability": {"date"},
    "book_appointment": {"date", "time", "stylist", "service", "customer_name"},
    "modify_appointment": {"appointment_id"},
    "cancel_appointment": {"appointment_id"},
    "get_salon_hours": {"date"},
    "get_booking_info": set(),
}

def render_tools_for_prompt() -> str:
    """Turn the tool registry into text the model reads in its system prompt."""
    lines = []
    for tool in TOOLS:
        params = ", ".join(
            f"{key} ({value})"
            for key, value in tool["parameters"].items()
        )
        lines.append(f"- {tool['name']}({params}): {tool['description']}")
    return "\n".join(lines)

def validate_required_args(name: str, arguments: dict) -> dict | None:
    """Return an error dict if required tool arguments are missing."""
    required = REQUIRED_ARGS.get(name, set())

    missing = sorted(
        arg for arg in required
        if arg not in arguments or arguments.get(arg) in (None, "")
    )

    if missing:
        return {
            "error": (
                f"Missing required argument(s) for {name}: "
                f"{', '.join(missing)}."
            )
        }

    return None

def validate_known_values(name: str, arguments: dict) -> dict | None:
    """Return an error dict if stylist/service values are invalid."""
    stylist = arguments.get("stylist")
    service = arguments.get("service")

    if stylist and booking._normalize_stylist(stylist) is None:
        return {
            "error": (
                f"Invalid stylist '{stylist}'. "
                f"Choose one of: {booking.STYLISTS}."
            )
        }

    exact_service_tools = {
        "book_appointment",
        "modify_appointment",
        "check_availability",
    }

    if (
        service
        and name in exact_service_tools
        and booking._normalize_service(service) is None
    ):
        return {
            "error": (
                f"Invalid service '{service}'. "
                f"Choose one of: {booking.SERVICES}."
            )
        }

    return None

def execute_tool(name: str, arguments: dict):
    """Dispatch a parsed tool call to the matching Python function."""
    if name not in REQUIRED_ARGS:
        return {"error": f"Unknown tool: {name}"}
    
    if not isinstance(arguments, dict):
        return {"error": f"Tool arguments for {name} must be a JSON object."}
    
    missing_error = validate_required_args(name, arguments)
    if missing_error:
        return missing_error

    value_error = validate_known_values(name, arguments)
    if value_error:
        return value_error
    
    try:
        match name:
            case "search_haircare_knowledge": 
                return rag.search_knowledge_base(arguments["query"])
            case "get_booking_info":
                return booking.get_booking_info(
                    request_type=arguments.get("request_type", "auto"),
                    date=arguments.get("date"),
                    stylist=arguments.get("stylist"),
                    service=arguments.get("service"),
                    category=arguments.get("category"),
                )
            case "book_appointment":
                # print(f'Booking appointment for {arguments["customer_name"]} with email {arguments.get("customer_email")} at {arguments["date"]} and {arguments["time"]} with {arguments["stylist"]} for {arguments["service"]}')
                return booking.book_appointment(
                    date=arguments["date"],
                    time=arguments["time"],
                    stylist=arguments["stylist"],
                    service=arguments["service"],
                    customer_name=arguments["customer_name"],
                    customer_email=arguments.get("customer_email"),
                    )
            case "modify_appointment":
                return booking.modify_appointment(
                    appointment_id=arguments["appointment_id"],
                    date=arguments.get("date"),
                    time=arguments.get("time"),
                    stylist=arguments.get("stylist"),
                    service=arguments.get("service"),
                    )
            case "cancel_appointment":
                return booking.cancel_appointment(appointment_id=arguments["appointment_id"])
    except TypeError as e:
        return {"error": f"Tool call failed because of invalid arguments: {e}"}
    except Exception as e:
        return {"error": f"Tool call failed unexpectedly: {e}"}
