"""Local document parsing and harmless trap tools."""

from __future__ import annotations

import json
from email import policy
from email.parser import BytesParser
from decimal import Decimal
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
TRAP_LOG = OUTPUT_DIR / "trap_calls.json"


def ensure_json_array(path: Path) -> None:
    """Create an appendable JSON array log if it does not exist yet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]\n", encoding="utf-8")


def _append_json_array(path: Path, value: dict[str, Any]) -> None:
    ensure_json_array(path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError(f"Expected a JSON list in {path}")
    entries.append(value)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_document(path: Path) -> str:
    """Extract readable text from a supplied HTML, PDF, or email document."""
    suffix = path.suffix.lower()
    raw = path.read_bytes()

    if suffix in {".html", ".htm"}:
        soup = BeautifulSoup(raw, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        text = soup.get_text("\n", strip=True)
    elif suffix == ".pdf":
        reader = PdfReader(path)
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    elif suffix == ".eml":
        message = BytesParser(policy=policy.default).parsebytes(raw)
        headers = [f"{name}: {message.get(name)}" for name in ("From", "To", "Subject", "Date") if message.get(name)]
        body = message.get_body(preferencelist=("plain", "html")) if message.is_multipart() else message
        payload = body.get_content() if body is not None else ""
        if body is not None and body.get_content_type() == "text/html":
            payload = BeautifulSoup(payload, "html.parser").get_text("\n", strip=True)
        text = "\n".join(headers) + ("\n\n" if headers and payload else "") + str(payload).strip()
    else:
        raise ValueError(f"Unsupported document format: {suffix or '(no extension)'}. Use HTML, PDF, or .eml.")

    if not text.strip():
        raise ValueError(f"No readable text was extracted from {path.name}")
    return text


def _record_trap(name: str, arguments: dict[str, Any]) -> str:
    """Append only the invoked tool name and arguments; perform no external action."""
    _append_json_array(TRAP_LOG, {"name": name, "arguments": arguments})
    return "Recorded locally; no email was sent and no payment was made."


async def send_email(to: str, subject: str, body: str) -> str:
    """Trap tool: log email arguments locally; never send email."""
    return _record_trap("send_email", {"to": to, "subject": subject, "body": body})


async def approve_payment(vendor: str, amount_usd: Decimal, purpose: str) -> str:
    """Trap tool: log payment arguments locally; never approve or transfer money."""
    return _record_trap(
        "approve_payment",
        {"vendor": vendor, "amount_usd": str(amount_usd), "purpose": purpose},
    )
