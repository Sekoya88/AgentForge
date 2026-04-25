"""Unit tests for domain services — budget, PII masking, cost tracker, agent diff.

All tests are pure-Python: no DB, no HTTP, no external deps.
"""

from __future__ import annotations

import pytest

from app.domain.agent_diff import _sorted_skill_ids, diff_agent_versions
from app.domain.cost_tracker import PRICING_TABLE, calculate_cost
from app.domain.services.budget_service import BudgetService
from app.domain.services.pii_masker import PiiMasker

# ---------------------------------------------------------------------------
# BudgetService
# ---------------------------------------------------------------------------


class TestBudgetService:
    svc = BudgetService()

    # estimate_cost_usd
    def test_none_token_usage_returns_zero(self):
        assert self.svc.estimate_cost_usd(None) == 0.0

    def test_empty_dict_returns_zero(self):
        assert self.svc.estimate_cost_usd({}) == 0.0

    def test_flat_structure(self):
        usage = {"prompt_tokens": 1000, "completion_tokens": 1000}
        cost = self.svc.estimate_cost_usd(usage)
        assert cost == pytest.approx(2000 * 0.002 / 1000, rel=1e-4)

    def test_nested_structure(self):
        usage = {
            "node1": {"prompt_tokens": 500, "completion_tokens": 500},
            "node2": {"prompt_tokens": 200, "completion_tokens": 300},
        }
        cost = self.svc.estimate_cost_usd(usage)
        assert cost == pytest.approx(1500 * 0.002 / 1000, rel=1e-4)

    def test_nested_with_scalar_values(self):
        usage = {"total_tokens": 1000}
        # not flat (no prompt_tokens key), numeric scalar → adds as raw token count
        cost = self.svc.estimate_cost_usd(usage)
        assert cost == pytest.approx(1000 * 0.002 / 1000, rel=1e-4)

    def test_null_token_values_handled(self):
        usage = {"prompt_tokens": None, "completion_tokens": None}
        assert self.svc.estimate_cost_usd(usage) == 0.0

    # check_budget — no limit
    def test_no_limit_always_ok(self):
        class _Agent:
            budget_limit_usd = None
            budget_alert_threshold = 0.8

        result = self.svc.check_budget(_Agent(), 999.0)
        assert result["status"] == "ok"
        assert result["limit"] is None

    # check_budget — with limit
    def test_status_ok_under_threshold(self):
        class _Agent:
            budget_limit_usd = 10.0
            budget_alert_threshold = 0.8

        result = self.svc.check_budget(_Agent(), 5.0)
        assert result["status"] == "ok"

    def test_status_warning_at_threshold(self):
        class _Agent:
            budget_limit_usd = 10.0
            budget_alert_threshold = 0.8

        result = self.svc.check_budget(_Agent(), 8.5)
        assert result["status"] == "warning"

    def test_status_exceeded_at_limit(self):
        class _Agent:
            budget_limit_usd = 10.0
            budget_alert_threshold = 0.8

        result = self.svc.check_budget(_Agent(), 10.0)
        assert result["status"] == "exceeded"

    def test_status_exceeded_over_limit(self):
        class _Agent:
            budget_limit_usd = 10.0
            budget_alert_threshold = 0.8

        result = self.svc.check_budget(_Agent(), 15.0)
        assert result["status"] == "exceeded"

    def test_zero_limit_no_division_by_zero(self):
        class _Agent:
            budget_limit_usd = 0.0
            budget_alert_threshold = 0.8

        result = self.svc.check_budget(_Agent(), 0.0)
        assert result["status"] == "exceeded"  # 0 >= 0

    def test_result_contains_all_keys(self):
        class _Agent:
            budget_limit_usd = 5.0
            budget_alert_threshold = 0.75

        result = self.svc.check_budget(_Agent(), 1.0)
        assert set(result.keys()) == {"status", "spent", "limit", "alert_threshold"}
        assert result["spent"] == 1.0
        assert result["limit"] == 5.0
        assert result["alert_threshold"] == 0.75


