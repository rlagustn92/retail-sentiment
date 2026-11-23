"""바닥 신호: 월가가 '바닥'이 아니라 '진짜 반등'을 확인할 때 보는 신호들을 우리 데이터로 계산하고,
과거에 그 신호가 켜졌을 때 그 뒤 지수가 어땠는지(상승 확률·중간값)를 같이 보여줘요.

- 공포탐욕지수(CNN)는 지난 한 달 주가·VIX로 만든 '백미러'라 바닥 신호로 쓰지 않고 참고로만 보여줘요.
- 신호가 켜졌다고 반드시 오르는 건 아니에요. 과거 통계는 표본이 적고, 미래를 보장하지 않아요.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36"}
HORIZONS = {"1개월": 21, "3개월": 63, "6개월": 126, "1년": 252}


# ---------------------------------------------------------------- 공통: 신호 뒤 수익률
def forward_stats(price: pd.Series, dates, horizons: dict | None = None) -> dict:
    """신호 날짜들 다음날 종가에 샀다고 보고, 기간별 (표본 수, 오른 비율, 중간값, 최악)"""
    horizons = horizons or HORIZONS
    p = price.dropna().sort_index()
    idx = p.index
    out = {}
    for name, h in horizons.items():
        rets = []
        for d in dates:
            i = idx.searchsorted(pd.Timestamp(d), side="right")  # 신호 다음 거래일
            if i + h < len(idx):
                rets.append(p.iloc[i + h] / p.iloc[i] - 1)
        r = np.array(rets)
        out[name] = {"n": len(r), "up": float((r > 0).mean()) if len(r) else None,
                     "median": float(np.median(r)) if len(r) else None, "worst": float(r.min()) if len(r) else None}
    return out


def base_stats(price: pd.Series, horizons: dict | None = None) -> dict:
    """아무 날에나 샀을 때 (비교 기준)"""
    p = price.dropna().sort_index()
    out = {}
    for name, h in (horizons or HORIZONS).items():
        r = (p.shift(-h) / p - 1).dropna()
        out[name] = {"n": len(r), "up": float((r > 0).mean()), "median": float(r.median()), "worst": float(r.min())}
    return out


def _naive(s: pd.Series) -> pd.Series:
    s = s.dropna().astype(float)
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.Series(s.values, index=idx).sort_index()


# ---------------------------------------------------------------- 1. VIX 기간구조 (VIX/VIX3M)
def vix_term(vix: pd.Series, vix3m: pd.Series, spx: pd.Series | None = None, now_ratio: float | None = None,
             min_days: int = 3) -> dict | None:
    """VIX/VIX3M > 1 = 단기 공포가 장기보다 큰 '역전'. 월가는 역전이 시작될 때가 아니라 풀릴 때(1 아래 복귀)를 봐요.
    episodes: 역전 시작~해소 (min_days일 이상 이어진 것만)"""
    if vix is None or vix3m is None or len(vix3m) < 250:
        return None
    r = (_naive(vix) / _naive(vix3m)).dropna()
    if now_ratio:
        r.loc[r.index.max() + pd.Timedelta(days=1)] = now_ratio if r.index.max().date() < pd.Timestamp.now().date() else r.iloc[-1]
        r = r[~r.index.duplicated(keep="last")]
    inv = r > 1.0
    eps, start = [], None
    for d, v in inv.items():
        if v and start is None:
            start = d
        elif not v and start is not None:
            days = int(inv[start:d].sum())
            if days >= min_days:
                eps.append({"start": start, "end": d, "days": days, "peak": float(r[start:d].max())})
            start = None
    cur_days = int(inv[start:].sum()) if start is not None else 0
    out = {"ratio": float(r.iloc[-1]), "inverted": bool(inv.iloc[-1]), "days": cur_days,
           "episodes": pd.DataFrame(eps), "since": int(r.index.min().year)}
    last = eps[-1] if eps else None
    out["resolved_recent"] = bool(last and not out["inverted"] and (r.index.max() - last["end"]).days <= 7)
    out["last"] = last
    if spx is not None and len(eps):
        p = _naive(spx)
        out["at_start"] = forward_stats(p, [e["start"] for e in eps])
        out["at_end"] = forward_stats(p, [e["end"] for e in eps])
        out["base"] = base_stats(p[p.index >= r.index.min()])
        out["durations"] = sorted(e["days"] for e in eps)
    return out


# ---------------------------------------------------------------- 2. 브레스 스러스트 (츠바이크)
def breadth_thrust(br: pd.DataFrame, low: float = 0.40, high: float = 0.615, window: int = 10) -> dict | None:
    """br: date, adv, dec. 상승 종목 비율의 10일 지수평균이 10거래일 안에 0.40 아래 → 0.615 위로 가면 신호"""
    if br is None or br.empty or len(br) < 30:
        return None
    b = br.copy()
    b["date"] = pd.to_datetime(b["date"])
    if getattr(b["date"].dt, "tz", None) is not None:
        b["date"] = b["date"].dt.tz_localize(None)
    b = b.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    ratio = b["adv"] / (b["adv"] + b["dec"]).replace(0, np.nan)
    ema = ratio.ewm(span=window, adjust=False).mean()
    sig = []
    lows = ema.rolling(window, min_periods=1).min()
    for i, (d, v) in enumerate(ema.items()):
        if v > high and lows.iloc[i] < low and (not sig or (d - sig[-1]).days > 30):
            sig.append(d)
    return {"ema": ema, "ratio": ratio, "now": float(ema.iloc[-1]), "low10": float(lows.iloc[-1]),
            "signals": sig, "recent": bool(sig and (ema.index[-1] - sig[-1]).days <= 20),
            "since": int(ema.index.min().year)}


def washout(br: pd.DataFrame, col: str = "above50", level: float = 0.15) -> dict | None:
    """시장 폭 바닥: 50일선 위 종목 비율이 15% 아래로 떨어진 날(첫날) — 투매형 바닥에서 자주 나와요"""
    if br is None or br.empty or col not in br:
        return None
    b = br.copy()
    b["date"] = pd.to_datetime(b["date"])
    if getattr(b["date"].dt, "tz", None) is not None:
        b["date"] = b["date"].dt.tz_localize(None)
    s = b.sort_values("date").drop_duplicates("date", keep="last").set_index("date")[col].dropna()
    if s.empty:
        return None
    below = s < level
    first = below & ~below.shift(1, fill_value=False)
    days = [d for d in s.index[first] if True]
    sig = []
    for d in days:  # 한 달 안에 다시 나온 건 같은 사건
        if not sig or (d - sig[-1]).days > 30:
            sig.append(d)
    return {"now": float(s.iloc[-1]), "signals": sig, "active": bool(below.iloc[-1]), "since": int(s.index.min().year)}


# ---------------------------------------------------------------- 3. CNN 공포탐욕 (참고: 백미러)
def fear_greed() -> dict | None:
    r = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                     headers=dict(UA, Referer="https://edition.cnn.com/markets/fear-and-greed",
                                  Accept="application/json"), timeout=15)
    r.raise_for_status()
    j = r.json()
    fg = j.get("fear_and_greed", {})
    hist = pd.DataFrame(j.get("fear_and_greed_historical", {}).get("data", []))
    if len(hist):
        hist["date"] = pd.to_datetime(hist["x"], unit="ms")
        hist = hist.rename(columns={"y": "score"})[["date", "score"]]
    return {"score": fg.get("score"), "rating": fg.get("rating"), "week": fg.get("previous_1_week"),
            "month": fg.get("previous_1_month"), "hist": hist}


RATING_KO = {"extreme fear": "극단적 공포", "fear": "공포", "neutral": "중립", "greed": "탐욕", "extreme greed": "극단적 탐욕"}


# ---------------------------------------------------------------- 시장 폭 계산 (미국·한국 공통)
def breadth_from_closes(close: pd.DataFrame) -> pd.DataFrame:
    """close: index=날짜, columns=종목 → 날짜별 상승·하락 종목 수, 50일선·200일선 위 비율, 52주 신고가·신저가 수"""
    close = close.sort_index()
    d = close.diff()
    a50 = (close > close.rolling(50, min_periods=50).mean()).where(close.rolling(50, min_periods=50).mean().notna())
    a200 = (close > close.rolling(200, min_periods=200).mean()).where(close.rolling(200, min_periods=200).mean().notna())
    hi = close.rolling(252, min_periods=200).max()
    lo = close.rolling(252, min_periods=200).min()
    out = pd.DataFrame({
        "adv": (d > 0).sum(axis=1), "dec": (d < 0).sum(axis=1), "unch": (d == 0).sum(axis=1),
        "n": close.notna().sum(axis=1),
        "above50": a50.sum(axis=1) / a50.notna().sum(axis=1).replace(0, np.nan),
        "above200": a200.sum(axis=1) / a200.notna().sum(axis=1).replace(0, np.nan),
        "nh": (close >= hi).where(hi.notna()).sum(axis=1), "nl": (close <= lo).where(lo.notna()).sum(axis=1),
    })
    out = out.iloc[1:]  # 첫날은 전날이 없어서 뺌
    out.index.name = "date"
    return out.reset_index()


def _series(df: pd.DataFrame, col: str, date_col: str = "date", where: dict | None = None) -> pd.Series:
    if df is None or df.empty or col not in df:
        return pd.Series(dtype=float)
    x = df
    for k, v in (where or {}).items():
        x = x[x[k] == v]
    s = pd.Series(pd.to_numeric(x[col], errors="coerce").values, index=pd.to_datetime(x[date_col]))
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    return s[~s.index.duplicated(keep="last")].sort_index().dropna()


# ---------------------------------------------------------------- 신용 (하이일드 채권 vs 국채)
def credit_state(credit: pd.DataFrame) -> dict | None:
    """HYG(하이일드 채권 ETF) ÷ IEF(중기 국채 ETF). 3개월 고점 대비 얼마나 빠졌는지 = 신용 시장 긴장도.
    주식만 겁먹고 신용이 멀쩡하면 '아직 항복 아님', 신용까지 무너지면 '진짜 공포'"""
    hyg, ief = _series(credit, "hyg"), _series(credit, "ief")
    if len(hyg) < 300 or len(ief) < 300:
        return None
    r = (hyg / ief).dropna()
    dd = r / r.rolling(63, min_periods=20).max() - 1
    hist = dd.dropna()
    now = float(dd.iloc[-1])
    p90, p98 = float(hist.quantile(0.10)), float(hist.quantile(0.02))   # 낙폭이라 아래쪽 꼬리
    level = "항복" if now <= p98 else "긴장" if now <= p90 else "평온"
    return {"dd": now, "p90": p90, "p98": p98, "level": level, "since": int(r.index.min().year),
            "worst": float(hist.min()), "worst_date": hist.idxmin()}


# ---------------------------------------------------------------- 한국: 외국인 매도 멈춤 · 개인 항복
def foreign_stop(hist_market: pd.DataFrame, streak: int = 5) -> dict | None:
    """외국인이 5일 넘게 연속 순매도(그 5일 합이 최근 1년 중 매도 상위 20%)하다가 처음 순매수로 돌아선 날"""
    f = _series(hist_market, "foreign", where={"market": "전체"})
    if len(f) < 300:
        return None
    neg = f < 0
    run = neg.groupby((~neg).cumsum()).cumsum()           # 연속 순매도 일수
    s5 = f.rolling(5).sum()
    thr = s5.rolling(250, min_periods=120).quantile(0.20)
    sig = []
    for i in range(1, len(f)):
        if f.iloc[i] > 0 and run.iloc[i - 1] >= streak and s5.iloc[i - 1] <= thr.iloc[i - 1]:
            sig.append(f.index[i])
    cur_run = int(run.iloc[-1])
    return {"signals": sig, "run": cur_run, "five": float(s5.iloc[-1]), "thr": float(thr.iloc[-1]),
            "recent": bool(sig and (f.index[-1] - sig[-1]).days <= 7), "since": int(f.index.min().year)}


def retail_capitulation(hist_market: pd.DataFrame, mult: float = 2.0) -> dict | None:
    """개인이 순매도하고 큰손(외국인+기관)이 평소의 2배 넘게 순매수한 날 = 개인 항복 물량을 큰손이 받은 날"""
    m = hist_market[hist_market["market"] == "전체"] if hist_market is not None and len(hist_market) else None
    if m is None or len(m) < 300:
        return None
    big = _series(m, "foreign") + _series(m, "inst")
    per = _series(m, "personal")
    scale = big.abs().rolling(60, min_periods=40).mean().shift(1)
    strength = big / scale
    hit = (per < 0) & (strength >= mult)
    sig = []
    for d in strength.index[hit.reindex(strength.index, fill_value=False)]:
        if not sig or (d - sig[-1]).days > 20:
            sig.append(d)
    return {"signals": sig, "now": float(strength.iloc[-1]) if len(strength) else None,
            "personal": float(per.iloc[-1]), "recent": bool(sig and (big.index[-1] - sig[-1]).days <= 7),
            "since": int(big.index.min().year)}
