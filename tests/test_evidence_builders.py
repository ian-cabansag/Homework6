from __future__ import annotations

import json
import unittest
from pathlib import Path

import build_attack_report
import build_defense_report


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"


class EvidenceBuilderTests(unittest.TestCase):
    def test_problem5_builder_reconciles_original_baseline_window(self):
        generated = build_attack_report.build_results()
        stored = json.loads((OUTPUT / "attack_results.json").read_text(encoding="utf-8"))
        self.assertEqual(generated, stored)
        self.assertEqual(len(generated["documents"]), 12)

    def test_problem6_builder_scopes_to_practice_documents_only(self):
        generated = build_defense_report.build_results()
        stored = json.loads((OUTPUT / "defense_results.json").read_text(encoding="utf-8"))
        self.assertEqual(generated, stored)
        self.assertEqual(len(generated["documents"]), 12)


if __name__ == "__main__":
    unittest.main()
