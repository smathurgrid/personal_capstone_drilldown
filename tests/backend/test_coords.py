"""Coordinate utility unit tests."""

import pytest

from backend.shared.coordinates import norm_to_pixel, pixel_to_norm


def test_pixel_to_norm_center() -> None:
    x, y = pixel_to_norm(50, 25, 100, 50)
    assert x == pytest.approx(0.5)
    assert y == pytest.approx(0.5)


def test_norm_to_pixel_round_trip() -> None:
    x_px, y_px = norm_to_pixel(0.25, 0.75, 200, 100)
    assert x_px == 50
    assert y_px == 75
    x, y = pixel_to_norm(x_px, y_px, 200, 100)
    assert x == pytest.approx(0.25)
    assert y == pytest.approx(0.75)


def test_invalid_dimensions_raise() -> None:
    with pytest.raises(ValueError):
        pixel_to_norm(1, 1, 0, 10)
    with pytest.raises(ValueError):
        norm_to_pixel(0.5, 0.5, 10, -1)
