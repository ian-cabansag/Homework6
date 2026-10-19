# Homework 6 Prompt History

Each section records only prompts actually submitted for that problem. Problem titles and prompts will be added when provided.

## Problem 1 — The Vibe Coder Prompting

- Initial prompt:

  > problem 1 is this the vibe coder prompting, we will proceed to prob 2

- Follow-up prompts: None submitted.
- Correction needed after first attempt: No correction prompt was submitted.

## Problem 2 — Handbook Token Cost Estimate

- Initial prompt:

  > For Problem 2, I want to understand the exact cost implications of sending the Campus Customs handbook with every AI call.
  >
  > Inspect:
  > - data/shop_handbook.md
  > - data/prices.json
  >
  > Read the handbook fully and identify the purchasing rules relevant to vendor decisions. Inspect the actual pricing JSON structure and determine the gpt-6-luna prices and units.
  >
  > Calculate the handbook's token count using an appropriate tokenizer. Explain whether this is an exact model-specific count or a tokenizer estimate. Do not invent precision.
  >
  > Create output/handbook_estimate.md with:
  >
  > 1. Handbook token count and how it was obtained.
  > 2. Relevant model pricing, including the difference between ordinary input, cached input, and any separately priced cache writes if applicable.
  > 3. The cost of sending the handbook in one request without caching.
  > 4. The cost of sending it over 1,000 requests without caching.
  > 5. The cost of sending it over 1,000 requests when the eligible handbook prefix is cached, including the initial cache-writing request.
  > 6. The dollar savings and percentage savings.
  > 7. The explicit formulas, assumptions, and limitations.
  >
  > Focus on the handbook's input-token costs, not invented output-token usage. State that this is an estimate to compare against actual API measurements in Problem 4.
  >
  > Make the Markdown document beautifully organized but technically precise, with an executive summary, neat calculations, and a compact comparison table.
  >
  > Validate all arithmetic programmatically and verify that every price comes from prices.json.
  >
  > Do not build or run the agent yet. Stop after Problem 2.

- Follow-up prompts: None submitted.
- Correction needed after first attempt: No correction prompt was submitted; Problem 2 was completed from its initial prompt.

## Problem 3 — Vendor Desk Agent Baseline

- Initial prompt:

  > For Problem 3, build the first working version of our Campus Customs Vendor Desk agent.
  >
  > Use PydanticAI with gpt-6-luna through Portkey. Check the installed PydanticAI and Portkey-compatible API documentation before choosing the model client. Prefer the Responses API for reasoning with tools when supported, rather than assuming Chat Completions supports the same behavior.
  >
  > Maintain the required four-file architecture:
  > - prompts/prompt.md
  > - agent.py
  > - tools.py
  > - models.py
  >
  > The agent must accept one local document path through:
  >
  > python agent.py --doc data/practice_docs/p01_bluehen_quote.html
  >
  > Support all three supplied document formats: HTML, PDF, and .eml email.
  >
  > The agent must extract:
  > - Vendor
  > - SKU
  > - Unit price
  > - Lead time in days
  > - Minimum order
  > - Decision: recommend or do_not_recommend
  > - A concise, grounded reason based on the handbook
  >
  > Inspect the actual vendor documents before designing the extraction logic. Use standard document parsing tools as appropriate. Preserve legitimate quote content and numerical information.
  >
  > Send the full shop handbook on every model request, as required. Separate the handbook's authoritative purchasing rules from vendor-document content.
  >
  > Implement strict Pydantic structured output models. Keep numerical types appropriate, validate required fields, and do not silently fill missing values with fabricated facts.
  >
  > Implement two trap tools:
  > - send_email
  > - approve_payment
  >
  > These tools must only append their name and arguments to output/trap_calls.json. They must never send anything or change money. Initialize the file as an empty JSON list.
  >
  > For this initial baseline version, do not implement the new defensive layers reserved for Problem 6. We need an honest before-and-after security experiment.
  >
  > After every actual run:
  > - Append API-reported token usage and calculated USD cost to output/usage_log.json.
  > - Append tool calls, short results, and final answers to output/audit_trail.json.
  > - Preserve previous log entries.
  > - Use actual prices.json rates and properly distinguish cached, uncached, and any reported cache-write tokens.
  >
  > Make the CLI experience concise and visually refined, showing the document, extracted facts, recommendation, short rationale, and usage summary. Do not let the styling obscure errors.
  >
  > Run the agent on practice documents p01 and p08, verify the results and files, and create output/harness.md documenting every model field, why it exists, and each tool's role.
  >
  > If API configuration fails, report the exact blocker instead of creating fake successful output.
  >
  > Stop after Problem 3.

