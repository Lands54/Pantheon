from gods.mnemosyne.semantics import semantics_service


def tool_intent_names() -> list[str]:
    return semantics_service.get_tool_names()


def registered_intent_keys() -> list[str]:
    return semantics_service.list_intent_keys()


def is_registered_intent_key(intent_key: str) -> bool:
    return semantics_service.is_registered_intent(intent_key)
