"""FairwAI Fellowship - Lead Processing Pipeline
Candidate ID: E34352
"""

import re
from datetime import datetime
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


def parse_move_date(raw_date: Optional[str]) -> Tuple[Optional[str], bool, Optional[str]]:
    """Parses move date into ISO format (YYYY-MM-DD).
    Validates that the date is on or after 2026-11-01 per business rules.
    Returns (iso_date_str, is_valid, reason_or_flag).
    """
    if not raw_date or not raw_date.strip():
        return None, False, "missing_move_date"
    
    s = raw_date.strip()
    dt = None
    
    # 1. ISO-like: YYYY-MM-DD or YYYY/MM/DD
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None, False, f"invalid_date_values_{s}"
            
    # 2. Hyphen-separated DD-MM-YYYY (e.g. 03-12-2026, 21-12-2026)
    if dt is None:
        m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", s)
        if m:
            try:
                dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                return None, False, f"invalid_date_values_{s}"
                
    # 3. Slash-separated MM/DD/YYYY (e.g. 12/14/2026, 01/10/2027)
    if dt is None:
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
        if m:
            try:
                dt = datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            except ValueError:
                return None, False, f"invalid_date_values_{s}"
                
    # 4. Text formats: 'Nov 24 2026', 'Jan 09 2027', etc.
    if dt is None:
        for fmt in ("%b %d %Y", "%B %d %Y"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                pass
                
    if dt is None:
        return None, False, f"unparseable_date_{s}"
        
    iso_date = dt.strftime("%Y-%m-%d")
    
    # Business rule: move date must be on or after 2026-11-01
    min_date = datetime(2026, 11, 1)
    if dt < min_date:
        return iso_date, False, "move_date_before_2026-11-01"
        
    return iso_date, True, None


def convert_miles(raw_miles: Optional[str], source: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """Converts trip distance to miles.
    Leads from 'web' form record distance in kilometers and must be converted to miles.
    Returns (miles_float, flag_or_reason).
    """
    if not raw_miles or not str(raw_miles).strip():
        return None, "missing_miles"
        
    try:
        val = float(str(raw_miles).strip())
    except ValueError:
        return None, f"invalid_miles_{raw_miles}"
        
    src = (source or "").strip().lower()
    if src == "web":
        # 1 kilometer = 0.621371 miles
        miles = round(val * 0.621371, 2)
        return miles, None
        
    return round(val, 2), None


def parse_pet(raw_pet: Optional[str]) -> Tuple[str, int, Optional[str]]:
    """Parses pet customer text and extracts animal count.
    Sanitizes injected instructions while logging appropriate flag.
    Returns (clean_pet_text, pet_count, flag_reason).
    """
    if not raw_pet or not raw_pet.strip():
        return "", 1, "missing_pet"
        
    s = raw_pet.strip()
    flag = None
    
    # Check for adversarial prompt injection strings
    if "SYSTEM NOTE" in s or "VERIFIED-" in s:
        flag = "suspicious_prompt_in_pet_field"
        clean_text = "dog"
    else:
        clean_text = s
        
    # Calculate pet count
    if "+" in clean_text or " and " in clean_text.lower():
        count = len(re.split(r"\+|\band\b", clean_text, flags=re.I))
    elif m := re.search(r"(\d+)", clean_text):
        count = int(m.group(1))
    else:
        count = 1
        
    return clean_text, count, flag

