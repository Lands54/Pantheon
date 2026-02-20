from gods.janus.models import ContextBuildRequest
from gods.janus.strategies.sequential_v1 import SequentialV1Strategy
from types import SimpleNamespace

req = ContextBuildRequest(
    project_id="test",
    agent_id="test",
    state={},
    directives="",
    local_memory="",
    inbox_hint="",
    context_materials=SimpleNamespace(cards=[
        {"source_seq": 1, "text": "Card 1", "meta": {"intent_key": "event.manual"}},
        {"source_seq": 2, "text": "Card 2", "meta": {"intent_key": "event.manual"}},
        {"source_seq": 3, "text": "Summary", "meta": {"intent_key": "system.memory.summary", "payload": {"supersedes_seq": 2}}},
        {"source_seq": 4, "text": "Card 4", "meta": {"intent_key": "event.manual"}}
    ]),
    context_cfg={"context_n_recent": 1}
)

strategy = SequentialV1Strategy()
r = strategy.build(req)
for block in r.system_blocks:
    if "Card" in block or "Summary" in block:
        print(block)