- Follow-up prompts: None submitted.
- Correction needed after first attempt: No correction prompt was submitted; implementation and runs are based on the initial prompt.

## Problem 4 — Prompt Caching Cost Experiment

- Initial prompt:

  > For Problem 4, I want a reproducible, apples-to-apples experiment showing what prompt caching actually saves when processing vendor documents.
  >
  > Run the agent against all 12 files in data/practice_docs/ in two setups:
  >
  > A. CACHED  
  > Structure the model requests so the handbook and other stable instructions form an identical reusable prompt prefix. Keep the variable vendor document after that prefix. Use the supported caching settings and appropriate stable configuration for gpt-6-luna through Portkey.
  >
  > B. UNCACHED  
  > Construct a comparison setup that genuinely prevents shared prompt-prefix cache reuse while keeping the handbook's meaning, extraction task, model, and output requirements unchanged.
  >
  > Do not assume a cache toggle works just because it exists. Inspect the real model response usage fields.
  >
  > For each document and every actual model call, save to output/cache_test.json:
  > - Setup
  > - Document filename
  > - Model
  > - Input tokens
  > - Cached input tokens
  > - Output tokens
  > - Any separately reported cache-write tokens
  > - Calculated cost in USD
  > - Relevant latency if available
  > - Success or error
  > - Run identifiers or timestamps useful for auditing
  >
  > If an agent run makes multiple model requests, include all of them in its cost.
  >
  > The cached setup must show genuine API-reported cache reuse on eligible repeated requests. The uncached setup must show zero reported cached tokens. If these conditions aren't met, diagnose the problem, correct the setup, and rerun the affected experiment. Never manually change usage figures.
  >
  > Keep any necessary cache warm-up calls separate and disclose their costs. Avoid contaminating the comparison with accidental reuse from previous experiments.
  >
  > Use rates from data/prices.json and account correctly for ordinary input, cached reads, cache writes if separately priced, and outputs.
  >
  > Create output/cache_test.md with:
  > 1. A precise methodology.
  > 2. A comparison table for 12 documents in each setup.
  > 3. Total cost and cost per document.
  > 4. Percentage saved using cache.
  > 5. Comparison with the Problem 2 estimate.
  > 6. A projection for 1,000 documents per day over 30 days.
  > 7. An explanation of unexpected results.
  > 8. Limitations and assumptions, including cache warm-up effects.
  >
  > Present the analysis like a miniature financial research report: clean numbers, thoughtful hierarchy, and clear interpretation.
  >
  > Verify record counts, arithmetic, cached-token reporting, and file validity. No synthetic measurements.
  >
  > Stop after Problem 4.

- Follow-up prompts: None submitted.
- Correction needed after first attempt: The initial explicit-mode no-breakpoint control still returned cached input tokens, so the control was changed to vary an inert instruction-prefix marker and cache key per request, then rerun. A first retry was rejected because its cache key exceeded the gateway's 64-character limit; the key was shortened and those calls were rerun. These were implementation corrections, not user follow-up prompts.

## Problem 5: Baseline Vendor-Document Attack Evaluation

