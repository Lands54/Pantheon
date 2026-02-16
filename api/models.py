"""
API Models
Pydantic request/response models for the Gods Platform API.
"""
from pydantic import BaseModel


class OracleRequest(BaseModel):
    """Request model for oracle/debate endpoint."""
    task: str
    thread_id: str = "temple_main"


class PrivateChatRequest(BaseModel):
    """Request model for private chat with an agent."""
    agent_id: str
    message: str
    thread_id: str = "private_session"


class CreateAgentRequest(BaseModel):
    """Request model for creating a new agent."""
    agent_id: str
    directives: str


class BroadcastRequest(BaseModel):
    """Request model for broadcasting to all agents."""
    message: str
    thread_id: str = "sacred_decree"


class HumanMessageRequest(BaseModel):
    """Request model for sending a private message to an agent (confession)."""
    agent_id: str
    title: str = ""
    message: str
    silent: bool = False
