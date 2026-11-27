"""FairwAI Fellowship - Lead Processing Pipeline
Candidate ID: E34352
"""

import re
from typing import Tuple, Optional

# US State name/abbreviation mapping to 2-letter USPS postal codes
US_STATE_MAP = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
    "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC"
}


def clean_name(raw_name: Optional[str]) -> str:
    """Standardizes customer name to 'First Last' title case.
    Handles inverted formats like '  LAST, First ' and casual lowercase.
    """
    if not raw_name:
        return ""
    name = raw_name.strip()
    if not name:
        return ""
    
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        # parts[0] is Last, parts[1] is First
        first = " ".join(w.capitalize() for w in parts[1].split())
        last = " ".join(w.capitalize() for w in parts[0].split())
        return f"{first} {last}".strip()
    
    return " ".join(w.capitalize() for w in name.split())


def clean_email(raw_email: Optional[str]) -> str:
    """Standardizes email address to lowercase and trimmed."""
    if not raw_email:
        return ""
    return raw_email.strip().lower()


def is_usable_email(email: str) -> bool:
    """Validates whether email address has a valid usable structure."""
    if not email:
        return False
    # Basic RFC-compliant email regex: user@domain.tld
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def clean_phone(raw_phone: Optional[str]) -> Tuple[str, Optional[str]]:
    """Standardizes US phone number to E.164 (+1XXXXXXXXXX).
    Returns (e164_phone, flag_reason).
    """
    if not raw_phone:
        return "", "missing_phone"
    
    phone = raw_phone.strip()
    digits = re.sub(r"\D", "", phone)
    
    # Strip leading US country code if present
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    
    if len(digits) != 10:
        return phone, f"invalid_phone_digits_{len(digits)}"
    
    e164 = f"+1{digits}"
    flag = None
    # Check for fictitious/test area codes per NANP
    if digits.startswith("999") or digits.startswith("000") or digits.startswith("555"):
        flag = "suspicious_phone_number"
    
    return e164, flag


def clean_state(raw_state: Optional[str]) -> Tuple[str, Optional[str]]:
    """Standardizes state to 2-letter uppercase USPS postal code.
    Returns (state_code, flag_reason).
    """
    if not raw_state:
        return "", "missing_state"
    
    state_str = raw_state.strip()
    upper_state = state_str.upper()
    
    # Already a 2-letter code
    if len(upper_state) == 2:
        if upper_state in US_STATE_MAP.values():
            return upper_state, None
        return upper_state, f"unrecognized_state_code_{upper_state}"
    
    # Full state name lookup
    if upper_state in US_STATE_MAP:
        return US_STATE_MAP[upper_state], None
    
    return upper_state, f"unknown_state_{state_str}"
