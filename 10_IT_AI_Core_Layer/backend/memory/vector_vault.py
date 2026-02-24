"""
AutoHaus C-OS v3.1 — MODULE 4: Sovereign Memory (The Vector Vault)
===================================================================
This module provides the Digital Chief of Staff with a persistent,
searchable long-term memory that is strictly ISOLATED from operational
data (BigQuery). It stores CEO strategic preferences, SOP summaries,
and historical context in a vector embedding space.

Architecture:
  - Storage:   A local JSON file acting as the vector index (upgradable
                to Vertex AI Vector Search or Pinecone in production).
  - Embedding: Google Gemini Text Embeddings (`text-embedding-004`).
  - Retrieval: Cosine similarity search returning the top-K most
                semantically relevant memories for system prompt injection.

Isolation Principle (from AUTOHAUS_SYSTEM_STATE.json):
  - Operational Data (VINs, Ledgers, Invoices) → BigQuery (strict SQL).
  - Strategic Context (CEO preferences, SOP rules) → Vector Vault (this module).

Usage:
  vault = VectorVault()
  vault.store("Ahsin prefers margin reports grouped by week, not month.")
  context = vault.recall("How should I format the finance report?")
  # Returns: ["Ahsin prefers margin reports grouped by week, not month."]

Author: AutoHaus CIL Build System
Version: 1.0.0
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

import numpy as np
import google.generativeai as genai

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autohaus.vector_vault")

# Default storage path for the local vector index
DEFAULT_VAULT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "auth", "sovereign_memory.json"
)

# Embedding model
EMBEDDING_MODEL = "models/text-embedding-004"


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
@dataclass
class MemoryEntry:
    """A single memory stored in the Vault."""
    memory_id: str
    content: str
    category: str
    source: str
    created_at: str
    embedding: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RecallResult:
    """A memory recalled by semantic similarity."""
    content: str
    category: str
    similarity: float
    memory_id: str


# ---------------------------------------------------------------------------
# Vector Vault Class
# ---------------------------------------------------------------------------
class VectorVault:
    """
    The Sovereign Memory Vault for the AutoHaus Digital Chief of Staff.

    Stores strategic CEO preferences and SOP context as vector embeddings.
    Retrieves semantically similar memories to inject into the Chatbot's
    system prompt before generating responses.

    This implementation uses a local JSON file for portability. In production,
    swap the storage layer to Vertex AI Vector Search or Pinecone by
    overriding the _load / _save / _search methods.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        vault_path: Optional[str] = None,
    ):
        """
        Initialize the VectorVault.

        Args:
            api_key:    Google AI API key. Falls back to GEMINI_API_KEY env var.
            vault_path: Path to the local JSON vector index file.
        """
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. "
                "Provide it via the constructor or set the GEMINI_API_KEY environment variable."
            )

        genai.configure(api_key=resolved_key)
        self._vault_path = vault_path or DEFAULT_VAULT_PATH
        self._memories: list[MemoryEntry] = []
        self._load()
        logger.info(
            f"VectorVault initialized with {len(self._memories)} memories "
            f"(path: {self._vault_path})"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(
        self,
        content: str,
        category: str = "GENERAL",
        source: str = "CEO_DIRECT",
    ) -> MemoryEntry:
        """
        Store a new preference or context string in the Vault.

        Args:
            content:  The strategic text to remember.
            category: Classification tag (e.g., FINANCE, SERVICE, SOP, GENERAL).
            source:   Origin of the memory (CEO_DIRECT, SOP_DOCUMENT, SYSTEM).

        Returns:
            The created MemoryEntry with its embedding.
        """
        # Generate embedding via Gemini
        embedding = self._embed(content)

        entry = MemoryEntry(
            memory_id=f"mem_{len(self._memories):04d}_{int(datetime.now(timezone.utc).timestamp())}",
            content=content,
            category=category,
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
            embedding=embedding,
        )

        self._memories.append(entry)
        self._save()

        logger.info(
            f"Stored memory: [{entry.category}] '{content[:60]}...' "
            f"(id: {entry.memory_id})"
        )
        return entry

    def recall(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.3,
        category_filter: Optional[str] = None,
    ) -> list[RecallResult]:
        """
        Recall the most semantically relevant memories for a query.

        Args:
            query:           The natural language query to match against.
            top_k:           Maximum number of results to return.
            min_similarity:  Minimum cosine similarity threshold (0.0 to 1.0).
            category_filter: Optional category to restrict search scope.

        Returns:
            A list of RecallResult objects ordered by descending similarity.
        """
        if not self._memories:
            logger.warning("Vault is empty. No memories to recall.")
            return []

        query_embedding = self._embed(query)

        results: list[RecallResult] = []

        for mem in self._memories:
            # Apply category filter if specified
            if category_filter and mem.category != category_filter:
                continue

            if not mem.embedding:
                continue

            similarity = self._cosine_similarity(query_embedding, mem.embedding)

            if similarity >= min_similarity:
                results.append(RecallResult(
                    content=mem.content,
                    category=mem.category,
                    similarity=round(similarity, 4),
                    memory_id=mem.memory_id,
                ))

        # Sort by descending similarity
        results.sort(key=lambda r: r.similarity, reverse=True)

        top_results = results[:top_k]

        if top_results:
            logger.info(
                f"Recalled {len(top_results)} memories for query: '{query[:50]}...' "
                f"(top similarity: {top_results[0].similarity})"
            )
        else:
            logger.info(f"No relevant memories found for: '{query[:50]}...'")

        return top_results

    def build_context_injection(self, query: str, top_k: int = 3) -> str:
        """
        Convenience method: Recall memories and format them as a string
        block ready to inject into the Chatbot's system prompt.

        Args:
            query: The user's current command or conversation context.
            top_k: Maximum memories to inject.

        Returns:
            A formatted string block, or empty string if no memories found.
        """
        results = self.recall(query, top_k=top_k)

        if not results:
            return ""

        lines = ["## CEO STRATEGIC CONTEXT (from Sovereign Memory Vault):"]
        for r in results:
            lines.append(f"- [{r.category}] {r.content} (relevance: {r.similarity})")

        return "\n".join(lines)

    def list_all(self) -> list[dict]:
        """Return all stored memories (without embeddings, for display)."""
        return [
            {
                "memory_id": m.memory_id,
                "content": m.content,
                "category": m.category,
                "source": m.source,
                "created_at": m.created_at,
            }
            for m in self._memories
        ]

    @property
    def count(self) -> int:
        """Total number of stored memories."""
        return len(self._memories)

    # ------------------------------------------------------------------
    # Private Methods
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> list[float]:
        """Generate a vector embedding for a text string using Gemini."""
        try:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return []

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two embedding vectors."""
        a = np.array(vec_a)
        b = np.array(vec_b)

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def _load(self):
        """Load memories from the local JSON vault file."""
        path = Path(self._vault_path)
        if path.exists():
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                self._memories = [MemoryEntry(**entry) for entry in data]
            except Exception as e:
                logger.error(f"Failed to load vault from {path}: {e}")
                self._memories = []
        else:
            self._memories = []

    def _save(self):
        """Persist memories to the local JSON vault file."""
        path = Path(self._vault_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w") as f:
                json.dump([m.to_dict() for m in self._memories], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save vault to {path}: {e}")


# ---------------------------------------------------------------------------
# Local Test Harness (__main__)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("  AutoHaus C-OS v3.1 — Sovereign Memory Vault Test Harness")
    print("=" * 70)

    vault = VectorVault()

    # Store strategic CEO preferences
    print("\n--- STORING MEMORIES ---")
    vault.store(
        "Ahsin prefers margin reports grouped by week, not by month.",
        category="FINANCE",
        source="CEO_DIRECT",
    )
    vault.store(
        "Never pay more than $500 for transport from Chicago to Des Moines.",
        category="LOGISTICS",
        source="CEO_DIRECT",
    )
    vault.store(
        "All BMW vehicles must go through Lane B cosmetic before listing on the lot.",
        category="SERVICE",
        source="SOP_DOCUMENT",
    )
    vault.store(
        "Mohsin handles all PPF and ceramic work at AstroLogistics.",
        category="SERVICE",
        source="SOP_DOCUMENT",
    )
    vault.store(
        "VIP customers get a 10% loyalty discount on service work above $1,000.",
        category="CRM",
        source="CEO_DIRECT",
    )

    print(f"\nTotal memories stored: {vault.count}")

    # Recall test: semantically similar but NOT exact match
    print("\n--- RECALL TESTS ---")

    test_queries = [
        "How should I group the financial reports?",
        "What's the max budget for shipping a car from Illinois?",
        "Where does PPF installation happen?",
        "Do we offer any discounts to returning customers?",
    ]

    for query in test_queries:
        print(f"\nQUERY: {query}")
        results = vault.recall(query, top_k=2)
        for r in results:
            print(f"  → [{r.category}] {r.content} (sim: {r.similarity})")

    # Test the context injection builder
    print("\n--- CONTEXT INJECTION ---")
    injection = vault.build_context_injection("Prepare a finance report for Lane A")
    print(injection)
