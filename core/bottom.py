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


def effect(stats: dict | None, base: dict | None, h: str = "3개월") -> str:
    """신호 뒤 성적을 '아무 날에나 샀을 때'와 비교한 한 줄 판정"""
    if not stats or not base or h not in stats or not stats[h]["n"]:
        return ""
    s, b = stats[h], base[h]
    if s["n"] < 5:
        return "표본 적음"
    du, dm = s["up"] - b["up"], s["median"] - b["median"]
    if du >= 0.08 and dm > 0:
        return "과거 효과 있음"
    if du <= -0.05 and dm < 0:
        return "과거엔 오히려 나빴음"
    return "과거 효과 약함"


def big_panic(hist_market: pd.DataFrame, mult: float = 3.0) -> dict | None:
    """큰손(외국인+기관)이 평소(직전 60거래일 평균 크기)의 3배 넘게 순매도한 날 = 공포 정점 후보"""
    m = hist_market[hist_market["market"] == "전체"] if hist_market is not None and len(hist_market) else None
    if m is None or len(m) < 300:
        return None
    big = _series(m, "foreign") + _series(m, "inst")
    strength = -big / big.abs().rolling(60, min_periods=40).mean().shift(1)
    sig = []
    for d in strength.index[(strength >= mult).values]:
        if not sig or (d - sig[-1]).days > 20:
            sig.append(d)
    return {"signals": sig, "now": float(strength.iloc[-1]), "max5": float(strength.tail(5).max()),
            "recent": bool(sig and (strength.index[-1] - sig[-1]).days <= 7), "since": int(big.index.min().year)}


# ---------------------------------------------------------------- 한국: VKOSPI 공포 급등·꺾임
VOL_HI, VOL_LO, VOL_WIN = 1.5, 1.2, 250
VOL_EP_COLS = ["start", "end", "days", "peak", "peak_ratio"]


def vol_episodes(v: pd.Series, hi: float = VOL_HI, lo: float = VOL_LO, window: int = VOL_WIN) -> tuple[pd.DataFrame, dict] | None:
    """VKOSPI ÷ 직전 1년(250거래일) 중앙값. 1.5배를 넘으면 공포 급등(시작), 1.2배 아래로 내려오면 꺾임(끝).
    한국엔 VIX3M 같은 3개월물 지수가 없어서, 미국 VIX 기간구조 대신 'VKOSPI가 자기 평소 수준보다 얼마나 높은지'로 봐요.
    수집기가 KRX 원본으로 계산하고, 공개 파일엔 이 결과(구간 날짜·최고치·지금 값)만 남겨요."""
    v = _naive(v)
    if len(v) < window + 20:
        return None
    med = v.rolling(window, min_periods=int(window * 0.8)).median().shift(1)
    ratio = (v / med).dropna()
    eps, start = [], None
    for d, x in ratio.items():
        if start is None and x >= hi:
            start = d
        elif start is not None and x < lo:
            eps.append({"start": start, "end": d, "days": int(len(ratio[start:d]) - 1),
                        "peak": float(v[start:d].max()), "peak_ratio": float(ratio[start:d].max())})
            start = None
    if start is not None:  # 지금 급등 중
        eps.append({"start": start, "end": pd.NaT, "days": int(len(ratio[start:])),
                    "peak": float(v[start:].max()), "peak_ratio": float(ratio[start:].max())})
    now = {"date": ratio.index[-1], "vkospi": float(v.iloc[-1]), "median": float(med.iloc[-1]),
           "ratio": float(ratio.iloc[-1]), "since": v.index.min(), "n": int(len(v)),
           "pct_all": float((v <= v.iloc[-1]).mean()), "median_all": float(v.median())}  # 전체 기간 속 위치
    return pd.DataFrame(eps, columns=VOL_EP_COLS), now


