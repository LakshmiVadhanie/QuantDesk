"""
Ingestion pipeline: SEC EDGAR -> chunk -> embed -> Qdrant + BM25 index.

Usage:
    python -m data_ingestion.ingest --tickers MSFT AAPL NVDA --filing-types 10-K 10-Q
"""

from __future__ import annotations

import argparse
import sys

from core.config import get_settings
from core.logging import configure_logging, get_logger
from core.types import FilingType
from data_ingestion.chunker import Chunk, chunk_document
from data_ingestion.sec_edgar import SECEdgarClient
from rag.qdrant_store import QdrantStore

logger = get_logger(__name__)


def ingest_ticker(
    ticker: str,
    filing_types: list[FilingType],
    qdrant: QdrantStore,
) -> int:
    client = SECEdgarClient()
    total_chunks = 0

    for doc in client.fetch_documents(ticker, filing_types):
        chunks: list[Chunk] = chunk_document(
            text=doc.text,
            ticker=doc.ticker,
            filing_type=doc.filing_type,
            period=doc.period,
            filed_at=doc.filed_at,
            source_url=doc.source_url,
            metadata=doc.metadata,
        )

        if not chunks:
            logger.warning("no_chunks_produced", ticker=ticker, filing_type=doc.filing_type)
            continue

        qdrant.upsert_chunks(chunks)
        total_chunks += len(chunks)
        logger.info(
            "chunks_indexed",
            ticker=ticker,
            filing_type=doc.filing_type,
            period=doc.period,
            count=len(chunks),
        )

    return total_chunks


def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser(description="QuantDesk ingestion pipeline")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument(
        "--filing-types",
        nargs="+",
        default=["10-K", "10-Q"],
        choices=["10-K", "10-Q", "8-K"],
    )
    args = parser.parse_args()

    filing_types = [FilingType(f) for f in args.filing_types]

    settings = get_settings()
    qdrant = QdrantStore(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    qdrant.ensure_collection()

    total = 0
    failed = []

    for ticker in args.tickers:
        logger.info("ingestion_start", ticker=ticker)
        try:
            count = ingest_ticker(ticker, filing_types, qdrant)
            total += count
            logger.info("ingestion_complete", ticker=ticker, chunks=count)
        except Exception as e:
            logger.error("ingestion_failed", ticker=ticker, error=str(e))
            failed.append(ticker)

    logger.info("ingestion_summary", total_chunks=total, failed=failed)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
