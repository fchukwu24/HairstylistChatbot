"""Loads salon booking configuration from markdown files in app/data/.

These files use YAML frontmatter so they can be both:
1. machine-readable for booking.py
2. readable by the RAG knowledge base
"""

import os
import yaml


BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")

HOURS_FILE = os.path.join(DATA_DIR, "salon_open_closed_information.md")
SERVICES_FILE = os.path.join(DATA_DIR, "salon_services.md")
STYLISTS_FILE = os.path.join(DATA_DIR, "salon_stylists.md")


def _load_yaml_frontmatter(path: str) -> dict:
    """Load YAML frontmatter from a markdown file.

    Expected format:

    ---
    key: value
    ---

    Optional markdown body can come after the second ---.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text.startswith("---"):
        raise ValueError(f"{path} must start with YAML frontmatter.")

    try:
        _start, frontmatter, _body = text.split("---", 2)
    except ValueError as e:
        raise ValueError(f"Could not parse YAML frontmatter from {path}.") from e

    data = yaml.safe_load(frontmatter)

    if not data:
        raise ValueError(f"No YAML data found in {path}.")

    return data


hours_config = _load_yaml_frontmatter(HOURS_FILE)
services_config = _load_yaml_frontmatter(SERVICES_FILE)
stylists_config = _load_yaml_frontmatter(STYLISTS_FILE)


TIMEZONE = hours_config.get("timezone", "America/Detroit")
BUSINESS_HOURS = hours_config["business_hours"]
SLOT_INTERVAL_MINUTES = hours_config.get("slot_interval_minutes", 30)


STYLISTS = list(stylists_config["stylists"].keys())
STYLISTS_FULL = stylists_config["stylists"]
STYLIST_EMAILS = {
    stylist: data.get("email", "")
    for stylist, data in stylists_config["stylists"].items()
}

SERVICES = list(services_config["services"].keys())

STYLIST_SERVICE_CATEGORIES = {
    stylist: data.get("service_categories", [])
    for stylist, data in STYLISTS_FULL.items()
}

SERVICE_CATEGORIES = {
    service: data["category"]
    for service, data in services_config["services"].items()
}

SERVICE_DURATIONS_MINUTES = {
    service: data["duration_minutes"]
    for service, data in services_config["services"].items()
}

SERVICE_DISPLAY_NAMES = {
    service: data.get("display_name", service.title())
    for service, data in services_config["services"].items()
}

SERVICE_PRICES = {
    service: data.get("price", {})
    for service, data in services_config["services"].items()
}