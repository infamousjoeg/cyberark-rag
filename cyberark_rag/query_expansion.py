"""
Query Expansion Module for CyberArk RAG

Handles semantic query expansion to improve search accuracy by including
related terms, aliases, and synonyms for CyberArk products and concepts.
"""

import os
import re
from typing import List, Set, Dict
from pathlib import Path

import yaml

from cyberark_rag.config import Settings


class QueryExpander:
    """
    Expands search queries with related terms and aliases.
    """

    def __init__(self, expansions_path: str = None):
        """
        Initialize the query expander.

        Args:
            expansions_path: Path to YAML file with query expansions
        """
        self.expansions_path = expansions_path or str(Settings.QUERY_EXPANSIONS_PATH)
        self.expansions = {}
        self.term_to_group = {}  # Maps any term to its expansion group
        self._load_expansions()

    def _load_expansions(self):
        """Load query expansions from YAML file."""
        if not os.path.exists(self.expansions_path):
            print(f"Warning: Query expansions file not found at {self.expansions_path}")
            return

        try:
            with open(self.expansions_path, 'r') as f:
                raw_expansions = yaml.safe_load(f)

            if not raw_expansions:
                print("Warning: Query expansions file is empty")
                return

            # Build bidirectional mapping
            # Each term (primary or alias) maps to the full group of related terms
            for primary_term, aliases in raw_expansions.items():
                if not isinstance(aliases, list):
                    continue

                # Create full group: primary + all aliases
                full_group = {primary_term.lower()}
                full_group.update(alias.lower() for alias in aliases)

                # Store expansion group
                self.expansions[primary_term.lower()] = full_group

                # Map every term in group back to the full group
                for term in full_group:
                    self.term_to_group[term] = full_group

            print(f"Loaded {len(self.expansions)} query expansion groups")

        except Exception as e:
            print(f"Error loading query expansions: {e}")

    def expand_query(self, query: str, max_expansions: int = 5) -> List[str]:
        """
        Expand a query with related terms.

        Args:
            query: Original search query
            max_expansions: Maximum number of expansion terms to add

        Returns:
            List of expanded query terms (original + expansions)
        """
        if not self.term_to_group:
            # No expansions loaded, return original
            return [query]

        # Tokenize query (split on whitespace and common punctuation)
        tokens = re.findall(r'\b[\w-]+\b', query.lower())

        # Find all matching expansion groups
        expanded_terms = set()
        expansions_triggered = []

        for token in tokens:
            # Check for exact match
            if token in self.term_to_group:
                group = self.term_to_group[token]
                expanded_terms.update(group)
                expansions_triggered.append(token)
                continue

            # Check for multi-word phrases
            # Try bigrams and trigrams
            for phrase_length in [3, 2]:
                for i in range(len(tokens) - phrase_length + 1):
                    phrase = ' '.join(tokens[i:i+phrase_length])
                    if phrase in self.term_to_group:
                        group = self.term_to_group[phrase]
                        expanded_terms.update(group)
                        expansions_triggered.append(phrase)
                        break

        # If no expansions found, return original query
        if not expanded_terms:
            return [query]

        # Build list of expansion queries
        # Start with original query
        queries = [query]

        # Add individual expansion terms (up to max_expansions)
        expansion_count = 0
        for term in sorted(expanded_terms):
            # Skip terms already in original query
            if term.lower() in query.lower():
                continue

            queries.append(term)
            expansion_count += 1

            if expansion_count >= max_expansions:
                break

        # Log expansion for debugging
        if len(queries) > 1:
            print(f"Query expansion: '{query}' → {len(queries)} terms")
            print(f"  Triggered by: {expansions_triggered}")
            print(f"  Added terms: {queries[1:]}")

        return queries

    def get_related_terms(self, term: str) -> Set[str]:
        """
        Get all related terms for a given term.

        Args:
            term: Term to find relations for

        Returns:
            Set of related terms (including the term itself)
        """
        term_lower = term.lower()

        if term_lower in self.term_to_group:
            return self.term_to_group[term_lower].copy()

        # No relations found
        return {term_lower}

    def has_expansions(self) -> bool:
        """Check if expansions are loaded."""
        return len(self.term_to_group) > 0

    def get_expansion_stats(self) -> Dict:
        """Get statistics about loaded expansions."""
        return {
            'expansion_groups': len(self.expansions),
            'total_terms': len(self.term_to_group),
            'expansions_path': self.expansions_path,
            'loaded': self.has_expansions()
        }


# Singleton instance for easy access
_expander = None


def get_expander() -> QueryExpander:
    """Get or create the global query expander instance."""
    global _expander
    if _expander is None:
        _expander = QueryExpander()
    return _expander


def expand_query(query: str, max_expansions: int = 5) -> List[str]:
    """
    Convenience function to expand a query.

    Args:
        query: Search query to expand
        max_expansions: Max number of expansion terms

    Returns:
        List of query terms (original + expansions)
    """
    expander = get_expander()
    return expander.expand_query(query, max_expansions)


def get_related_terms(term: str) -> Set[str]:
    """
    Convenience function to get related terms.

    Args:
        term: Term to find relations for

    Returns:
        Set of related terms
    """
    expander = get_expander()
    return expander.get_related_terms(term)


if __name__ == "__main__":
    # Test the query expander
    expander = QueryExpander()

    print("\n" + "="*80)
    print("QUERY EXPANSION TESTER")
    print("="*80)

    # Display stats
    stats = expander.get_expansion_stats()
    print(f"\nLoaded: {stats['expansion_groups']} expansion groups")
    print(f"Total terms: {stats['total_terms']}")

    # Test queries from audit findings
    test_queries = [
        "configure spire kubernetes",
        "setup dual accounts",
        "jwt authentication configuration",
        "getting started with conjur",
        "rotate secrets in privilege cloud",
        "install credential provider",
        "kubernetes secret management",
        "mfa setup",
    ]

    print("\n" + "="*80)
    print("TEST EXPANSIONS")
    print("="*80)

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        expansions = expander.expand_query(query, max_expansions=5)
        print(f"  Original: {expansions[0]}")
        if len(expansions) > 1:
            print(f"  Expanded with: {', '.join(expansions[1:])}")
        else:
            print("  (no expansions)")

    # Test specific term relations
    print("\n" + "="*80)
    print("TERM RELATIONS")
    print("="*80)

    test_terms = ["spire", "dual account", "jwt", "kubernetes"]
    for term in test_terms:
        related = expander.get_related_terms(term)
        print(f"\n'{term}' relates to:")
        for rel_term in sorted(related):
            if rel_term != term.lower():
                print(f"  - {rel_term}")
