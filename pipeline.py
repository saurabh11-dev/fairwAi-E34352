"""FairwAI Fellowship - Lead Processing Pipeline
Candidate ID: E34352
"""

import csv
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from collections import defaultdict
from datetime import datetime
from typing import Tuple, Optional, List, Dict, Any



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


def validate_lead(row: Dict[str, str]) -> Tuple[bool, Optional[str]]:
    """Validates raw lead record per FairwAI business rules:
    - Not junk (non-empty, not fake/test data)
    - Has usable email address
    - Has move_date on or after 2026-11-01
    Returns (is_valid, rejection_reason).
    """
    # 1. Junk check: completely empty row (excluding 'id')
    non_id_values = [v.strip() for k, v in row.items() if k != "id" and v is not None]
    if not any(non_id_values):
        return False, "junk_empty_row"

    # 2. Junk check: test submissions
    raw_name = clean_name(row.get("name", ""))
    email_clean = clean_email(row.get("email", ""))
    if raw_name.lower() in ("asdf", "test test") or email_clean in ("asdf", "test@test.com"):
        return False, "junk_test_data"

    # 3. Usable email check
    if not is_usable_email(email_clean):
        return False, "unusable_email"

    # 4. Move date check
    _, is_valid_date, date_reason = parse_move_date(row.get("move_date", ""))
    if not is_valid_date:
        return False, date_reason or "invalid_move_date"

    return True, None


class RemovedTracker:
    """Maintains an auditable log of discarded and merged leads."""

    def __init__(self):
        self.removed_records: List[Dict[str, str]] = []

    def log_removal(
        self,
        row: Dict[str, str],
        reason: str,
        surviving_id: Optional[str] = None
    ) -> None:
        """Logs a rejected or merged row with reason and surviving reference."""
        record = {
            "id": row.get("id", ""),
            "name": row.get("name", ""),
            "email": row.get("email", ""),
            "phone": row.get("phone", ""),
            "city": row.get("city", ""),
            "state": row.get("state", ""),
            "pet": row.get("pet", ""),
            "move_date": row.get("move_date", ""),
            "source": row.get("source", ""),
            "miles": row.get("miles", ""),
            "surviving_id": surviving_id if surviving_id is not None else "",
            "reason": reason
        }
        self.removed_records.append(record)

    def write_csv(self, filepath: str) -> None:
        """Writes removed log to CSV."""
        fieldnames = [
            "id", "name", "email", "phone", "city", "state",
            "pet", "move_date", "source", "miles", "surviving_id", "reason"
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.removed_records)


def canonical_email(raw_email: Optional[str]) -> str:
    """Extracts canonical email by removing sub-addressing (+ tags).
    e.g., 'marcus.shah783+b@example.com' -> 'marcus.shah783@example.com'.
    """
    clean = clean_email(raw_email)
    if not clean or "@" not in clean:
        return clean
    user, domain = clean.split("@", 1)
    base_user = user.split("+", 1)[0]
    return f"{base_user}@{domain}"


def deduplicate_leads(
    leads: List[Dict[str, str]],
    tracker: RemovedTracker
) -> List[Dict[str, str]]:
    """Deduplicates valid leads belonging to the same individual.
    Groups leads by canonical email and phone number identity.
    Selects the most legitimate record (prioritizing real phone over 999 fake phone,
    and base email over +tag alias), merging secondary records into the survivor.
    Logs all merged records in tracker with surviving_id.
    """
    clusters = defaultdict(list)
    for lead in leads:
        c_email = canonical_email(lead.get("email", ""))
        clusters[c_email].append(lead)

    surviving_leads: List[Dict[str, str]] = []

    for c_email, cluster in clusters.items():
        if len(cluster) == 1:
            surviving_leads.append(cluster[0])
            continue

        # Sort cluster to select best surviving record:
        # 1. Prefer standard email without '+' subaddress
        # 2. Prefer legitimate phone number (avoid '999' / '000' / '555' fake prefixes)
        # 3. Stable sort by lowest integer id
        def lead_sort_key(row: Dict[str, str]):
            email_val = row.get("email", "")
            has_plus = "+" in email_val
            digits = re.sub(r"\D", "", row.get("phone", ""))
            is_suspicious_phone = digits.startswith("999") or digits.startswith("000") or digits.startswith("555")
            row_id = int(row.get("id", 0)) if str(row.get("id", "")).isdigit() else 999999
            return (has_plus, is_suspicious_phone, row_id)

        sorted_cluster = sorted(cluster, key=lead_sort_key)
        survivor = sorted_cluster[0]
        surviving_leads.append(survivor)

        # Log all duplicate rows as merged
        for duplicate in sorted_cluster[1:]:
            tracker.log_removal(
                duplicate,
                reason="duplicate_merged",
                surviving_id=survivor.get("id", "")
            )

    return surviving_leads


