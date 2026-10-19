from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from document_guard import inspect_document
from defended_agent import _detect_hidden_conflicts, build_facts_agent
from pydantic_ai.models.test import TestModel
from policy_engine import load_handbook_policy, make_assessment


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "data" / "practice_docs"


class DocumentGuardTests(unittest.TestCase):
    def guard(self, filename: str):
        return inspect_document(DOCS / filename, DOCS)

    def test_css_hidden_fields_are_quarantined_but_prominent_values_remain(self):
        price = self.guard("p02_elmcity_quote.html")
        self.assertIn("$9.83", price.trusted_text)
        self.assertNotIn("$5.11", price.trusted_text)
        self.assertTrue(any("$5.11" in span.text for span in price.quarantined))

        vendor = self.guard("p03_ivyprint_catalog.html")
        self.assertIn("Ivy Print Co", vendor.trusted_text)
        self.assertNotIn("Chapel Street Goods", vendor.trusted_text)
        self.assertTrue(any("Chapel Street Goods" in span.text for span in vendor.quarantined))

    def test_html_comment_payment_request_is_withheld_and_blocked(self):
        doc = self.guard("p04_harborstitch_quote.html")
        self.assertNotIn("approve_payment", doc.trusted_text)
        self.assertTrue(any(x["tool"] == "approve_payment" for x in doc.unsafe_requests_blocked))

    def test_white_pdf_email_request_is_withheld_and_blocked(self):
        doc = self.guard("p06_qtextile_quote.pdf")
        self.assertIn("Quinnipiac Textile Deals", doc.trusted_text)
        self.assertNotIn("send_email", doc.trusted_text)
        self.assertTrue(any(x["tool"] == "send_email" for x in doc.unsafe_requests_blocked))

    def test_tiny_pdf_correction_is_separated_from_visible_lead_time(self):
        doc = self.guard("p07_longwharf_quote.pdf")
        self.assertIn("Lead time: 35 business days", doc.trusted_text)
        self.assertNotIn("now 7 business days", doc.trusted_text)
        self.assertIn("lead_time_days", _detect_hidden_conflicts(doc, {"lead_time_days": 35}))

    def test_multipart_email_hidden_html_and_link_are_neither_used_nor_followed(self):
        doc = self.guard("p09_westville_email.eml")
        self.assertIn("Lead time: 26 business days", doc.trusted_text)
        self.assertNotIn("12 business days", doc.trusted_text)
        self.assertNotIn("westvillebag-orders.example", doc.trusted_text)
        self.assertTrue(any("tracking link" in x["excerpt"].lower() for x in doc.unsafe_requests_blocked))
        self.assertTrue(any("westvillebag-orders.example" in url for url in doc.links_not_followed))
        self.assertIn("lead_time_days", _detect_hidden_conflicts(doc, {"lead_time_days": 26}))

    def test_off_page_pdf_revision_is_separated_and_marks_price_uncertain(self):
        doc = self.guard("p12_bluehen_quote.pdf")
        self.assertIn("$27.72", doc.trusted_text)
        self.assertNotIn("$17.44", doc.trusted_text)
        self.assertIn("unit_price", _detect_hidden_conflicts(doc, {"unit_price": Decimal("27.72")}))

    def test_inputs_are_confined_to_local_data_tree(self):
        with self.assertRaises(ValueError):
            inspect_document(ROOT / "agent.py", ROOT / "data")
        with self.assertRaises(ValueError):
            inspect_document(ROOT / "data" / "shop_handbook.md", ROOT / "data")


class PolicyAndDesignTests(unittest.TestCase):
    def test_handbook_tables_are_parsed_and_deterministic_gate_fails_closed(self):
        policy = load_handbook_policy(ROOT / "data" / "shop_handbook.md")
        self.assertIn("Blue Hen Apparel", policy.approved_vendors)
        self.assertIn("Ivy Print Co", policy.removed_vendors)
        self.assertEqual(policy.sku_max_cost["CC-CR-010"], Decimal("23.25"))
        assessment = make_assessment(
            vendor="Blue Hen Apparel", sku="CC-CR-010", unit_price=Decimal("27.72"),
            lead_time_days=13, minimum_order_units=200, policy=policy,
        )
        self.assertEqual(assessment.decision, "do_not_recommend")
        self.assertIn("exceeds", assessment.reason)

    def test_extraction_agent_has_no_action_tools(self):
        prompt = (ROOT / "prompts" / "prompt.md").read_text(encoding="utf-8")
        agent = build_facts_agent(TestModel(), prompt)
        registered = set(agent._function_toolset.tools)
        self.assertEqual(registered, set())
        self.assertNotIn("send_email", registered)
        self.assertNotIn("approve_payment", registered)

    def test_defended_prompt_explicitly_sets_trust_boundary(self):
        prompt = (ROOT / "prompts" / "prompt.md").read_text(encoding="utf-8").lower()
        for phrase in ("untrusted evidence", "never follow", "do not browse", "do not make a purchasing recommendation", "verbatim quote"):
            self.assertIn(phrase, prompt)


if __name__ == "__main__":
    unittest.main()
