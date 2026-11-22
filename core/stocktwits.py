"""Stocktwits 공개 API (키 필요 없음).

각 글에는 작성자가 직접 단 강세(Bullish)/약세(Bearish) 태그가 있을 수 있습니다.
- 약세 비율 = 약세 / (강세 + 약세)  ← 태그 단 글만
- 글 속도 = 최근 60분 동안 올라온 글 수
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

URL = "https://api.stocktwits.com/api/2/streams/symbol/{}.json"
UA = {"User-Agent": "Mozilla/5.0 (retail-sentiment dashboard)"}


def fetch_recent(symbol: str, minutes: int = 60, max_pages: int = 10) -> tuple[list[dict], float]:
    """최근 minutes분 동안의 글과, 실제로 훑은 시간(분)을 돌려줍니다 (한 페이지 30개).

    글이 너무 많아 max_pages 안에 minutes분을 다 못 채우면, 훑은 시간이 minutes보다
    짧게 나옵니다. 이때 글 속도는 비례해서 환산합니다.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=minutes)
    out: list[dict] = []
    params: dict = {}
    covered = float(minutes)
    oldest = None
    for _ in range(max_pages):
        r = requests.get(URL.format(symbol), params=params, headers=UA, timeout=15)
        r.raise_for_status()
        j = r.json()
        msgs = j.get("messages", [])
        if not msgs:
            break
        oldest = None
        for m in msgs:
            ts = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00"))
            oldest = ts
            if ts >= cutoff:
                s = (m.get("entities") or {}).get("sentiment") or {}
                out.append({"ts": ts, "sentiment": s.get("basic"), "body": m.get("body", "")})
        cur = j.get("cursor") or {}
        if oldest is None or oldest < cutoff or not cur.get("more"):
            break
        params = {"max": cur.get("max")}
    else:
        if oldest is not None and oldest > cutoff:
            covered = max((now - oldest).total_seconds() / 60, 1.0)
    return out, covered


def summarize(msgs: list[dict], covered_min: float = 60.0) -> dict:
    bull = sum(1 for m in msgs if m["sentiment"] == "Bullish")
    bear = sum(1 for m in msgs if m["sentiment"] == "Bearish")
    tagged = bull + bear
    return {
        "msgs_per_hour": len(msgs) * 60.0 / covered_min,
        "bull": bull,
        "bear": bear,
        "bear_ratio": (bear / tagged) if tagged >= 5 else None,
    }