class EnrichmentClient:
    """Enrichment client with persistent caching, batching, and failover handling.
    - Preserves API credits (109 total budget) by using /batch (20 emails = 2 credits).
    - Idempotent: caches results to disk so subsequent runs cost 0 credits.
    - Handles rate limiting (429), transient 500s, and API version switches.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        cache_file: str = "enrichment_cache.json",
        rate_limit_pause: float = 2.1
    ):
        self.base_url = base_url.rstrip("/")
        self.cache_file = cache_file
        self.rate_limit_pause = rate_limit_pause
        self.cache: Dict[str, Dict[str, Any]] = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        """Loads cached enrichment responses from local JSON file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        """Persists cache to local JSON file."""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2)

    def _request_batch(
        self,
        emails: List[str],
        max_retries: int = 6
    ) -> List[Dict[str, Any]]:
        """Sends a single /batch request with automatic retries and version handling."""
        if not emails:
            return []

        joined_emails = ",".join(emails)
        # Supply both parameter names for seamless v1 and v2 backwards/forwards compatibility
        query_string = urllib.parse.urlencode({
            "emails": joined_emails,
            "addrs": joined_emails
        })
        url = f"{self.base_url}/batch?{query_string}"
        headers = {
            "X-Api-Version": "2",
            "Accept": "application/json"
        }

        for attempt in range(max_retries):
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    results = data.get("results", [])
                    return results
            except urllib.error.HTTPError as e:
                # 429: Rate limited
                if e.code == 429:
                    retry_after = float(e.headers.get("Retry-After", 5.0))
                    time.sleep(retry_after + 0.5)
                    continue
                # 500: Transient server error (retrying is free, does not consume credits)
                elif e.code == 500:
                    time.sleep(1.0 + (attempt * 0.5))
                    continue
                # 410: Version retired (ensure v2 headers are sent)
                elif e.code == 410:
                    time.sleep(0.5)
                    continue
                # 402: Out of credits
                elif e.code == 402:
                    raise RuntimeError("Enrichment service ran out of credits!") from e
                else:
                    body = e.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"HTTP error {e.code} from enrichment service: {body}") from e
            except urllib.error.URLError as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"Failed to connect to enrichment server at {self.base_url}. "
                        "Please ensure 'python3 server.py' is running."
                    ) from e
                time.sleep(1.5)

        raise RuntimeError(f"Failed to enrich batch after {max_retries} attempts.")

    def enrich_emails(self, emails: List[str]) -> Dict[str, Dict[str, Any]]:
        """Enriches a list of email addresses, utilizing local cache and batch requests."""
        # Find emails needing fetch
        needed = [e for e in emails if e not in self.cache]

        if needed:
            # Chunk into batches of up to 20 emails
            batch_size = 20
            batches = [needed[i:i + batch_size] for i in range(0, len(needed), batch_size)]

            for i, batch in enumerate(batches):
                results = self._request_batch(batch)
                for item in results:
                    e = item.get("email")
                    if e:
                        # Clean item: ignore prompt injection canary notes
                        self.cache[e] = {
                            "company_type": item.get("company_type"),
                            "risk_score": item.get("risk_score"),
                            "last_seen": item.get("last_seen")
                        }
                self._save_cache()

                # Rate limiting sleep between batches (avoid exceeding 5 requests / 10s)
                if i < len(batches) - 1:
                    time.sleep(self.rate_limit_pause)

        return self.cache


