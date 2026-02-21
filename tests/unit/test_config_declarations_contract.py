from gods.config.blocks import ALL_CONFIG_BLOCKS
from gods.config.declarations import validate_declaration_blocks


def test_declaration_blocks_are_valid():
    validate_declaration_blocks(ALL_CONFIG_BLOCKS)


def test_declaration_fields_have_required_metadata():
    for b in ALL_CONFIG_BLOCKS:
        assert b.module_id
        assert b.module_title
        assert b.group_id
        assert b.group_title
        for f in b.fields:
            assert f.key
            assert f.description.strip()
            assert f.owner.strip()
            assert f.scope == b.scope
            if f.status != "deprecated":
                assert list(f.runtime_used_by or [])
