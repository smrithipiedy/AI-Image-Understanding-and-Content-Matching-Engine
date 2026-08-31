"""Tests for MismatchGuard module."""

import pytest
from app.services.guard import MismatchGuard, GuardResult


class TestMismatchGuard:
    """Tests for MismatchGuard rules and threshold evaluations."""

    def test_guard_accepts_valid_matching_candidate(self):
        """Should accept candidate with high similarity, matching category, and high confidence."""
        guard = MismatchGuard(similarity_threshold=0.65, confidence_threshold=0.70)
        res = guard.evaluate(
            similarity=0.85,
            image_category="red_fox",
            image_confidence=0.92,
            is_low_confidence=False,
            expected_category="red_fox",
        )
        assert res.decision == "accepted"
        assert len(res.reasons) == 0

    def test_guard_rejects_category_mismatch(self):
        """Probe 3 requirement: Should reject wolf candidate for fox post."""
        guard = MismatchGuard(similarity_threshold=0.65, confidence_threshold=0.70)
        res = guard.evaluate(
            similarity=0.80,
            image_category="wolf",
            image_confidence=0.90,
            is_low_confidence=False,
            expected_category="red_fox",
        )
        assert res.decision == "rejected"
        assert "category_mismatch" in res.reasons
        assert "expected 'red_fox', detected 'wolf'" in res.explanation

    def test_guard_rejects_low_similarity(self):
        """Should reject candidate when similarity is below threshold."""
        guard = MismatchGuard(similarity_threshold=0.65, confidence_threshold=0.70)
        res = guard.evaluate(
            similarity=0.45,
            image_category="red_fox",
            image_confidence=0.90,
            is_low_confidence=False,
            expected_category="red_fox",
        )
        assert res.decision == "rejected"
        assert "similarity_below_threshold" in res.reasons

    def test_guard_rejects_low_vision_confidence(self):
        """Should reject candidate when vision confidence is low."""
        guard = MismatchGuard(similarity_threshold=0.65, confidence_threshold=0.70)
        res = guard.evaluate(
            similarity=0.85,
            image_category="red_fox",
            image_confidence=0.50,
            is_low_confidence=True,
            expected_category="red_fox",
        )
        assert res.decision == "rejected"
        assert "low_vision_confidence" in res.reasons
