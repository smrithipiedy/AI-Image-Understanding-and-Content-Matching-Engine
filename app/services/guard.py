"""Mismatch Guard module for validating image-post content matching."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class GuardResult:
    """Result returned by the MismatchGuard evaluation."""
    decision: str  # 'accepted', 'rejected', 'no_confident_match'
    reasons: List[str] = field(default_factory=list)
    explanation: Optional[str] = None


class MismatchGuard:
    """Mismatch Guard module to prevent improper image suggestions."""

    CATEGORY_SYNONYMS = {
        "red_fox": {"red_fox", "fox", "red fox", "vulpes vulpes"},
        "wolf": {"wolf", "gray wolf", "canis lupus", "timber wolf"},
        "dog": {"dog", "domestic dog", "canis lupus familiaris", "canine"},
        "bear": {"bear", "grizzly bear", "brown bear", "black bear"},
        "deer": {"deer", "white-tailed deer", "stag", "elk"},
    }

    def __init__(
        self,
        similarity_threshold: float = 0.65,
        confidence_threshold: float = 0.70,
    ):
        self.similarity_threshold = similarity_threshold
        self.confidence_threshold = confidence_threshold

    def _normalize_category(self, cat: Optional[str]) -> Optional[str]:
        if not cat:
            return None
        cleaned = cat.strip().lower().replace("-", "_").replace(" ", "_")
        for norm_cat, synonyms in self.CATEGORY_SYNONYMS.items():
            if cleaned in synonyms or any(s in cleaned for s in synonyms):
                return norm_cat
        return cleaned

    def evaluate(
        self,
        similarity: float,
        image_category: Optional[str],
        image_confidence: Optional[float],
        is_low_confidence: bool = False,
        expected_category: Optional[str] = None,
    ) -> GuardResult:
        """Evaluate match candidate against mismatch guard rules."""
        reasons: List[str] = []
        explanations: List[str] = []

        # Rule 1: Category / Subject Mismatch Guard
        norm_expected = self._normalize_category(expected_category)
        norm_image = self._normalize_category(image_category)

        if norm_expected and norm_image and norm_expected != norm_image:
            reasons.append("category_mismatch")
            explanations.append(
                f"Animal category mismatch: expected '{expected_category}', detected '{image_category}'"
            )

        # Rule 2: Similarity Threshold Guard
        if similarity < self.similarity_threshold:
            reasons.append("similarity_below_threshold")
            explanations.append(
                f"Low semantic similarity: {similarity:.2f} (threshold {self.similarity_threshold:.2f})"
            )

        # Rule 3: Vision Confidence Guard
        conf = image_confidence if image_confidence is not None else 0.0
        if is_low_confidence or conf < self.confidence_threshold:
            reasons.append("low_vision_confidence")
            explanations.append(
                f"Low vision confidence: {conf:.2f} (threshold {self.confidence_threshold:.2f})"
            )

        if not reasons:
            return GuardResult(
                decision="accepted",
                reasons=[],
                explanation="Candidate passed all guard rules with sufficient similarity and confidence.",
            )
        else:
            return GuardResult(
                decision="rejected",
                reasons=reasons,
                explanation="; ".join(explanations),
            )
