"""
Query Intent Detection for CyberArk RAG

Detects user intent from queries to enable content-type aware ranking.
"""

import re
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class QueryIntent:
    """Represents detected query intent."""
    intent_type: str  # 'how-to', 'explanation', 'reference', 'troubleshooting', 'general'
    confidence: float  # 0-1
    boost_factors: Dict[str, float]  # content_type -> boost multiplier


class QueryIntentDetector:
    """
    Detects user intent from queries to enable better content ranking.
    """

    def __init__(self):
        """Initialize detector with intent patterns and boost factors."""

        # How-to / Procedural queries
        self.howto_patterns = [
            r'\b(how do i|how to|how can i|how do you)\b',
            r'\b(setup|set up|configure|install|deploy|create|enable)\b',
            r'\b(implement|initialize|start|begin)\b',
            r'\b(step by step|guide|tutorial|walkthrough)\b',
        ]

        # Explanation / Conceptual queries
        self.explanation_patterns = [
            r'\b(what is|what are|what does|explain|describe)\b',
            r'\b(overview|introduction|understanding|concept)\b',
            r'\b(architecture|design|theory|why)\b',
            r'\b(difference between|compare|vs)\b',
        ]

        # Reference / Lookup queries
        self.reference_patterns = [
            r'\b(command|parameter|option|flag|argument|syntax)\b',
            r'\b(api|endpoint|method|function)\b',
            r'\b(list of|show me|display|available)\b',
            r'\b(reference|documentation|spec|specification)\b',
        ]

        # Troubleshooting queries
        self.troubleshooting_patterns = [
            r'\b(error|failed|not working|broken|issue|problem)\b',
            r'\b(debug|troubleshoot|fix|solve|resolve)\b',
            r'\b(why.*not|why.*fail|can\'t|cannot|unable)\b',
            r'\b(workaround|alternative|instead)\b',
        ]

        # Default boost factors for each intent type
        self.boost_configs = {
            'how-to': {
                'procedural': 2.0,
                'code-example': 1.5,
                'reference': 1.0,
                'conceptual': 0.8,
                'general': 1.0
            },
            'explanation': {
                'conceptual': 2.0,
                'reference': 1.2,
                'procedural': 0.9,
                'code-example': 0.8,
                'general': 1.0
            },
            'reference': {
                'reference': 2.0,
                'code-example': 1.5,
                'procedural': 1.0,
                'conceptual': 0.8,
                'general': 1.0
            },
            'troubleshooting': {
                'code-example': 2.0,
                'procedural': 1.5,
                'reference': 1.2,
                'conceptual': 0.8,
                'general': 1.0
            },
            'general': {
                'procedural': 1.0,
                'conceptual': 1.0,
                'reference': 1.0,
                'code-example': 1.0,
                'general': 1.0
            }
        }

    def detect_intent(self, query: str) -> QueryIntent:
        """
        Detect query intent and return boost factors.

        Args:
            query: User query

        Returns:
            QueryIntent with detected type, confidence, and boost factors
        """
        query_lower = query.lower()

        # Calculate scores for each intent
        scores = {
            'how-to': self._calculate_score(query_lower, self.howto_patterns),
            'explanation': self._calculate_score(query_lower, self.explanation_patterns),
            'reference': self._calculate_score(query_lower, self.reference_patterns),
            'troubleshooting': self._calculate_score(query_lower, self.troubleshooting_patterns)
        }

        # Get intent with highest score
        if max(scores.values()) == 0:
            # No clear intent
            return QueryIntent(
                intent_type='general',
                confidence=0.5,
                boost_factors=self.boost_configs['general']
            )

        # Find highest scoring intent
        intent_type = max(scores.items(), key=lambda x: x[1])[0]
        max_score = scores[intent_type]

        # Calculate confidence (normalize by max possible score ~5)
        confidence = min(max_score / 5.0, 1.0)

        return QueryIntent(
            intent_type=intent_type,
            confidence=confidence,
            boost_factors=self.boost_configs[intent_type]
        )

    def _calculate_score(self, query: str, patterns: list) -> int:
        """Calculate match score for patterns."""
        score = 0
        for pattern in patterns:
            if re.search(pattern, query, re.IGNORECASE):
                score += 1
        return score

    def get_boost_factor(self, query: str, content_type: str) -> float:
        """
        Get boost factor for a specific content type given a query.

        Args:
            query: User query
            content_type: Content type to get boost for

        Returns:
            Boost multiplier (1.0 = no boost)
        """
        intent = self.detect_intent(query)
        return intent.boost_factors.get(content_type, 1.0)