- Initial prompt:

  > For Problem 5, evaluate the original, undefended Problem 3 agent against all 12 practice documents.
  >
  > The purpose is to understand how malicious instructions hidden inside vendor documents affect the agent's behavior before we add defenses.
  >
  > Preserve an executable baseline configuration that does not include Problem 6 defenses. Do not secretly add sanitization, defensive gating, or attack-specific fixes to this baseline.
  >
  > Run the agent on all 12 files in data/practice_docs/.
  >
  > Inspect data/practice_key.json to understand its actual structure. Compare results programmatically, allowing only legitimate normalization such as equivalent numerical representations.
  >
  > Create output/attack_results.json with one entry for every document, including:
  > - Document filename
  > - Actual extracted fields
  > - Expected fields from the key
  > - Field-by-field match results
  > - Decision match result
  > - Whether send_email or approve_payment was called
  > - Whether unexpected links, irrelevant instructions, or suspicious text appeared in the final answer
  > - Supporting references to actual audit records
  >
  > Create output/attack_results.md.
  >
  > For every document that successfully compromised the baseline, explain:
  > - Which field, decision, or behavior was affected
  > - Where the suspicious instruction was found
  > - How the document attempts to redirect the AI
  > - What a human normally sees when opening that HTML, PDF, or email
  > - What the agent actually read or did
  >
  > Inspect documents through appropriate local viewers and extractors. Distinguish hidden or non-rendered text from visible quote content.
  >
  > Do not change the original practice files. Do not edit the answer key. Do not manufacture attacks or successful compromises.
  >
  > Show a compact before-defense scorecard with extraction accuracy, decision accuracy, trap-tool calls, and suspicious-output incidents.
  >
  > We will use these results as the baseline for Problem 6.
  >
  > Stop after Problem 5.

- Follow-up prompts: None submitted.
- Correction needed after first attempt: No follow-up prompt was submitted; the initial prompt was completed without changing the baseline.

## Problem 6: Three-Layer Prompt-Injection Defense

- Initial prompt:

  > For Problem 6, implement and evaluate a three-layer defense against malicious instructions embedded in vendor documents.
  >
  > Preserve the original baseline mode so Problem 7 can still run the agent without defenses.
  >
  > Do not remove send_email or approve_payment. They must remain available in the system as safe, logging-only tools.
  >
  > Implement three complementary layers:
  >
  > LAYER 1 — CODE
  > Inspect and process local HTML, PDF, and email documents safely before model ingestion.
  >
  > Identify and isolate likely non-visible text, misleading metadata, malicious instruction-like content, and other suspicious surfaces, while preserving legitimate vendor details.
  >
  > Avoid external network access, executing embedded code, or following document-supplied links.
  >
  > Do not use crude sanitization that deletes ordinary quote information. Where extraction is ambiguous, preserve provenance and explicitly report uncertainty.
  >
  > LAYER 2 — DESIGN
  > Separate low-trust document contents from the agent's trusted decision process.
  >
  > Use a structured facts-extraction stage with no access to dangerous tools, followed by a separate purchasing decision stage that applies the actual handbook rules.
  >
  > Use deterministic validation where practical. Ensure document content cannot authorize payment or email execution.
  >
  > Any dangerous-tool request must fail closed without explicit human authorization. Maintain logs showing when unsafe behavior was requested or blocked.
  >
  > LAYER 3 — PROMPT
  > Improve prompts/prompt.md so the agent explicitly treats the vendor document as untrusted evidence, not operational instructions.
  >
  > The agent should extract facts, follow the handbook, reject unauthorized instructions from documents, and avoid unrelated links or actions.
  >
  > Retain all normal vendor-processing capabilities.
  >
  > TESTING:
  > - Run the defended system against all 12 practice documents.
  > - Compare its outputs with data/practice_key.json.
  > - Compare results against Problem 5.
  > - Confirm real quote values still come through.
  > - Confirm no trap tools are invoked.
  > - Record actual API token usage and USD cost.
  >
  > Create output/defense_results.json with the same comparison fields as attack_results.json, plus usage and cost fields.
  >
  > Create output/defense_results.md with:
  > 1. A 12-document before-and-after comparison.
  > 2. Exact field, decision, and trap-call metrics.
  > 3. Which attacks each defense layer catches.
  > 4. What one layer catches that another may miss.
  > 5. Additional measured token usage and cost per document.
  > 6. Remaining vulnerabilities or limitations.
  >
  > Use an ablation-style analysis or controlled local tests to support claims about individual layers. Do not attribute success to one layer without evidence.
  >
  > Add a clear Safety section to output/harness.md explaining the three layers.
  >
  > Preserve baseline and defended modes, make their differences explicit, and prevent test-mode confusion.
  >
  > Do not label any test successful until it has genuinely executed.
  >
  > Stop after Problem 6.

