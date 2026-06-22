from __future__ import annotations

import importlib.util
from typing import Any, TypedDict

from app.config import Settings, get_settings
from app.observability import add_trace_outputs, langsmith_trace
from app.schemas import LastSeenObject, ServiceHealthState, ServiceStatus


class ObjectRecoveryState(TypedDict, total=False):
    query: str
    object_key: str
    memory: dict[str, Any] | None
    current_visible: bool
    should_open_task: bool
    state: str
    recommended_action: str


class ObjectRecoveryWorkflow:
    """Object-recovery lifecycle planner with an optional LangGraph runtime."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        force_disabled: bool = False,
    ) -> None:
        self._settings = settings or get_settings()
        self._force_disabled = force_disabled
        self._compiled_graph: Any | None = None

    def status(self) -> ServiceStatus:
        if self.available:
            return ServiceStatus(
                state=ServiceHealthState.OK,
                message="LangGraph is available for object-recovery workflow planning.",
            )
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="LangGraph is not installed; deterministic workflow fallback is available.",
        )

    @property
    def available(self) -> bool:
        if self._force_disabled:
            return False
        return importlib.util.find_spec("langgraph") is not None

    def plan_recovery(
        self,
        *,
        query: str,
        object_key: str,
        memory: LastSeenObject | None,
        current_visible: bool,
    ) -> ObjectRecoveryState:
        state: ObjectRecoveryState = {
            "query": query,
            "object_key": object_key,
            "memory": memory.model_dump(mode="json") if memory else None,
            "current_visible": current_visible,
        }
        trace_inputs: dict[str, Any] = {
            "object_key": object_key,
            "has_memory": memory is not None,
            "current_visible": current_visible,
        }
        if self._settings.langsmith_trace_content:
            trace_inputs["query"] = query
            trace_inputs["memory"] = state["memory"]
        with langsmith_trace(
            self._settings,
            "langgraph.object_recovery.plan",
            inputs=trace_inputs,
            metadata={
                "workflow": "object_recovery",
                "langgraph_available": self.available,
            },
            tags=["langgraph", "object-recovery"],
        ) as trace_run:
            result = self._plan_recovery_state(state)
            add_trace_outputs(
                trace_run,
                {
                    "state": result.get("state"),
                    "should_open_task": result.get("should_open_task"),
                    "has_recommended_action": bool(result.get("recommended_action")),
                    "recommended_action": result.get("recommended_action")
                    if self._settings.langsmith_trace_content
                    else None,
                },
                include_content=self._settings.langsmith_trace_content,
            )
            return result

    def _plan_recovery_state(self, state: ObjectRecoveryState) -> ObjectRecoveryState:
        if not self.available:
            return self._deterministic_plan(state)

        try:
            graph = self._graph()
            result = graph.invoke(state)
        except Exception:
            return self._deterministic_plan(state)
        return ObjectRecoveryState(**result)

    def _graph(self) -> Any:
        if self._compiled_graph is not None:
            return self._compiled_graph

        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(ObjectRecoveryState)
        graph.add_node("assess_recovery_need", self._assess_recovery_need)
        graph.add_node("plan_human_recovery", self._plan_human_recovery)
        graph.add_edge(START, "assess_recovery_need")
        graph.add_conditional_edges(
            "assess_recovery_need",
            self._next_node,
            {
                "plan_human_recovery": "plan_human_recovery",
                "done": END,
            },
        )
        graph.add_edge("plan_human_recovery", END)
        self._compiled_graph = graph.compile()
        return self._compiled_graph

    def _deterministic_plan(self, state: ObjectRecoveryState) -> ObjectRecoveryState:
        assessed = self._assess_recovery_need(state)
        if self._next_node(assessed) == "plan_human_recovery":
            return self._plan_human_recovery(assessed)
        return assessed

    @staticmethod
    def _assess_recovery_need(state: ObjectRecoveryState) -> ObjectRecoveryState:
        has_memory = bool(state.get("memory"))
        current_visible = bool(state.get("current_visible"))
        state["should_open_task"] = has_memory and not current_visible
        state["state"] = "open" if state["should_open_task"] else "no_task_needed"
        return state

    @staticmethod
    def _plan_human_recovery(state: ObjectRecoveryState) -> ObjectRecoveryState:
        memory = state.get("memory") or {}
        location = memory.get("last_seen_relative_location")
        room = memory.get("last_seen_room")
        if location and room:
            action = f"Check {room} near {location}, then verify in person."
        elif location:
            action = f"Check near {location}, then verify in person."
        elif room:
            action = f"Check {room}, then verify in person."
        else:
            action = "Check the last-seen area and verify in person."
        state["recommended_action"] = action
        return state

    @staticmethod
    def _next_node(state: ObjectRecoveryState) -> str:
        return "plan_human_recovery" if state.get("should_open_task") else "done"
