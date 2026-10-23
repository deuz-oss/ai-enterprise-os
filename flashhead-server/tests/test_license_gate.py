"""Gerbang lisensi varian FlashHead (tanpa GPU/torch):
`python -m pytest flashhead-server/tests`."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from license_gate import LicenseError, check_license  # noqa: E402


def test_default_is_pro():
    assert check_license(None, None) == "pro"
    assert check_license(" PRO ", None) == "pro"


def test_lite_refused_without_noncommercial_ack():
    # VAE LTX-Video 0.9 = RAIL-M "academic or research purposes only".
    with pytest.raises(LicenseError, match="riset"):
        check_license("lite", None)
    with pytest.raises(LicenseError):
        check_license("lite", "yes")


def test_lite_allowed_with_explicit_ack():
    assert check_license("lite", "1") == "lite"


def test_unknown_variant_refused():
    with pytest.raises(LicenseError):
        check_license("pretrained", "1")
