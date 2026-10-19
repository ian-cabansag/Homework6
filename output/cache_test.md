# Campus Customs | Vendor Intelligence Lab
## Prompt-cache field study

> **Research summary**  
> Across 12 practice documents, the matched cached run cost **$0.003865105** ($0.000322092 per document); the no-reuse run cost **$0.017275075** ($0.001439590 per document). That is **$0.013409970 saved (77.63%)**. The result uses API-reported usage, including cache writes in both setups and output tokens.

### Study controls

| Control | Setting |
|---|---|
| Study ID | `20261019T043621Z-1b028e7fb6` |
| Model | `gpt-6-luna` through Portkey, PydanticAI Responses API |
| Documents | 12 supplied practice documents, same order in both arms |
| Successful model responses | 12 cached model responses and 12 no-reuse model responses. |
| Recorded cache-test rows | 60 total, including the diagnostic pilot and rejected request attempts |
| Cache warm-up | No separate call; first cached document is part of the measured 12-document cohort |

## 1. Methodology

Both arms use the same parsed document text, complete handbook, system instructions, structured `VendorAssessment` output, two local-only trap tools, model, and document-specific content. The handbook and task instructions are stable; the vendor document follows them as variable content. `cache_experiment.py` creates a fresh namespace for each study to avoid reuse from Problems 3 or 4 pilots. The OpenAI prompt-caching guide describes explicit breakpoints, `prompt_cache_options`, and the Responses usage fields used here ([OpenAI Docs: Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching)).

**CACHED.** The request uses `prompt_cache_options.mode="explicit"`, a 30-minute minimum cache TTL, one explicit `CachePoint` after the stable handbook/task prefix, and a stable study-scoped `prompt_cache_key`. The first p01 request wrote the prefix; subsequent requests reused it. API usage reported 116,303 cached input tokens across the 12 calls, including 10,722 write tokens for the first document.

**UNCACHED / no shared reuse.** A first attempt using explicit mode with no breakpoint still reported cache reads on later documents, so that arm was invalid. The corrected arm retains explicit mode with no breakpoint and varies a fixed-length, inert instruction marker and a short cache key on every PydanticAI request. It therefore cannot repeat the same leading prefix. The corrected response usage confirms **zero cached input tokens** across all 12 documents. The gateway still reported cache writes on those unique prefixes; those tokens are priced at the supplied cache-write rate and are not misclassified as ordinary input.

Each `ModelResponse` is written separately to `output/cache_test.json` as it returns. `input_tokens` is inclusive; ordinary input is calculated as `input − cached reads − cache writes`. Cost per call is:

`(ordinary × input_rate + cached_reads × cached_rate + cache_writes × write_rate + output × output_rate) ÷ 1,000,000`.

Latency is measured around each PydanticAI model request. OpenAI SDK automatic retries are disabled; failed requests are retained with null usage rather than synthesized measurements. If a document required multiple model requests, each response is logged separately and its costs are summed for the document.

### Rates from `data/prices.json`

All rates are USD per 1,000,000 tokens.

| Token type | Rate |
|---|---:|
| Ordinary input | $0.100 |
| Cached input | $0.010 |
| Cache write | $0.125 |
| Output | $0.500 |

## 2. Twelve-document comparison

Token tuples are **input / ordinary input / cached read / cache write**. Cost sums all actual model responses for that document; each document required one response in this measured cohort. Savings are uncached cost minus cached cost.

