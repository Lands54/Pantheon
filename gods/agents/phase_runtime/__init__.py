"""Phase runtime package entrypoint."""
from .core import AgentPhaseRuntime
from .policy import AgentPhase, PhaseToolPolicy, base_phases
from .strategies import (
    PHASE_STRATEGIES,
    PHASE_STRATEGY_ITERATIVE_ACTION,
    PHASE_STRATEGY_STRICT_TRIAD,
)

__all__ = [
    "AgentPhaseRuntime",
    "AgentPhase",
    "PhaseToolPolicy",
    "_base_phases",
    "PHASE_STRATEGIES",
    "PHASE_STRATEGY_ITERATIVE_ACTION",
    "PHASE_STRATEGY_STRICT_TRIAD",
]


def _base_phases():
    """Backward-compatible alias for tests and legacy imports."""
    return base_phases()
