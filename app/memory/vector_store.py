"""
Vector memory store using FAISS + sentence-transformers.
Provides semantic search over past interactions and user preferences.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from loguru import logger

# Lazy imports — FAISS and sentence-transformers are optional
try:
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    _VECTOR_AVAILABLE = True
except ImportError:
    _VECTOR_AVAILABLE = False
    logger.warning("FAISS / sentence-transformers not available. Vector memory disabled.")


class VectorMemory:
    """
    In-process FAISS vector store with simple metadata sidecar.
    Persists index + metadata to disk so memory survives restarts.
    """

    def __init__(self, index_path: str, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.index_path = Path(index_path)
        self.meta_path = self.index_path.with_suffix(".json")
        self.model_name = model_name
        self._index: Any = None
        self._meta: list[dict] = []
        self._model: Any = None

        if _VECTOR_AVAILABLE:
            self._load_or_create()

    def _load_or_create(self) -> None:
        """Load existing index from disk or create a fresh one."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._model = SentenceTransformer(self.model_name)
        dim = self._model.get_sentence_embedding_dimension()

        if self.index_path.exists() and self.meta_path.exists():
            self._index = faiss.read_index(str(self.index_path))
            with open(self.meta_path) as f:
                self._meta = json.load(f)
            logger.info(f"[VectorMemory] Loaded {len(self._meta)} entries from disk.")
        else:
            self._index = faiss.IndexFlatL2(dim)
            self._meta = []
            logger.info("[VectorMemory] Created fresh FAISS index.")

    def add(self, text: str, metadata: dict) -> None:
        """Embed text and add to the index."""
        if not _VECTOR_AVAILABLE:
            return
        vec = self._model.encode([text]).astype("float32")
        self._index.add(vec)
        self._meta.append(metadata)
        self._save()

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return the top-k most similar entries to the query."""
        if not _VECTOR_AVAILABLE or self._index.ntotal == 0:
            return []
        vec = self._model.encode([query]).astype("float32")
        distances, indices = self._index.search(vec, min(top_k, self._index.ntotal))
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0:
                entry = dict(self._meta[idx])
                entry["_distance"] = float(dist)
                results.append(entry)
        return results

    def _save(self) -> None:
        faiss.write_index(self._index, str(self.index_path))
        with open(self.meta_path, "w") as f:
            json.dump(self._meta, f)


# Module-level singleton — initialised lazily
_memory_instance: VectorMemory | None = None


def get_memory(index_path: str = "./data/faiss_index") -> VectorMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = VectorMemory(index_path)
    return _memory_instance
