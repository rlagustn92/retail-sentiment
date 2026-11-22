"""알파카 무료(Basic) 플랜용 최소 클라이언트.

무료 플랜 규칙
- IEX 피드: 실시간 (전체 거래량의 일부만 포함)
- SIP 피드: 전체 시장, 단 최근 15분은 조회 불가
- 분당 200회 호출 제한
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import requests

DATA = "https://data.alpaca.markets"
PAPER = "https://paper-api.alpaca.markets"
SIP_DELAY = timedelta(minutes=16)  # 15분 규칙에 1분 여유


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Alpaca:
    def __init__(self, key: str, secret: str, timeout: int = 20, min_interval: float = 0.32):
        self.s = requests.Session()
        self.s.headers.update({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
        self.timeout = timeout
        self.min_interval = min_interval  # 분당 200회 제한을 넘지 않게
        self._last = 0.0

    # ---- 공통 -------------------------------------------------------------
    def _get(self, url: str, params: dict | None = None) -> dict:
        for attempt in range(4):
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            r = self.s.get(url, params=params, timeout=self.timeout)
            if r.status_code == 429:  # 호출 제한: 잠깐 쉬고 다시
                time.sleep(2 + attempt * 3)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()
        return {}

    def _paged(self, url: str, params: dict, key: str, max_pages: int = 200):
        params = dict(params)
        for _ in range(max_pages):
            j = self._get(url, params)
            yield j.get(key)
            tok = j.get("next_page_token")
            if not tok:
                return
            params["page_token"] = tok

    @staticmethod
    def sip_end(now: datetime | None = None) -> datetime:
        """무료 플랜이 SIP로 조회할 수 있는 가장 최근 시각"""
        return (now or datetime.now(timezone.utc)) - SIP_DELAY

    # ---- 장 운영 -----------------------------------------------------------
    def clock(self) -> dict:
        return self._get(f"{PAPER}/v2/clock")

    def calendar(self, start: str, end: str) -> list[dict]:
        """거래일 목록 [{'date': '2026-11-20', 'open': '09:30', 'close': '16:00'}, ...]"""
        j = self.s.get(f"{PAPER}/v2/calendar", params={"start": start, "end": end},
                       timeout=self.timeout)
        j.raise_for_status()
        return j.json()

    # ---- 시세 -------------------------------------------------------------
    def bars(self, symbols: list[str], timeframe: str, start: datetime, end: datetime,
             feed: str = "sip") -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {s: [] for s in symbols}
        for i in range(0, len(symbols), 80):
            params = {"symbols": ",".join(symbols[i:i + 80]), "timeframe": timeframe,
                      "start": iso(start), "end": iso(end), "feed": feed, "limit": 10000,
                      "adjustment": "split"}
            for page in self._paged(f"{DATA}/v2/stocks/bars", params, "bars"):
                for sym, rows in (page or {}).items():
                    out.setdefault(sym, []).extend(rows)
        return out

    def snapshots(self, symbols: list[str], feed: str = "iex") -> dict[str, dict]:
        """종목별 최신 체결·오늘 일봉·전일 일봉 (IEX는 실시간)"""
        out: dict[str, dict] = {}
        for i in range(0, len(symbols), 80):
            j = self._get(f"{DATA}/v2/stocks/snapshots",
                          {"symbols": ",".join(symbols[i:i + 80]), "feed": feed})
            out.update(j.get("snapshots", j) if isinstance(j, dict) else {})
        return out

    def latest_trades(self, symbols: list[str], feed: str = "iex") -> dict[str, dict]:
        j = self._get(f"{DATA}/v2/stocks/trades/latest",
                      {"symbols": ",".join(symbols), "feed": feed})
        return j.get("trades", {})

    def trades(self, symbol: str, start: datetime, end: datetime):
        """SIP 전체 체결. 페이지(최대 1만 건)마다 리스트를 돌려줍니다."""
        params = {"start": iso(start), "end": iso(end), "limit": 10000, "feed": "sip"}
        yield from self._paged(f"{DATA}/v2/stocks/{symbol}/trades", params, "trades", 400)

    # ---- 뉴스 -------------------------------------------------------------
    def news(self, symbols: list[str], start: datetime, end: datetime | None = None,
             max_pages: int = 60) -> list[dict]:
        params = {"symbols": ",".join(symbols), "start": iso(start), "limit": 50,
                  "sort": "desc", "include_content": "false"}
        if end:
            params["end"] = iso(end)
        items: list[dict] = []
        for page in self._paged(f"{DATA}/v1beta1/news", params, "news", max_pages):
            items.extend(page or [])
        return items

    # ---- 스크리너 ----------------------------------------------------------
    def most_actives(self, top: int = 20) -> list[dict]:
        j = self._get(f"{DATA}/v1beta1/screener/stocks/most-actives", {"by": "volume", "top": top})
        return j.get("most_actives", [])