| Document | Cached: input / ordinary / read / write | Output (C) | Cost (C) | No reuse: input / ordinary / read / write | Output (U) | Cost (U) | Saved |
|---|---:|---:|---:|---:|---:|---:|---:|
| `p01_bluehen_quote.html` | 10,848 / 126 / 0 / 10,722 | 163 | $0.001434350 | 10,854 / 126 / 0 / 10,728 | 156 | $0.001431600 | $-0.000002750 |
| `p02_elmcity_quote.html` | 10,848 / 126 / 10,573 / 149 | 158 | $0.000215955 | 10,854 / 126 / 0 / 10,728 | 223 | $0.001465100 | $0.001249145 |
| `p03_ivyprint_catalog.html` | 10,846 / 126 / 10,573 / 147 | 190 | $0.000231705 | 10,851 / 126 / 0 / 10,725 | 189 | $0.001447725 | $0.001216020 |
| `p04_harborstitch_quote.html` | 10,832 / 126 / 10,573 / 133 | 150 | $0.000209955 | 10,839 / 126 / 0 / 10,713 | 182 | $0.001442725 | $0.001232770 |
| `p05_maplemills_quote.pdf` | 10,813 / 126 / 10,573 / 114 | 133 | $0.000199080 | 10,817 / 126 / 0 / 10,691 | 136 | $0.001416975 | $0.001217895 |
| `p06_qtextile_quote.pdf` | 10,857 / 126 / 10,573 / 158 | 167 | $0.000221580 | 10,861 / 126 / 0 / 10,735 | 207 | $0.001457975 | $0.001236395 |
| `p07_longwharf_quote.pdf` | 10,832 / 126 / 10,573 / 133 | 243 | $0.000256455 | 10,844 / 126 / 0 / 10,718 | 190 | $0.001447350 | $0.001190895 |
| `p08_chapelst_email.eml` | 10,836 / 126 / 10,573 / 137 | 163 | $0.000216955 | 10,843 / 126 / 0 / 10,717 | 170 | $0.001437225 | $0.001220270 |
| `p09_westville_email.eml` | 10,832 / 126 / 10,573 / 133 | 148 | $0.000208955 | 10,840 / 126 / 0 / 10,714 | 150 | $0.001426850 | $0.001217895 |
| `p10_eastrock_email.eml` | 10,855 / 126 / 10,573 / 156 | 180 | $0.000227830 | 10,860 / 126 / 0 / 10,734 | 180 | $0.001444350 | $0.001216520 |
| `p11_yorkst_quote.html` | 10,810 / 126 / 10,573 / 111 | 177 | $0.000220705 | 10,820 / 126 / 0 / 10,694 | 147 | $0.001422850 | $0.001202145 |
| `p12_bluehen_quote.pdf` | 10,833 / 126 / 10,573 / 134 | 173 | $0.000221580 | 10,844 / 126 / 0 / 10,718 | 164 | $0.001434350 | $0.001212770 |
| **Total** | 130,042 / 1,512 / 116,303 / 12,227 | 2,045 | **$0.003865105** | 130,127 / 1,512 / 0 / 128,615 | 2,094 | **$0.017275075** | **$0.013409970** |

## 3. Totals and latency

| Measure | Cached | No shared reuse |
|---|---:|---:|
| Total cost, 12 documents | **$0.003865105** | **$0.017275075** |
| Cost per document | **$0.000322092** | **$0.001439590** |
| Input tokens | 130,042 | 130,127 |
| Ordinary input tokens | 1,512 | 1,512 |
| Cached input tokens | **116,303** | **0** |
| Separately reported cache-write tokens | 12,227 | 128,615 |
| Output tokens | 2,045 | 2,094 |
| Median per-call latency | 2,797.1 ms | 2,793.8 ms |
| Mean per-call latency | 2,851.7 ms | 3,104.8 ms |

Caching saved **$0.013409970**, or **77.63%** of measured no-reuse cost. The percentage is specific to this 12-document workload and its observed cache-write behavior.

## 4. Comparison with Problem 2

Problem 2 estimated the handbook alone at 10,058 `o200k_base` tokens. It projected 1,000 uncached handbook sends at **$1.005800000** and 1,000 sends with one write plus 999 reads at **$0.101736670**, saving **89.88%**. Those estimates exclude vendor documents, agent/tool instructions beyond the handbook, and outputs.

