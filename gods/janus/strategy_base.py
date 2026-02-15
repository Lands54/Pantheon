"""Janus strategy base interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from gods.janus.models import ContextBuildRequest, ContextBuildResult


class ContextStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def build(self, req: ContextBuildRequest) -> ContextBuildResult:
        raise NotImplementedError