def vol_state(ep: pd.DataFrame | None, now: pd.DataFrame | None) -> dict | None:
    """수집기가 남긴 결과(kr_vol_ep·kr_vol_now)를 지금 상태로"""
    if now is None or now.empty:
        return None
    n = now.iloc[-1]

    def nv(x):
        t = pd.to_datetime(x)
        return t.tz_localize(None) if getattr(t, "tzinfo", None) is not None else t
    e = ep.copy() if ep is not None and len(ep) else pd.DataFrame(columns=VOL_EP_COLS)
    for c in ("start", "end"):
        e[c] = pd.to_datetime(e[c], utc=True).dt.tz_localize(None)
    e = e.sort_values("start")
    closed, open_ = e[e["end"].notna()], e[e["end"].isna()]
    d = nv(n["date"])
    in_ep = len(open_) > 0
    pa, ma = n.get("pct_all"), n.get("median_all")
    return {"date": d, "vkospi": float(n["vkospi"]), "median": float(n["median"]), "ratio": float(n["ratio"]),
            "pct_all": None if pa is None or pd.isna(pa) else float(pa),
            "median_all": None if ma is None or pd.isna(ma) else float(ma),
            "since": nv(n["since"]), "in_ep": in_ep, "days": int(open_["days"].iloc[-1]) if in_ep else 0,
            "starts": list(e["start"]), "ends": list(closed["end"]), "durations": sorted(int(x) for x in closed["days"]),
            "resolved_recent": bool(len(closed) and not in_ep and (d - closed["end"].max()).days <= 7),
            "last_end": closed["end"].max() if len(closed) else None,
            "peak": e.loc[e["peak"].idxmax()] if len(e) else None}


# ---------------------------------------------------------------- 한국: 레버리지·곱버스 쏠림 (KRX ETF)
def etf_bet(flow: pd.DataFrame | None, index: pd.DataFrame | None, low: float = 0.10, high: float = 0.90) -> dict | None:
    """상승 베팅(레버리지 − 인버스·곱버스) 5일 순유입이 지난 1년 중 하위 10%·상위 10%로 처음 들어간 날과 그 뒤 코스피"""
    from core import krx
    t = krx.flow_table(flow)
    kospi = _series(index, "close", where={"market": "코스피"}) if index is not None and len(index) else pd.Series(dtype=float)
    if t is None or len(t[0]) < 300 or len(kospi) < 300:
        return None
    b5 = krx.bet_series(t[0]).rolling(5).sum()
    pos = b5.rolling(250, min_periods=120).apply(lambda h: (h <= h[-1]).mean(), raw=True)
    k = kospi[kospi.index >= pos.index.min()]

    def sig(cond):
        first = cond & ~cond.shift(1, fill_value=False)
        out = []
        for d in pos.index[first.values]:
            if not out or (d - out[-1]).days > 20:
                out.append(d)
        return out
    lo, hi = sig(pos <= low), sig(pos >= high)
    base = base_stats(k)
    fl, fh = forward_stats(k, lo), forward_stats(k, hi)
    return {"pos": float(pos.iloc[-1]), "b5": float(b5.iloc[-1]), "date": pos.index[-1], "since": int(pos.index.min().year),
            "low_dates": lo, "high_dates": hi, "low_stats": fl, "high_stats": fh, "base": base,
            "low": fl["3개월"], "high": fh["3개월"]}


# ---------------------------------------------------------------- 미국: 금융 스트레스 (세인트루이스 연준)
def stress_state(stress: pd.DataFrame | None, hi: float = 1.0, lo: float = 0.0) -> dict | None:
    """STLFSI4: 0이 평균, 1 = 평균보다 1표준편차 높은 스트레스. 0 아래로 내려왔다가 다시 1을 넘은 첫 주를 신호로"""
    s = _series(stress, "value", where={"series": "STLFSI4"}) if stress is not None and len(stress) else pd.Series(dtype=float)
    if len(s) < 300:
        return None
    starts, armed = [], True
    for d, v in s.items():
        if armed and v >= hi:
            starts.append(d)
            armed = False
        elif not armed and v < lo:
            armed = True
    nfci = _series(stress, "value", where={"series": "NFCI"})
    peaks = {y: float(s[s.index.year == y].max()) for y in (2008, 2020) if (s.index.year == y).any()}
    return {"now": float(s.iloc[-1]), "date": s.index[-1], "starts": starts, "since": int(s.index.min().year),
            "recent": bool(starts and (s.index[-1] - starts[-1]).days <= 28), "peaks": peaks,
            "nfci": float(nfci.iloc[-1]) if len(nfci) else None}


def hy_official(fred_df: pd.DataFrame | None) -> dict | None:
    """공식 하이일드 스프레드 (ICE BofA, FRED). FRED가 최근 3년치만 줘서 위치는 그 안에서만 봐요"""
    s = _series(fred_df, "value", where={"series": "BAMLH0A0HYM2"}) if fred_df is not None and len(fred_df) else pd.Series(dtype=float)
    if len(s) < 60:
        return None
    return {"now": float(s.iloc[-1]), "date": s.index[-1], "pct": float((s <= s.iloc[-1]).mean()),
            "years": max(1, round((s.index[-1] - s.index[0]).days / 365))}


