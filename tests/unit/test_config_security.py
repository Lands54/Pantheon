from __future__ import annotations

from api.routes.config import _mask_api_key


def test_mask_api_key_empty():
    assert _mask_api_key("") == ""


def test_mask_api_key_keeps_suffix():
    masked = _mask_api_key("sk-test-abcdefghijklmnop")
    assert masked.endswith("mnop")
    assert "sk-test-abcdefghijkl" not in masked
    assert len(masked) == len("sk-test-abcdefghijklmnop")

