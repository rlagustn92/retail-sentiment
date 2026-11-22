"""뉴스 수치화 (알파카·벤징가 뉴스 + Finnhub 보충).

- 뉴스 강도: 최근 1시간 반도체 뉴스 건수 ÷ 평소 같은 시간대 평균
- 뉴스 톤: 헤드라인마다 -1(악재) ~ +1(호재), 단어 사전 방식
- 악재 비율: 최근 1시간 헤드라인 중 톤이 음수인 비율
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pandas as pd

# 금융 헤드라인용 간단 사전. 여러 단어 표현을 먼저 검사합니다.
NEG_PHRASES = [
    "cuts guidance", "lowers guidance", "cut guidance", "weak guidance", "misses estimates",
    "export ban", "export restrictions", "export controls", "price target cut", "sell-off",
    "selloff", "profit warning", "below expectations", "falls short", "chip curbs",
    "antitrust probe", "rate hike", "margin call",
]
NEG_WORDS = {
    "plunge", "plunges", "plunged", "tumble", "tumbles", "tumbled", "slump", "slumps", "slumped",
    "crash", "crashes", "crashed", "sink", "sinks", "sank", "drop", "drops", "dropped", "fall",
    "falls", "fell", "slide", "slides", "slid", "plummet", "plummets", "downgrade", "downgrades",
    "downgraded", "miss", "misses", "missed", "weak", "weaker", "weakness", "cut", "cuts",
    "loss", "losses", "lawsuit", "probe", "investigation", "ban", "bans", "curb", "curbs",
    "tariff", "tariffs", "sanction", "sanctions", "recall", "delay", "delays", "delayed",
    "shortfall", "warn", "warns", "warning", "fear", "fears", "concern", "concerns", "risk",
    "bubble", "layoffs", "halt", "halts", "bearish", "decline", "declines", "declined", "rout",
    "selloff", "worst", "outflow", "outflows", "panic", "slashes", "slash", "glut", "oversupply", "slowdown", "recession", "default",
}
POS_PHRASES = [
    "raises guidance", "beats estimates", "tops estimates", "price target raised",
    "record revenue", "strong guidance", "above expectations", "raised guidance",
]
POS_WORDS = {
    "surge", "surges", "surged", "soar", "soars", "soared", "jump", "jumps", "jumped", "rally",
    "rallies", "rallied", "gain", "gains", "gained", "rise", "rises", "rose", "climb", "climbs",
    "upgrade", "upgrades", "upgraded", "beat", "beats", "record", "strong", "stronger", "boost",
    "boosts", "bullish", "outperform", "growth", "demand", "partnership", "approval", "approved",
    "rebound", "rebounds", "inflow", "inflows", "highs", "best", "wins", "expands", "expansion",
}
_WORD = re.compile(r"[a-z][a-z\-']+")


def tone(headline: str) -> float:
    h = headline.lower()
    pos = sum(h.count(p) for p in POS_PHRASES) * 2
    neg = sum(h.count(p) for p in NEG_PHRASES) * 2
    for w in _WORD.findall(h):
        if w in POS_WORDS:
            pos += 1
        elif w in NEG_WORDS:
            neg += 1
    return 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)


COLS = ["id", "ts", "headline", "source", "url", "symbols", "tone"]


def to_frame(items: list[dict]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=COLS)
    df = pd.DataFrame([{
        "id": str(it.get("id")),  # 알파카(숫자)·Finnhub(fh-…) id가 섞여도 비교되게 문자열로
        "ts": pd.to_datetime(it.get("created_at"), utc=True),
        "headline": it.get("headline", ""),
        "source": it.get("source", ""),
        "url": it.get("url", ""),
        "symbols": "," + ",".join(it.get("symbols", [])) + ",",
    } for it in items])
    df = df.drop_duplicates("id")
    df["tone"] = df["headline"].map(tone)
    return df.sort_values("ts", ascending=False).reset_index(drop=True)


def merge(*frames: pd.DataFrame) -> pd.DataFrame:
    fs = [f for f in frames if f is not None and not f.empty]
    if not fs:
        return pd.DataFrame(columns=COLS)
    df = pd.concat(fs, ignore_index=True)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["id"] = df["id"].astype(str)
    df = df.drop_duplicates("id").sort_values("ts")
    # 같은 기사가 알파카와 Finnhub에서 다 들어오면 먼저 나온 것 하나만 남겨요
    norm = df["headline"].astype(str).str.lower().str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
    df = df[~(norm.duplicated() & (norm != ""))]
    return df.sort_values("ts", ascending=False).reset_index(drop=True)


def for_symbols(df: pd.DataFrame, syms: list[str]) -> pd.DataFrame:
    """해당 종목이 태그된 뉴스만"""
    if df is None or df.empty:
        return df
    pat = "|".join("," + s.replace(".", r"\.") + "," for s in syms)
    return df[df["symbols"].astype(str).str.contains(pat, regex=True)]


def hourly(df: pd.DataFrame) -> pd.DataFrame:
    """시간별 뉴스 건수와 악재 비율 (기준치용). 뉴스가 없던 시간은 0건으로 채웁니다."""
    if df.empty:
        return pd.DataFrame(columns=["hour", "count", "neg_share"])
    g = df.assign(hour=df["ts"].dt.floor("h"), neg=df["tone"] < 0).groupby("hour")
    out = g.agg(count=("headline", "size"), neg_share=("neg", "mean"))
    full = pd.date_range(out.index.min(), out.index.max(), freq="h")
    out = out.reindex(full)
    out["count"] = out["count"].fillna(0)
    return out.rename_axis("hour").reset_index()


def current(df: pd.DataFrame, now: datetime | None = None, minutes: int = 60) -> dict:
    now = now or datetime.now(timezone.utc)
    recent = df[df["ts"] >= now - timedelta(minutes=minutes)] if not df.empty else df
    n = len(recent)
    return {
        "count": n,
        "neg_share": float((recent["tone"] < 0).mean()) if n else 0.0,
        "tone_mean": float(recent["tone"].mean()) if n else 0.0,
    }