# ---------------------------------------------------------------- 데이터 받기
def cboe_hist(name: str) -> pd.Series:
    """CBOE 일별 종가 (SPX는 1975년~, VIX 1990년~, VIX3M 2009년~)"""
    import io
    r = requests.get(f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv",
                     headers=UA, timeout=30, allow_redirects=True)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df["DATE"] = pd.to_datetime(df["DATE"])
    col = "CLOSE" if "CLOSE" in df else df.columns[-1]
    return df.set_index("DATE")[col].astype(float).sort_index()


# ---------------------------------------------------------------- 체크리스트
def _row(key, group, title, state, now, what, how, stats=None, base=None, sample="", market=""):
    return {"key": key, "group": group, "title": title, "state": state, "now": now, "what": what, "how": how,
            "stats": stats, "base": base, "sample": sample, "market": market}


def _since_dates(dates, since_year):
    return [d for d in dates if pd.Timestamp(d).year >= since_year]


def checklist_us(spx: pd.Series | None, vix: pd.Series | None, vix3m: pd.Series | None, now_ratio: float | None,
                 breadth: pd.DataFrame | None, credit: pd.DataFrame | None, flow: dict | None = None,
                 fg: dict | None = None, fred_df: pd.DataFrame | None = None,
                 stress: pd.DataFrame | None = None) -> list[dict]:
    rows = []
    spx = _naive(spx) if spx is not None and len(spx) else None
    # ① 항복: 시장 폭 바닥
    w = washout(breadth)
    if w and spx is not None:
        on = w["active"] or (w["signals"] and (pd.Timestamp.now() - w["signals"][-1]).days <= 10)
        rows.append(_row("us_washout", "항복", "시장 폭 바닥 (50일선 위 종목 15% 아래)",
                         "켜짐" if on else "아직", f"S&P500 종목 중 50일선 위 {w['now']:.0%}",
                         "S&P500 500여 종목 중 50일 이동평균선 위에 있는 종목 비율이에요. 15% 아래면 거의 모든 종목이 무너진 '투매형 바닥' 상태예요.",
                         "바닥권 조건이에요. 이것만으로 반등 확인은 아니고, 아래 '반등 확인' 신호와 같이 봐요.",
                         forward_stats(spx, w["signals"]), base_stats(spx[spx.index >= f"{w['since']}-01-01"]),
                         f"{len(w['signals'])}번 · {w['since']}년~", "S&P500"))
        rows[-1].update(big=f"{w['now']:.0%}", rule="15% 아래로 떨어지면 켜짐",
                        say="거의 모든 종목이 무너진 투매형 바닥권이에요" if on else
                        f"아직 {w['now']:.0%}가 50일선 위 — 바닥권(15%)까지 {(w['now'] - 0.15) * 100:.0f}%p 남았어요")
    else:
        rows.append(_row("us_washout", "항복", "시장 폭 바닥 (50일선 위 종목 15% 아래)", "데이터 없음",
                         "S&P500 구성종목 기록을 쌓는 중", "", ""))
    # ① 항복: 개인 투매를 기관이 받기 (우리 체결 데이터, 통계는 아직)
    if flow:
        on = flow.get("capitulation")
        rows.append(_row("us_retail", "항복", "개인 투매를 기관이 받기 (SPY·QQQ)", "켜짐" if on else "아직",
                         flow.get("text", ""),
                         "레버리지·대표 ETF 체결에서 개인(1센트 미만 가격 개선)과 기관(20만 달러 넘는 대량 체결) 방향을 나눠 봐요.",
                         "개인이 평소보다 크게 팔고 기관이 사면 '항복 물량을 받아 가는' 모습이에요. 기록이 60거래일뿐이라 과거 통계는 아직 없어요.",
                         None, None, "기록 60거래일", "S&P500·나스닥"))
        r_ = flow.get("retail")
        rows[-1].update(big=(f"개인 {'매도' if r_ > 0 else '매수'} {abs(r_):.0%}" if r_ is not None else "–"),
                        rule="개인 매도 10%↑ + 기관 매수 5%↑면 켜짐",
                        say=("개인이 던진 물량을 기관이 받아 가는 중이에요" if on else
                             "개인은 크게 팔지만 기관이 사 주지 않아요" if r_ is not None and r_ > 0.10 else
                             "개인이 크게 던지는 날은 아니에요"))
    # ② 반등 확인: VIX 기간구조 역전 해소
    vt = vix_term(vix, vix3m, spx, now_ratio) if vix is not None and vix3m is not None else None
    if vt:
        st_ = "켜짐" if vt["resolved_recent"] else "진행 중" if vt["inverted"] else "아직"
        now = (f"VIX/VIX3M {vt['ratio']:.2f} · 역전 {vt['days']}일째" if vt["inverted"] else
               f"VIX/VIX3M {vt['ratio']:.2f} · 정상 (마지막 역전 {vt['last']['end']:%y.%m.%d} 해소)" if vt["last"] else
               f"VIX/VIX3M {vt['ratio']:.2f}")
        durs = vt.get("durations") or []
        how = ("평소엔 3개월 공포(VIX3M)가 1개월 공포(VIX)보다 커요. 당장 발등에 불이 떨어지면 뒤집히는데(역전), "
               "월가는 역전이 시작될 때가 아니라 다시 1 아래로 풀리는 때를 봐요.")
        if durs:
            how += f" 2009년 이후 역전은 보통 {int(np.median(durs))}일 이어졌고, 길게는 코로나 {max(durs)}일이었어요."
        rows.append(_row("vix_resolve", "확인", "VIX 기간구조 역전 해소", st_, now,
                         "1개월 공포 지수(VIX) ÷ 3개월 공포 지수(VIX3M)예요.", how,
                         vt.get("at_end"), vt.get("base"), f"{len(vt['episodes'])}번 · {vt['since']}년~", "S&P500"))
        rows[-1].update(big=f"{vt['ratio']:.2f}", rule="1 넘으면 공포 역전 · 다시 1 아래로 내려오면 켜짐",
                        say=("역전이 막 풀렸어요 — 월가가 기다리는 반등 확인이에요" if vt["resolved_recent"] else
                             f"단기 공포가 장기 공포보다 큰 '역전' {vt['days']}일째 — 1 아래로 내려와야 확인" if vt["inverted"] else
                             "역전 없음 — 단기 공포가 평소 수준이에요"))
        if vt.get("at_start"):
            rows[-1]["compare"] = ("역전이 시작된 날 샀다면", vt["at_start"])
    # ② 반등 확인: 브레스 스러스트
    bt = breadth_thrust(breadth)
    if bt and spx is not None:
        rows.append(_row("us_zbt", "확인", "브레스 스러스트 (츠바이크)",
                         "켜짐" if bt["recent"] else "진행 중" if bt["low10"] < 0.40 else "아직",
                         f"상승 종목 비율 10일 평균 {bt['now']:.0%} (최근 10일 최저 {bt['low10']:.0%})",
                         "S&P500 종목 중 오른 종목 비율의 10일 평균이 10거래일 안에 40% 아래에서 61.5% 위로 치솟는 것.",
                         "극단적 과매도에서 시장 전체가 한꺼번에 사자로 돌아서는 드문 신호라, 바닥 '확인'으로 써요. "
                         "원래 뉴욕증권거래소 전 종목으로 계산하는데 여기선 S&P500 구성종목으로 계산해요.",
                         forward_stats(spx, bt["signals"]), base_stats(spx[spx.index >= f"{bt['since']}-01-01"]),
                         f"{len(bt['signals'])}번 · {bt['since']}년~", "S&P500"))
        rows[-1].update(big=f"{bt['now']:.0%}", rule="10일 안에 40% 아래 → 61.5% 위로 치솟으면 켜짐",
                        say=("시장 전체가 한꺼번에 사자로 돌아섰어요 — 드문 반등 확인 신호" if bt["recent"] else
                             f"준비 조건(40% 아래)은 충족 · {(0.615 - bt['now']) * 100:.0f}%p 더 오르면 켜져요" if bt["low10"] < 0.40 else
                             "과매도 준비 조건(40% 아래)도 아직이에요"))
    else:
        rows.append(_row("us_zbt", "확인", "브레스 스러스트 (츠바이크)", "데이터 없음", "S&P500 구성종목 기록을 쌓는 중", "", ""))
    # 참고: 신용
    cs = credit_state(credit)
    hy = hy_official(fred_df)
    if cs:
        now = f"3개월 고점 대비 {cs['dd']:+.1%} · {cs['level']}"
        how = (f"주식 공포가 회사 부도 걱정(신용)까지 번졌는지 봐요. {cs['since']}년 이후 하위 10%({cs['p90']:+.1%}) 아래면 긴장, "
               f"하위 2%({cs['p98']:+.1%}) 아래면 항복 수준이에요. 신용이 멀쩡하면 아직 진짜 항복은 아니라고 봐요.")
        if hy:
            now += f" · 공식 하이일드 스프레드 {hy['now']:.2f}% ({hy['date']:%m/%d})"
            how += (f" 공식 스프레드(ICE BofA, FRED)는 최근 {hy['years']}년 중 낮은 쪽부터 {hy['pct']:.0%} 위치예요. "
                    "FRED가 최근 3년치만 줘서 과거 위기와의 비교는 HYG÷IEF로 해요.")
        rows.append(_row("credit", "참고", "신용 시장 (하이일드 채권 ÷ 국채)",
                         {"항복": "켜짐", "긴장": "진행 중", "평온": "아직"}[cs["level"]], now,
                         "HYG(하이일드 채권 ETF) ÷ IEF(중기 국채 ETF)가 3개월 고점에서 얼마나 빠졌는지예요.", how,
                         None, None, "", "미국 신용"))
        rows[-1].update(big=f"{cs['dd']:+.1%}", rule=f"긴장 {cs['p90']:+.1%} · 항복 {cs['p98']:+.1%} 아래",
                        say={"평온": "신용 시장은 멀쩡해요 — 공포가 부도 걱정까지 번지진 않았어요",
                             "긴장": "신용 시장도 긴장하기 시작했어요",
                             "항복": "신용 시장까지 무너진 진짜 공포 수준이에요"}[cs["level"]]
                        + (f" (공식 스프레드 {hy['now']:.2f}%)" if hy else ""))
    # 참고: 금융 스트레스 (연준)
    ss = stress_state(stress)
    if ss and spx is not None:
        peaks = " · ".join(f"{y}년 {v:.1f}" for y, v in ss["peaks"].items())
        rows.append(_row("stress", "참고", "금융 스트레스 지수 (세인트루이스 연준)",
                         "켜짐" if ss["now"] >= 1 else "진행 중" if ss["now"] >= 0 else "아직",
                         f"{ss['now']:+.2f} ({ss['date']:%m/%d} 주)" + (f" · 시카고 연준 NFCI {ss['nfci']:+.2f}" if ss["nfci"] is not None else ""),
                         "연준이 금리·신용 스프레드·변동성 등 18가지로 매주 만드는 금융시장 스트레스 지수예요. "
                         "0이 평균이고, 1이면 평균보다 1표준편차 높은 스트레스예요.",
                         "주가만 빠지고 이 지수가 낮으면 금융 시스템까지 겁먹은 건 아니에요"
                         + (f" (최고치: {peaks})" if peaks else "") + ". 표는 0 아래에서 다시 1을 처음 넘은 주에 샀다면이에요.",
                         forward_stats(spx, ss["starts"]), base_stats(spx[spx.index >= f"{ss['since']}-01-01"]),
                         f"{len(ss['starts'])}번 · {ss['since']}년~", "S&P500"))
        rows[-1].update(big=f"{ss['now']:+.2f}", rule="0이 평균 · 1 넘으면 스트레스",
                        say=("금융 시스템이 스트레스 구간이에요" if ss["now"] >= 1 else
                             "평균보다 높아지는 중이에요" if ss["now"] >= 0 else "금융 시스템은 평균보다 차분해요"))
    # 참고: CNN 공포탐욕 (백미러)
    if fg and fg.get("score") is not None:
        rows.append(_row("fg", "참고", "CNN 공포탐욕지수 (백미러)", "참고",
                         f"{fg['score']:.0f} · {RATING_KO.get(fg.get('rating'), fg.get('rating'))}"
                         + (f" (1주 전 {fg['week']:.0f})" if fg.get("week") is not None else ""),
                         "7가지 재료 중 5가지가 주가·VIX에서 나와요. 지난 한 달이 평소보다 얼마나 나빴는지를 보여줘요.",
                         "지난 한 달 주가와는 거의 같이 움직이지만 다음 한 달 주가와는 상관이 거의 없어요. "
                         "그래서 '공포가 크다'는 기록일 뿐, 바닥 신호로 세지 않아요.", None, None, "", "미국"))
        rows[-1].update(big=f"{fg['score']:.0f}", rule="0~100 · 25 아래 극단적 공포",
                        say="지난 한 달이 얼마나 나빴는지 보여주는 '백미러'라 개수에 안 넣어요")
    return rows


