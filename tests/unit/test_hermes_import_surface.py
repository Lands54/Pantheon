from __future__ import annotations

import pytest


def test_hermes_package_no_longer_exports_service():
    with pytest.raises(ImportError):
        from gods.hermes import hermes_service  # noqa: F401


def test_hermes_service_module_exports_service_singleton():
    from gods.hermes.facade import hermes_service

    assert hermes_service is not None
    assert hasattr(hermes_service, "route")
