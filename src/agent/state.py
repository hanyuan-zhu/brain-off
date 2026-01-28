"""
Agent state management for conversation context.
"""
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Message:
    """Represents a single message in the conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None


@dataclass
class AgentState:
    """
    Agent state for managing conversation context.

    This is stored in-memory for now. In Phase 9, we can add Redis persistence.
    """
    session_id: UUID = field(default_factory=uuid4)
    conversation_history: List[Message] = field(default_factory=list)
    current_context: Dict[str, Any] = field(default_factory=dict)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    pending_clarifications: List[str] = field(default_factory=list)

    # Context tracking
    active_task_id: Optional[UUID] = None
    active_idea_ids: List[UUID] = field(default_factory=list)
    last_query_type: Optional[str] = None  # "capture", "search", "process", etc.
    recent_task_ids: List[UUID] = field(default_factory=list)
    current_filters: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Add a message to conversation history."""
        message = Message(role=role, content=content, **kwargs)
        self.conversation_history.append(message)

    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Get recent messages from conversation history."""
        return self.conversation_history[-limit:]

    def clear_context(self) -> None:
        """Clear current context but keep conversation history."""
        self.current_context = {}
        self.active_task_id = None
        self.active_idea_ids = []
        self.current_filters = {}


class SessionManager:
    """
    Manages agent sessions in-memory.

    In Phase 9, this can be upgraded to use Redis for persistence.
    """

    def __init__(self):
        self._sessions: Dict[UUID, AgentState] = {}

    def create_session(self) -> AgentState:
        """Create a new agent session."""
        state = AgentState()
        self._sessions[state.session_id] = state
        return state

    def get_session(self, session_id: UUID) -> Optional[AgentState]:
        """Get an existing session by ID."""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def list_sessions(self) -> List[UUID]:
        """List all active session IDs."""
        return list(self._sessions.keys())


# Global session manager instance
_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    return _session_manager
