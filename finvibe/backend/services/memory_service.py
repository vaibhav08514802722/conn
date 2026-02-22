"""
Mem0 wrapper — episodic memory for user-level preferences and conversation history.
"""
from backend.deps import get_memory


def add_user_memory(user_id: str, messages: list[dict]) -> None:
    """
    Store conversation messages into Mem0 for a specific user.
    messages: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    try:
        get_memory().add(user_id=user_id, messages=messages)
        print(f"[MemoryService] Stored memory for user={user_id}")
    except Exception as e:
        print(f"[MemoryService] Failed to add memory: {e}")


def search_user_memory(user_id: str, query: str) -> list[str]:
    """
    Search Mem0 for relevant memories about a user.
    Returns a list of memory strings.
    """
    try:
        results = get_memory().search(query=query, user_id=user_id)
        # Mem0 returns list of dicts with 'memory' key
        return [r.get("memory", str(r)) for r in results]
    except Exception as e:
        print(f"[MemoryService] Search failed: {e}")
        return []
