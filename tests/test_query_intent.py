"""Tests for query intent detection and content-type boost factors."""

import pytest

from cyberark_rag.query_intent import QueryIntentDetector, detect_intent


@pytest.fixture(scope="module")
def detector() -> QueryIntentDetector:
    return QueryIntentDetector()


class TestIntentDetection:
    """Verify intent classification for representative queries."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("how to configure conjur kubernetes", "how-to"),
        ("how do I configure conjur authn-k8s", "how-to"),
        ("setup dual accounts in privilege cloud", "how-to"),
        ("install conjur on docker", "how-to"),
        ("what is SPIFFE", "explanation"),
        ("explain the difference between Conjur and Secrets Hub", "explanation"),
        ("overview of privilege cloud architecture", "explanation"),
        ("PVWA error 401 troubleshooting", "troubleshooting"),
        ("fix CONJ00004E authenticator not enabled", "troubleshooting"),
        ("debug conjur policy error", "troubleshooting"),
        ("conjur CLI reference", "reference"),
        ("list of PVWA API endpoints", "reference"),
        ("conjur api authentication parameters", "reference"),
    ])
    def test_intent_classification(self, detector, query, expected_intent):
        intent = detector.detect_intent(query)
        assert intent.intent_type == expected_intent, (
            f"Query '{query}': expected '{expected_intent}', got '{intent.intent_type}'"
        )

    def test_general_intent_for_ambiguous_query(self, detector):
        intent = detector.detect_intent("conjur authentication")
        assert intent.intent_type == "general"

    def test_confidence_range(self, detector):
        intent = detector.detect_intent("how to install conjur")
        assert 0.0 <= intent.confidence <= 1.0


class TestBoostFactors:
    """Verify content-type boost multipliers for each intent."""

    def test_howto_boosts_procedural(self, detector):
        intent = detector.detect_intent("how to configure conjur")
        assert intent.boost_factors["procedural"] >= 1.5

    def test_howto_does_not_boost_conceptual(self, detector):
        intent = detector.detect_intent("how to configure conjur")
        assert intent.boost_factors["conceptual"] <= 1.0

    def test_troubleshooting_boosts_code_example(self, detector):
        intent = detector.detect_intent("error CONJ00004E not enabled")
        assert intent.boost_factors["code-example"] >= 1.5

    def test_explanation_boosts_conceptual(self, detector):
        intent = detector.detect_intent("what is SPIFFE identity")
        assert intent.boost_factors["conceptual"] >= 1.5

    def test_reference_boosts_reference(self, detector):
        intent = detector.detect_intent("conjur CLI command reference")
        assert intent.boost_factors["reference"] >= 1.5

    def test_general_intent_all_boosts_equal(self, detector):
        intent = detector.detect_intent("conjur authentication")
        for boost in intent.boost_factors.values():
            assert boost == 1.0


class TestConvenienceFunction:
    """Test the module-level detect_intent() function."""

    def test_returns_query_intent(self):
        intent = detect_intent("how to install conjur")
        assert intent.intent_type is not None
        assert isinstance(intent.boost_factors, dict)
