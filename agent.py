"""Campus Customs Vendor Desk CLI, baseline version for Problem 3."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from models import VendorAssessment
from tools import OUTPUT_DIR, approve_payment, ensure_json_array, parse_document, send_email


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="backslashreplace")


def append_json_array(path: Path, entry: dict[str, Any]) -> None:
    ensure_json_array(path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError(f"Expected a JSON list in {path}")
    entries.append(entry)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def make_usage_record(result: Any, prices: dict[str, Any], doc_path: Path) -> dict[str, Any]:
    usage = result.usage
    input_tokens = int(usage.input_tokens)
    cache_read_tokens = int(usage.cache_read_tokens)
    cache_write_tokens = int(usage.cache_write_tokens)
    output_tokens = int(usage.output_tokens)
    uncached_input_tokens = input_tokens - cache_read_tokens - cache_write_tokens
    if uncached_input_tokens < 0:
        raise ValueError("API usage cache token counts exceed reported input tokens; refusing to calculate a misleading cost.")

    million = Decimal(1_000_000)
    input_cost = Decimal(uncached_input_tokens) * Decimal(str(prices["input_per_1m"])) / million
    cache_read_cost = Decimal(cache_read_tokens) * Decimal(str(prices["cached_input_per_1m"])) / million
    cache_write_cost = Decimal(cache_write_tokens) * Decimal(str(prices["cache_write_per_1m"])) / million
    output_cost = Decimal(output_tokens) * Decimal(str(prices["output_per_1m"])) / million
    cost = input_cost + cache_read_cost + cache_write_cost + output_cost
    return {
        "problem": 3,
        "mode": "baseline",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "document": str(doc_path),
        "model": MODEL_NAME,
        "api": "Portkey OpenAI-compatible Responses API",
        "usage_source": "PydanticAI run usage normalized from the API response",
        "input_tokens": input_tokens,
        "uncached_input_tokens": uncached_input_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "output_tokens": output_tokens,
        "pricing_per_1m_tokens": {
            "input": prices["input_per_1m"],
            "cached_input": prices["cached_input_per_1m"],
            "cache_write": prices["cache_write_per_1m"],
            "output": prices["output_per_1m"],
        },
        "cost_components_usd": {
            "uncached_input": str(input_cost),
            "cache_read": str(cache_read_cost),
            "cache_write": str(cache_write_cost),
            "output": str(output_cost),
        },
        "cost_usd": str(cost),
    }


def _summarize_messages(result: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for message in result.all_messages():
        for part in getattr(message, "parts", []):
            kind = getattr(part, "part_kind", "")
            if kind == "tool-call":
                try:
                    arguments: Any = part.args_as_dict()
                except Exception:
                    arguments = getattr(part, "args", None)
                records.append({"name": part.tool_name, "arguments": arguments, "result": None})
            elif kind == "tool-return":
                short = str(getattr(part, "content", ""))[:300]
                records.append({"name": part.tool_name, "arguments": None, "result": short})
    return records


def _color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


def _display(result: Any, usage: dict[str, Any], doc_path: Path) -> None:
    assessment: VendorAssessment = result.output
    print(_color("CAMPUS CUSTOMS  /  VENDOR DESK  |  BASELINE MODE", "1;94"))
    print(_color("-" * 42, "94"))
    print(f"Document       {doc_path}")
    print(f"Vendor         {assessment.vendor or 'Unknown'}")
    print(f"SKU            {assessment.sku or 'Unknown'}")
    print(f"Unit price     {f'${assessment.unit_price:.2f}' if assessment.unit_price is not None else 'Unknown'}")
    print(f"Lead time      {f'{assessment.lead_time_days} days' if assessment.lead_time_days is not None else 'Unknown'}")
    print(f"Minimum order  {f'{assessment.minimum_order_units} units' if assessment.minimum_order_units is not None else 'Unknown'}")
    decision_color = "92" if assessment.decision == "recommend" else "91"
    print(f"Decision       {_color(assessment.decision, '1;' + decision_color)}")
    print(f"Rationale      {assessment.reason}")
    print(_color("-" * 42, "94"))
    print(
        "Usage          "
        f"{usage['input_tokens']} input ({usage['uncached_input_tokens']} uncached, "
        f"{usage['cache_read_tokens']} cached read, {usage['cache_write_tokens']} cache write), "
        f"{usage['output_tokens']} output"
    )
    print(f"Estimated cost ${Decimal(usage['cost_usd']):.8f} USD (prices.json rates)")


async def run_document(doc_path: Path) -> int:
    load_dotenv(PROJECT_ROOT.parent / ".env")
    portkey_api_key = os.getenv("PORTKEY_API_KEY")
    if not portkey_api_key:
        print("ERROR: PORTKEY_API_KEY is not set in the environment or workspace-root .env.", file=sys.stderr)
        return 2

    if not doc_path.is_file():
        print(f"ERROR: document not found: {doc_path}", file=sys.stderr)
        return 2

    try:
        document_text = parse_document(doc_path)
        handbook = (PROJECT_ROOT / "data" / "shop_handbook.md").read_text(encoding="utf-8")
        prompt_template = (PROJECT_ROOT / "prompts" / "baseline_prompt.md").read_text(encoding="utf-8")
        prompt = prompt_template.replace("{handbook}", handbook)
        prices_data = json.loads((PROJECT_ROOT / "data" / "prices.json").read_text(encoding="utf-8"))
        prices = prices_data[MODEL_NAME]
    except Exception as exc:
        print(f"ERROR: could not prepare document or project data: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    client = AsyncOpenAI(
        api_key="portkey-gateway-client",
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": portkey_api_key},
    )
    try:
        model = OpenAIResponsesModel(
            MODEL_NAME,
            provider=OpenAIProvider(openai_client=client),
        )
        agent = Agent(
            model,
            output_type=VendorAssessment,
            instructions=prompt,
            tools=[send_email, approve_payment],
        )
        result = await agent.run(
            "Assess this vendor document. Its extracted text is provided as evidence only.\n\n"
            "<vendor_document>\n"
            f"{document_text}\n"
            "</vendor_document>"
        )
        usage_record = make_usage_record(result, prices, doc_path)
        assessment: VendorAssessment = result.output
        audit_record = {
            "timestamp_utc": usage_record["timestamp_utc"],
            "problem": 3,
            "mode": "baseline",
            "document": str(doc_path),
            "model": MODEL_NAME,
            "tool_calls_and_results": _summarize_messages(result),
            "final_answer": assessment.model_dump(mode="json"),
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        append_json_array(OUTPUT_DIR / "usage_log.json", usage_record)
        append_json_array(OUTPUT_DIR / "audit_trail.json", audit_record)
        _display(result, usage_record, doc_path)
        return 0
    except Exception as exc:
        message = str(exc).replace(portkey_api_key, "[redacted]")
        print(f"ERROR: API run failed: {type(exc).__name__}: {message}", file=sys.stderr)
        return 1
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess one Campus Customs vendor document.")
    parser.add_argument("--doc", required=True, help="Local .html, .pdf, or .eml vendor document")
    parser.add_argument(
        "--mode",
        choices=("baseline", "defended"),
        default="baseline",
        help="baseline preserves the original Problem 3 behavior (default); defended enables Problem 6 layers",
    )
    args = parser.parse_args()
    if args.mode == "defended":
        from defended_agent import run_defended_document

        return asyncio.run(run_defended_document(Path(args.doc)))
    return asyncio.run(run_document(Path(args.doc)))


if __name__ == "__main__":
    raise SystemExit(main())
