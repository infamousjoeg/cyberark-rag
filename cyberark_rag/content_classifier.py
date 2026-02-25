"""
Content-Type Classifier for CyberArk Documentation

Classifies documentation chunks into content types to enable better ranking
for different query intents.
"""

import re
from typing import List, Set, Dict


class ContentClassifier:
    """
    Classifies documentation content into types: procedural, conceptual, reference, code-example.
    """

    def __init__(self):
        """Initialize the classifier with pattern definitions."""

        # Procedural content patterns
        self.procedural_patterns = [
            # Action verbs
            r'\b(configure|configuring|install|installing|setup|set up|setting up)\b',
            r'\b(create|creating|deploy|deploying|enable|enabling)\b',
            r'\b(implement|implementing|initialize|initializing)\b',

            # Step-by-step indicators
            r'\bstep\s+\d+',
            r'\b(first|second|third|next|then|finally)\b.*\b(configure|install|create|deploy)\b',

            # Procedural headers/sections
            r'\b(how to|how-to|procedure|procedures|instructions)\b',
            r'\b(getting started|quick start|quickstart|tutorial)\b',

            # Imperative instructions
            r'^(run|execute|enter|type|click|select|choose)',
            r'\bmust\s+(configure|install|create|set|enable)',
        ]

        # Conceptual content patterns
        self.conceptual_patterns = [
            # Overview/explanation
            r'\b(overview|introduction|about|understanding)\b',
            r'\b(architecture|concept|concepts|theory|principles)\b',
            r'\b(what is|what are|describes|description)\b',

            # Explanatory language
            r'\b(explains|explains how|provides|allows you to)\b',
            r'\bthis (section|chapter|document|page) (describes|explains|introduces)\b',

            # Glossary/definitions
            r'\b(glossary|definition|definitions|terminology)\b',
        ]

        # Reference content patterns
        self.reference_patterns = [
            # API/Command reference
            r'\b(api reference|command reference|cli reference|syntax)\b',
            r'\b(parameters?|options?|arguments?|flags?)\b.*\b(table|list)\b',
            r'\b(return values?|response|request|endpoint)\b',

            # Structured reference
            r'\b(specification|specifications|schema|format)\b',
            r'\b(property|properties|attribute|attributes|field|fields)\b',

            # Tables and lists
            r'\|\s*parameter\s*\|',  # Markdown table with "parameter" header
            r'\|\s*option\s*\|',
        ]

        # Code example patterns
        self.code_patterns = [
            # Code blocks
            r'```',  # Markdown code fence
            r'^\s{4,}\w+',  # Indented code block

            # Command prompts
            r'^\s*[$#>]\s+\w+',  # Shell prompt
            r'^\s*C:\\>',  # Windows prompt

            # File paths and examples
            r'\b(example|sample|snippet)\b.*\b(code|configuration|config|yaml|json)\b',
            r'/etc/|/var/|/opt/|C:\\Program Files',

            # Code-like content
            r'\bcurl\s+',
            r'\b(import|from|def|class|function|var|const|let)\b',  # Programming keywords
        ]

        # URL patterns for classification
        self.url_procedural_patterns = [
            r'/install|/setup|/configure|/deploy|/tutorial|/guide|/how-to|/getting-started',
        ]

        self.url_conceptual_patterns = [
            r'/overview|/introduction|/about|/architecture|/concept',
        ]

        self.url_reference_patterns = [
            r'/reference|/api|/cli|/command|/syntax|/parameters',
        ]

    def classify_content(
        self,
        url: str,
        title: str,
        content: str
    ) -> List[str]:
        """
        Classify content into one or more types.

        Args:
            url: Document URL
            title: Document title
            content: Document content

        Returns:
            List of content types (can have multiple)
        """
        text = f"{url} {title} {content}".lower()
        types = []

        # Calculate scores for each type
        procedural_score = self._calculate_score(text, self.procedural_patterns)
        conceptual_score = self._calculate_score(text, self.conceptual_patterns)
        reference_score = self._calculate_score(text, self.reference_patterns)
        code_score = self._calculate_score(text, self.code_patterns)

        # Check URL patterns
        url_lower = url.lower()
        if any(re.search(pattern, url_lower) for pattern in self.url_procedural_patterns):
            procedural_score += 2

        if any(re.search(pattern, url_lower) for pattern in self.url_conceptual_patterns):
            conceptual_score += 2

        if any(re.search(pattern, url_lower) for pattern in self.url_reference_patterns):
            reference_score += 2

        # Determine primary type (highest score)
        scores = {
            'procedural': procedural_score,
            'conceptual': conceptual_score,
            'reference': reference_score,
            'code-example': code_score
        }

        # Get types with significant scores (threshold: 2)
        significant_types = [
            content_type for content_type, score in scores.items()
            if score >= 2
        ]

        # If no significant scores, use highest score
        if not significant_types:
            max_score = max(scores.values())
            if max_score > 0:
                significant_types = [
                    content_type for content_type, score in scores.items()
                    if score == max_score
                ]

        # Default to general if still nothing
        if not significant_types:
            significant_types = ['general']

        return significant_types

    def classify_content_primary(
        self,
        url: str,
        title: str,
        content: str
    ) -> str:
        """
        Get primary content type (single classification).

        Args:
            url: Document URL
            title: Document title
            content: Document content

        Returns:
            Primary content type
        """
        types = self.classify_content(url, title, content)
        return types[0] if types else 'general'

    def _calculate_score(self, text: str, patterns: List[str]) -> int:
        """
        Calculate match score for a set of patterns.

        Args:
            text: Text to analyze
            patterns: List of regex patterns

        Returns:
            Match score
        """
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            score += len(matches)

        return score

    def get_classification_confidence(
        self,
        url: str,
        title: str,
        content: str
    ) -> Dict[str, float]:
        """
        Get confidence scores for each content type.

        Args:
            url: Document URL
            title: Document title
            content: Document content

        Returns:
            Dictionary of content_type -> confidence (0-1)
        """
        text = f"{url} {title} {content}".lower()

        # Calculate raw scores
        scores = {
            'procedural': self._calculate_score(text, self.procedural_patterns),
            'conceptual': self._calculate_score(text, self.conceptual_patterns),
            'reference': self._calculate_score(text, self.reference_patterns),
            'code-example': self._calculate_score(text, self.code_patterns)
        }

        # Add URL bonuses
        url_lower = url.lower()
        if any(re.search(pattern, url_lower) for pattern in self.url_procedural_patterns):
            scores['procedural'] += 2
        if any(re.search(pattern, url_lower) for pattern in self.url_conceptual_patterns):
            scores['conceptual'] += 2
        if any(re.search(pattern, url_lower) for pattern in self.url_reference_patterns):
            scores['reference'] += 2

        # Normalize to 0-1 confidence
        total = sum(scores.values())
        if total == 0:
            return {k: 0.25 for k in scores}  # Equal distribution

        confidences = {
            content_type: score / total
            for content_type, score in scores.items()
        }

        return confidences


