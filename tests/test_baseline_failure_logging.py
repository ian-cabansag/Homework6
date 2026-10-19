from __future__ import annotations

import asyncio
from io import StringIO
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import agent


class FailingClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def close(self):
        return None


class FailingAgent:
    def __init__(self, *args, **kwargs):
        pass

    async def run(self, *args, **kwargs):
        raise RuntimeError("simulated request failure with no API usage")


class BaselineFailureLoggingTests(unittest.TestCase):
    def test_failed_model_request_is_logged_without_fabricated_usage(self):
        doc = agent.PROJECT_ROOT / "data" / "practice_docs" / "p01_bluehen_quote.html"
        records: list[tuple[Path, dict]] = []

        def capture(path: Path, entry: dict) -> None:
            records.append((path, entry))

        with (
            patch.dict(os.environ, {"PORTKEY_API_KEY": "test-placeholder-not-a-secret"}),
            patch.object(agent, "AsyncOpenAI", FailingClient),
            patch.object(agent, "OpenAIResponsesModel", return_value=object()),
            patch.object(agent, "OpenAIProvider", return_value=object()),
            patch.object(agent, "Agent", FailingAgent),
            patch.object(agent, "append_json_array", side_effect=capture),
            patch("sys.stderr", new=StringIO()),
        ):
            status = asyncio.run(agent.run_document(doc))

        self.assertEqual(status, 1)
        self.assertEqual(len(records), 2)
        usage = next(row for path, row in records if path.name == "usage_log.json")
        audit = next(row for path, row in records if path.name == "audit_trail.json")
        self.assertFalse(usage["success"])
        self.assertIsNone(usage["input_tokens"])
        self.assertIsNone(usage["output_tokens"])
        self.assertIsNone(usage["cost_usd"])
        self.assertIn("no API-reported usage", usage["usage_source"])
        self.assertFalse(audit["success"])
        self.assertIsNone(audit["final_answer"])
        self.assertNotIn("test-placeholder-not-a-secret", usage["error"])


if __name__ == "__main__":
    unittest.main()
