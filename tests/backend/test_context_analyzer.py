"""Tests for ContextAnalyzer coordinate normalization and bbox parsing."""

from backend.services.explainer.context_analyzer import ContextAnalyzer
from backend.shared.image_utils import compute_drill_crop_radius


def test_normalize_scalar_percent_coordinates():
    assert ContextAnalyzer._normalize_scalar(45.0) == 0.45
    assert ContextAnalyzer._normalize_scalar(100.0) == 1.0


def test_normalize_scalar_pixel_coordinates():
    assert ContextAnalyzer._normalize_scalar(450.0) == 0.45


def test_normalize_scalar_normalized_coordinates():
    assert ContextAnalyzer._normalize_scalar(0.45) == 0.45


def test_bbox_to_point_prefers_xyxy_for_ambiguous_bbox():
    point = ContextAnalyzer._bbox_to_point([0.3, 0.4, 0.6, 0.7])
    assert point == [0.45, 0.55]


def test_compute_drill_crop_radius_scales_with_image():
    assert compute_drill_crop_radius(400, 300) == 80
    assert compute_drill_crop_radius(2000, 1500) == 150
