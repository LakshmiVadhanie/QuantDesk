"""
Qdrant vector store.

Uses fastembed for embeddings (runs locally, no separate embedding service needed).
"""

from __future__ import annotations

from typing import Any

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from core.config import get_settings
from core.logging import get_logger
from data_ingestion.chunker import Chunk

logger = get_logger(__name__)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384


class QdrantStore:
    def __init__(self, url: str, api_key: str = "") -> None:
        self._client = QdrantClient(url=url, api_key=api_key or None)
        self._embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
        self._collection = get_settings().qdrant_collection

    def ensure_collection(self) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qmodels.VectorParams(
                    size=VECTOR_SIZE,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            # Payload indexes for filtering
            for field_name in ("ticker", "filing_type", "period"):
                self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field_name,
                    field_schema=qmodels.PayloadSchemaType.KEYWORD,
                )
            logger.info("qdrant_collection_created", collection=self._collection)
        else:
            logger.info("qdrant_collection_exists", collection=self._collection)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._embedder.embed(texts)]

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return

        texts = [c.text for c in chunks]
        vectors = self._embed(texts)

        points = [
            qmodels.PointStruct(
                id=abs(hash(chunk.chunk_id)) % (2**63),
                vector=vector,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "ticker": chunk.ticker,
                    "filing_type": chunk.filing_type,
                    "period": chunk.period,
                    "filed_at": chunk.filed_at,
                    "source_url": chunk.source_url,
                    "chunk_index": chunk.chunk_index,
                    **chunk.metadata,
                },
            )
            for chunk, vector in zip(chunks, vectors)
        ]

        self._client.upsert(
            collection_name=self._collection,
            points=points,
            wait=True,
        )
        logger.debug("upserted_chunks", count=len(chunks))

    def search(
        self,
        query: str,
        top_k: int,
        ticker: str | None = None,
        filing_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query_vector = self._embed([query])[0]

        filters: list[qmodels.Condition] = []
        if ticker:
            filters.append(
                qmodels.FieldCondition(
                    key="ticker",
                    match=qmodels.MatchValue(value=ticker),
                )
            )
        if filing_type:
            filters.append(
                qmodels.FieldCondition(
                    key="filing_type",
                    match=qmodels.MatchValue(value=filing_type),
                )
            )

        query_filter = qmodels.Filter(must=filters) if filters else None

        results = self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            {
                "chunk_id": r.payload["chunk_id"],
                "text": r.payload["text"],
                "ticker": r.payload["ticker"],
                "filing_type": r.payload["filing_type"],
                "period": r.payload["period"],
                "source_url": r.payload["source_url"],
                "score": r.score,
            }
            for r in results
        ]

    def get_all_chunks_for_ticker(self, ticker: str) -> list[dict[str, Any]]:
        """Scroll through all chunks for BM25 corpus construction."""
        results = []
        offset = None

        while True:
            records, offset = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="ticker",
                            match=qmodels.MatchValue(value=ticker),
                        )
                    ]
                ),
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            results.extend(
                {
                    "chunk_id": r.payload["chunk_id"],
                    "text": r.payload["text"],
                    "ticker": r.payload["ticker"],
                    "filing_type": r.payload["filing_type"],
                    "period": r.payload["period"],
                    "source_url": r.payload["source_url"],
                }
                for r in records
            )
            if offset is None:
                break

        return results
