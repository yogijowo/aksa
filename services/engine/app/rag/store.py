"""Hybrid Vector (LanceDB / Dense Numpy) + SQLite FTS5 Search Engine with Reciprocal Rank Fusion (RRF) & Multi-Tier Memory."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

import aiosqlite
import numpy as np

from app.config import settings
from app.core.sandbox import RiskLevel
from app.db.models import DatabaseManager, _now_iso, db_manager
from app.rag.ingest import (
    SUPPORTED_RAG_EXTENSIONS,
    DocumentChunk,
    compute_file_sha256,
    parse_and_chunk_file,
)
from app.tools.registry import ToolResult, tool_registry

EMBEDDING_DIM = 128


class MultilingualEmbedder:
    """Offline-capable multilingual dense vector embedder using character & word n-gram projections."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def embed_text(self, text: str) -> np.ndarray:
        """Compute a normalized dense embedding vector for Indonesian/English text."""
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = re.findall(r"[a-zA-Z0-9_\-/]+", text.lower())
        if not tokens:
            return vec

        for tok in tokens:
            # Word feature + character trigram features for robust Indonesian morphology matching
            grams = [tok] + [tok[i : i + 3] for i in range(max(0, len(tok) - 2))]
            for g in grams:
                digest = hashlib.md5(g.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:2], "little") % self.dim
                sign = 1.0 if (digest[2] % 2 == 0) else -1.0
                vec[idx] += sign

        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec


