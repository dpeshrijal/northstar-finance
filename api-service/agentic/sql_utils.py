import re
from typing import Tuple

from .config import settings


_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|vacuum|analyze)\b",
    re.IGNORECASE,
)


def normalize_sql(query: str) -> str:
    return query.strip().rstrip(";")


def validate_sql(query: str) -> Tuple[bool, str]:
    if not query:
        return False, "Empty SQL."
    if len(query) > settings.max_query_chars:
        return False, "SQL exceeds max length."
    if ";" in query.strip().rstrip(";"):
        return False, "Multiple statements are not allowed."
    lowered = query.strip().lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False, "Only SELECT queries are allowed."
    if _FORBIDDEN_SQL.search(query):
        return False, "Forbidden SQL operation detected."
    if "--" in query or "/*" in query:
        return False, "SQL comments are not allowed."
    return True, ""


def enforce_limit(query: str, limit: int) -> str:
    if re.search(r"\blimit\b", query, re.IGNORECASE):
        return query
    return f"{query} LIMIT {limit}"