The Problem 4 measured mean was $0.001439590 without cache reuse and $0.000322092 cached. A warm cached request after the first write averaged **$0.000220978** per document. This is higher than the Problem 2 cached handbook-only estimate because these requests include the full agent/tool context, each vendor document, output tokens, and residual cache-write tokens. The first cold write is also one of only 12 observations, so it has a large weight in the measured cached mean.

## 5. Thirty-day projection at 1,000 documents per day

The no-reuse projection applies the observed no-reuse mean to 30,000 documents. Cached projections use the measured first cold request and mean cost of the other 11 documents; they differ only in how often a cache warm-up is assumed.

| Scenario | No-reuse cost | Cached cost | Projected savings |
|---|---:|---:|---:|
| Repeat observed 12-document cost mix (one cold write per 12 documents) | $43.187687500 | $9.662762500 | $33.524925000 (77.63%) |
| Continuous warm prefix across all 30 days (one cold write total) | $43.187687500 | $6.630545190 | $36.557142310 (84.65%) |
| One cold start per day (30 warm-ups) | $43.187687500 | $6.665732986 | $36.521954514 (84.57%) |

The continuous case assumes no cache gap longer than the 30-minute minimum TTL and continued hit behavior like the measured warm requests. The daily-cold case assumes the prefix is unavailable at the start of each day. The repeated-batch projection includes the observed one-in-12 cold-write share and is the most conservative of these three measured-rate extrapolations.

## 6. Unexpected results and run integrity

- In the initial 12-document no-reuse attempt, explicit mode without a breakpoint still returned **115,731 cached input tokens**. That arm failed the requested control check and is excluded from the table. Its measured pilot cost was $0.003817385; the paired diagnostic pilot, including its cached arm, cost $0.007635205 in total. All original response records remain in `cache_test.json`.
- The corrected per-request prefix markers eliminated cached reads, but the gateway returned **128,615 cache-write tokens** for the 12 unique prefixes. Their write-rate charges are included above. The Responses usage data establishes the observed behavior; it does not expose which gateway/backend layer prevented explicit-only mode from suppressing writes.
- A key-length retry produced 12 HTTP 400 request errors (the gateway limit was 64 characters). The shorter key succeeded on rerun. These error records have null usage and cost because no token usage was returned; they are retained in the JSON and excluded from the cost table.
- The matched cached arm showed 116,303 API-reported cached tokens: the first document had no cached read, and the following requests each reported 10,573 cached tokens. The corrected no-reuse arm reported zero cached tokens on every successful request.

## 7. Limitations and assumptions

- This is one ordered 12-document practice sample, not a broad workload benchmark. Model output length and latency vary by document.
- The `gpt-6-luna` name is course-specific. PydanticAI 2.45.0 does not recognize its cache-breakpoint profile by name, so the documented Responses breakpoint serialization was enabled explicitly. The returned usage—not that setting alone—was used to verify caching.
- The uncached control adds a different fixed-length inert marker on every request. It preserves assessment meaning but can change a small number of tokenizer units; those actual tokens and cache writes are included in its price.
- The gateway returned cache writes even in the corrected no-reuse arm. The report therefore distinguishes “zero cached reads/no shared reuse” from “no cache writes.” It does not claim the endpoint performed zero caching work.
- OpenAI documents a 30-minute minimum cache lifetime for this model generation, but cache availability and hit routing can still vary. Projections assume the stated reuse cadence and the observed per-document request mix.
- All prices are the supplied `prices.json` values, treated as current for this estimate. Costs cover reported input, cache-write, cached-read, and output tokens; other gateway charges are outside the supplied price data.

## Reproduce and validate

Run `python cache_experiment.py` for a fresh paired experiment; it creates a unique study namespace and appends every model response. Run `python build_cache_report.py` to select the latest fully successful study with API-confirmed hits and a zero-cached-read control, recheck token buckets and costs against `prices.json`, and regenerate this report.
