"""Finnhub 종목 뉴스 — 알파카(벤징가) 뉴스를 보충해요. 수집기만 쓰고, 키는 GitHub Secrets의 FINNHUB_KEY.

무료 플랜은 분당 60회라서 요청 사이를 1초 넘게 띄워요.
"""
from __future__ import annotations

import time
from datetime import date

import pandas as pd
import requests

from . import news as newsmod

URL = "https://finnhub.io/api/v1/company-news"


class Finnhub:
    def __init__(self, key: str, min_interval: float = 1.05, timeout: int = 20):
        self.s = requests.Session()
        self.s.headers.update({"X-Finnhub-Token": key})  # 키를 주소(URL)에 넣지 않으려고 헤더로 보내요
        self.min_interval, self.timeout = min_interval, timeout
        self._last = 0.0

    def _get(self, params: dict):
        for attempt in range(3):
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            r = self.s.get(URL, params=params, timeout=self.timeout)
            if r.status_code == 429:
                time.sleep(5 + attempt * 5)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()
        return []

    def company_news(self, sym: str, start: date, end: date) -> list[dict]:
        j = self._get({"symbol": sym, "from": start.isoformat(), "to": end.isoformat()})
        return j if isinstance(j, list) else []


def to_frame(items: list[dict], sym: str) -> pd.DataFrame:
    """Finnhub 뉴스 → 알파카 뉴스와 같은 모양 (id 앞에 fh- 를 붙여 겹치지 않게)"""
    rows = []
    for it in items:
        if not it.get("headline") or not it.get("datetime"):
            continue
        related = [s.strip() for s in str(it.get("related") or "").split(",") if s.strip()]
        if sym not in related:
            related.append(sym)
        rows.append({"id": f"fh-{it.get('id')}", "created_at": pd.Timestamp(int(it["datetime"]), unit="s", tz="UTC"),
                     "headline": it["headline"], "source": it.get("source", ""), "url": it.get("url", ""),
                     "symbols": related})
    return newsmod.to_frame(rows)
