from __future__ import annotations

from gods.metis.strategy_runtime import validate_spec_registry_alignment
from gods.metis.strategy_specs import list_strategy_specs


def test_metis_spec_registry_alignment_zero_diff():
    spec_ids = [s.strategy_id for s in list_strategy_specs()]
    assert validate_spec_registry_alignment(spec_ids) == []