def checklist_kr(hist_market: pd.DataFrame | None, index: pd.DataFrame | None, breadth: pd.DataFrame | None,
                 vol_ep: pd.DataFrame | None = None, vol_now: pd.DataFrame | None = None,
                 etf_flow: pd.DataFrame | None = None) -> list[dict]:
    rows = []
    kospi = _series(index, "close", where={"market": "코스피"}) if index is not None and len(index) else pd.Series(dtype=float)
    ok = len(kospi) > 300

    def base_from(since):  # 비교 기준(아무 날)도 신호와 같은 기간으로
        return base_stats(kospi[kospi.index >= pd.Timestamp(f"{since}-01-01")])
    w = washout(breadth)
    if w and ok:
        on = w["active"] or (w["signals"] and (pd.Timestamp.now() - w["signals"][-1]).days <= 10)
        rows.append(_row("kr_washout", "항복", "시장 폭 바닥 (50일선 위 종목 15% 아래)", "켜짐" if on else "아직",
                         f"시총 상위 300 중 50일선 위 {w['now']:.0%}",
                         "코스피·코스닥 시총 상위 300 종목 중 50일 이동평균선 위에 있는 종목 비율이에요.",
                         "15% 아래면 거의 모든 종목이 무너진 투매형 바닥 상태예요. 바닥권 조건이고, 반등 확인은 아래 신호로 봐요.",
                         forward_stats(kospi, w["signals"]), base_from(w["since"]), f"{len(w['signals'])}번 · {w['since']}년~", "코스피"))
        rows[-1].update(big=f"{w['now']:.0%}", rule="15% 아래로 떨어지면 켜짐",
                        say="거의 모든 종목이 무너진 투매형 바닥권이에요" if on else
                        f"아직 {w['now']:.0%}가 50일선 위 — 바닥권(15%)까지 {(w['now'] - 0.15) * 100:.0f}%p 남았어요")
    else:
        rows.append(_row("kr_washout", "항복", "시장 폭 바닥 (50일선 위 종목 15% 아래)", "데이터 없음",
                         "시장 폭 기록을 쌓는 중", "", ""))
    bp = big_panic(hist_market)
    if bp and ok:
        rows.append(_row("kr_panic", "항복", "큰손 투매 정점 (평소의 3배 넘게 매도)", "켜짐" if bp["recent"] else "아직",
                         f"최근 5일 중 가장 센 날: 평소의 {bp['max5']:.1f}배 매도",
                         "외국인+기관이 직전 60거래일 평균 크기의 3배 넘게 순매도한 날이에요 (시총 상위 300 종목 합).",
                         "큰손이 한꺼번에 던지는 공포 정점에 가까운 날이에요. 과거엔 이런 날 뒤 몇 달 성적이 평소보다 나았지만, "
                         "그 뒤 더 빠진 경우도 있었어요(최악 값 참고).",
                         forward_stats(kospi, bp["signals"]), base_from(bp["since"]), f"{len(bp['signals'])}번 · {bp['since']}년~", "코스피"))
        rows[-1].update(big=f"{bp['max5']:.1f}배", rule="평소의 3배 넘게 팔면 켜짐 (최근 5일 중 최대)",
                        say=("큰손이 한꺼번에 던진 공포 정점이 나왔어요" if bp["recent"] else
                             f"가장 세게 판 날도 평소의 {bp['max5']:.1f}배 — 공포 정점(3배)은 아니에요"))
    fs = foreign_stop(hist_market)
    if fs and ok:
        rows.append(_row("kr_foreign", "참고", "외국인 매도 멈춤", "켜짐" if fs["recent"] else
                         "진행 중" if fs["run"] >= 5 else "아직",
                         f"외국인 연속 순매도 {fs['run']}일째 · 최근 5일 합 {fs['five']:,.0f}억" if fs["run"] else
                         f"오늘 외국인 순매수 · 최근 5일 합 {fs['five']:,.0f}억",
                         "외국인이 5일 넘게 연속으로, 그것도 최근 1년 중 센 쪽(하위 20%)으로 팔다가 처음 순매수로 돌아선 날이에요.",
                         "흔히 '외국인이 팔다 멈추면 반등'이라고 하는데, 2020년 이후 데이터로는 효과가 없어서 개수에 넣지 않고 참고로만 보여줘요.",
                         forward_stats(kospi, fs["signals"]), base_from(fs["since"]), f"{len(fs['signals'])}번 · {fs['since']}년~", "코스피"))
        rows[-1].update(big=f"{fs['run']}일째 매도" if fs["run"] else "순매수", rule="센 매도 5일+ 뒤 첫 순매수면 켜짐",
                        say=("외국인이 팔다가 멈췄어요" if fs["recent"] else
                             f"외국인이 {fs['run']}일째 팔고 있어요 (5일 합 {fs['five']:,.0f}억)" if fs["run"] else
                             "외국인이 오늘은 순매수예요"))
    bt = breadth_thrust(breadth)
    if bt and ok:
        rows.append(_row("kr_zbt", "확인", "브레스 스러스트 (한국)",
                         "켜짐" if bt["recent"] else "진행 중" if bt["low10"] < 0.40 else "아직",
                         f"상승 종목 비율 10일 평균 {bt['now']:.0%} (최근 10일 최저 {bt['low10']:.0%})",
                         "시총 상위 300 종목 중 오른 종목 비율의 10일 평균이 10거래일 안에 40% 아래에서 61.5% 위로 치솟는 것.",
                         "미국 츠바이크 신호를 한국 대형주에 같은 방식으로 적용했어요.",
                         forward_stats(kospi, bt["signals"]), base_from(bt["since"]), f"{len(bt['signals'])}번 · {bt['since']}년~", "코스피"))
        rows[-1].update(big=f"{bt['now']:.0%}", rule="10일 안에 40% 아래 → 61.5% 위로 치솟으면 켜짐",
                        say=("시장 전체가 한꺼번에 사자로 돌아섰어요 — 드문 반등 확인 신호" if bt["recent"] else
                             f"준비 조건(40% 아래)은 충족 · {(0.615 - bt['now']) * 100:.0f}%p 더 오르면 켜져요" if bt["low10"] < 0.40 else
                             "과매도 준비 조건(40% 아래)도 아직이에요"))
    else:
        rows.append(_row("kr_zbt", "확인", "브레스 스러스트 (한국)", "데이터 없음", "시장 폭 기록을 쌓는 중", "", ""))
    # ② 반등 확인: VKOSPI 공포 꺾임 (미국 VIX 기간구조 해소의 한국판)
    vs = vol_state(vol_ep, vol_now)
    if vs and ok:
        since = max(vs["since"], kospi.index.min())          # 코스피 기록이 있는 기간만 통계에
        starts = [d for d in vs["starts"] if d >= since]
        ends = [d for d in vs["ends"] if d >= since]
        st_ = "켜짐" if vs["resolved_recent"] else "진행 중" if vs["in_ep"] else "아직"
        now = f"VKOSPI {vs['vkospi']:.1f} ({vs['date']:%m/%d})"
        if vs["pct_all"] is not None:
            now += f" · {vs['since']:%Y}년 이후 높은 쪽 상위 {max(1 - vs['pct_all'], 0.01):.0%} (전체 중앙값 {vs['median_all']:.1f})"
        now += f" · 1년 중앙값 {vs['median']:.1f}의 {vs['ratio']:.2f}배"
        now += f" · 급등 {vs['days']}일째" if vs["in_ep"] else (f" · 마지막 급등 {vs['last_end']:%y.%m.%d} 꺾임" if vs["last_end"] is not None else "")
        ends_stats, kb = forward_stats(kospi, ends), base_from(since.year)
        works = effect(ends_stats, kb) == "과거 효과 있음"
        how = ("VKOSPI가 지난 1년 중앙값의 1.5배를 넘으면 옵션 시장에 공포가 몰린 '급등', 다시 1.2배 아래로 내려오면 "
               "'꺾임'으로 봐요. 미국 VIX 기간구조 역전·해소와 같은 생각인데, 한국엔 3개월물 공포 지수가 없어서 자기 평소 수준과 비교해요.")
        how += (" 과거에도 꺾인 뒤 성적이 아무 날보다 나아서 반등 확인으로 세요." if works else
                " 다만 한국에선 꺾인 날 산 성적이 아무 날보다 낫지 않았어요(아래 표, 급등 첫날 비교도 참고). "
                "그래서 반등 확인 개수에 넣지 않고 참고로만 보여줘요.")
        if vs["pct_all"] is not None and vs["pct_all"] >= 0.9 and vs["ratio"] < VOL_HI:
            how += " 지금은 절대 수준은 높지만 올해 내내 높았던 탓에 '평소 대비 급등'으로는 안 잡혀요."
        if vs["durations"]:
            how += f" {since.year}년 이후 급등은 보통 {int(np.median(vs['durations']))}거래일 이어졌어요."
        if vs["peak"] is not None:
            pk = vs["peak"]
            how += f" 가장 셌던 건 {pd.Timestamp(pk['start']):%Y년 %m월}에 시작한 급등(최고 {pk['peak']:.1f})이에요."
        rows.append(_row("kr_vkospi", "확인" if works else "참고", "VKOSPI 공포 꺾임", st_, now,
                         "코스피200 옵션 가격으로 계산한 한국판 VIX예요 (KRX 정보데이터, 전 거래일 확정치).", how,
                         ends_stats, kb, f"{len(ends)}번 · {since.year}년~", "코스피"))
        rows[-1]["compare"] = ("급등 첫날 샀다면", forward_stats(kospi, starts))
        rows[-1].update(big=f"{vs['vkospi']:.1f}", rule="1년 중앙값의 1.5배↑ 급등 → 1.2배↓로 꺾이면 켜짐",
                        say=(f"공포 급등 {vs['days']}일째 (1년 중앙값의 {vs['ratio']:.2f}배)" if vs["in_ep"] else
                             "급등했던 공포가 막 꺾였어요" if vs["resolved_recent"] else
                             f"2010년 이후로는 상위 {max(1 - vs['pct_all'], 0.01):.0%}로 높지만, 올해 내내 높아 평소 대비 {vs['ratio']:.2f}배 — 급등 아님"
                             if vs["pct_all"] is not None and vs["pct_all"] >= 0.9 else
                             f"평소(1년 중앙값 {vs['median']:.1f}) 대비 {vs['ratio']:.2f}배 — 급등 아님"))
    elif vol_now is not None:
        rows.append(_row("kr_vkospi", "확인", "VKOSPI 공포 꺾임", "데이터 없음", "VKOSPI 기록을 쌓는 중 (KRX)", "", ""))
    # 참고: 레버리지·곱버스 쏠림 (개인 베팅 방향)
    eb = etf_bet(etf_flow, index)
    if eb:
        p = eb["pos"]
        where = f"상위 {max(1 - p, 0.01):.0%}" if p >= 0.5 else f"하위 {max(p, 0.01):.0%}"
        rows.append(_row("kr_etf", "참고", "레버리지·곱버스 쏠림 (개인 베팅)",
                         "켜짐" if p <= 0.10 else "아직",
                         f"상승 베팅 5일 순유입 {eb['b5']:+,.0f}억 ({eb['date']:%m/%d}) · 지난 1년 중 {where}",
                         "레버리지 ETF로 들어온 돈 − 인버스·곱버스로 들어온 돈(상장좌수 변화 × NAV)을 5일 합한 거예요. "
                         "개인 거래 비중이 높은 상품이라 개인이 어느 쪽에 거는지 보여줘요 (KRX 정보데이터).",
                         "표는 하락 베팅 쪽으로 크게 기운 첫날(1년 중 하위 10%)에 샀다면이에요. "
                         "반대로 과거 폭락 5번은 모두 개인이 레버리지를 크게 산(상위 5%) 무렵이었어요. "
                         "어느 쪽이든 그 뒤 성적이 아무 날과 크게 다르지 않아서 개수에 넣지 않아요.",
                         eb["low_stats"], eb["base"], f"{len(eb['low_dates'])}번 · {eb['since']}년~", "코스피"))
        rows[-1]["compare"] = ("상승 베팅 쏠림(상위 10%) 첫날 샀다면", eb["high_stats"])
        rows[-1].update(big=f"{eb['b5']:+,.0f}억", rule="5일 합이 1년 중 하위 10%(하락 베팅 쏠림)면 켜짐",
                        say=(f"하락 베팅 쪽으로 크게 기울었어요 (1년 중 {where})" if p <= 0.10 else
                             f"레버리지로 크게 몰렸어요 (1년 중 {where}) — 과거 폭락 때 흔한 모습" if p >= 0.9 else
                             f"5일 동안 상승 베팅 쪽으로 {eb['b5']:+,.0f}억 — 1년 기준 평소 범위({where})"))
    return rows


