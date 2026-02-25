"""Tests for CyberArk-specific query expansion."""

import pytest

from cyberark_rag.query_expansion import QueryExpander


@pytest.fixture(scope="module")
def expander() -> QueryExpander:
    """Shared query expander loaded from the project's YAML."""
    return QueryExpander()


class TestExpansionLoading:
    """Verify expansion data loads from YAML."""

    def test_expansions_loaded(self, expander):
        assert expander.has_expansions()

    def test_stats_show_groups(self, expander):
        stats = expander.get_expansion_stats()
        assert stats["expansion_groups"] > 0
        assert stats["total_terms"] > 0
        assert stats["loaded"] is True


class TestExpansionPreservesOriginal:
    """Original query must always be first in the expansion list."""

    def test_original_query_is_first(self, expander):
        queries = expander.expand_query("conjur", max_expansions=5)
        assert queries[0] == "conjur"

    def test_no_expansion_returns_original(self, expander):
        queries = expander.expand_query("quantumxyz")
        assert queries == ["quantumxyz"]


class TestCyberArkExpansions:
    """CyberArk domain-specific term expansions."""

    def test_conjur_expands(self, expander):
        related = expander.get_related_terms("conjur")
        assert "conjur" in related
        assert len(related) > 1

    def test_kubernetes_expands(self, expander):
        related = expander.get_related_terms("kubernetes")
        assert "kubernetes" in related

    def test_spire_expands_to_spiffe(self, expander):
        related = expander.get_related_terms("spire")
        lower_related = {t.lower() for t in related}
        # spire and spiffe should be in the same expansion group
        assert "spire" in lower_related
        assert "spiffe" in lower_related

    def test_expansion_limits_count(self, expander):
        queries = expander.expand_query("conjur", max_expansions=3)
        # Original + at most 3 expansions
        assert len(queries) <= 4


class TestRelatedTerms:
    """Test the get_related_terms API."""

    def test_known_term_has_relations(self, expander):
        related = expander.get_related_terms("conjur")
        assert len(related) >= 2

    def test_unknown_term_returns_self(self, expander):
        related = expander.get_related_terms("xyznonexistent")
        assert related == {"xyznonexistent"}
