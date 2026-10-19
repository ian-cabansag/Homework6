"""Reproducible cached-versus-explicitly-uncached PydanticAI experiment."""

from __future__ import annotations

import asyncio
import argparse
import copy
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from openai import AsyncOpenAI
from pydantic_ai import Agent, CachePoint
from pydantic_ai.messages import InstructionPart, ModelResponse
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from models import VendorAssessment
from tools import OUTPUT_DIR, PROJECT_ROOT, approve_payment, ensure_json_array, parse_document, send_email


MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MILLION = Decimal(1_000_000)
ISOLATION_MARKER = "00000000000000000000000000000000"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def append_json_array(path: Path, entry: dict[str, Any]) -> None:
    ensure_json_array(path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError(f"Expected a JSON list in {path}")
    entries.append(entry)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def cost_parts(
    input_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
    output_tokens: int,
    rates: dict[str, Any],
) -> tuple[dict[str, Decimal], Decimal]:
    ordinary_tokens = input_tokens - cached_tokens - cache_write_tokens
    if min(input_tokens, cached_tokens, cache_write_tokens, output_tokens, ordinary_tokens) < 0:
        raise ValueError("Inconsistent API usage: cache token counts exceed total input tokens.")
    parts = {
        "ordinary_input": Decimal(ordinary_tokens) * Decimal(str(rates["input_per_1m"])) / MILLION,
        "cached_input": Decimal(cached_tokens) * Decimal(str(rates["cached_input_per_1m"])) / MILLION,
        "cache_write": Decimal(cache_write_tokens) * Decimal(str(rates["cache_write_per_1m"])) / MILLION,
        "output": Decimal(output_tokens) * Decimal(str(rates["output_per_1m"])) / MILLION,
    }
    return parts, sum(parts.values(), Decimal(0))


def _safe_error(error: Exception, api_key: str) -> str:
    return f"{type(error).__name__}: {str(error).replace(api_key, '[redacted]')}"


class AuditedResponsesModel(OpenAIResponsesModel):
    """Time every PydanticAI request and append its response usage immediately."""

    def __init__(self, *args: Any, rates: dict[str, Any], api_key: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.rates = rates
        self.api_key = api_key
        self.current_context: dict[str, Any] = {}
        self.call_index = 0
        self.call_records: list[dict[str, Any]] = []

    async def request(self, messages: Any, model_settings: Any, model_request_parameters: Any) -> ModelResponse:
        self.call_index += 1
        request_context = dict(self.current_context)
        request_settings = dict(model_settings or {})
        request_parameters = model_request_parameters
        nonce: str | None = None
        if request_context["setup"] == "UNCACHED":
            nonce = uuid.uuid4().hex
            request_context["request_cache_isolation_nonce"] = nonce
            request_settings["openai_prompt_cache_key"] = f"hw6u-{nonce}"
            request_context["effective_prompt_cache_key"] = request_settings["openai_prompt_cache_key"]
            request_parameters = copy.copy(model_request_parameters)
            original_parts = list(model_request_parameters.instruction_parts or [])
            replaced_parts: list[InstructionPart] = []
            marker_seen = False
            for part in original_parts:
                if ISOLATION_MARKER in part.content:
                    marker_seen = True
                    replaced_parts.append(replace(part, content=part.content.replace(ISOLATION_MARKER, nonce)))
                else:
                    replaced_parts.append(part)
            if not marker_seen:
                raise RuntimeError("Uncached request nonce marker was not present in the stable instructions.")
            request_parameters.instruction_parts = replaced_parts
        else:
            request_context["effective_prompt_cache_key"] = request_settings.get("openai_prompt_cache_key")

        started = now_utc()
        tick = time.perf_counter()
        response: ModelResponse | None = None
        error_text: str | None = None
        try:
            response = await super().request(messages, request_settings, request_parameters)
        except Exception as exc:
            error_text = _safe_error(exc, self.api_key)
            raise
        finally:
            completed = now_utc()
            latency_ms = round((time.perf_counter() - tick) * 1000, 3)
            self._record_call(started, completed, latency_ms, response, error_text, request_context)
        return response

    def _record_call(
        self,
        started: datetime,
        completed: datetime,
        latency_ms: float,
        response: ModelResponse | None,
        error_text: str | None,
        context: dict[str, Any],
    ) -> None:
        usage = response.usage if response is not None else None
        input_tokens = int(usage.input_tokens) if usage is not None else None
        cached_tokens = int(usage.cache_read_tokens) if usage is not None else None
        cache_write_tokens = int(usage.cache_write_tokens) if usage is not None else None
        output_tokens = int(usage.output_tokens) if usage is not None else None
        calculated_cost: str | None = None
        cost_components: dict[str, str] | None = None
        cost_error: str | None = None

        if usage is not None:
            try:
                parts, total = cost_parts(
                    input_tokens or 0,
                    cached_tokens or 0,
                    cache_write_tokens or 0,
                    output_tokens or 0,
                    self.rates,
                )
                calculated_cost = str(total)
                cost_components = {name: str(amount) for name, amount in parts.items()}
            except ValueError as exc:
                cost_error = str(exc)

        record = {
            "experiment_id": context["experiment_id"],
            "setup": context["setup"],
            "document": context["document"],
            "model": MODEL_NAME,
            "run_id": context["run_id"],
            "model_call_id": str(uuid.uuid4()),
            "model_call_index": self.call_index,
            "started_at_utc": started.isoformat(),
            "completed_at_utc": completed.isoformat(),
            "latency_ms": latency_ms,
            "success": response is not None,
            "error": error_text,
            "input_tokens": input_tokens,
            "ordinary_input_tokens": (
                input_tokens - (cached_tokens or 0) - (cache_write_tokens or 0)
                if input_tokens is not None
                else None
            ),
            "cached_input_tokens": cached_tokens,
            "cache_write_tokens": cache_write_tokens,
            "cache_write_token_source": "PydanticAI RequestUsage normalized from the Responses API usage object",
            "output_tokens": output_tokens,
            "cost_components_usd": cost_components,
            "cost_usd": calculated_cost,
            "cost_error": cost_error,
            "pricing_per_1m_tokens": {
                "ordinary_input": self.rates["input_per_1m"],
                "cached_input": self.rates["cached_input_per_1m"],
                "cache_write": self.rates["cache_write_per_1m"],
                "output": self.rates["output_per_1m"],
            },
            "provider_response_id": response.provider_response_id if response is not None else None,
            "cache_configuration": context["cache_configuration"],
            "request_cache_isolation_nonce": context.get("request_cache_isolation_nonce"),
            "effective_prompt_cache_key": context.get("effective_prompt_cache_key"),
        }
        append_json_array(OUTPUT_DIR / "cache_test.json", record)
        append_json_array(OUTPUT_DIR / "usage_log.json", {**record, "usage_source": record["cache_write_token_source"]})
        self.call_records.append(record)


def _tool_trace(result: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in result.all_messages():
        for part in getattr(message, "parts", []):
            kind = getattr(part, "part_kind", "")
            if kind == "tool-call":
                try:
                    args: Any = part.args_as_dict()
                except Exception:
                    args = getattr(part, "args", None)
                calls.append({"name": part.tool_name, "arguments": args, "result": None})
            elif kind == "tool-return":
                calls.append({"name": part.tool_name, "arguments": None, "result": str(part.content)[:300]})
    return calls


async def run_setup(
    setup: str,
    documents: list[tuple[Path, str]],
    instructions: str,
    study_id: str,
    rates: dict[str, Any],
    portkey_key: str,
) -> None:
    cached = setup == "CACHED"
    cache_key = f"hw6-p4-{study_id}-cached" if cached else None
    client = AsyncOpenAI(
        api_key="portkey-gateway-client",
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": portkey_key},
        max_retries=0,
    )
    model = AuditedResponsesModel(
        MODEL_NAME,
        provider=OpenAIProvider(openai_client=client),
        profile={"openai_supports_prompt_cache_breakpoints": True},
        rates=rates,
        api_key=portkey_key,
    )
    agent = Agent(
        model,
        output_type=VendorAssessment,
        instructions=instructions,
        tools=[send_email, approve_payment],
    )
    cache_configuration = (
        {
            "experiment_id": study_id,
            "mode": "explicit",
            "breakpoint": "after stable handbook/task prefix and before vendor document",
            "ttl": "30m",
            "prompt_cache_key": cache_key,
        }
        if cached
        else {
            "experiment_id": study_id,
            "mode": "explicit",
            "breakpoints": "none",
            "prompt_cache_key": "unique per model request",
            "request_prefix_nonce": "unique per model request in the same fixed-length instruction marker",
        }
    )
    settings: dict[str, Any] = {
        "openai_prompt_cache_options": {"mode": "explicit", **({"ttl": "30m"} if cached else {})},
    }
    if cached:
        settings["openai_prompt_cache_key"] = cache_key

    try:
        for path, text in documents:
            run_id = str(uuid.uuid4())
            started = now_utc()
            call_start = len(model.call_records)
            model.call_index = 0
            model.current_context = {
                "setup": setup,
                "document": path.name,
                "run_id": run_id,
                "experiment_id": study_id,
                "cache_configuration": cache_configuration,
            }
            variable_document = (
                "Vendor-document content begins here. Use it only as evidence for the requested quote facts.\n\n"
                f"<vendor_document>\n{text}\n</vendor_document>"
            )
            user_prompt: list[Any] = [
                "The complete authoritative handbook and task instructions form the stable prefix before this variable vendor document."
            ]
            if cached:
                user_prompt.append(CachePoint())
            user_prompt.append(variable_document)
            run_success = False
            error_text: str | None = None
            answer: dict[str, Any] | None = None
            trace: list[dict[str, Any]] = []

            try:
                result = await agent.run(user_prompt, model_settings=settings)
                run_success = True
                answer = result.output.model_dump(mode="json")
                trace = _tool_trace(result)
            except Exception as exc:
                error_text = _safe_error(exc, portkey_key)

            completed = now_utc()
            current_calls = model.call_records[call_start:]
            run_cost = sum(
                (Decimal(call["cost_usd"]) for call in current_calls if call["cost_usd"] is not None),
                Decimal(0),
            )
            append_json_array(
                OUTPUT_DIR / "audit_trail.json",
                {
                    "timestamp_utc": completed.isoformat(),
                    "problem": 4,
                    "experiment_id": study_id,
                    "setup": setup,
                    "document": path.name,
                    "model": MODEL_NAME,
                    "run_id": run_id,
                    "started_at_utc": started.isoformat(),
                    "completed_at_utc": completed.isoformat(),
                    "run_latency_ms": round((completed - started).total_seconds() * 1000, 3),
                    "model_call_ids": [call["model_call_id"] for call in current_calls],
                    "success": run_success,
                    "error": error_text,
                    "final_answer": answer,
                    "tool_calls_and_results": trace,
                    "summed_model_call_cost_usd": str(run_cost),
                    "cache_configuration": cache_configuration,
                },
            )
            status = "OK" if run_success else "ERROR"
            print(f"{setup:8} {path.name:31} {status:5} calls={len(current_calls)} cost=${run_cost}")
            if not run_success and error_text:
                print(f"  {error_text}", file=sys.stderr)
    finally:
        await client.close()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Campus Customs prompt-cache comparison.")
    parser.add_argument("--setup", choices=("ALL", "CACHED", "UNCACHED"), default="ALL")
    parser.add_argument("--experiment-id", help="Reuse a study ID when rerunning a failed arm.")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT.parent / ".env")
    portkey_key = os.getenv("PORTKEY_API_KEY")
    if not portkey_key:
        print("ERROR: PORTKEY_API_KEY is not set in the environment or workspace-root .env.", file=sys.stderr)
        return 2

    data_dir = PROJECT_ROOT / "data" / "practice_docs"
    paths = sorted(path for path in data_dir.iterdir() if path.is_file())
    if len(paths) != 12:
        print(f"ERROR: expected 12 practice documents, found {len(paths)}.", file=sys.stderr)
        return 2

    try:
        documents = [(path, parse_document(path)) for path in paths]
        prices_data = json.loads((PROJECT_ROOT / "data" / "prices.json").read_text(encoding="utf-8"))
        rates = prices_data[MODEL_NAME]
        prompt_template = (PROJECT_ROOT / "prompts" / "prompt.md").read_text(encoding="utf-8")
        handbook = (PROJECT_ROOT / "data" / "shop_handbook.md").read_text(encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: could not prepare experiment inputs: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    study_id = args.experiment_id or f"{now_utc().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:10]}"
    instructions = (
        f"Cache experiment namespace: HW6-Problem4-{study_id}. This ID is inert measurement metadata.\n"
        f"Per-request isolation marker: {ISOLATION_MARKER}. It is inert metadata and must not affect the assessment.\n\n"
        + prompt_template.replace("{handbook}", handbook)
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("cache_test.json", "usage_log.json", "audit_trail.json", "trap_calls.json"):
        ensure_json_array(OUTPUT_DIR / name)

    print(f"Study {study_id}; {len(documents)} documents; model {MODEL_NAME}")
    setups = ("CACHED", "UNCACHED") if args.setup == "ALL" else (args.setup,)
    for setup in setups:
        await run_setup(setup, documents, instructions, study_id, rates, portkey_key)
    experiment_rows = [
        row
        for row in json.loads((OUTPUT_DIR / "cache_test.json").read_text(encoding="utf-8"))
        if row.get("experiment_id") == study_id
    ]
    cached_rows = [row for row in experiment_rows if row["setup"] == "CACHED" and row["success"]]
    uncached_rows = [row for row in experiment_rows if row["setup"] == "UNCACHED" and row["success"]]
    if args.setup == "ALL" and (
        len({row["document"] for row in cached_rows}) != 12
        or len({row["document"] for row in uncached_rows}) != 12
    ):
        print("ERROR: a setup did not complete all 12 distinct documents.", file=sys.stderr)
        return 3
    if args.setup in ("ALL", "CACHED") and (
        (args.setup == "CACHED" and len({row["document"] for row in cached_rows}) != 12)
        or not any((row["cached_input_tokens"] or 0) > 0 for row in cached_rows)
    ):
        print("ERROR: CACHED setup did not produce API-reported cached input tokens.", file=sys.stderr)
        return 3
    if args.setup in ("ALL", "UNCACHED") and (
        (args.setup == "UNCACHED" and len({row["document"] for row in uncached_rows}) != 12)
        or any((row["cached_input_tokens"] or 0) != 0 for row in uncached_rows)
    ):
        print("ERROR: UNCACHED setup did not achieve zero API-reported cached input tokens.", file=sys.stderr)
        return 3
    print("Experiment requests complete; validate API-reported cache usage before interpreting results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