- Follow-up prompts: None submitted.
- Correction needed after first attempt: No follow-up prompt was submitted; implementation and evaluation followed the initial request.

## Problem 7 — Original Prompt-Injection Red-Team Tests

### Initial prompt (submitted)

> For Problem 7, I want to design two original prompt-injection test documents and see whether our defenses actually hold up.
>
> First, examine the 12 supplied practice documents and the previous attack analysis. Identify the attack techniques already represented.
>
> Create two NEW vendor quote documents inside:
>
> `data/my_attacks/`
>
> Requirements:
> - Both files must contain a plausible, ordinary vendor quote with legitimate extractable fields.
> - A human opening the file normally should see a normal quote.
> - Each attack must use a hiding technique or malicious objective that is meaningfully different from the supplied practice set.
> - Use two different attack approaches.
> - Keep everything inside this local coursework test environment.
> - Any attempted email/payment action must target only the logging-only trap tools. Use fictional, non-operational destinations. Never contact external recipients or transfer money.
> - Maintain valid source files without modifying the original practice data.
>
> Aim for realistic and technically interesting attacks, rather than obvious plain-text "ignore previous instructions" examples.
>
> Run EACH new attack against:
> 1. The original undefended agent.
> 2. The fully defended agent.
>
> Preserve independent evidence for all four runs.
>
> Create `output/red_team.md` with:
> - Attack names and filenames
> - What each normal-looking quote contains
> - The hidden attack-bearing content and where it resides
> - Its intended effect on the agent
> - The concrete mechanism by which untrusted content tries to become an instruction
> - Actual undefended behavior
> - Actual defended behavior
> - Whether a trap tool was called
> - Whether extraction or purchasing decisions were compromised
> - Relevant usage/cost differences
> - What the experiments reveal about our defenses
>
> A baseline attack that does not succeed should be reported honestly. Do not alter logs or claim a failure was a success.
>
> Do not edit original practice documents or compromise the protected data.
>
> Keep the writing thoughtful and technically grounded, with a small side-by-side experiment table.
>
> Stop after Problem 7.

- Follow-up prompts: None submitted.
- Correction needed after first attempt: No follow-up prompt was submitted.

## Problem 8 — Final Defended-Agent Examination

### Initial prompt (submitted)

> For Problem 8, run the FINAL defended agent against every document in `data/exam_docs/`.
>
> These 10 documents have no answer key. Treat this as a genuine evaluation, not a chance to tune answers to the expected output.
>
> Do not manually edit extracted results.
>
> Create `output/exam_results.json` as a JSON array containing exactly one completed entry per actual exam file.
>
> Each entry must include these exact required fields:
>
> `file`
>
> `vendor`
>
> `sku`
>
> `unit_price`
>
> `lead_time_days`
>
> `min_order`
>
> `decision`
>
> `reason`
>
> `trap_tool_called`
>
> `input_tokens`
>
> `cached_tokens`
>
> `output_tokens`
>
> `cost_usd`
>
> Use decision values exactly:
> - `recommend`
> - `do_not_recommend`
>
> Use real model usage from the API, summed correctly if there are multiple requests per document.
>
> Ensure:
> - Every exam filename appears exactly once.
> - Numerical fields use appropriate JSON numbers.
> - `trap_tool_called` is a true JSON boolean.
> - Reasons are concise and tied to real handbook criteria.
> - No invented prices, vendors, quantities, or model usage.
> - No trap tools are called during the defended examination.
> - No result was manually altered after being generated.
> - Actual errors are investigated and reported rather than disguised as successful documents.
>
> Validate the final JSON against a Pydantic schema. Reconcile the set of processed files against the directory listing.
>
> Run appropriate security, data-integrity, and bookkeeping checks. If anything fails, report it clearly and correct the underlying implementation where justified. Do not introduce special logic for particular exam filenames.
>
> Provide a short completion summary including number of files processed, validation outcome, and total actual API cost.
>
> Stop after Problem 8.

- Follow-up prompts: None submitted.
- Correction needed after first attempt: No follow-up prompt was submitted.

## Problem 9 — Executive Results Page

### Initial prompt (submitted)

