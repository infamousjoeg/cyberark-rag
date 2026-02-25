"""Tests for the search pipeline: query expansion, intent detection, and hybrid search.

Integration tests for search.py use mocked ChromaDB to avoid requiring a pre-built index.
Unit tests for query expansion and intent detection use the real YAML configs.
"""

import pytest

from cyberark_rag.query_expansion import QueryExpander
from cyberark_rag.query_intent import detect_intent


class TestQueryExpansion:
    """Verify query expansion loads and operates correctly."""

    @pytest.fixture(scope="class")
    def expander(self):
        return QueryExpander()

    def test_expansion_loads(self, expander):
        assert expander.has_expansions()

    def test_conjur_expansion(self, expander):
        queries = expander.expand_query("conjur", max_expansions=5)
        assert len(queries) >= 1
        assert queries[0] == "conjur"

    def test_no_expansion_passthrough(self, expander):
        queries = expander.expand_query("xyznonexistent")
        assert queries == ["xyznonexistent"]

    def test_related_terms(self, expander):
        related = expander.get_related_terms("conjur")
        assert "conjur" in related
        assert len(related) >= 1

    def test_expansion_preserves_original_query(self, expander):
        queries = expander.expand_query("kubernetes auth", max_expansions=5)
        assert queries[0] == "kubernetes auth"


class TestIntentDetection:
    """Verify intent detection returns correct structure."""

    def test_detect_error_intent(self):
        intent = detect_intent("PVWA error 401 unauthorized")
        assert intent.intent_type == "troubleshooting"
        assert intent.confidence > 0

    def test_detect_howto_intent(self):
        intent = detect_intent("how to configure conjur kubernetes")
        assert intent.intent_type == "how-to"

    def test_detect_returns_boost_factors(self):
        intent = detect_intent("install credential provider")
        assert isinstance(intent.boost_factors, dict)
        assert len(intent.boost_factors) > 0

    def test_general_intent_for_bare_query(self):
        intent = detect_intent("conjur authentication")
        assert intent.intent_type == "general"
