import re

def extract_session_id(value):
    """Extract the session ID from a Dialogflow session or context path."""
    match = re.search(r"/sessions/([^/]+)", value or "")
    return match.group(1) if match else ""


def get_str_from_food_dict(items):
    """Format a cart, for example: '2 Pizza, 1 Mango Lassi'."""
    return (
        ", ".join(
            f"{quantity} {name}"
            for name, quantity in items.items()
        )
        or "nothing yet"
    )
