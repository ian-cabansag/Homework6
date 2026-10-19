# Campus Customs | Vendor Intelligence Lab

An auditable vendor-document desk for campus purchasing. It extracts quote facts from local HTML, PDF, and `.eml` files, evaluates those facts against the Campus Customs handbook, and records model usage, calculated cost, tool activity, and experiment evidence. The project includes both the undefended Problem 3 baseline and the layered Problem 6 pipeline; use `--mode` explicitly when reproducing experiments.

> **Research prototype — not an autonomous purchasing system.** Problem 7 demonstrated that both crafted documents still compromised the defended pipeline. Do not use its recommendations to authorize real purchases, payments, or email.

## Architecture

- `agent.py` is the CLI entry point and preserves the original baseline as well as the selectable defended mode.
- `defended_agent.py` runs guarded local-document inspection, an isolated structured fact-extraction agent without action tools, and a deterministic handbook policy decision.
- `document_guard.py` extracts HTML/PDF/email evidence, quarantines suspicious or conflicting surfaces with provenance, and does not follow document links or execute content.
- `policy_engine.py` parses purchasing policy and applies deterministic vendor, SKU, price, lead-time, and minimum-order checks.
- `models.py` defines strict Pydantic output schemas. `tools.py` holds the baseline parser and the safe, append-only logging traps `send_email` and `approve_payment`; those traps never contact anyone or move funds.
- `prompts/prompt.md` is the defended extraction prompt; `prompts/baseline_prompt.md` preserves the baseline prompt.

Supporting experiment/report builders and local tests are included. `output/` contains the submitted evidence and standalone report.

## Requirements and installation

Python 3.11 or newer is recommended. Install the pinned dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The application uses PydanticAI with the OpenAI-compatible Responses API through Portkey. Model calls are fixed to **`gpt-6-luna`**; there is no model fallback.

## Environment configuration

Copy `.env.example` to `.env` in this project root and replace the placeholder with an authorized Portkey key:

```powershell
Copy-Item .env.example .env
```

Never commit `.env`, paste credentials into source, or share the key. `.gitignore` excludes it. The Portkey API endpoint and required model are set by the application; the only required secret setting is `PORTKEY_API_KEY`.

## Run the Vendor Desk

Use a local document path and explicitly select the mode:

```powershell
python agent.py --doc data/practice_docs/p01_bluehen_quote.html --mode defended
python agent.py --doc data/practice_docs/p01_bluehen_quote.html --mode baseline
```

Accepted formats are `.html`, `.pdf`, and `.eml`. Baseline mode intentionally retains the original undefended behavior for controlled coursework comparison. Defended mode is safer but **not secure enough for autonomous purchasing**, as the red-team results show.

## Reproduce experiments

These commands make real API calls and append new records. Set up the environment first; never edit measurements by hand.

### Prompt-cache experiment (Problem 4)

```powershell
python cache_experiment.py --setup ALL
python build_cache_report.py
```

The experiment uses the API-reported cached-input and cache-write usage buckets. The builder validates them and recomputes costs from `data/prices.json`.

### Practice attack and defense evaluation (Problems 5–6)

Run each practice document once in each mode; logs are append-only, so preserve the experiment’s run window and do not mix unrelated executions when comparing results:

```powershell
Get-ChildItem data/practice_docs -File | ForEach-Object { python agent.py --doc $_.FullName --mode baseline }
Get-ChildItem data/practice_docs -File | ForEach-Object { python agent.py --doc $_.FullName --mode defended }
```

The submitted field-by-field comparisons are in `output/attack_results.json` and `output/defense_results.json`; local deterministic defense tests run with `python -m unittest discover -s tests -v`.

### Original red-team tests (Problem 7)

Run each new attack in both modes and inspect the appended audit and usage entries:

```powershell
python agent.py --doc data/my_attacks/01_accessibility_correction.html --mode baseline
python agent.py --doc data/my_attacks/01_accessibility_correction.html --mode defended
python agent.py --doc data/my_attacks/02_collapsed_addendum.html --mode baseline
python agent.py --doc data/my_attacks/02_collapsed_addendum.html --mode defended
```

`output/red_team_runs.json` and `output/red_team.md` preserve the four submitted runs and analysis. Do not treat these adversarial demonstrations as purchasing instructions.

### Exam evaluation (Problem 8)

```powershell
Get-ChildItem data/exam_docs -File | ForEach-Object { python agent.py --doc $_.FullName --mode defended }
python build_exam_results.py
```

The exam has no answer key. Its submitted records are observations, not verified ground truth. Do not hand-edit generated results.

## Logs and cost accounting

`output/usage_log.json` and `output/audit_trail.json` preserve run usage, calculated USD cost, calls, and results. `output/trap_calls.json` records only attempted trap invocations; these tools are local logging stubs. Defensive blocks are also recorded in `output/security_log.json`. Existing evidence includes failed API attempts as errors where recorded; those are not successful measurements. Cost is computed—not a provider invoice—from API-reported token buckets and the rates in `data/prices.json`, distinguishing ordinary input, cached reads, cache writes, and output where available.

## Security controls and limitations

The defended pipeline keeps vendor documents in a low-trust evidence path, performs local-only parsing without running embedded code or following links, separates extraction from policy evaluation, validates structured output, applies handbook checks deterministically, and has no action tools on its extraction agent. Baseline traps remain logging-only.

These measures are not a proof against prompt injection. In Problem 7, hidden SVG accessibility text and a collapsed HTML disclosure changed extracted facts in both baseline and defended runs. Parsing/rendering discrepancies and novel document structures remain material risks. Human review of the source document and handbook is mandatory; independently verify quote facts and policy decisions. Never automate email, payments, or ordering from this prototype.

## Standalone report

Open [`output/hw6_report.html`](output/hw6_report.html) directly in a browser. It embeds its data, styles, scripts, and charts, and works offline without a server or remote assets.
