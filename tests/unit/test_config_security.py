from __future__ import annotations

from api.services.config_service import config_service


def test_mask_api_key_empty():
    assert config_service.mask_api_key("") == ""


def test_mask_api_key_keeps_suffix():
    masked = config_service.mask_api_key("sk-test-abcdefghijklmnop")
    assert masked.endswith("mnop")
    assert "sk-test-abcdefghijkl" not in masked
    assert len(masked) == len("sk-test-abcdefghijklmnop")