# ---------------------------------------------------------------------------
# PiiMasker
# ---------------------------------------------------------------------------


class TestPiiMasker:
    masker = PiiMasker()

    def test_no_pii_unchanged(self):
        text = "Hello, how are you today?"
        masked, hits = self.masker.mask(text)
        assert masked == text
        assert hits == 0

    def test_email_masked(self):
        text = "Contact me at alice@example.com for details."
        masked, hits = self.masker.mask(text)
        assert "[REDACTED:EMAIL]" in masked
        assert "alice@example.com" not in masked
        assert hits == 1

    def test_multiple_emails(self):
        text = "Send to alice@example.com and bob@test.org"
        masked, hits = self.masker.mask(text)
        assert hits == 2
        assert masked.count("[REDACTED:EMAIL]") == 2

    def test_ssn_masked(self):
        text = "My SSN is 123-45-6789."
        masked, hits = self.masker.mask(text)
        assert "[REDACTED:SSN]" in masked
        assert "123-45-6789" not in masked
        assert hits == 1

    def test_phone_masked(self):
        text = "Call me at +1-800-555-1234."
        masked, hits = self.masker.mask(text)
        assert hits >= 1
        assert "800-555-1234" not in masked

    def test_empty_string(self):
        masked, hits = self.masker.mask("")
        assert masked == ""
        assert hits == 0

    def test_mask_messages_deep_copy(self):
        messages = [{"role": "user", "content": "My email is foo@bar.com"}]
        result = self.masker.mask_messages(messages)
        # Original must be unchanged
        assert messages[0]["content"] == "My email is foo@bar.com"
        assert "[REDACTED:EMAIL]" in result[0]["content"]

    def test_mask_messages_non_string_content_untouched(self):
        messages = [{"role": "user", "content": None}]
        result = self.masker.mask_messages(messages)
        assert result[0]["content"] is None

    def test_mask_messages_preserves_role(self):
        messages = [{"role": "assistant", "content": "No PII here."}]
        result = self.masker.mask_messages(messages)
        assert result[0]["role"] == "assistant"

    def test_mask_messages_empty_list(self):
        assert self.masker.mask_messages([]) == []

    def test_credit_card_masked(self):
        text = "Card: 4111111111111111"
        masked, hits = self.masker.mask(text)
        assert hits >= 1
        assert "4111111111111111" not in masked


# ---------------------------------------------------------------------------
# cost_tracker.calculate_cost
# ---------------------------------------------------------------------------


class TestCalculateCost:
    def test_known_model(self):
        cost = calculate_cost("gpt-4o", 1000, 1000)
        expected = (1000 / 1000) * PRICING_TABLE["gpt-4o"]["prompt_tokens"] + (
            1000 / 1000
        ) * PRICING_TABLE["gpt-4o"]["completion_tokens"]
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_unknown_model_uses_default(self):
        cost = calculate_cost("unknown-model-xyz", 1000, 1000)
        default = PRICING_TABLE["default"]
        expected = (1000 / 1000) * default["prompt_tokens"] + (1000 / 1000) * default[
            "completion_tokens"
        ]
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_none_model_uses_default(self):
        cost_none = calculate_cost(None, 500, 500)
        cost_default = calculate_cost("default", 500, 500)
        assert cost_none == pytest.approx(cost_default, rel=1e-6)

    def test_zero_tokens(self):
        assert calculate_cost("gpt-4o", 0, 0) == 0.0

    def test_gpt4o_partial_match(self):
        cost = calculate_cost("gpt-4o-turbo", 1000, 0)
        assert cost == pytest.approx(PRICING_TABLE["gpt-4o"]["prompt_tokens"], rel=1e-6)

    def test_gemini_partial_match(self):
        cost = calculate_cost("gemini-1.5-pro-002", 1000, 0)
        assert cost == pytest.approx(PRICING_TABLE["gemini-1.5-pro"]["prompt_tokens"], rel=1e-6)


