"""Validate cache experiment records and build output/cache_test.md."""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
MODEL = "gpt-6-luna"
MILLION = Decimal(1_000_000)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def money(value: Decimal) -> str:
    return f"${value:.9f}"


def number(value: int) -> str:
    return f"{value:,}"


def percent(value: Decimal) -> str:
    return f"{value:.2f}%"


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        field: sum(int(row[field] or 0) for row in rows)
        for field in (
            "input_tokens",
            "ordinary_input_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "output_tokens",
        )
    }
    totals["cost"] = sum((Decimal(row["cost_usd"]) for row in rows), Decimal(0))
    totals["latency_ms"] = sum(float(row["latency_ms"]) for row in rows)
    totals["calls"] = len(rows)
    return totals


def call_cost(row: dict[str, Any], rates: dict[str, Any]) -> Decimal:
    ordinary = int(row["ordinary_input_tokens"])
    cached = int(row["cached_input_tokens"])
    writes = int(row["cache_write_tokens"])
    output = int(row["output_tokens"])
    return (
        Decimal(ordinary) * Decimal(str(rates["input_per_1m"]))
        + Decimal(cached) * Decimal(str(rates["cached_input_per_1m"]))
        + Decimal(writes) * Decimal(str(rates["cache_write_per_1m"]))
        + Decimal(output) * Decimal(str(rates["output_per_1m"]))
    ) / MILLION


