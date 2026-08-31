"""Tests for vision schemas - TDD: written BEFORE implementation."""

import pytest
from pydantic import ValidationError

from app.schemas.vision import VisionOutput, ImageMetadataResponse, ImageResponse, ImageIngestRequest


class TestVisionOutputSchema:
    """Tests for VisionOutput schema validation."""

    def test_valid_vision_output(self):
        """Valid vision output should pass validation."""
        data = {
            "subject": "red fox",
            "category": "animal",
            "attributes": ["orange fur", "wild", "forest"],
            "caption": "A red fox standing in a forest",
            "confidence": 0.94,
        }
        output = VisionOutput(**data)
        assert output.subject == "red fox"
        assert output.category == "animal"
        assert output.attributes == ["orange fur", "wild", "forest"]
        assert output.caption == "A red fox standing in a forest"
        assert output.confidence == 0.94

    def test_valid_minimal_vision_output(self):
        """Minimal valid vision output should pass."""
        data = {
            "subject": "fox",
            "category": "animal",
            "attributes": [],
            "caption": "A fox",
            "confidence": 0.5,
        }
        output = VisionOutput(**data)
        assert output.subject == "fox"
        assert output.attributes == []

    def test_confidence_boundary_values(self):
        """Confidence at boundaries 0.0 and 1.0 should be valid."""
        for conf in [0.0, 1.0]:
            data = {
                "subject": "fox",
                "category": "animal",
                "attributes": [],
                "caption": "A fox",
                "confidence": conf,
            }
            output = VisionOutput(**data)
            assert output.confidence == conf

    def test_confidence_below_zero_rejected(self):
        """Confidence < 0 should be rejected."""
        data = {
            "subject": "fox",
            "category": "animal",
            "attributes": [],
            "caption": "A fox",
            "confidence": -0.1,
        }
        with pytest.raises(ValidationError) as exc_info:
            VisionOutput(**data)
        assert "confidence" in str(exc_info.value).lower()

    def test_confidence_above_one_rejected(self):
        """Confidence > 1 should be rejected."""
        data = {
            "subject": "fox",
            "category": "animal",
            "attributes": [],
            "caption": "A fox",
            "confidence": 1.1,
        }
        with pytest.raises(ValidationError) as exc_info:
            VisionOutput(**data)
        assert "confidence" in str(exc_info.value).lower()

    def test_empty_subject_rejected(self):
        """Empty subject should be rejected."""
        data = {
            "subject": "",
            "category": "animal",
            "attributes": [],
            "caption": "A fox",
            "confidence": 0.5,
        }
        with pytest.raises(ValidationError) as exc_info:
            VisionOutput(**data)
        assert "subject" in str(exc_info.value).lower()

    def test_whitespace_subject_rejected(self):
        """Whitespace-only subject should be rejected."""
        data = {
            "subject": "   ",
            "category": "animal",
            "attributes": [],
            "caption": "A fox",
            "confidence": 0.5,
        }
        with pytest.raises(ValidationError) as exc_info:
            VisionOutput(**data)
        assert "subject" in str(exc_info.value).lower()

    def test_empty_category_rejected(self):
        """Empty category should be rejected."""
        data = {
            "subject": "fox",
            "category": "",
            "attributes": [],
            "caption": "A fox",
            "confidence": 0.5,
        }
        with pytest.raises(ValidationError) as exc_info:
            VisionOutput(**data)
        assert "category" in str(exc_info.value).lower()

    def test_empty_caption_rejected(self):
        """Empty caption should be rejected."""
        data = {
            "subject": "fox",
            "category": "animal",
            "attributes": [],
            "caption": "",
            "confidence": 0.5,
        }
        with pytest.raises(ValidationError) as exc_info:
            VisionOutput(**data)
        assert "caption" in str(exc_info.value).lower()

    def test_attributes_must_be_list(self):
        """Attributes must be a list."""
        data = {
            "subject": "fox",
            "category": "animal",
            "attributes": "not a list",
            "caption": "A fox",
            "confidence": 0.5,
        }
        with pytest.raises(ValidationError) as exc_info:
            VisionOutput(**data)
        assert "attributes" in str(exc_info.value).lower()

    def test_attributes_strips_whitespace(self):
        """Attributes should strip whitespace."""
        data = {
            "subject": "fox",
            "category": "animal",
            "attributes": ["  orange fur  ", "  wild  ", ""],
            "caption": "A fox",
            "confidence": 0.5,
        }
        output = VisionOutput(**data)
        assert output.attributes == ["orange fur", "wild"]

    def test_confidence_type_coercion(self):
        """Confidence should accept int and coerce to float."""
        data = {
            "subject": "fox",
            "category": "animal",
            "attributes": [],
            "caption": "A fox",
            "confidence": 1,  # int
        }
        output = VisionOutput(**data)
        assert output.confidence == 1.0
        assert isinstance(output.confidence, float)


class TestImageIngestRequest:
    """Tests for ImageIngestRequest schema."""

    def test_valid_urls(self):
        """Valid HTTP/HTTPS URLs should pass."""
        data = {"urls": ["https://example.com/image1.jpg", "http://example.com/image2.png"]}
        req = ImageIngestRequest(**data)
        assert len(req.urls) == 2

    def test_empty_urls_rejected(self):
        """Empty urls list should be rejected."""
        data = {"urls": []}
        with pytest.raises(ValidationError) as exc_info:
            ImageIngestRequest(**data)
        assert "urls" in str(exc_info.value).lower()

    def test_too_many_urls_rejected(self):
        """More than 50 URLs should be rejected."""
        data = {"urls": [f"https://example.com/{i}.jpg" for i in range(51)]}
        with pytest.raises(ValidationError) as exc_info:
            ImageIngestRequest(**data)
        assert "urls" in str(exc_info.value).lower()

    def test_invalid_url_rejected(self):
        """Non-HTTP URLs should be rejected."""
        data = {"urls": ["ftp://example.com/image.jpg"]}
        with pytest.raises(ValidationError) as exc_info:
            ImageIngestRequest(**data)
        assert "url" in str(exc_info.value).lower()

    def test_malformed_url_rejected(self):
        """Malformed URLs should be rejected."""
        data = {"urls": ["not-a-url"]}
        with pytest.raises(ValidationError) as exc_info:
            ImageIngestRequest(**data)
        assert "url" in str(exc_info.value).lower()