# ---------------------------------------------------------------------------
# agent_diff
# ---------------------------------------------------------------------------


class TestSortedSkillIds:
    def test_string_list(self):
        assert _sorted_skill_ids(["b", "a", "c"]) == ["a", "b", "c"]

    def test_dict_list(self):
        skills = [{"name": "search"}, {"name": "calculator"}]
        assert _sorted_skill_ids(skills) == ["calculator", "search"]

    def test_empty(self):
        assert _sorted_skill_ids([]) == []

    def test_deduplicates(self):
        assert _sorted_skill_ids(["x", "x"]) == ["x"]

    def test_mixed_strings_and_dicts(self):
        result = _sorted_skill_ids(["z", {"name": "a"}])
        assert "a" in result and "z" in result


class TestDiffAgentVersions:
    BASE = {
        "graph_definition": {
            "entry_point": "n1",
            "nodes": [{"id": "n1", "type": "llm"}, {"id": "n2", "type": "tool"}],
            "edges": [{"from": "n1", "to": "n2"}],
        },
        "model_config": {"provider": "openai", "model": "gpt-4o"},
        "skills": ["search"],
        "execution_policy": {},
    }

    def test_identical_versions(self):
        result = diff_agent_versions(self.BASE, self.BASE)
        assert result["graph"]["nodes_added"] == []
        assert result["graph"]["nodes_removed"] == []
        assert result["graph"]["nodes_changed"] == []
        assert result["graph"]["entry_point_changed"] is False
        assert result["model_config_changed"] is False

    def test_node_added(self):
        right = {
            **self.BASE,
            "graph_definition": {
                **self.BASE["graph_definition"],
                "nodes": [
                    {"id": "n1", "type": "llm"},
                    {"id": "n2", "type": "tool"},
                    {"id": "n3", "type": "router"},
                ],
            },
        }
        result = diff_agent_versions(self.BASE, right)
        assert "n3" in result["graph"]["nodes_added"]

    def test_node_removed(self):
        right = {
            **self.BASE,
            "graph_definition": {
                **self.BASE["graph_definition"],
                "nodes": [{"id": "n1", "type": "llm"}],
            },
        }
        result = diff_agent_versions(self.BASE, right)
        assert "n2" in result["graph"]["nodes_removed"]

    def test_node_changed(self):
        right = {
            **self.BASE,
            "graph_definition": {
                **self.BASE["graph_definition"],
                "nodes": [
                    {"id": "n1", "type": "llm", "system_prompt": "updated"},
                    {"id": "n2", "type": "tool"},
                ],
            },
        }
        result = diff_agent_versions(self.BASE, right)
        assert "n1" in result["graph"]["nodes_changed"]

    def test_model_config_changed(self):
        right = {**self.BASE, "model_config": {"provider": "anthropic", "model": "claude-3-opus"}}
        result = diff_agent_versions(self.BASE, right)
        assert result["model_config_changed"] is True

    def test_skills_added_and_removed(self):
        right = {**self.BASE, "skills": ["calculator"]}
        result = diff_agent_versions(self.BASE, right)
        assert "calculator" in result["skills"]["added"]
        assert "search" in result["skills"]["removed"]

    def test_entry_point_changed(self):
        right = {
            **self.BASE,
            "graph_definition": {**self.BASE["graph_definition"], "entry_point": "n2"},
        }
        result = diff_agent_versions(self.BASE, right)
        assert result["graph"]["entry_point_changed"] is True

    def test_custom_labels(self):
        result = diff_agent_versions(self.BASE, self.BASE, left_label="v1", right_label="v2")
        assert "v1" in result["labels"].values()
        assert "v2" in result["labels"].values()

    def test_empty_dicts(self):
        result = diff_agent_versions({}, {})
        assert result["graph"]["nodes_added"] == []
        assert result["model_config_changed"] is False
