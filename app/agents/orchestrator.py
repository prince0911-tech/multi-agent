"""
Orchestrator Agent — the primary LangGraph-based coordinator.

Graph structure:
  START → router → task_node / calendar_node / notes_node / risk_node
       → synthesiser → END

Inter-agent messages are logged to MongoDB for auditability.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from loguru import logger

from app.config import get_settings
from app.database.connection import get_db
from app.database.models import AgentMessage
from app.agents.task_agent import TaskAgent
from app.agents.calendar_agent import CalendarAgent
from app.agents.notes_agent import NotesAgent
from app.agents.risk_agent import RiskAgent
from app.memory.vector_store import get_memory


# ─────────────────────────────────────────────────────────────────────────────
# Graph state
# ─────────────────────────────────────────────────────────────────────────────

class OrchestratorState(TypedDict):
    user_id: str
    query: str
    route: str                      # which sub-agent to invoke
    sub_agent_result: str           # raw output from sub-agent
    final_answer: str               # polished answer for the user
    messages: list                  # conversation history


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

ROUTER_PROMPT = """You are the orchestration layer of a multi-agent AI productivity system.

Given a user query, decide which sub-agent should handle it:
- "task"     → questions about tasks, priorities, deadlines, to-do lists
- "calendar" → questions about events, scheduling, free time, meetings
- "notes"    → questions about notes, documents, information storage
- "risk"     → questions about overload, risks, warnings, health check
- "general"  → any other query (you will answer directly)

Respond with ONLY one of: task, calendar, notes, risk, general
"""

SYNTHESISER_PROMPT = """You are the final synthesis layer of a multi-agent AI productivity system.

You receive:
1. The original user query
2. The structured output from the relevant sub-agent

