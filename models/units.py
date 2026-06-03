"""Length parsing/conversion helpers for diameter input."""

import re

INCH_TO_CM = 2.54


def parse_inches(text: str):
    """Parse decimal or fractional inches.

    Accepts: '1.5', '0.5', '1/2', '1 1/4', '3/8'.
    Returns a float (inches) or None if unparseable / invalid.
    """
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None

    # Mixed number, e.g. "1 1/4"
    m = re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", text)
    if m:
        whole, num, den = (int(g) for g in m.groups())
        return whole + num / den if den else None

    # Simple fraction, e.g. "1/2"
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", text)
    if m:
        num, den = (int(g) for g in m.groups())
        return num / den if den else None

    # Plain decimal
    try:
        return float(text)
    except ValueError:
        return None


def parse_length_to_cm(text: str, unit: str):
    """Convert a length string in the given unit ('cm' or 'in') to cm.

    Inch input may be decimal or fractional. Returns float cm or None.
    """
    if unit == "in":
        inches = parse_inches(text)
        return inches * INCH_TO_CM if inches is not None else None
    # cm: decimal only
    try:
        return float(text.strip())
    except (ValueError, AttributeError):
        return None
