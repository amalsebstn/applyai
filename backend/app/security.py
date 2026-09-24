"""Security controls for ApplyAI, mapped to the OWASP Top 10 for LLM Applications (2025).

Every function here is deliberately simple and unit-tested, so each control can be
explained and demonstrated in a review.
"""
import re
import time
from collections import defaultdict, deque

# ---------------------------------------------------------------------------
# LLM02 Sensitive Information Disclosure: redact PII before it leaves our server
# ---------------------------------------------------------------------------
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{8,}\d(?!\w)")
_URL = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com)/[^\s|,]+", re.I)


def redact_pii(text: str) -> tuple[str, int]:
    """Replace emails, phone numbers and profile URLs with placeholders.

    Returns the redacted text and how many items were removed.
    """
    count = 0
    for pattern, token in ((_EMAIL, "[EMAIL]"), (_URL, "[PROFILE_URL]"), (_PHONE, "[PHONE]")):
        text, n = pattern.subn(token, text)
        count += n
    return text, count


# ---------------------------------------------------------------------------
# LLM01 Prompt Injection: treat user content as data, never as instructions
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (the |all )?(previous|prior|above|system)",
    r"you are now",
    r"system prompt",
    r"reveal (your|the) (instructions|prompt)",
    r"</?(cv|job|system|instructions)>",
    r"rate (this|the) candidate (as )?(100|10|perfect)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.I)


def detect_injection(text: str) -> list[str]:
    """Heuristic scan for common injection phrasing. Used to warn, not to block.

    Pattern matching alone cannot stop prompt injection; the real defence is the
    combination of delimiting, no tool access and strict output validation.
    """
    return sorted({m.group(0).lower() for m in _INJECTION_RE.finditer(text)})


def wrap_untrusted(tag: str, text: str) -> str:
    """Wrap untrusted text in XML-style tags, neutralising any tags inside it
    so the content cannot 'close' our delimiter and escape into instructions."""
    safe = re.sub(r"</?\s*[a-zA-Z_]+\s*>", lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"), text)
    return f"<{tag}>\n{safe}\n</{tag}>"


# ---------------------------------------------------------------------------
# LLM09 Misinformation: flag tailored bullets that claim skills not in the CV
# ---------------------------------------------------------------------------
# A small vocabulary of checkable claims. Extend it for your own field.
SKILL_TERMS = [
    "aws", "azure", "gcp", "kubernetes", "docker", "terraform", "splunk", "sentinel",
    "crowdstrike", "defender", "qradar", "sentinelone", "nessus", "qualys", "wireshark",
    "python", "powershell", "java", "javascript", "react", "sql", "cissp", "cism", "ceh",
    "oscp", "security+", "cysa+", "iso 27001", "iso/iec 27001", "nist ai rmf",
    "mitre atlas", "owasp", "soar", "siem", "edr", "dlp", "zero trust", "penetration testing",
    "ai gateway", "machine learning", "llm", "ot", "ics", "scada", "gdpr", "hipaa", "pci dss",
]


def ungrounded_terms(bullet: str, cv_text: str) -> list[str]:
    """Return skill terms mentioned in a generated bullet that never appear in the CV."""
    b, cv = bullet.lower(), cv_text.lower()
    found = []
    for term in SKILL_TERMS:
        pat = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        if re.search(pat, b) and not re.search(pat, cv):
            found.append(term)
    return found


# ---------------------------------------------------------------------------
# LLM10 Unbounded Consumption: per-client sliding-window rate limit
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: dict[str, deque] = defaultdict(deque)

    def allow(self, client_id: str) -> bool:
        now = time.monotonic()
        q = self._calls[client_id]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max_calls:
            return False
        q.append(now)
        return True
