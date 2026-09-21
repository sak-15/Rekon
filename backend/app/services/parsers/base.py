"""
Base Parser Interfaces and Normalization Utilities for Rekon.

Provides common type parsing, currency cleaning, date parsing,
and standard data containers for all CSV ingestion services.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Generic, List, Optional, TypeVar
import re


T = TypeVar("T")


@dataclass
class RowError:
    """
    Captures a row-level validation failure without terminating batch ingestion.
    """
    row_number: int
    field: str
    message: str
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class ParseResult(Generic[T]):
    """
    Container returning sanitized records and diagnostic errors from CSV ingestion.
    """
    valid_records: List[T] = field(default_factory=list)
    errors: List[RowError] = field(default_factory=list)
    total_rows: int = 0

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    @property
    def error_count(self) -> int:
        return len(self.errors)


def clean_string(val: Any) -> Optional[str]:
    """
    Strips leading and trailing whitespace; returns None if empty or NaN.
    """
    if val is None:
        return None
    s = str(val).strip()
    return None if s == "" or s.lower() == "nan" or s.lower() == "none" else s


def clean_amount(val: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    """
    Converts diverse monetary formats into a clean Decimal.
    Handles currency symbols (₹, $, €), commas, and negative parentheses:
      '₹ 1,500.50'  -> Decimal('1500.50')
      '(250.00)'    -> Decimal('-250.00')
      '-$50.00'     -> Decimal('-50.00')
    """
    if val is None:
        return default
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return default

    # Handle accounting parentheses for negative numbers e.g. (100.00)
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()

    # Strip currency symbols and thousands separators
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return default

    try:
        dec = Decimal(s)
        return -dec if is_negative else dec
    except InvalidOperation:
        raise ValueError(f"Unable to parse amount '{val}' into a valid decimal")


def parse_flexible_date(val: Any) -> datetime:
    """
    Parses timestamps and dates across standard SaaS and bank export formats:
      - ISO 8601: '2026-05-14T10:30:00Z', '2026-05-14 10:30:00'
      - Standard date: '2026-05-14'
      - Indian / UK format: '14/05/2026', '14-05-2026', '14/05/2026 14:30:00'
      - US format: '05/14/2026'
      - Unix timestamp in seconds or milliseconds
    """
    if val is None:
        raise ValueError("Date value is missing")

    s = str(val).strip()
    if not s or s.lower() == "nan":
        raise ValueError("Date value is empty")

    # Check for Unix epoch (e.g. 1778760000 or 1778760000000)
    if s.isdigit():
        ts = int(s)
        if ts > 10**11:  # milliseconds
            ts = ts / 1000.0
        return datetime.utcfromtimestamp(ts)

    # Common datetime formats in CSV exports
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=None)  # normalize to naive UTC
        except ValueError:
            continue

    # Fallback to dateutil if available
    try:
        from dateutil import parser
        return parser.parse(s).replace(tzinfo=None)
    except Exception as e:
        raise ValueError(f"Unsupported date format '{val}': {str(e)}")