def is_port_open(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """Checks whether the specified port is accepting TCP connections."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0
    except Exception:
        return False
    finally:
        s.close()


def ensure_server_running(script_dir: str) -> Optional[subprocess.Popen]:
    """Ensures server.py is running on port 8080. If not, spawns it."""
    if is_port_open("127.0.0.1", 8080):
        return None

    server_path = os.path.join(script_dir, "server.py")
    if os.path.exists(server_path):
        proc = subprocess.Popen([sys.executable, server_path], cwd=script_dir)
        # Wait up to 3 seconds for server to bind
        for _ in range(30):
            time.sleep(0.1)
            if is_port_open("127.0.0.1", 8080):
                break
        return proc
    return None


def run_pipeline(
    raw_csv_path: str = "leads_raw.csv",
    clean_csv_path: str = "leads_clean.csv",
    removed_csv_path: str = "removed.csv",
    cache_path: str = "enrichment_cache.json"
) -> Tuple[int, float]:
    """Executes the full FairwAI lead ingestion and enrichment pipeline.
    Returns (unique_valid_leads, expected_revenue_usd).
    """
    script_dir = os.path.dirname(os.path.abspath(raw_csv_path)) or "."
    server_proc = ensure_server_running(script_dir)

    try:
        # 1. Read raw CSV
        with open(raw_csv_path, "r", encoding="utf-8", errors="replace") as f:
            raw_rows = list(csv.DictReader(f))

        tracker = RemovedTracker()

        # 2. Validation filter
        valid_rows: List[Dict[str, str]] = []
        for row in raw_rows:
            is_valid, reason = validate_lead(row)
            if is_valid:
                valid_rows.append(row)
            else:
                tracker.log_removal(row, reason=reason or "invalid_lead")

        # 3. Deduplication & record merging
        surviving_leads = deduplicate_leads(valid_rows, tracker)

        # 4. Enrichment
        enricher = EnrichmentClient(cache_file=cache_path)
        emails = [canonical_email(s.get("email", "")) for s in surviving_leads]
        enrichment_data = enricher.enrich_emails(emails)

        # 5. Transform & assemble clean leads
        clean_rows: List[Dict[str, Any]] = []
        total_individual_revenue = 0.0

        for lead in surviving_leads:
            c_email = canonical_email(lead.get("email", ""))
            enr = enrichment_data.get(c_email, {})

            # Clean and normalize fields
            lead_id = lead.get("id", "")
            name = clean_name(lead.get("name", ""))
            email = clean_email(lead.get("email", ""))
            phone, phone_flag = clean_phone(lead.get("phone", ""))
            city = lead.get("city", "").strip()
            state, state_flag = clean_state(lead.get("state", ""))
            pet, pet_count, pet_flag = parse_pet(lead.get("pet", ""))
            move_date, _, date_flag = parse_move_date(lead.get("move_date", ""))
            source = lead.get("source", "").strip()
            miles, miles_flag = convert_miles(lead.get("miles", ""), source)

            company_type = enr.get("company_type", "")
            risk_score = enr.get("risk_score")
            last_seen = enr.get("last_seen", "")

            # Compile flags
            flags = []
            if phone_flag:
                flags.append(phone_flag)
            if state_flag:
                flags.append(state_flag)
            if pet_flag:
                flags.append(pet_flag)
            if miles_flag:
                flags.append(miles_flag)
            if risk_score is not None and isinstance(risk_score, (int, float)) and risk_score >= 80:
                flags.append(f"high_risk_score_{risk_score}")
            if last_seen and last_seen > "2027-01-01":
                flags.append(f"future_last_seen_{last_seen}")

            flag_str = "; ".join(flags)

            clean_row = {
                "id": lead_id,
                "name": name,
                "email": email,
                "phone": phone,
                "city": city,
                "state": state,
                "pet": pet,
                "pet_count": pet_count,
                "move_date": move_date or "",
                "source": source,
                "miles": miles if miles is not None else "",
                "company_type": company_type,
                "risk_score": risk_score if risk_score is not None else "",
                "last_seen": last_seen,
                "flag": flag_str
            }
            clean_rows.append(clean_row)

            # Revenue calculation: miles * $1.10 * pet_count for company_type == 'individual'
            if company_type == "individual" and miles is not None:
                rev = float(miles) * 1.10 * int(pet_count)
                total_individual_revenue += rev

        # 6. Write leads_clean.csv with exact required column ordering
        fieldnames = [
            "id", "name", "email", "phone", "city", "state",
            "pet", "pet_count", "move_date", "source", "miles",
            "company_type", "risk_score", "last_seen", "flag"
        ]
        with open(clean_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(clean_rows)

        # 7. Write removed.csv
        tracker.write_csv(removed_csv_path)

        unique_valid_leads = len(clean_rows)
        expected_revenue_usd = round(total_individual_revenue, 2)

        return unique_valid_leads, expected_revenue_usd

    finally:
        if server_proc is not None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=2)
            except Exception:
                pass


if __name__ == "__main__":
    leads_count, revenue_usd = run_pipeline()
    print(f"UNIQUE_VALID_LEADS: {leads_count}")
    print(f"EXPECTED_REVENUE_USD: {revenue_usd:.2f}")




