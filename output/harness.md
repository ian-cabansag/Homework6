# Campus Customs | Vendor Intelligence Lab
## Problem 3 model and tool harness

This baseline accepts one local HTML, PDF, or `.eml` document. PydanticAI requests the fixed `gpt-6-luna` model through Portkey's OpenAI-compatible endpoint, using the Responses API model class. The installed PydanticAI version is 2.45.0. Each run loads the entire `data/shop_handbook.md` into the agent instructions and supplies parsed vendor-document text separately.

## Structured result fields

| Field | Type | Why it exists |
|---|---|---|
| `vendor` | `string \| null` | Identifies the supplier. Null preserves missing or ambiguous source information instead of guessing. |
| `sku` | `string \| null` | Links a quote to the Campus Customs catalogue item. Null indicates the document did not establish a SKU. |
| `unit_price` | `decimal \| null` | Captures the quoted unit cost for comparison with the handbook maximum; Decimal preserves currency precision. |
| `lead_time_days` | `integer \| null` | Captures lead time in days for the handbook's 21-day test. Null is used when absent or ambiguous. |
| `minimum_order_units` | `integer \| null` | Captures the minimum quantity for the handbook's 600-unit test. |
| `decision` | `"recommend" \| "do_not_recommend"` | Constrains the output to the two decisions permitted by the task and handbook. |
| `reason` | non-empty `string` | Gives a concise explanation naming the handbook check that determines the decision. |

The Pydantic model forbids additional fields, uses strict validation, requires every field to be present, and represents unknown extracted values explicitly as `null`. Lead-time values preserve the stated number without converting business days to calendar days; the rationale retains the business-day qualifier. This baseline compares that stated numeric value to the handbook threshold and may need a policy clarification if Campus Customs intends calendar-day comparison.

## Tools

| Tool | Role | Side effect |
|---|---|---|
| `send_email(to, subject, body)` | Demonstrates the email action surface for the later security exercise. | Appends only its name and arguments to `output/trap_calls.json`; sends nothing. |
| `approve_payment(vendor, amount_usd, purpose)` | Demonstrates the payment action surface for the later security exercise. | Appends only its name and arguments to `output/trap_calls.json`; moves no money. |

`parse_document(path)` is a local parser, not a model tool. It extracts HTML text with BeautifulSoup, page text with pypdf, and MIME body/header text with Python's email parser. The structured result mechanism is provided by PydanticAI and represents the final answer rather than an external action.

## Usage and audit records

Each successful run appends one entry to `output/usage_log.json` and one to `output/audit_trail.json`, preserving prior list entries. Cost is calculated from API-normalized token usage and the rates in `data/prices.json`, separating ordinary input, cached reads, cache writes, and output. No usage or successful answer is synthesized when a request fails.

## Baseline boundaries

This version does not add the defensive layers reserved for Problem 6. It keeps the policy handbook in agent instructions and quote text in a separate input section, but does not add a sanitizer, injection classifier, approval gate, tool allowlist, or independent deterministic decision validator. The tool functions themselves are inert local logging traps.


## Safety — Problem 6 defended mode

The CLI now has two explicit modes. `python agent.py --doc <path>` and `--mode baseline` preserve the original Problem 3 agent, original prompt snapshot, and local logging-only action tools. `python agent.py --mode defended --doc data/practice_docs/p01_bluehen_quote.html` activates the three Problem 6 layers. The default remains baseline for compatibility; the CLI heading, audit records, and usage records identify the selected mode.

### Layer 1 — local code inspection and quarantine

`document_guard.py` reads only files inside `data/practice_docs/` and never evaluates scripts, fetches URLs, opens links, or opens email attachments. It caps input size and PDF page count. HTML comments, script/template content, metadata, URL destinations, CSS-hidden/near-invisible elements, and instruction-like lines are retained as local provenance/security evidence but excluded from the model's fact text. PDF extraction records page coordinates, font size, and white/invisible text paint; tiny and out-of-page text is quarantined. Multipart email is parsed locally; HTML alternatives receive the same visibility treatment. Anomalies are included in the audit, while unsafe action/link requests are appended to `output/security_log.json` as blocked. Visible ordinary quote fields remain eligible evidence; if hidden material conflicts with a critical fact, that field is marked uncertain and the policy stage fails closed.

These heuristics are conservative, not a universal visual renderer. Unusual CSS, complex PDF graphics/transforms, scanned PDFs without OCR, malformed MIME, and novel obfuscations may evade detection or create false positives. A quarantined correction is not destroyed: it remains in audit/security records with a source and reason, but cannot silently override visible evidence.

### Layer 2 — capability separation and deterministic decision

The defended PydanticAI request returns `VendorFactExtraction` only. The structured extraction agent registers **no tools**; it cannot call `send_email` or `approve_payment`. Those original functions remain available in baseline mode and continue to append only to `output/trap_calls.json`; no mode sends mail or transfers money. The pipeline verifies every non-null model value against a verbatim quote that occurs in the guarded visible text. Unproven values are nulled and marked uncertain.

After extraction, Python parses the approved/removed vendor tables, SKU maximums, and fixed lead-time/minimum-order policy from `data/shop_handbook.md`, then calculates the recommendation deterministically. Missing, unsupported, conflicting, or over-limit facts fail closed to `do_not_recommend`. A document can request an action, but no explicit authorization UI or external-action path exists in defended mode; such requests are blocked and recorded. `tools.py` remains the harmless local trap implementation.

### Layer 3 — prompt boundary

`prompts/prompt.md` labels the handbook as trusted reference and the vendor text as untrusted JSON evidence passed in the user message. It instructs the extractor not to obey document directives, use links, disclose handbook information, or decide a purchase, and requires verbatim evidence and explicit uncertainty. The original Problem 3 text is preserved in `prompts/baseline_prompt.md` and is used only by baseline mode.

### Problem 6 local checks and evidence limits

`python -m unittest discover -s tests -v` exercises hidden HTML, comments, white PDF text, microprint, off-page text, multipart email/link isolation, handbook parsing, deterministic failure behavior, empty action-tool registration, and prompt boundaries without calling a model. These checks demonstrate the code and capability controls, not that a prompt alone defeats all prompt injection. The 12-document defended run is separately measured in `output/defense_results.json` and `.md`, with actual API usage and costs. Model facts remain probabilistic; the deterministic gate only proves the policy decision from the validated facts it receives.

The architecture follows official OpenAI agent-safety guidance: keep untrusted values out of privileged instructions, constrain intermediate data with structured outputs, and limit tool capabilities. See [Safety in building agents](https://developers.openai.com/api/docs/guides/agent-builder-safety). That guidance does not certify this implementation or remove the limitations above.