# Singleton instance
_detector = None


def get_detector() -> QueryIntentDetector:
    """Get or create the global intent detector instance."""
    global _detector
    if _detector is None:
        _detector = QueryIntentDetector()
    return _detector


def detect_intent(query: str) -> QueryIntent:
    """
    Convenience function to detect query intent.

    Args:
        query: User query

    Returns:
        QueryIntent with type, confidence, and boost factors
    """
    detector = get_detector()
    return detector.detect_intent(query)


if __name__ == "__main__":
    # Test the intent detector
    detector = QueryIntentDetector()

    print("="*80)
    print("QUERY INTENT DETECTOR TESTER")
    print("="*80)

    # Test queries
    test_queries = [
        # How-to queries
        "how to setup dual accounts",
        "configure spire kubernetes",
        "install conjur on docker",
        "create a new policy in conjur",

        # Explanation queries
        "what is dual account",
        "explain jwt authentication",
        "overview of privilege cloud architecture",
        "difference between conjur and dap",

        # Reference queries
        "conjur api authentication parameters",
        "list of kubectl commands",
        "psm configuration options",
        "available authentication methods",

        # Troubleshooting queries
        "jwt authentication not working",
        "error connecting to vault",
        "why is rotation failing",
        "debug conjur policy error",

        # General queries
        "dual accounts",
        "kubernetes secrets",
        "privilege cloud",
    ]

    print("\nTest Queries:")
    print("-"*80)

    for query in test_queries:
        intent = detector.detect_intent(query)

        print(f"\nQuery: '{query}'")
        print(f"  Intent: {intent.intent_type} (confidence: {intent.confidence:.2f})")

        # Show top boost factors
        sorted_boosts = sorted(
            intent.boost_factors.items(),
            key=lambda x: x[1],
            reverse=True
        )

        print("  Content-type boosts:")
        for content_type, boost in sorted_boosts[:3]:
            if boost != 1.0:
                symbol = "↑" if boost > 1.0 else "↓"
                print(f"    {symbol} {content_type}: {boost}x")

    # Test specific scenarios
    print("\n" + "="*80)
    print("SCENARIO TESTING")
    print("="*80)

    scenarios = [
        {
            'query': 'setup dual accounts',
            'expected_intent': 'how-to',
            'expected_boost': 'procedural'
        },
        {
            'query': 'what is dual account',
            'expected_intent': 'explanation',
            'expected_boost': 'conceptual'
        },
        {
            'query': 'dual account api parameters',
            'expected_intent': 'reference',
            'expected_boost': 'reference'
        },
        {
            'query': 'dual account configuration error',
            'expected_intent': 'troubleshooting',
            'expected_boost': 'code-example'
        }
    ]

    print("\nValidation Tests:")
    print("-"*80)

    for scenario in scenarios:
        intent = detector.detect_intent(scenario['query'])

        # Find highest boost
        max_boost_type = max(intent.boost_factors.items(), key=lambda x: x[1])[0]

        intent_match = intent.intent_type == scenario['expected_intent']
        boost_match = max_boost_type == scenario['expected_boost']

        status_intent = "✓" if intent_match else "✗"
        status_boost = "✓" if boost_match else "✗"

        print(f"\nQuery: '{scenario['query']}'")
        print(f"  {status_intent} Intent: {intent.intent_type} (expected: {scenario['expected_intent']})")
        print(f"  {status_boost} Top boost: {max_boost_type} (expected: {scenario['expected_boost']})")
