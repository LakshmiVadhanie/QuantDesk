"""
SEC EDGAR ingestion.

Downloads filings for a given ticker, extracts text, chunks, and returns
Document objects ready for indexing.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import httpx
from bs4 import BeautifulSoup

from core.config import get_settings
from core.logging import get_logger
from core.types import FilingType

logger = get_logger(__name__)

EDGAR_BASE = "https://data.sec.gov"
EDGAR_FULL_TEXT = "https://efts.sec.gov/LATEST/search-index"


@dataclass
class Document:
    text: str
    ticker: str
    filing_type: str
    period: str
    filed_at: str
    source_url: str
    chunk_id: str = ""
    metadata: dict = field(default_factory=dict)


class SECEdgarClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.headers = {"User-Agent": self.settings.sec_edgar_user_agent}
        self._client = httpx.Client(headers=self.headers, timeout=30)

    def _get_cik(self, ticker: str) -> str:
        url = f"{EDGAR_BASE}/submissions/CIK{ticker.upper().zfill(10)}.json"
        resp = self._client.get(f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&enddt=2024-12-31&forms=10-K")
        # Use the company search endpoint instead
        search_url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=10-K"
        
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        resp = self._client.get(tickers_url)
        resp.raise_for_status()
        data = resp.json()

        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                cik = str(entry["cik_str"]).zfill(10)
                logger.info("resolved_cik", ticker=ticker, cik=cik)
                return cik

        raise ValueError(f"CIK not found for ticker: {ticker}")

    def _get_filings_index(self, cik: str, form_type: str) -> list[dict]:
        url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
        resp = self._client.get(url)
        resp.raise_for_status()
        data = resp.json()

        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accession_numbers = filings.get("accessionNumber", [])
        periods = filings.get("reportDate", [])

        results = []
        for form, date, acc, period in zip(forms, dates, accession_numbers, periods):
            if form == form_type:
                results.append({
                    "form": form,
                    "filed_at": date,
                    "accession_number": acc.replace("-", ""),
                    "period": period,
                    "cik": cik,
                })

        # Most recent first
        results.sort(key=lambda x: x["filed_at"], reverse=True)
        return results[:4]  # last 4 filings

    def _fetch_filing_text(self, cik: str, accession_number: str) -> str:
        index_url = (
            f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/"
            f"{accession_number}/{accession_number}-index.htm"
        )
        try:
            resp = self._client.get(index_url)
            resp.raise_for_status()
        except Exception:
            # Fall back to json index
            index_url = (
                f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/"
                f"{accession_number}/index.json"
            )
            resp = self._client.get(index_url)
            resp.raise_for_status()
            data = resp.json()
            # find the primary document
            for doc in data.get("directory", {}).get("item", []):
                if doc.get("type") in ("10-K", "10-Q", "8-K"):
                    doc_url = (
                        f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/"
                        f"{accession_number}/{doc['name']}"
                    )
                    doc_resp = self._client.get(doc_url)
                    return self._strip_html(doc_resp.text)
            return ""

        soup = BeautifulSoup(resp.text, "lxml")
        # Find the main document link
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.endswith((".htm", ".html")) and "index" not in href.lower():
                doc_url = f"{EDGAR_BASE}{href}" if href.startswith("/") else href
                try:
                    doc_resp = self._client.get(doc_url)
                    return self._strip_html(doc_resp.text)
                except Exception:
                    continue

        return ""

    @staticmethod
    def _strip_html(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        # Remove script and style
        for tag in soup(["script", "style", "table"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def fetch_documents(
        self,
        ticker: str,
        filing_types: list[FilingType],
    ) -> Iterator[Document]:
        try:
            cik = self._get_cik(ticker)
        except Exception as e:
            logger.error("cik_lookup_failed", ticker=ticker, error=str(e))
            return

        for filing_type in filing_types:
            logger.info("fetching_filings", ticker=ticker, filing_type=filing_type.value)
            try:
                filings = self._get_filings_index(cik, filing_type.value)
            except Exception as e:
                logger.error("filings_index_failed", ticker=ticker, filing_type=filing_type.value, error=str(e))
                continue

            for filing in filings:
                time.sleep(0.1)  # EDGAR rate limit
                try:
                    text = self._fetch_filing_text(cik, filing["accession_number"])
                    if not text:
                        continue
                    yield Document(
                        text=text,
                        ticker=ticker,
                        filing_type=filing_type.value,
                        period=filing["period"],
                        filed_at=filing["filed_at"],
                        source_url=(
                            f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/"
                            f"{filing['accession_number']}/"
                        ),
                        metadata={
                            "cik": cik,
                            "accession_number": filing["accession_number"],
                        },
                    )
                    logger.info(
                        "filing_fetched",
                        ticker=ticker,
                        filing_type=filing_type.value,
                        period=filing["period"],
                        text_length=len(text),
                    )
                except Exception as e:
                    logger.error(
                        "filing_fetch_failed",
                        ticker=ticker,
                        accession=filing["accession_number"],
                        error=str(e),
                    )