def build_report() -> str:
    records = read_json(OUTPUT / "cache_test.json")
    prices_root = read_json(ROOT / "data" / "prices.json")
    rates = prices_root[MODEL]
    expected_rates = {
        "ordinary_input": rates["input_per_1m"],
        "cached_input": rates["cached_input_per_1m"],
        "cache_write": rates["cache_write_per_1m"],
        "output": rates["output_per_1m"],
    }
    filenames = sorted(path.name for path in (ROOT / "data" / "practice_docs").iterdir() if path.is_file())
    assert len(filenames) == 12, f"Expected 12 practice documents, got {len(filenames)}"

    by_experiment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        if row.get("experiment_id"):
            by_experiment[row["experiment_id"]].append(row)

    valid_studies: list[tuple[int, str, list[dict[str, Any]]]] = []
    for study_id, study_rows in by_experiment.items():
        successful = [row for row in study_rows if row.get("success") and row.get("cost_usd") is not None]
        cached = [row for row in successful if row["setup"] == "CACHED"]
        uncached = [row for row in successful if row["setup"] == "UNCACHED"]
        cached_docs = {row["document"] for row in cached}
        uncached_docs = {row["document"] for row in uncached}
        if (
            cached_docs == set(filenames)
            and uncached_docs == set(filenames)
            and any(int(row["cached_input_tokens"] or 0) > 0 for row in cached)
            and all(int(row["cached_input_tokens"] or 0) == 0 for row in uncached)
        ):
            last_timestamp = max(row["completed_at_utc"] for row in successful)
            valid_studies.append((int(last_timestamp.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")[:14]), study_id, successful))

    if not valid_studies:
        raise ValueError("No complete study has 12 successful documents per setup and verified cache reporting.")
    _, study_id, matched = max(valid_studies, key=lambda item: item[0])
    cached_calls = [row for row in matched if row["setup"] == "CACHED"]
    uncached_calls = [row for row in matched if row["setup"] == "UNCACHED"]
    assert len({row["document"] for row in cached_calls}) == 12
    assert len({row["document"] for row in uncached_calls}) == 12
    assert all(row["model"] == MODEL for row in matched)

    for row in matched:
        assert row["pricing_per_1m_tokens"] == expected_rates, f"Rate mismatch in call {row['model_call_id']}"
        assert int(row["input_tokens"]) == (
            int(row["ordinary_input_tokens"])
            + int(row["cached_input_tokens"])
            + int(row["cache_write_tokens"])
        ), f"Input token buckets do not sum for call {row['model_call_id']}"
        assert call_cost(row, rates) == Decimal(row["cost_usd"]), f"Cost mismatch for call {row['model_call_id']}"

    c_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    u_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cached_calls:
        c_by_doc[row["document"]].append(row)
    for row in uncached_calls:
        u_by_doc[row["document"]].append(row)
    c_docs = {name: aggregate(c_by_doc[name]) for name in filenames}
    u_docs = {name: aggregate(u_by_doc[name]) for name in filenames}
    c_total = aggregate(cached_calls)
    u_total = aggregate(uncached_calls)
    saved = u_total["cost"] - c_total["cost"]
    saved_pct = saved / u_total["cost"] * 100
    c_per_doc = c_total["cost"] / 12
    u_per_doc = u_total["cost"] / 12

    p2_tokens = 10_058
    p2_uncached_1000 = Decimal(p2_tokens) * Decimal(str(rates["input_per_1m"])) / MILLION * 1000
    p2_cached_1000 = (
        Decimal(p2_tokens) * Decimal(str(rates["cache_write_per_1m"]))
        + Decimal(p2_tokens) * Decimal(999) * Decimal(str(rates["cached_input_per_1m"]))
    ) / MILLION
    p2_saved_pct = (p2_uncached_1000 - p2_cached_1000) / p2_uncached_1000 * 100

    first_cached_call = min(cached_calls, key=lambda row: row["started_at_utc"])
    first_doc = first_cached_call["document"]
    first_doc_cost = c_docs[first_doc]["cost"]
    later_doc_costs = [c_docs[name]["cost"] for name in filenames if name != first_doc]
    later_avg = sum(later_doc_costs, Decimal(0)) / Decimal(len(later_doc_costs))
    uncached_per_day = u_per_doc * 1000
    uncached_30d = uncached_per_day * 30
    observed_mix_30d = c_per_doc * 30_000
    continuous_30d = first_doc_cost + later_avg * Decimal(29_999)
    daily_cold_30d = first_doc_cost * Decimal(30) + later_avg * Decimal(29_970)
    expected_savings_projection = uncached_30d - continuous_30d
    continuous_savings_pct = expected_savings_projection / uncached_30d * 100
    daily_cold_savings_pct = (uncached_30d - daily_cold_30d) / uncached_30d * 100
    observed_mix_savings_pct = (uncached_30d - observed_mix_30d) / uncached_30d * 100

    latencies_c = [float(row["latency_ms"]) for row in cached_calls]
    latencies_u = [float(row["latency_ms"]) for row in uncached_calls]
    audit = read_json(OUTPUT / "audit_trail.json")
    matched_audit = [row for row in audit if row.get("problem") == 4 and row.get("experiment_id") == study_id]
    assert all(row.get("success") for row in matched_audit if row.get("setup") == "CACHED")
    final_audit = [row for row in matched_audit if row.get("success")]
    assert len(final_audit) >= 24

    pilot = [row for row in records if not row.get("experiment_id")]
    pilot_costs = {
        setup: sum((Decimal(row["cost_usd"]) for row in pilot if row.get("setup") == setup and row.get("cost_usd") is not None), Decimal(0))
        for setup in ("CACHED", "UNCACHED")
    }
    pilot_uncached_reads = sum(int(row["cached_input_tokens"] or 0) for row in pilot if row.get("setup") == "UNCACHED")
    pilot_total = sum(pilot_costs.values(), Decimal(0))
    rejected = [row for row in by_experiment[study_id] if not row.get("success")]
    rejected_count = len(rejected)
    assert all(row.get("cost_usd") is None and row.get("input_tokens") is None for row in rejected)
    total_records = len(records)

    prices_table = (
        f"| Ordinary input | ${rates['input_per_1m']:.3f} |\n"
        f"| Cached input | ${rates['cached_input_per_1m']:.3f} |\n"
        f"| Cache write | ${rates['cache_write_per_1m']:.3f} |\n"
        f"| Output | ${rates['output_per_1m']:.3f} |"
    )

    table_rows: list[str] = []
    for name in filenames:
        c = c_docs[name]
        u = u_docs[name]
        doc_saved = u["cost"] - c["cost"]
        c_bucket = " / ".join(number(c[key]) for key in ("input_tokens", "ordinary_input_tokens", "cached_input_tokens", "cache_write_tokens"))
        u_bucket = " / ".join(number(u[key]) for key in ("input_tokens", "ordinary_input_tokens", "cached_input_tokens", "cache_write_tokens"))
        table_rows.append(
            f"| `{name}` | {c_bucket} | {number(c['output_tokens'])} | {money(c['cost'])} | "
            f"{u_bucket} | {number(u['output_tokens'])} | {money(u['cost'])} | {money(doc_saved)} |"
        )

    table_rows.append(
        f"| **Total** | {number(c_total['input_tokens'])} / {number(c_total['ordinary_input_tokens'])} / "
        f"{number(c_total['cached_input_tokens'])} / {number(c_total['cache_write_tokens'])} | "
        f"{number(c_total['output_tokens'])} | **{money(c_total['cost'])}** | "
        f"{number(u_total['input_tokens'])} / {number(u_total['ordinary_input_tokens'])} / "
        f"{number(u_total['cached_input_tokens'])} / {number(u_total['cache_write_tokens'])} | "
        f"{number(u_total['output_tokens'])} | **{money(u_total['cost'])}** | **{money(saved)}** |"
    )

    rows_per_call = f"{c_total['calls']} cached model responses and {u_total['calls']} no-reuse model responses."
    report = f"""# Campus Customs | Vendor Intelligence Lab
## Prompt-cache field study

> **Research summary**  
> Across 12 practice documents, the matched cached run cost **{money(c_total['cost'])}** ({money(c_per_doc)} per document); the no-reuse run cost **{money(u_total['cost'])}** ({money(u_per_doc)} per document). That is **{money(saved)} saved ({percent(saved_pct)})**. The result uses API-reported usage, including cache writes in both setups and output tokens.

### Study controls

| Control | Setting |
|---|---|
| Study ID | `{study_id}` |
| Model | `{MODEL}` through Portkey, PydanticAI Responses API |
| Documents | 12 supplied practice documents, same order in both arms |
| Successful model responses | {rows_per_call} |
| Recorded cache-test rows | {total_records} total, including the diagnostic pilot and rejected request attempts |
| Cache warm-up | No separate call; first cached document is part of the measured 12-document cohort |

## 1. Methodology

Both arms use the same parsed document text, complete handbook, system instructions, structured `VendorAssessment` output, two local-only trap tools, model, and document-specific content. The handbook and task instructions are stable; the vendor document follows them as variable content. `cache_experiment.py` creates a fresh namespace for each study to avoid reuse from Problems 3 or 4 pilots. The OpenAI prompt-caching guide describes explicit breakpoints, `prompt_cache_options`, and the Responses usage fields used here ([OpenAI Docs: Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching)).

**CACHED.** The request uses `prompt_cache_options.mode="explicit"`, a 30-minute minimum cache TTL, one explicit `CachePoint` after the stable handbook/task prefix, and a stable study-scoped `prompt_cache_key`. The first p01 request wrote the prefix; subsequent requests reused it. API usage reported {number(c_total['cached_input_tokens'])} cached input tokens across the 12 calls, including {number(c_docs[first_doc]['cache_write_tokens'])} write tokens for the first document.

**UNCACHED / no shared reuse.** A first attempt using explicit mode with no breakpoint still reported cache reads on later documents, so that arm was invalid. The corrected arm retains explicit mode with no breakpoint and varies a fixed-length, inert instruction marker and a short cache key on every PydanticAI request. It therefore cannot repeat the same leading prefix. The corrected response usage confirms **zero cached input tokens** across all 12 documents. The gateway still reported cache writes on those unique prefixes; those tokens are priced at the supplied cache-write rate and are not misclassified as ordinary input.

Each `ModelResponse` is written separately to `output/cache_test.json` as it returns. `input_tokens` is inclusive; ordinary input is calculated as `input − cached reads − cache writes`. Cost per call is:

`(ordinary × input_rate + cached_reads × cached_rate + cache_writes × write_rate + output × output_rate) ÷ 1,000,000`.

Latency is measured around each PydanticAI model request. OpenAI SDK automatic retries are disabled; failed requests are retained with null usage rather than synthesized measurements. If a document required multiple model requests, each response is logged separately and its costs are summed for the document.

### Rates from `data/prices.json`

All rates are USD per 1,000,000 tokens.

| Token type | Rate |
|---|---:|
{prices_table}

## 2. Twelve-document comparison

Token tuples are **input / ordinary input / cached read / cache write**. Cost sums all actual model responses for that document; each document required one response in this measured cohort. Savings are uncached cost minus cached cost.

| Document | Cached: input / ordinary / read / write | Output (C) | Cost (C) | No reuse: input / ordinary / read / write | Output (U) | Cost (U) | Saved |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(table_rows)}

## 3. Totals and latency

| Measure | Cached | No shared reuse |
|---|---:|---:|
| Total cost, 12 documents | **{money(c_total['cost'])}** | **{money(u_total['cost'])}** |
| Cost per document | **{money(c_per_doc)}** | **{money(u_per_doc)}** |
| Input tokens | {number(c_total['input_tokens'])} | {number(u_total['input_tokens'])} |
| Ordinary input tokens | {number(c_total['ordinary_input_tokens'])} | {number(u_total['ordinary_input_tokens'])} |
| Cached input tokens | **{number(c_total['cached_input_tokens'])}** | **0** |
| Separately reported cache-write tokens | {number(c_total['cache_write_tokens'])} | {number(u_total['cache_write_tokens'])} |
| Output tokens | {number(c_total['output_tokens'])} | {number(u_total['output_tokens'])} |
| Median per-call latency | {median(latencies_c):,.1f} ms | {median(latencies_u):,.1f} ms |
| Mean per-call latency | {sum(latencies_c) / len(latencies_c):,.1f} ms | {sum(latencies_u) / len(latencies_u):,.1f} ms |

Caching saved **{money(saved)}**, or **{percent(saved_pct)}** of measured no-reuse cost. The percentage is specific to this 12-document workload and its observed cache-write behavior.

## 4. Comparison with Problem 2

Problem 2 estimated the handbook alone at 10,058 `o200k_base` tokens. It projected 1,000 uncached handbook sends at **{money(p2_uncached_1000)}** and 1,000 sends with one write plus 999 reads at **{money(p2_cached_1000)}**, saving **{percent(p2_saved_pct)}**. Those estimates exclude vendor documents, agent/tool instructions beyond the handbook, and outputs.

The Problem 4 measured mean was {money(u_per_doc)} without cache reuse and {money(c_per_doc)} cached. A warm cached request after the first write averaged **{money(later_avg)}** per document. This is higher than the Problem 2 cached handbook-only estimate because these requests include the full agent/tool context, each vendor document, output tokens, and residual cache-write tokens. The first cold write is also one of only 12 observations, so it has a large weight in the measured cached mean.

## 5. Thirty-day projection at 1,000 documents per day

The no-reuse projection applies the observed no-reuse mean to 30,000 documents. Cached projections use the measured first cold request and mean cost of the other 11 documents; they differ only in how often a cache warm-up is assumed.

| Scenario | No-reuse cost | Cached cost | Projected savings |
|---|---:|---:|---:|
| Repeat observed 12-document cost mix (one cold write per 12 documents) | {money(uncached_30d)} | {money(observed_mix_30d)} | {money(uncached_30d - observed_mix_30d)} ({percent(observed_mix_savings_pct)}) |
| Continuous warm prefix across all 30 days (one cold write total) | {money(uncached_30d)} | {money(continuous_30d)} | {money(uncached_30d - continuous_30d)} ({percent(continuous_savings_pct)}) |
| One cold start per day (30 warm-ups) | {money(uncached_30d)} | {money(daily_cold_30d)} | {money(uncached_30d - daily_cold_30d)} ({percent(daily_cold_savings_pct)}) |

The continuous case assumes no cache gap longer than the 30-minute minimum TTL and continued hit behavior like the measured warm requests. The daily-cold case assumes the prefix is unavailable at the start of each day. The repeated-batch projection includes the observed one-in-12 cold-write share and is the most conservative of these three measured-rate extrapolations.

## 6. Unexpected results and run integrity

- In the initial 12-document no-reuse attempt, explicit mode without a breakpoint still returned **{number(pilot_uncached_reads)} cached input tokens**. That arm failed the requested control check and is excluded from the table. Its measured pilot cost was {money(pilot_costs['UNCACHED'])}; the paired diagnostic pilot, including its cached arm, cost {money(pilot_total)} in total. All original response records remain in `cache_test.json`.
- The corrected per-request prefix markers eliminated cached reads, but the gateway returned **{number(u_total['cache_write_tokens'])} cache-write tokens** for the 12 unique prefixes. Their write-rate charges are included above. The Responses usage data establishes the observed behavior; it does not expose which gateway/backend layer prevented explicit-only mode from suppressing writes.
- A key-length retry produced {rejected_count} HTTP 400 request errors (the gateway limit was 64 characters). The shorter key succeeded on rerun. These error records have null usage and cost because no token usage was returned; they are retained in the JSON and excluded from the cost table.
- The matched cached arm showed {number(c_total['cached_input_tokens'])} API-reported cached tokens: the first document had no cached read, and the following requests each reported {number(c_docs[filenames[1]]['cached_input_tokens'])} cached tokens. The corrected no-reuse arm reported zero cached tokens on every successful request.

## 7. Limitations and assumptions

- This is one ordered 12-document practice sample, not a broad workload benchmark. Model output length and latency vary by document.
- The `gpt-6-luna` name is course-specific. PydanticAI 2.45.0 does not recognize its cache-breakpoint profile by name, so the documented Responses breakpoint serialization was enabled explicitly. The returned usage—not that setting alone—was used to verify caching.
- The uncached control adds a different fixed-length inert marker on every request. It preserves assessment meaning but can change a small number of tokenizer units; those actual tokens and cache writes are included in its price.
- The gateway returned cache writes even in the corrected no-reuse arm. The report therefore distinguishes “zero cached reads/no shared reuse” from “no cache writes.” It does not claim the endpoint performed zero caching work.
- OpenAI documents a 30-minute minimum cache lifetime for this model generation, but cache availability and hit routing can still vary. Projections assume the stated reuse cadence and the observed per-document request mix.
- All prices are the supplied `prices.json` values, treated as current for this estimate. Costs cover reported input, cache-write, cached-read, and output tokens; other gateway charges are outside the supplied price data.

## Reproduce and validate

Run `python cache_experiment.py` for a fresh paired experiment; it creates a unique study namespace and appends every model response. Run `python build_cache_report.py` to select the latest fully successful study with API-confirmed hits and a zero-cached-read control, recheck token buckets and costs against `prices.json`, and regenerate this report.
"""
    return report


if __name__ == "__main__":
    report = build_report()
    (OUTPUT / "cache_test.md").write_text(report, encoding="utf-8")
    print(f"Wrote {OUTPUT / 'cache_test.md'}")
