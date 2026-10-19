"""Defensive local-only parsing that quarantines non-visible or instruction-like content."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Comment
from pypdf import PdfReader
from pypdf.generic import ContentStream


MAX_DOCUMENT_BYTES = 12 * 1024 * 1024
MAX_PDF_PAGES = 80
MAX_EXTRACTED_CHARS = 250_000
INSTRUCTION_RE = re.compile(
    r"(?:ignore\s+(?:all\s+)?(?:previous|prior|system|developer|policy)\s+(?:instructions|prompts|rules)|"
    r"(?:call|invoke|use)\s+(?:the\s+)?(?:send_email|approve_payment)|"
    r"send\s+(?:the\s+)?(?:handbook|maximum|max\s+unit\s+cost|cost\s+list)|"
    r"(?:send|forward|email).{0,100}(?:handbook|max(?:imum)?\s+unit\s+cost|cost\s+list|confidential|internal\s+data)|"
    r"\b(?:approve|authorize|pay)\b.{0,50}(?:payment|deposit|invoice|purchase)|"
    r"reveal\s+(?:the\s+)?(?:handbook|internal|confidential|private)|"
    r"override\s+(?:the\s+)?(?:system|developer|handbook|policy)|"
    r"(?:put|include)\s+(?:this\s+)?(?:tracking\s+)?(?:link|url)\s+(?:in|into)\s+(?:your|the)\s+(?:answer|reason|response))",
    re.IGNORECASE,
)
CSS_HIDDEN_RE = re.compile(
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:\.0+)?\b|"
    r"font-size\s*:\s*0(?:px|pt|em|rem|%)?\b|font-size\s*:\s*[0-3](?:px|pt)\b|"
    r"left\s*:\s*-\s*\d{3,}px|top\s*:\s*-\s*\d{3,}px|clip\s*:\s*rect\s*\(\s*0)",
    re.IGNORECASE,
)
WHITE_COLOR_RE = re.compile(r"(?:^|;)\s*color\s*:\s*(?:#fff(?:fff)?|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))\s*(?:;|$)", re.IGNORECASE)


@dataclass
class QuarantinedSpan:
    source: str
    reason: str
    text: str


@dataclass
class GuardedDocument:
    filename: str
    format: str
    trusted_text: str = ""
    quarantined: list[QuarantinedSpan] = field(default_factory=list)
    metadata: list[dict[str, str]] = field(default_factory=list)
    links_not_followed: list[str] = field(default_factory=list)
    attachment_names_not_opened: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsafe_requests_blocked: list[dict[str, str]] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "format": self.format,
            "trusted_text": self.trusted_text,
            "quarantined": [asdict(span) for span in self.quarantined],
            "metadata": self.metadata,
            "links_not_followed": self.links_not_followed,
            "attachment_names_not_opened": self.attachment_names_not_opened,
            "warnings": self.warnings,
            "unsafe_requests_blocked": self.unsafe_requests_blocked,
        }


def _clean_join(values: list[str]) -> str:
    text = "\n".join(value.strip() for value in values if value and value.strip())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _quarantine_instruction_lines(text: str, source: str, doc: GuardedDocument) -> list[str]:
    kept: list[str] = []
    for line in text.splitlines():
        if INSTRUCTION_RE.search(line):
            line_clean = line.strip()
            doc.quarantined.append(QuarantinedSpan(source, "instruction-like text; withheld from extraction", line_clean))
            mentioned_tool = "send_email" if "send_email" in line_clean.lower() else (
                "approve_payment" if "approve_payment" in line_clean.lower() else ""
            )
            if mentioned_tool:
                doc.unsafe_requests_blocked.append({"tool": mentioned_tool, "source": source, "excerpt": line_clean[:240]})
        else:
            kept.append(line)
    return kept


def _is_hidden_element(element: Any) -> str | None:
    if element.has_attr("hidden"):
        return "hidden attribute"
    if str(element.get("aria-hidden", "")).lower() == "true":
        return "aria-hidden=true"
    style = str(element.get("style", ""))
    if CSS_HIDDEN_RE.search(style):
        return f"non-visible inline CSS: {style.strip()}"
    if WHITE_COLOR_RE.search(style):
        backgrounds: list[str] = []
        current = element
        while getattr(current, "attrs", None) is not None:
            parent_style = str(current.get("style", ""))
            backgrounds.extend(re.findall(r"background(?:-color)?\s*:\s*([^;]+)", parent_style, re.I))
            current = current.parent
            if current is None:
                break
        explicit_nonwhite = any(value.strip().lower() not in {"white", "#fff", "#ffffff", "rgb(255, 255, 255)"} for value in backgrounds)
        if not explicit_nonwhite:
            return f"likely white-on-default-white text: {style.strip()}"
    return None


def _extract_html(source: str, filename: str, doc: GuardedDocument) -> str:
    soup = BeautifulSoup(source, "html.parser")

    # Collect document metadata, link destinations and comments without following them.
    if soup.title and soup.title.get_text(strip=True):
        doc.metadata.append({"kind": "title", "value": soup.title.get_text(" ", strip=True)})
    for meta in soup.find_all("meta"):
        key = str(meta.get("name") or meta.get("property") or "meta")
        value = str(meta.get("content") or "").strip()
        if value:
            doc.metadata.append({"kind": key, "value": value[:1000]})
            normalized_meta = "".join(char for char in value if char not in {"\u200b", "\u200c", "\u200d", "\ufeff"})
            if INSTRUCTION_RE.search(normalized_meta):
                doc.quarantined.append(QuarantinedSpan("html_metadata", "untrusted instruction-like metadata", value[:2000]))
    for element in soup.find_all(True):
        for attribute in ("href", "src", "action", "data", "poster"):
            destination = str(element.get(attribute) or "").strip()
            if destination:
                doc.links_not_followed.append(destination[:1000])
    for node in soup.find_all(string=lambda value: isinstance(value, Comment)):
        text = str(node).strip()
        if text:
            doc.quarantined.append(QuarantinedSpan("html_comment", "not rendered; HTML comments are never evidence", text[:2000]))
        node.extract()

    # CSS is parsed only as text: it is never evaluated or fetched.
    styles: list[str] = []
    for style_tag in soup.find_all("style"):
        css = style_tag.get_text("\n", strip=True)
        if css:
            styles.append(css)
        style_tag.decompose()
    for css in styles:
        for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if not CSS_HIDDEN_RE.search(declarations):
                continue
            selector = selector.strip()
            try:
                targets = soup.select(selector)
            except Exception:
                doc.warnings.append(f"Could not interpret CSS visibility selector safely: {selector[:120]}")
                continue
            for target in targets:
                if target.attrs is None:
                    continue
                txt = target.get_text(" ", strip=True)
                if txt:
                    doc.quarantined.append(QuarantinedSpan("html_css", f"non-visible stylesheet rule for {selector[:120]}", txt[:2000]))
                target.decompose()

    # Scripts and executable elements are not run. Their contents are retained only as quarantined evidence.
    for element in soup.find_all(["script", "noscript", "template", "iframe", "object", "embed"]):
        txt = element.get_text(" ", strip=True)
        if txt:
            doc.quarantined.append(QuarantinedSpan("html_non_content_element", f"{element.name} content is not executed or trusted", txt[:2000]))
        element.decompose()

    for element in list(soup.find_all(True)):
        if element.attrs is None or element.parent is None:
            continue
        reason = _is_hidden_element(element)
        if reason:
            txt = element.get_text(" ", strip=True)
            if txt:
                doc.quarantined.append(QuarantinedSpan("html_hidden_element", reason, txt[:2000]))
            element.decompose()

    if soup.head:
        soup.head.decompose()

    visible = soup.get_text("\n", strip=True)
    kept = _quarantine_instruction_lines(visible, "html_visible_text", doc)
    return _clean_join(kept)


def _pdf_hidden_strings(page: Any, reader: PdfReader) -> list[str]:
    """Identify text painting in white or invisible text-rendering mode."""
    if page.get_contents() is None:
        return []
    content = ContentStream(page.get_contents(), reader)
    fill: tuple[float, ...] = (0.0,)
    render_mode = 0
    font_size = 12.0
    hidden: list[str] = []
    for operands, operator in content.operations:
        try:
            if operator == b"rg":
                fill = tuple(float(v) for v in operands)
            elif operator == b"g":
                fill = (float(operands[0]),)
            elif operator == b"k":
                fill = tuple(float(v) for v in operands)
            elif operator == b"Tf":
                font_size = abs(float(operands[1]))
            elif operator == b"Tr":
                render_mode = int(operands[0])
            elif operator in {b"Tj", b"'", b'"'}:
                raw = operands[-1]
                text = str(raw) if not isinstance(raw, bytes) else raw.decode("utf-8", "replace")
                is_white = (len(fill) == 3 and all(c >= 0.98 for c in fill)) or (len(fill) == 1 and fill[0] >= 0.98)
                if text.strip() and (is_white or render_mode in {3, 7} or font_size < 4):
                    hidden.append(text)
            elif operator == b"TJ" and operands:
                chunks = [str(item) for item in operands[0] if isinstance(item, (str, bytes))]
                text = "".join(chunks)
                is_white = (len(fill) == 3 and all(c >= 0.98 for c in fill)) or (len(fill) == 1 and fill[0] >= 0.98)
                if text.strip() and (is_white or render_mode in {3, 7} or font_size < 4):
                    hidden.append(text)
        except (TypeError, ValueError, IndexError):
            continue
    return hidden


def _extract_pdf(path: Path, doc: GuardedDocument) -> str:
    reader = PdfReader(path, strict=False)
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(f"PDF page count {len(reader.pages)} exceeds defensive limit {MAX_PDF_PAGES}.")
    trusted_pages: list[str] = []
    for page_no, page in enumerate(reader.pages, start=1):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        white_or_tiny = _pdf_hidden_strings(page, reader)
        white_norm = [re.sub(r"\s+", " ", text).strip().casefold() for text in white_or_tiny]
        segments: list[tuple[str, float, float, float]] = []

        def visitor(text: str, cm: Any, tm: Any, font: Any, font_size: float) -> None:
            if text and text.strip():
                segments.append((text, float(tm[4]), float(tm[5]), abs(float(font_size))))

        page.extract_text(visitor_text=visitor)
        kept: list[str] = []
        for text, x, y, size in segments:
            normalized = re.sub(r"\s+", " ", text).strip().casefold()
            is_white = any(
                normalized
                and (
                    normalized == h
                    or (len(normalized) >= 50 and normalized in h)
                    or (len(h) >= 50 and h in normalized)
                )
                for h in white_norm
            )
            off_page = x < -1 or y < -1 or x > width + 1 or y > height + 1
            tiny = size < 4
            if is_white or off_page or tiny:
                if not is_white and not off_page and not tiny:
                    continue
                reasons = []
                if is_white:
                    reasons.append("white/invisible PDF text paint")
                if off_page:
                    reasons.append(f"text outside page box at x={x:.1f}, y={y:.1f}")
                if tiny:
                    reasons.append(f"sub-4-point PDF text ({size:.2f} pt)")
                doc.quarantined.append(
                    QuarantinedSpan(f"pdf_page_{page_no}", "; ".join(reasons), text.strip()[:2000])
                )
                continue
            kept.append(text)

        # Links/annotations are recorded as inert metadata and never dereferenced.
        for annotation in page.get("/Annots", []):
            try:
                uri = annotation.get_object().get("/A", {}).get("/URI")
                if uri:
                    doc.links_not_followed.append(str(uri)[:1000])
            except Exception:
                doc.warnings.append(f"Unreadable PDF annotation on page {page_no}; ignored.")
        page_text = _clean_join(kept)
        trusted_pages.append(_clean_join(_quarantine_instruction_lines(page_text, f"pdf_page_{page_no}", doc)))
    return _clean_join(trusted_pages)


def _extract_email(path: Path, doc: GuardedDocument) -> str:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    for header in ("From", "To", "Subject", "Date", "Reply-To", "Return-Path"):
        value = message.get(header)
        if value:
            doc.metadata.append({"kind": f"email_{header.lower()}", "value": str(value)[:1000]})
            normalized_header = "".join(char for char in str(value) if char not in {"\u200b", "\u200c", "\u200d", "\ufeff"})
            if INSTRUCTION_RE.search(normalized_header):
                doc.quarantined.append(QuarantinedSpan(f"email_header_{header}", "instruction-like metadata; withheld", str(value)[:1000]))
    bodies: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            filename = part.get_filename()
            if filename:
                doc.attachment_names_not_opened.append(filename[:300])
                continue
            if part.get_content_type() not in {"text/plain", "text/html"}:
                continue
            try:
                payload = part.get_content()
            except Exception as exc:
                doc.warnings.append(f"Could not decode an email body part ({type(exc).__name__}); omitted.")
                continue
            payload = str(payload)
            if part.get_content_type() == "text/html":
                bodies.append(_extract_html(payload, path.name, doc))
            else:
                bodies.append(_clean_join(_quarantine_instruction_lines(payload, "email_body", doc)))
    else:
        payload = str(message.get_content())
        if message.get_content_type() == "text/html":
            bodies.append(_extract_html(payload, path.name, doc))
        else:
            bodies.append(_clean_join(_quarantine_instruction_lines(payload, "email_body", doc)))
    return _clean_join(bodies)


def inspect_document(path: Path, allowed_root: Path) -> GuardedDocument:
    resolved = path.resolve(strict=True)
    root = allowed_root.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError(f"Document must be inside {root}.")
    if not resolved.is_file():
        raise ValueError(f"Not a regular local document: {resolved}")
    if resolved.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError(f"Document exceeds defensive size limit of {MAX_DOCUMENT_BYTES} bytes.")
    suffix = resolved.suffix.lower()
    doc = GuardedDocument(filename=resolved.name, format=suffix.lstrip("."))
    if suffix in {".html", ".htm"}:
        source = resolved.read_text(encoding="utf-8", errors="replace")
        if "\ufffd" in source:
            doc.warnings.append("Input contains undecodable byte sequences represented as U+FFFD.")
        doc.trusted_text = _extract_html(source, resolved.name, doc)
    elif suffix == ".pdf":
        doc.trusted_text = _extract_pdf(resolved, doc)
    elif suffix == ".eml":
        doc.trusted_text = _extract_email(resolved, doc)
    else:
        raise ValueError(f"Unsupported document format {suffix!r}; accepted: HTML, PDF, .eml.")
    if not doc.trusted_text:
        doc.warnings.append("No visible/trusted body text could be extracted; all key facts remain unknown.")
    for span in doc.quarantined:
        low = "".join(char for char in span.text if char not in {"\u200b", "\u200c", "\u200d", "\ufeff"}).lower()
        for tool_name in ("send_email", "approve_payment"):
            if tool_name in low and not any(
                request["tool"] == tool_name and request["source"] == span.source
                for request in doc.unsafe_requests_blocked
            ):
                doc.unsafe_requests_blocked.append(
                    {"tool": tool_name, "source": span.source, "excerpt": span.text[:240]}
                )
        if INSTRUCTION_RE.search(low) and not any(
            request["source"] == span.source and request["excerpt"] == span.text[:240]
            for request in doc.unsafe_requests_blocked
        ):
            doc.unsafe_requests_blocked.append(
                {"tool": "none", "source": span.source, "excerpt": span.text[:240]}
            )
        doc.links_not_followed.extend(re.findall(r"https?://[^\s)<>\]]+", span.text, re.IGNORECASE))
    if len(doc.trusted_text) > MAX_EXTRACTED_CHARS:
        doc.trusted_text = doc.trusted_text[:MAX_EXTRACTED_CHARS]
        doc.warnings.append(f"Trusted text truncated at {MAX_EXTRACTED_CHARS} characters.")
    return doc