# Singleton instance
_classifier = None


def get_classifier() -> ContentClassifier:
    """Get or create the global content classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = ContentClassifier()
    return _classifier


def classify_content(url: str, title: str, content: str) -> List[str]:
    """
    Convenience function to classify content.

    Args:
        url: Document URL
        title: Document title
        content: Document content

    Returns:
        List of content types
    """
    classifier = get_classifier()
    return classifier.classify_content(url, title, content)


def classify_content_primary(url: str, title: str, content: str) -> str:
    """
    Convenience function to get primary content type.

    Args:
        url: Document URL
        title: Document title
        content: Document content

    Returns:
        Primary content type
    """
    classifier = get_classifier()
    return classifier.classify_content_primary(url, title, content)


if __name__ == "__main__":
    # Test the classifier
    classifier = ContentClassifier()

    print("="*80)
    print("CONTENT CLASSIFIER TESTER")
    print("="*80)

    # Test cases
    test_cases = [
        {
            'name': 'Procedural - Installation',
            'url': 'https://docs.cyberark.com/conjur/latest/en/install-conjur.htm',
            'title': 'Install Conjur',
            'content': '''To install Conjur, follow these steps:
            Step 1: Download the installer
            Step 2: Run the installation script
            Step 3: Configure the database connection
            '''
        },
        {
            'name': 'Conceptual - Overview',
            'url': 'https://docs.cyberark.com/conjur/latest/en/overview.htm',
            'title': 'Conjur Overview',
            'content': '''This section provides an overview of Conjur architecture.
            Conjur is a secrets management solution that provides secure storage
            and access control for sensitive credentials.
            '''
        },
        {
            'name': 'Reference - API',
            'url': 'https://docs.cyberark.com/conjur/latest/en/api-reference.htm',
            'title': 'API Reference',
            'content': '''
            | Parameter | Type | Description |
            |-----------|------|-------------|
            | api_key   | string | Authentication key |
            | secret_id | string | Secret identifier |
            '''
        },
        {
            'name': 'Code Example - Tutorial',
            'url': 'https://docs.cyberark.com/conjur/latest/en/tutorial.htm',
            'title': 'Getting Started Tutorial',
            'content': '''Here's how to authenticate with Conjur:
            ```bash
            $ conjur authn login -u admin
            $ conjur variable set -i db/password -v secret123
            ```
            '''
        },
        {
            'name': 'Mixed - Setup with Code',
            'url': 'https://docs.cyberark.com/conjur/latest/en/setup-kubernetes.htm',
            'title': 'Setup Kubernetes Integration',
            'content': '''To configure Kubernetes authentication:
            Step 1: Create a service account
            Step 2: Apply the following YAML:
            ```yaml
            apiVersion: v1
            kind: ServiceAccount
            metadata:
              name: conjur-auth
            ```
            '''
        }
    ]

    print("\nTest Cases:")
    print("-"*80)

    for test in test_cases:
        print(f"\n{test['name']}")
        print(f"  URL: {test['url']}")
        print(f"  Title: {test['title']}")

        # Classify
        types = classifier.classify_content(
            test['url'],
            test['title'],
            test['content']
        )

        primary = classifier.classify_content_primary(
            test['url'],
            test['title'],
            test['content']
        )

        confidences = classifier.get_classification_confidence(
            test['url'],
            test['title'],
            test['content']
        )

        print(f"  Primary Type: {primary}")
        print(f"  All Types: {', '.join(types)}")
        print(f"  Confidences:")
        for content_type, confidence in sorted(confidences.items(), key=lambda x: x[1], reverse=True):
            if confidence > 0.1:
                print(f"    {content_type}: {confidence:.2f}")