def with_effect(rows: list[dict]) -> list[dict]:
    for r in rows:
        r["effect"] = effect(r.get("stats"), r.get("base"))
    return rows


def verdict(rows: list[dict]) -> tuple[str, str, dict]:
    cnt = {g: (sum(r["state"] == "켜짐" for r in rows if r["group"] == g),
               sum(r["state"] != "데이터 없음" for r in rows if r["group"] == g)) for g in ("항복", "확인")}
    cap, con = cnt["항복"][0], cnt["확인"][0]
    going = any(r["state"] == "진행 중" for r in rows if r["group"] == "확인")
    if con:
        t = "반등 확인 신호가 켜졌어요"
        d = "월가가 바닥 대신 기다리는 '반등 확인' 신호가 나왔어요. 아래 과거 통계도 같이 보세요."
    elif cap:
        t = "항복은 나왔고, 반등 확인은 아직"
        d = "투매형 바닥 조건은 보이지만, 반등을 확인해 주는 신호는 아직이에요."
    else:
        t = "아직 바닥 확인 전"
        d = "공포가 커도 항복·반등 확인 신호는 아직 안 나왔어요. 공포가 크다는 것만으로는 바닥이라고 보지 않아요."
    if going:
        d += " 지금 진행 중인 신호가 있어요(풀리는지 지켜볼 것)."
    return t, d, cnt
