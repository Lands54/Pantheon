"""Docker runtime error definitions."""
from __future__ import annotations


class DockerRuntimeError(RuntimeError):
    """Typed runtime error with machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


DOCKER_NOT_AVAILABLE = "DOCKER_NOT_AVAILABLE"
DOCKER_COMMAND_FAILED = "DOCKER_COMMAND_FAILED"
DOCKER_TIMEOUT = "DOCKER_TIMEOUT"
DOCKER_CONTAINER_NOT_FOUND = "DOCKER_CONTAINER_NOT_FOUND"
