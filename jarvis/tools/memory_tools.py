"""Memory Tools for JARVIS.

Provides BaseTool implementations for remembering facts, recalling memories,
storing and searching knowledge documents, and managing task working memory.
"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification
from jarvis.subsystems.memory.unified_memory import UnifiedMemoryManager


_SHARED_MEMORY_MANAGER: Optional[UnifiedMemoryManager] = None


def get_memory_manager(db_path: str = "data/jarvis_memory.db") -> UnifiedMemoryManager:
    """Returns the singleton UnifiedMemoryManager instance."""
    global _SHARED_MEMORY_MANAGER
    if _SHARED_MEMORY_MANAGER is None:
        _SHARED_MEMORY_MANAGER = UnifiedMemoryManager(db_path=db_path)
    return _SHARED_MEMORY_MANAGER


class RememberFactTool(BaseTool):
    """Stores an intentional fact or user preference into long-term episodic memory."""
    name = "remember_fact"
    description = "Stores a personal fact, user preference, or permanent note into long-term episodic memory."
    risk_level = RiskLevel.LOW
    parameters = {
        "key": ToolParameter("key", "string", "Concept, preference, or fact key (e.g. 'exam_target', 'preferred_theme').", required=True),
        "value": ToolParameter("value", "string", "The value or information to remember.", required=True),
        "context": ToolParameter("context", "string", "Optional context or explanation.", required=False),
    }

    def __init__(self, memory_manager: Optional[UnifiedMemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def execute(self, key: str, value: str, context: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            self.memory.remember_fact(key, value, context)
            return ToolResult(
                success=True,
                output={"key": key, "value": value, "context": context or ""},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details="Failed to store fact.")
        prefs = self.memory.episodic.get_preferences()
        key = arguments.get("key", "")
        verified = key in prefs and prefs[key] == arguments.get("value")
        return ToolVerification(
            verified=verified,
            details=f"Fact '{key}' verified in episodic store." if verified else "Fact not found in preferences.",
        )


class RecallMemoryTool(BaseTool):
    """Recalls facts, user preferences, and past events matching a query."""
    name = "recall_memory"
    description = "Searches long-term episodic and knowledge memory for relevant details, facts, or past interactions."
    risk_level = RiskLevel.LOW
    parameters = {
        "query": ToolParameter("query", "string", "Topic or question to recall memories for.", required=True),
        "limit": ToolParameter("limit", "integer", "Maximum memories to return (default: 5).", required=False, default=5),
    }

    def __init__(self, memory_manager: Optional[UnifiedMemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def execute(self, query: str, limit: int = 5, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            results = self.memory.search_all(query, limit=int(limit))
            formatted = [
                {
                    "tier": r.memory_type.value,
                    "title": r.title,
                    "snippet": r.snippet,
                    "score": r.relevance_score,
                }
                for r in results
            ]
            context_block = self.memory.get_relevant_context(query)
            return ToolResult(
                success=True,
                output={"matches": formatted, "context_block": context_block, "count": len(formatted)},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None
        return ToolVerification(
            verified=verified,
            details=f"Retrieved {result.output.get('count', 0)} relevant memories." if verified else "Recall failed.",
        )


class StoreKnowledgeTool(BaseTool):
    """Stores and indexes documents, study notes, or reference information into knowledge memory."""
    name = "store_knowledge"
    description = "Stores and indexes text documents, notes, cheatsheets, or domain knowledge into SQLite FTS5."
    risk_level = RiskLevel.LOW
    parameters = {
        "title": ToolParameter("title", "string", "Title of the note or document.", required=True),
        "content": ToolParameter("content", "string", "The body text or technical content.", required=True),
        "tags": ToolParameter("tags", "string", "Comma-separated tags (e.g. 'gate, dbms, algorithms').", required=False, default=""),
        "source": ToolParameter("source", "string", "Source of the knowledge item (default: 'user_input').", required=False, default="user_input"),
    }

    def __init__(self, memory_manager: Optional[UnifiedMemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def execute(
        self,
        title: str,
        content: str,
        tags: str = "",
        source: str = "user_input",
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        try:
            tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()] if isinstance(tags, str) else list(tags)
            item_id = self.memory.store_knowledge(
                title=title,
                content=content,
                tags=tag_list,
                source=source,
            )
            return ToolResult(
                success=True,
                output={"item_id": item_id, "title": title, "tags": tag_list},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success or not result.output:
            return ToolVerification(verified=False, details="Failed to index knowledge.")
        item_id = result.output.get("item_id", "")
        item = self.memory.knowledge.get_item(item_id)
        verified = item is not None and item.title == arguments.get("title")
        return ToolVerification(
            verified=verified,
            details=f"Knowledge item verified in FTS5 index: {item_id}" if verified else "Item missing in FTS store.",
        )


class SearchKnowledgeTool(BaseTool):
    """Searches knowledge documents and notes using full-text search with BM25 ranking."""
    name = "search_knowledge"
    description = "Searches knowledge memory documents and notes using SQLite FTS5."
    risk_level = RiskLevel.LOW
    parameters = {
        "query": ToolParameter("query", "string", "Keywords or search term.", required=True),
        "limit": ToolParameter("limit", "integer", "Max results (default: 5).", required=False, default=5),
    }

    def __init__(self, memory_manager: Optional[UnifiedMemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def execute(self, query: str, limit: int = 5, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            items = self.memory.knowledge.search(query, limit=int(limit))
            data = [
                {
                    "id": item.id,
                    "title": item.title,
                    "content_snippet": item.content[:250],
                    "tags": item.tags,
                    "source": item.source,
                }
                for item in items
            ]
            return ToolResult(
                success=True,
                output={"results": data, "count": len(data)},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None
        return ToolVerification(
            verified=verified,
            details=f"FTS5 search completed ({result.output.get('count', 0)} matches found)." if verified else "Search failed.",
        )


class ManageWorkingMemoryTool(BaseTool):
    """Reads, writes, or clears ephemeral working memory scratchpad for tasks."""
    name = "manage_working_memory"
    description = "Reads, writes, deletes, or clears working memory variables for in-flight tasks."
    risk_level = RiskLevel.LOW
    parameters = {
        "action": ToolParameter("action", "string", "Action: 'get', 'set', 'get_all', 'delete', or 'clear'.", required=True),
        "task_id": ToolParameter("task_id", "string", "Task identifier.", required=True),
        "key": ToolParameter("key", "string", "Variable key name.", required=False),
        "value": ToolParameter("value", "string", "Value to store (for 'set' action).", required=False),
    }

    def __init__(self, memory_manager: Optional[UnifiedMemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def execute(
        self,
        action: str,
        task_id: str,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        act = action.strip().lower()
        try:
            if act == "set":
                if not key:
                    return ToolResult(success=False, output=None, error="Key required for 'set'", duration_ms=0)
                self.memory.working.set(task_id, key, value)
                out = {"task_id": task_id, "key": key, "value": value}
            elif act == "get":
                if not key:
                    return ToolResult(success=False, output=None, error="Key required for 'get'", duration_ms=0)
                val = self.memory.working.get(task_id, key)
                out = {"task_id": task_id, "key": key, "value": val}
            elif act == "get_all":
                all_vars = self.memory.working.get_all(task_id)
                out = {"task_id": task_id, "variables": all_vars}
            elif act == "delete":
                if not key:
                    return ToolResult(success=False, output=None, error="Key required for 'delete'", duration_ms=0)
                deleted = self.memory.working.delete(task_id, key)
                out = {"task_id": task_id, "key": key, "deleted": deleted}
            elif act == "clear":
                count = self.memory.working.clear(task_id)
                out = {"task_id": task_id, "cleared_count": count}
            else:
                return ToolResult(success=False, output=None, error=f"Unknown action '{action}'", duration_ms=0)

            return ToolResult(
                success=True,
                output=out,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None
        return ToolVerification(
            verified=verified,
            details="Working memory operation verified." if verified else "Working memory action failed.",
        )


class SessionRecallTool(BaseTool):
    """Answers 'What were we doing?' and inspects the active task and step history."""
    name = "session_recall"
    description = "Recall active session progress and recent actions to answer 'What were we doing?'"
    risk_level = RiskLevel.LOW

    parameters = {
        "query": ToolParameter("query", "string", "Optional natural language question or clarification", required=False),
    }

    def __init__(self, memory_manager: Optional[UnifiedMemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def execute(self, query: Optional[str | Dict[str, Any]] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        if isinstance(query, dict):
            query = query.get("query")
        try:
            summary = self.memory.what_were_we_doing()
            recent_activities = [a.to_dict() for a in self.memory.session.get_recent_activities(limit=5)]
            return ToolResult(
                success=True,
                output={"answer": summary, "recent_activities": recent_activities},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and bool(result.output and result.output.get("answer"))
        return ToolVerification(
            verified=verified,
            details="Session history recalled successfully." if verified else "Failed to recall session state.",
        )


class ManagePreferenceTool(BaseTool):
    """Manages explicit long-term user preferences (browser, editor, directories)."""
    name = "manage_preference"
    description = "Get, set, list, or delete explicit user preferences that JARVIS is permitted to remember."
    risk_level = RiskLevel.LOW

    parameters = {
        "action": ToolParameter("action", "string", "Action to perform: 'get', 'set', 'list', 'delete'", required=True),
        "key": ToolParameter("key", "string", "Preference key (e.g. 'preferred_browser', 'preferred_editor')", required=False),
        "value": ToolParameter("value", "string", "Preference value to set", required=False),
        "category": ToolParameter("category", "string", "Optional category (browser, editor, filesystem, general)", required=False),
    }

    def __init__(self, memory_manager: Optional[UnifiedMemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def execute(
        self,
        action: str | Dict[str, Any] = "",
        key: Optional[str] = None,
        value: Optional[str] = None,
        category: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        if isinstance(action, dict):
            args = action
            action = args.get("action", "")
            key = args.get("key", key)
            value = args.get("value", value)
            category = args.get("category", category)

        act = str(action).lower().strip()
        try:
            if act == "get":
                if not key:
                    return ToolResult(success=False, output=None, error="Key required for 'get'", duration_ms=0)
                val = self.memory.get_preference(key)
                out = {"key": key, "value": val, "found": val is not None}
            elif act == "set":
                if not key or value is None:
                    return ToolResult(success=False, output=None, error="Key and value required for 'set'", duration_ms=0)
                pref = self.memory.set_preference(key, value, category=category or "general")
                out = {"key": key, "value": value, "category": pref.category, "updated": True}
            elif act == "list":
                prefs = self.memory.list_preferences(category=category)
                out = {"preferences": prefs, "count": len(prefs)}
            elif act == "delete":
                if not key:
                    return ToolResult(success=False, output=None, error="Key required for 'delete'", duration_ms=0)
                deleted = self.memory.semantic.forget_preference(key)
                out = {"key": key, "deleted": deleted}
            else:
                return ToolResult(success=False, output=None, error=f"Unknown action '{action}'", duration_ms=0)

            return ToolResult(
                success=True,
                output=out,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None
        return ToolVerification(
            verified=verified,
            details="Preference operation verified." if verified else "Preference action failed.",
        )


class WorkflowMemoryTool(BaseTool):
    """Manages reusable task workflows (e.g. 'Open ECE Classroom')."""
    name = "manage_workflow"
    description = "Find, save, or list reusable workflows from previous executions."
    risk_level = RiskLevel.LOW

    parameters = {
        "action": ToolParameter("action", "string", "Action: 'find', 'save', 'list', 'get'", required=True),
        "prompt": ToolParameter("prompt", "string", "User prompt or trigger to find a matching workflow for", required=False),
        "name": ToolParameter("name", "string", "Workflow name for get or save", required=False),
        "trigger_patterns": ToolParameter("trigger_patterns", "array", "Regex trigger patterns for saving workflow", required=False),
        "steps": ToolParameter("steps", "array", "List of steps for saving workflow", required=False),
        "description": ToolParameter("description", "string", "Workflow description", required=False),
    }

    def __init__(self, memory_manager: Optional[UnifiedMemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def execute(
        self,
        action: str | Dict[str, Any] = "",
        prompt: Optional[str] = None,
        name: Optional[str] = None,
        trigger_patterns: Optional[List[str]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        if isinstance(action, dict):
            args = action
            action = args.get("action", "")
            prompt = args.get("prompt", prompt)
            name = args.get("name", name)
            trigger_patterns = args.get("trigger_patterns", trigger_patterns)
            steps = args.get("steps", steps)
            description = args.get("description", description)

        act = str(action).lower().strip()
        try:
            if act == "find":
                if not prompt:
                    return ToolResult(success=False, output=None, error="Prompt required for 'find'", duration_ms=0)
                wf = self.memory.find_workflow(prompt)
                out = {"found": wf is not None, "workflow": wf.to_dict() if wf else None}
            elif act == "get":
                if not name:
                    return ToolResult(success=False, output=None, error="Name required for 'get'", duration_ms=0)
                wf = self.memory.workflow.get_workflow(name)
                out = {"found": wf is not None, "workflow": wf.to_dict() if wf else None}
            elif act == "list":
                workflows = self.memory.list_workflows()
                out = {"workflows": [w.to_dict() for w in workflows], "count": len(workflows)}
            elif act == "save":
                if not name or not steps:
                    return ToolResult(success=False, output=None, error="Name and steps required for 'save'", duration_ms=0)
                wf = self.memory.save_workflow(
                    name=name,
                    trigger_patterns=trigger_patterns or [name.lower()],
                    steps=steps,
                    description=description or "",
                )
                out = {"saved": True, "workflow": wf.to_dict()}
            else:
                return ToolResult(success=False, output=None, error=f"Unknown action '{action}'", duration_ms=0)

            return ToolResult(
                success=True,
                output=out,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None
        return ToolVerification(
            verified=verified,
            details="Workflow memory operation verified." if verified else "Workflow action failed.",
        )
