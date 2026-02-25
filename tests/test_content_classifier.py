"""Tests for content type classification."""

import pytest

from cyberark_rag.content_classifier import ContentClassifier, classify_content_primary


@pytest.fixture(scope="module")
def classifier() -> ContentClassifier:
    return ContentClassifier()


class TestContentTypeDetection:
    """Verify pattern-based content classification."""

    @pytest.mark.parametrize("text,expected_type", [
        (
            "Step 1: Navigate to Settings. Step 2: Click Configure. Step 3: Save.",
            "procedural",
        ),
        (
            "This section provides an overview of the architecture and concepts behind the platform.",
            "conceptual",
        ),
        (
            "API Reference\n| Parameter | Type | Description |\n|---|---|---|\n| api_key | string | Auth key |\nSee the specification for available options and arguments.",
            "reference",
        ),
        (
            "```bash\ncurl -X POST https://conjur.example.com/authn/\n```",
            "code-example",
        ),
    ])
    def test_primary_type(self, classifier, text, expected_type):
        result = classifier.classify_content_primary("https://docs.cyberark.com/page", "Title", text)
        assert result == expected_type, f"Expected '{expected_type}', got '{result}'"


class TestUrlSignals:
    """URL path segments should bias classification."""

    def test_reference_url_boosts_reference(self, classifier):
        types = classifier.classify_content(
            "https://docs.cyberark.com/conjur/latest/en/api-reference.htm",
            "API Reference",
            "Some generic content about the system.",
        )
        assert "reference" in types

    def test_tutorial_url_boosts_procedural(self, classifier):
        types = classifier.classify_content(
            "https://docs.cyberark.com/conjur/latest/en/getting-started.htm",
            "Getting Started",
            "Welcome to the product.",
        )
        assert "procedural" in types

    def test_overview_url_boosts_conceptual(self, classifier):
        types = classifier.classify_content(
            "https://docs.cyberark.com/conjur/latest/en/overview.htm",
            "Product Overview",
            "The system provides functionality.",
        )
        assert "conceptual" in types


class TestClassificationConfidence:
    """Verify confidence scores are well-formed."""

    def test_confidence_sums_to_one(self, classifier):
        confidences = classifier.get_classification_confidence(
            "https://docs.cyberark.com/page",
            "Title",
            "Step 1: Install. Step 2: Configure.",
        )
        total = sum(confidences.values())
        assert abs(total - 1.0) < 0.01, f"Confidences sum to {total}, expected ~1.0"

    def test_all_content_types_present(self, classifier):
        confidences = classifier.get_classification_confidence(
            "https://docs.cyberark.com/page",
            "Title",
            "Some content.",
        )
        expected_keys = {"procedural", "conceptual", "reference", "code-example"}
        assert set(confidences.keys()) == expected_keys

    def test_no_content_gives_equal_distribution(self, classifier):
        confidences = classifier.get_classification_confidence("", "", "")
        for v in confidences.values():
            assert v == 0.25


class TestConvenienceFunction:
    """Test module-level classify_content_primary()."""

    def test_returns_string(self):
        result = classify_content_primary(
            "https://docs.cyberark.com/page",
            "Title",
            "Step 1: Install the software.",
        )
        assert isinstance(result, str)
        assert result in {"procedural", "conceptual", "reference", "code-example", "general"}
