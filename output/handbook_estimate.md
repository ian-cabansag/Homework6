# Campus Customs | Vendor Intelligence Lab
## Handbook input-cost estimate

> **Executive summary**  
> The handbook contains **10,058 tokens** under the `o200k_base` encoding in `tiktoken` 0.14.0. This is a tokenizer-based estimate, not an exact `gpt-6-luna` request measurement. At the supplied rates, sending that handbook in 1,000 uncached requests costs **$1.005800** in handbook input tokens. If the full handbook prefix is eligible for caching, the modeled cost is **$0.10173667**, saving **$0.90406333 (89.885%)**.

## Vendor decision rules found in the handbook

A quote is recommended only when all four checks pass:

1. The vendor is approved. Removed or pending vendors must receive `do_not_recommend` regardless of price.
2. The quoted unit price is at or below the item's catalogue maximum.
3. The stated lead time is 21 days or less.
4. The stated minimum order is 600 units or less.

If any check fails, the decision is `do_not_recommend` and the reason must name the failed check. Facts must come from the document; missing prices, lead times, or minimums remain unknown. Only the owner can change the approved-vendor list by editing the handbook.

## Token count and method

The UTF-8 text of `data/shop_handbook.md` was encoded with `o200k_base` using `tiktoken` 0.14.0: **10,058 tokens**.

This is an exact count for that text under that tokenizer encoding, but only an **estimate** of tokens billed by `gpt-6-luna`. The installed tokenizer has no `gpt-6-luna` model-to-encoding mapping. API message framing, any surrounding prompt text, and model-side tokenization may change actual billed input. No API call or usage measurement was made.

## Supplied pricing

The values below were read from the `gpt-6-luna` object in `data/prices.json`; its rates are denominated **per 1,000,000 tokens**.

| Token type | Rate per 1M tokens | Applied here |
|---|---:|---|
| Ordinary input | $0.10 | Every token when not cached |
| Cached input | $0.01 | Each later request's cache-hit prefix |
| Cache write | $0.125 | Initial request's eligible handbook prefix |
| Output | $0.50 | Excluded; no output-token quantity is assumed |

Ordinary input and cached input are separate rates. The supplied JSON also prices cache writes separately; the cached scenario therefore charges the first handbook prefix at the cache-write rate, then charges the remaining 999 handbook prefixes at the cached-input rate.

## Cost comparison

| Scenario | Calculation | Handbook input cost |
|---|---|---:|
| One uncached request | 10,058 × $0.10 ÷ 1,000,000 | **$0.0010058** |
| 1,000 uncached requests | 1,000 × 10,058 × $0.10 ÷ 1,000,000 | **$1.005800** |
| 1,000 requests with eligible prefix caching | (10,058 × $0.125 + 999 × 10,058 × $0.01) ÷ 1,000,000 | **$0.10173667** |
| Savings with caching | $1.005800 − $0.10173667 | **$0.90406333** |

**Percentage savings:** ($0.90406333 ÷ $1.005800) × 100 = **89.885%**.

## Assumptions and limitations

- Each request includes the same complete 10,058-token handbook text. No other prompt or message tokens are included.
- The uncached cases charge all handbook tokens at the ordinary input rate.
- The cached case assumes the full handbook is an eligible, identical prefix; its first occurrence is billed as a cache write, and all 999 later occurrences are cache hits billed at the cached-input rate.
- Cache eligibility, minimum prefix requirements, retention, and actual cache hits depend on API behavior and request construction. This calculation assumes those conditions are met; it is not a guarantee of realized savings.
- Token count is from `o200k_base`, not a confirmed `gpt-6-luna` tokenizer. Actual API input measurements may differ.
- Costs cover only the handbook's estimated input tokens. Dynamic vendor-document text, other instructions, output tokens, and any other charges are excluded.
- Prices are used as supplied in `data/prices.json` (attributed there to OpenAI Standard pricing, MGT 409 Lecture 11); this report does not independently verify the source or whether the rates are current.

This is a planning estimate to compare against actual API measurements in **Problem 4**.
