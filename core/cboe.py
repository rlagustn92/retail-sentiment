"""CBOE 무료 공개 데이터: VIX·VIX3M, 주식 옵션 풋/콜 비율."""
from __future__ import annotations

import io
import re
from datetime import date

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (retail-sentiment dashboard)"}
HIST = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{}_History.csv"
QUOTE = "https://cdn.cboe.com/api/global/delayed_quotes/quotes/_{}.json"
DAILY_STATS = "https://www.cboe.com/us/options/market_statistics/daily/"
INTRADAY_STATS = "https://ww2.cboe.com/us/options/market_statistics/?iframe=1"


def index_history(name: str) -> pd.Series:
    """일별 종가 (예: VIX, VIX3M). 인덱스는 날짜."""
    r = requests.get(HIST.format(name), headers=UA, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df["DATE"] = pd.to_datetime(df["DATE"])
    return df.set_index("DATE")["CLOSE"].astype(float)


def index_quote(name: str) -> float | None:
    """15분 지연 현재가. 실패하면 None."""
    try:
        r = requests.get(QUOTE.format(name), headers=UA, timeout=10)
        r.raise_for_status()
        d = r.json().get("data", {})
        v = d.get("current_price") or d.get("last") or d.get("close")
        return float(v) if v else None
    except Exception:
        return None


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def equity_putcall_daily(day: date) -> float | None:
    """해당 날짜의 주식 옵션 풋/콜 비율 (장 마감 후 확정치)."""
    r = requests.get(DAILY_STATS, params={"dt": day.isoformat()}, headers=UA, timeout=20)
    if r.status_code != 200:
        return None
    m = re.search(r"EQUITY PUT/CALL RATIO\s+([\d.]+)", _text(r.text))
    return float(m.group(1)) if m else None


def equity_putcall_intraday() -> float | None:
    """오늘 장중 30분 단위 주식 옵션 풋/콜 비율 중 가장 최근 값 (실험적)."""
    try:
        r = requests.get(INTRADAY_STATS, headers=UA, timeout=15)
        r.raise_for_status()
        t = _text(r.text)
        i = t.upper().find("EQUITY OPTIONS")
        if i < 0:
            return None
        seg = t[i:i + 4000]
        nxt = re.search(r"(INDEX|VIX|EXCHANGE TRADED|SPX)\b", seg[20:].upper())
        if nxt:
            seg = seg[: nxt.start() + 20]
        rows = re.findall(r"\d{1,2}:\d{2}\s*[AP]M\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+([\d.]+)", seg)
        return float(rows[-1]) if rows else None
    except Exception:
        return None
