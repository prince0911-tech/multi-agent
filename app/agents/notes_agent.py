"""
Notes Agent — manages user notes, supports semantic search via vector
memory, and links notes to tasks.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from app.config import get_settings
from app.memory.vector_store import get_memory
from app.tools import create_note, get_notes, update_note, search_notes


SYSTEM_PROMPT = """You are the Notes Agent in a multi-agent AI productivity system.

Your responsibilities:
1. Create, update, and retrieve notes for users.
2. Perform semantic and keyword search over notes.
3. Link notes to related tasks.
4. Summarise note content on request.
5. Surface relevant notes when users ask questions about their work.

Return structured JSON when listing notes.
"""


class NotesAgent:
    """
    Notes management agent with semantic search via FAISS memory.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )
        self.memory = get_memory(settings.faiss_index_path)

    async def run(self, user_id: str, query: str) -> str:
        """Process a natural-language notes query."""
        # Semantic search via vector memory first
        semantic_hits = self.memory.search(query, top_k=3)

        # Also fetch recent notes
        recent = await get_notes(user_id=user_id, limit=10)

        context_lines = ["Semantic memory hits:"]
        for h in semantic_hits:
            context_lines.append(
                f"- [{h.get('type', 'note')}] {h.get('text', '')[:120]}"
            )
        context_lines.append(f"\nRecent notes ({len(recent)}):")
        for n in recent:
            context_lines.append(
                f"- {n.get('title')}: {n.get('content', '')[:100]}"
            )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content="\n".join(context_lines) + f"\n\nUser query: {query}"
            ),
        ]
        response = await self.llm.ainvoke(messages)
        logger.info(f"[NotesAgent] Processed query for user {user_id}")
        return response.content

    async def create(
        self,
        user_id: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        related_task_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a note and index it in vector memory."""
        note = await create_note(
            user_id=user_id,
            title=title,
            content=content,
            tags=tags,
            related_task_id=related_task_id,
        )
        # Index into vector memory for semantic search
        self.memory.add(
            text=f"{title} {content}",
            metadata={
                "type": "note",
                "note_id": note["_id"],
                "user_id": user_id,
                "title": title,
                "text": content[:200],
            },
        )
        return note

    async def search(self, user_id: str, keyword: str) -> list[dict[str, Any]]:
        """Keyword search (MongoDB) + semantic search (FAISS) combined."""
        db_results = await search_notes(user_id=user_id, keyword=keyword)
        semantic = self.memory.search(keyword, top_k=5)

        # Deduplicate by note_id
        seen_ids: set[str] = {n["_id"] for n in db_results}
        for hit in semantic:
            if (
                hit.get("user_id") == user_id
                and hit.get("note_id")
                and hit["note_id"] not in seen_ids
            ):
                seen_ids.add(hit["note_id"])
                db_results.append(hit)

        return db_results