Your job is to produce a clear, friendly, and actionable response for the user.
Keep the response concise but complete.
"""


class OrchestratorAgent:
    """
    LangGraph-based primary agent that routes queries to sub-agents,
    collects results, and synthesises a final user-facing response.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )
        self.task_agent = TaskAgent()
        self.calendar_agent = CalendarAgent()
        self.notes_agent = NotesAgent()
        self.risk_agent = RiskAgent()
        self.memory = get_memory(settings.faiss_index_path)
        self._graph = self._build_graph()

    # ── Graph construction ────────────────────────────────────────────────

    def _build_graph(self) -> Any:
        """Build and compile the LangGraph workflow."""
        builder = StateGraph(OrchestratorState)

        builder.add_node("router", self._router_node)
        builder.add_node("task_node", self._task_node)
        builder.add_node("calendar_node", self._calendar_node)
        builder.add_node("notes_node", self._notes_node)
        builder.add_node("risk_node", self._risk_node)
        builder.add_node("general_node", self._general_node)
        builder.add_node("synthesiser", self._synthesiser_node)

        builder.set_entry_point("router")

        # Conditional routing based on router decision
        builder.add_conditional_edges(
            "router",
            lambda state: state["route"],
            {
                "task": "task_node",
                "calendar": "calendar_node",
                "notes": "notes_node",
                "risk": "risk_node",
                "general": "general_node",
            },
        )

        # All sub-agents feed into the synthesiser
        for node in ("task_node", "calendar_node", "notes_node", "risk_node", "general_node"):
            builder.add_edge(node, "synthesiser")

        builder.add_edge("synthesiser", END)

        return builder.compile()

    # ── Graph nodes ───────────────────────────────────────────────────────

    async def _router_node(self, state: OrchestratorState) -> OrchestratorState:
        """Determine which sub-agent should handle the query."""
        messages = [
            SystemMessage(content=ROUTER_PROMPT),
            HumanMessage(content=state["query"]),
        ]
        response = await self.llm.ainvoke(messages)
        route = response.content.strip().lower()
        if route not in ("task", "calendar", "notes", "risk", "general"):
            route = "general"
        logger.info(f"[Orchestrator] Routed '{state['query'][:60]}' → {route}")
        return {**state, "route": route}

    async def _task_node(self, state: OrchestratorState) -> OrchestratorState:
        result = await self.task_agent.run(state["user_id"], state["query"])
        await self._log_message("orchestrator", "task_agent", state["query"], result)
        return {**state, "sub_agent_result": result}

    async def _calendar_node(self, state: OrchestratorState) -> OrchestratorState:
        result = await self.calendar_agent.run(state["user_id"], state["query"])
        await self._log_message("orchestrator", "calendar_agent", state["query"], result)
        return {**state, "sub_agent_result": result}

    async def _notes_node(self, state: OrchestratorState) -> OrchestratorState:
        result = await self.notes_agent.run(state["user_id"], state["query"])
        await self._log_message("orchestrator", "notes_agent", state["query"], result)
        return {**state, "sub_agent_result": result}

    async def _risk_node(self, state: OrchestratorState) -> OrchestratorState:
        report = await self.risk_agent.analyse(state["user_id"])
        result = json.dumps(report, indent=2)
        await self._log_message("orchestrator", "risk_agent", state["query"], result)

        # Inter-agent: if critical risk, also trigger task prioritisation
        if report.get("risk_level") in ("high", "critical"):
            await self.task_agent.prioritise_all(state["user_id"])
            logger.info(
                "[Orchestrator] Critical risk detected — triggered task prioritisation."
            )

        return {**state, "sub_agent_result": result}

    async def _general_node(self, state: OrchestratorState) -> OrchestratorState:
        """Handle general queries not routed to a specific agent."""
        # Use semantic memory for personalisation
        memory_hits = self.memory.search(state["query"], top_k=3)
        memory_context = "\n".join(
            f"- {h.get('text', '')[:100]}" for h in memory_hits
        )

        messages = [
            SystemMessage(
                content=(
                    "You are a helpful AI productivity assistant. "
                    "Answer the user's question helpfully and concisely.\n\n"
                    f"Relevant memory:\n{memory_context}"
                )
            ),
            HumanMessage(content=state["query"]),
        ]
        response = await self.llm.ainvoke(messages)
        return {**state, "sub_agent_result": response.content}

    async def _synthesiser_node(self, state: OrchestratorState) -> OrchestratorState:
        """Synthesise a polished final answer from the sub-agent result."""
        messages = [
            SystemMessage(content=SYNTHESISER_PROMPT),
            HumanMessage(
                content=(
                    f"Original query: {state['query']}\n\n"
                    f"Sub-agent output:\n{state['sub_agent_result']}"
                )
            ),
        ]
        response = await self.llm.ainvoke(messages)
        final = response.content

        # Store interaction in vector memory for personalisation
        self.memory.add(
            text=f"Q: {state['query']} A: {final[:200]}",
            metadata={
                "type": "interaction",
                "user_id": state["user_id"],
                "query": state["query"],
                "text": final[:200],
            },
        )

        logger.info(
            f"[Orchestrator] Final answer synthesised for user {state['user_id']}"
        )
        return {**state, "final_answer": final}

    # ── Public API ────────────────────────────────────────────────────────

    async def query(self, user_id: str, query: str) -> dict[str, Any]:
        """
        Main entry point.  Runs the full LangGraph workflow and returns
        a structured response dict.
        """
        initial_state: OrchestratorState = {
            "user_id": user_id,
            "query": query,
            "route": "",
            "sub_agent_result": "",
            "final_answer": "",
            "messages": [],
        }
        final_state = await self._graph.ainvoke(initial_state)
        return {
            "user_id": user_id,
            "query": query,
            "route": final_state["route"],
            "answer": final_state["final_answer"],
            "raw_agent_output": final_state["sub_agent_result"],
        }

    # ── Inter-agent communication log ─────────────────────────────────────

    async def _log_message(
        self, from_agent: str, to_agent: str, query: str, result: str
    ) -> None:
        """Persist an inter-agent message to MongoDB for audit."""
        try:
            db = get_db()
            msg = AgentMessage(
                from_agent=from_agent,
                to_agent=to_agent,
                payload={"query": query[:500], "result": result[:500]},
            )
            await db.agent_messages.insert_one(msg.model_dump(by_alias=True))
        except Exception as exc:
            logger.warning(f"[Orchestrator] Failed to log agent message: {exc}")