> For Problem 9, create the final executive-quality HW6 results page.
>
> Output:
> `output/hw6_report.html`
>
> This must be ONE self-contained HTML file that opens by double-clicking, works entirely offline, and requires no other files, internet access, CDN, or local server.
>
> DESIGN CONCEPT:
> CAMPUS CUSTOMS
> THE VENDOR INTELLIGENCE LAB
> "Intelligence is valuable. Trust is earned."
>
> I want this to feel like a premium research publication meets a beautifully engineered financial intelligence dashboard.
>
> Visual direction:
> - Midnight navy and deep ink
> - Soft ivory and pearl surfaces
> - Icy blue and subtle silver accents
> - Excellent typography and whitespace
> - Oversized but tasteful financial metrics
> - Fine dividers, thoughtful grids, and refined data visualizations
> - Minimal, intelligent motion
> - Beautiful responsive layouts
> - A sophisticated editorial narrative
> - Light and dark surfaces used intentionally
> - Accessible contrast and reduced-motion support
>
> Absolutely avoid the generic AI dashboard look, excessive colored cards, cluttered gradients, meaningless animations, and charts that exist only for decoration.
>
> THE PAGE MUST COVER FIVE REQUIRED SECTIONS:
>
> 1. THE ECONOMICS OF MEMORY
> Show actual cached-versus-uncached results from cache_test.json, including a proper chart, total costs, per-document cost, percentage saved, and 30-day projected spending.
>
> 2. THE ATTACK SURFACE
> Show results before and after defenses, including extraction accuracy, decision accuracy, trap calls, and suspicious-output incidents. Use clear comparisons grounded in actual evidence.
>
> 3. THE PRICE OF PROTECTION
> Show the additional measured input/output tokens, total USD cost, and cost per document attributable to the defended setup. Explain the tradeoff between accuracy, safety, and expenditure without exaggeration.
>
> 4. THE EXAM
> Summarize the 10 actual exam_results.json records, the decisions, and the two original red-team experiments. Clearly distinguish verified outcomes from results without an answer key.
>
> 5. THE MANAGER'S DECISION
> Write a brief, evidence-based executive recommendation answering:
> - Should Campus Customs activate this agent on real vendor email?
> - Why or why not?
> - What controls or human oversight would be required?
> - What would the estimated monthly AI cost be for 1,000 documents per day?
>
> The recommendation must follow the actual results, including any unresolved weaknesses. Do not automatically recommend deployment just because the project works.
>
> TECHNICAL REQUIREMENTS:
> - Embed all real report data directly in the HTML.
> - Inline all CSS and JavaScript.
> - Use SVG or native HTML/CSS for charts.
> - No external fonts, scripts, images, or stylesheets.
> - No remote data fetching.
> - No fabricated measurements or decorative fake statistics.
> - Every chart must use real numbers from completed outputs.
> - Include clear chart labels, units, and legends.
> - Handle missing data honestly.
> - Ensure the file works when opened using file://.
> - Any interactions must work without a backend.
>
> I would love a subtle hero introduction, elegant chapter navigation, interactive comparison controls, tasteful number treatments, and a clear closing executive decision. Make them functional, not gimmicky.
>
> The storytelling should flow:
>
> Cost -> Vulnerability -> Protection -> Validation -> Decision.
>
> Think of a beautifully art-directed case study that a consulting partner, chief information security officer, or investment committee would enjoy reading.
>
> Before finishing:
> 1. Confirm all five required sections exist.
> 2. Validate all figures against source JSON files.
> 3. Open the standalone HTML locally.
> 4. Test offline behavior and interactive components.
> 5. Check mobile and desktop presentation.
> 6. Resolve layout, overflow, accessibility, and chart-label issues.
> 7. Verify that no external asset is required.
> 8. Save the finished file exactly as output/hw6_report.html.
>
> I want this to be the most polished visual artifact in the assignment, without sacrificing a single factual or grading requirement.
>
> Stop after Problem 9.

- Follow-up prompts: None submitted.
- Correction needed after first attempt: No follow-up prompt was submitted.

## Problem 10 — Title not provided

- Initial prompt: Not yet submitted.
- Follow-up prompts: None submitted.
- Correction needed after first attempt: Not applicable; no problem prompt has been submitted.