class HybridRAGStore:
    """Combines Embedded Dense Vectors (LanceDB directory) and SQLite FTS5 BM25 via Reciprocal Rank Fusion."""

    def __init__(self, db: DatabaseManager = db_manager, vector_dir: Path | None = None) -> None:
        self.db = db
        self.vector_dir = vector_dir or settings.lancedb_dir
        self.embedder = MultilingualEmbedder()
        self._vectors: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _vector_store_file(self) -> Path:
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        return self.vector_dir / "vectors_index.json"

    def _ensure_vectors_loaded(self) -> None:
        if self._loaded:
            return
        vfile = self._vector_store_file()
        if vfile.exists():
            try:
                self._vectors = json.loads(vfile.read_text(encoding="utf-8"))
            except Exception:
                self._vectors = {}
        self._loaded = True

    def _persist_vectors(self) -> None:
        vfile = self._vector_store_file()
        vfile.write_text(json.dumps(self._vectors), encoding="utf-8")

    async def index_file(self, workspace_id: str, file_path: str | Path) -> dict[str, Any]:
        """Incrementally index a single file using SHA-256 diff check into Dense Vectors + SQLite FTS5."""
        self._ensure_vectors_loaded()
        resolved = Path(file_path).expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"File '{resolved}' tidak ditemukan.")

        ext = resolved.suffix.lower()
        if ext not in SUPPORTED_RAG_EXTENSIONS:
            return {"status": "skipped_unsupported", "file_path": str(resolved)}

        sha256_hash = compute_file_sha256(resolved)
        stat = resolved.stat()

        async with aiosqlite.connect(self.db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM rag_documents WHERE file_path = ?",
                (str(resolved),),
            )
            existing = await cursor.fetchone()
            if existing and existing["sha256_hash"] == sha256_hash:
                return {
                    "status": "unchanged",
                    "document_id": existing["id"],
                    "file_name": resolved.name,
                    "chunk_count": existing["chunk_count"],
                }

            doc_id = existing["id"] if existing else f"doc_{uuid.uuid4().hex[:10]}"

            # Remove old chunks if updating modified file
            if existing:
                await conn.execute("DELETE FROM rag_chunks_fts WHERE document_id = ?", (doc_id,))
                stale_keys = [
                    k for k, v in self._vectors.items() if v.get("document_id") == doc_id
                ]
                for k in stale_keys:
                    self._vectors.pop(k, None)

            chunks: list[DocumentChunk] = parse_and_chunk_file(resolved, doc_id)

            for chk in chunks:
                await conn.execute(
                    """
                    INSERT INTO rag_chunks_fts (
                        chunk_id, document_id, workspace_id, file_name, section_title, content
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chk.chunk_id,
                        doc_id,
                        workspace_id,
                        resolved.name,
                        chk.section_title,
                        chk.content,
                    ),
                )
                emb = self.embedder.embed_text(f"{resolved.name} {chk.section_title} {chk.content}")
                self._vectors[chk.chunk_id] = {
                    "chunk_id": chk.chunk_id,
                    "document_id": doc_id,
                    "workspace_id": workspace_id,
                    "file_name": resolved.name,
                    "section_title": chk.section_title,
                    "content": chk.content,
                    "vector": emb.tolist(),
                }

            await conn.execute(
                """
                INSERT INTO rag_documents (
                    id, workspace_id, file_path, file_name, file_ext,
                    file_size_bytes, sha256_hash, chunk_count, status, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'indexed', ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_size_bytes = excluded.file_size_bytes,
                    sha256_hash = excluded.sha256_hash,
                    chunk_count = excluded.chunk_count,
                    status = 'indexed',
                    indexed_at = excluded.indexed_at
                """,
                (
                    doc_id,
                    workspace_id,
                    str(resolved),
                    resolved.name,
                    ext,
                    stat.st_size,
                    sha256_hash,
                    len(chunks),
                    _now_iso(),
                ),
            )
            await conn.commit()

        self._persist_vectors()
        return {
            "status": "indexed",
            "document_id": doc_id,
            "file_name": resolved.name,
            "chunk_count": len(chunks),
            "sha256_hash": sha256_hash,
        }

    async def index_workspace_folder(
        self, workspace_id: str, folder_path: str | Path
    ) -> dict[str, Any]:
        """Scan a workspace folder and incrementally index all supported documents."""
        root = Path(folder_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            return {"indexed": 0, "unchanged": 0, "total_files": 0}

        indexed_count = 0
        unchanged_count = 0
        for entry in sorted(root.rglob("*")):
            if any(part.startswith(".") for part in entry.parts):
                continue
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_RAG_EXTENSIONS:
                res = await self.index_file(workspace_id, entry)
                if res.get("status") == "indexed":
                    indexed_count += 1
                elif res.get("status") == "unchanged":
                    unchanged_count += 1

        async with aiosqlite.connect(self.db.db_path) as conn:
            await conn.execute(
                "UPDATE workspaces SET last_indexed_at = ? WHERE id = ?",
                (_now_iso(), workspace_id),
            )
            await conn.commit()

        return {
            "workspace_id": workspace_id,
            "folder_path": str(root),
            "indexed": indexed_count,
            "unchanged": unchanged_count,
            "total_files": indexed_count + unchanged_count,
        }

    async def list_indexed_documents(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        """List all indexed RAG documents in SQLite."""
        async with aiosqlite.connect(self.db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if workspace_id:
                cursor = await conn.execute(
                    "SELECT * FROM rag_documents WHERE workspace_id = ? ORDER BY indexed_at DESC",
                    (workspace_id,),
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM rag_documents ORDER BY indexed_at DESC"
                )
            return [dict(r) for r in await cursor.fetchall()]

    async def hybrid_search(
        self,
        query: str,
        workspace_id: str | None = None,
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        """Perform Hybrid Vector + SQLite FTS5 BM25 search fused with Reciprocal Rank Fusion (RRF)."""
        self._ensure_vectors_loaded()
        query_vec = self.embedder.embed_text(query)

        # 1. Dense Vector Ranking
        vec_candidates: list[tuple[str, float]] = []
        for cid, meta in self._vectors.items():
            if workspace_id and meta.get("workspace_id") != workspace_id:
                continue
            v = np.array(meta["vector"], dtype=np.float32)
            score = float(np.dot(query_vec, v))
            vec_candidates.append((cid, score))
        vec_candidates.sort(key=lambda x: x[1], reverse=True)
        vec_ranks = {cid: rank for rank, (cid, _) in enumerate(vec_candidates[:50], start=1)}

        # 2. SQLite FTS5 Exact / Keyword BM25 Ranking
        fts_ranks: dict[str, int] = {}
        fts_payloads: dict[str, dict[str, Any]] = {}
        tokens = [re.sub(r"[^a-zA-Z0-9]", "", t) for t in query.split()]
        tokens = [t for t in tokens if len(t) >= 2]

        if tokens:
            fts_query = " OR ".join(f'"{t}"' for t in tokens)
            async with aiosqlite.connect(self.db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                sql = (
                    "SELECT chunk_id, document_id, workspace_id, file_name, section_title, content, bm25(rag_chunks_fts) AS bm25_score "
                    "FROM rag_chunks_fts WHERE rag_chunks_fts MATCH ?"
                )
                params: list[Any] = [fts_query]
                if workspace_id:
                    sql += " AND workspace_id = ?"
                    params.append(workspace_id)
                sql += " ORDER BY bm25_score LIMIT 50"
                try:
                    cursor = await conn.execute(sql, tuple(params))
                    rows = await cursor.fetchall()
                    for rank, r in enumerate(rows, start=1):
                        cid = r["chunk_id"]
                        fts_ranks[cid] = rank
                        fts_payloads[cid] = dict(r)
                except Exception:
                    pass

        # 3. Reciprocal Rank Fusion (RRF)
        all_chunk_ids = set(vec_ranks.keys()) | set(fts_ranks.keys())
        fused_results: list[dict[str, Any]] = []

        for cid in all_chunk_ids:
            r_vec = vec_ranks.get(cid)
            r_fts = fts_ranks.get(cid)
            rrf_score = 0.0
            if r_vec is not None:
                rrf_score += 1.0 / (rrf_k + r_vec)
            if r_fts is not None:
                rrf_score += 1.5 / (rrf_k + r_fts)  # Boost exact FTS5 matches (nomor surat/angka)

            meta = self._vectors.get(cid) or fts_payloads.get(cid)
            if not meta:
                continue
            fused_results.append(
                {
                    "chunk_id": cid,
                    "document_id": meta.get("document_id"),
                    "workspace_id": meta.get("workspace_id"),
                    "file_name": meta.get("file_name"),
                    "section_title": meta.get("section_title"),
                    "content": meta.get("content"),
                    "rrf_score": round(rrf_score, 6),
                    "vector_rank": r_vec,
                    "fts5_rank": r_fts,
                }
            )

        fused_results.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fused_results[:top_k]

    async def remember_user_fact(
        self,
        fact: str,
        category: str = "preferensi_pengguna",
        workspace_id: str | None = None,
        workspace_folder: str | Path | None = None,
    ) -> dict[str, Any]:
        """Store a long-term user fact in SQLite `user_memories` and optionally `.aksa/MEMORY.md`."""
        mem_id = f"mem_{uuid.uuid4().hex[:10]}"
        now = _now_iso()
        await self.db.initialize()
        async with aiosqlite.connect(self.db.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO user_memories (id, category, fact, workspace_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (mem_id, category, fact.strip(), workspace_id, now),
            )
            await conn.commit()

        if workspace_folder:
            ws_dir = Path(workspace_folder).expanduser().resolve()
            if ws_dir.exists() and ws_dir.is_dir():
                aksa_dir = ws_dir / ".aksa"
                aksa_dir.mkdir(parents=True, exist_ok=True)
                mem_file = aksa_dir / "MEMORY.md"
                existing = mem_file.read_text(encoding="utf-8") if mem_file.exists() else "# Memori Proyek AKSA\n\n"
                mem_file.write_text(f"{existing}- **[{category}]** {fact.strip()}\n", encoding="utf-8")

        return {"id": mem_id, "category": category, "fact": fact.strip(), "created_at": now}

    async def recall_user_memories(
        self, query: str | None = None, category: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve persistent user facts from SQLite `user_memories`."""
        await self.db.initialize()
        async with aiosqlite.connect(self.db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            sql = "SELECT * FROM user_memories WHERE 1=1"
            params: list[Any] = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if query:
                sql += " AND LOWER(fact) LIKE ?"
                params.append(f"%{query.lower()}%")
            sql += " ORDER BY created_at DESC LIMIT 25"
            cursor = await conn.execute(sql, tuple(params))
            return [dict(r) for r in await cursor.fetchall()]


rag_store = HybridRAGStore()


async def search_workspace_knowledge(
    query: str,
    workspace_id: str | None = None,
    top_k: int = 5,
) -> ToolResult:
    """Agent tool: Search local Hybrid RAG (Vector + FTS5 RRF) and return compact citations."""
    hits = await rag_store.hybrid_search(query=query, workspace_id=workspace_id, top_k=top_k)
    summary = (
        f"Hybrid RAG RRF menemukan {len(hits)} kutipan relevan untuk kueri '{query}'."
        if hits
        else f"Tidak ditemukan kutipan yang cocok untuk kueri '{query}'."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data={"query": query, "results": hits},
        token_estimate=35 + len(hits) * 65,
    )


async def remember_user_fact_tool(
    fact: str,
    category: str = "preferensi_pengguna",
    workspace_folder: str | None = None,
) -> ToolResult:
    """Agent tool: Save an important user or project preference to long-term memory."""
    saved = await rag_store.remember_user_fact(
        fact=fact, category=category, workspace_folder=workspace_folder
    )
    return ToolResult(
        success=True,
        summary=f"Memori jangka panjang berhasil disimpan [{category}]: {fact}",
        data=saved,
        token_estimate=24,
    )


async def recall_user_memories_tool(
    query: str | None = None,
    category: str | None = None,
) -> ToolResult:
    """Agent tool: Recall stored user preferences and facts."""
    memories = await rag_store.recall_user_memories(query=query, category=category)
    return ToolResult(
        success=True,
        summary=f"Memuat {len(memories)} memori jangka panjang pengguna.",
        data={"memories": memories},
        token_estimate=20 + len(memories) * 18,
    )


def register_rag_and_memory_tools() -> None:
    tool_registry.register(
        name="search_workspace_knowledge",
        category="rag_search",
        description="Cari potongan dokumen akurat menggunakan Hybrid RAG (Vector + FTS5 BM25 RRF).",
        handler=search_workspace_knowledge,
        risk_level=RiskLevel.LOW,
    )
    tool_registry.register(
        name="remember_user_fact",
        category="rag_search",
        description="Simpan fakta atau preferensi pengguna ke Memori Jangka Panjang & .aksa/MEMORY.md.",
        handler=remember_user_fact_tool,
        risk_level=RiskLevel.LOW,
    )
    tool_registry.register(
        name="recall_user_memories",
        category="rag_search",
        description="Panggil kembali fakta dan preferensi pengguna dari Memori Jangka Panjang.",
        handler=recall_user_memories_tool,
        risk_level=RiskLevel.LOW,
    )


register_rag_and_memory_tools()
