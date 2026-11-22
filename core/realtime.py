"""알파카 무료 IEX 실시간 데이터로 '지금' 상대 거래량과 등락률을 추정합니다.

IEX는 전체 거래량의 일부지만 종목별 비중이 꽤 일정합니다. 그래서
  실시간 상대거래량 = 오늘 IEX 거래량 ÷ (최근 20일 IEX 하루 평균 × 지금까지 하루 거래량이 보통 몇 % 찼는지)
로 계산하면 전체 시장 기준 상대거래량과 거의 비슷하게 나옵니다.
'지금까지 몇 % 찼는지'(장중 거래량 분포)는 SIP 15분봉으로 구합니다. 장 초반·막판에 몰리는 U자 모양이에요.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from . import config

ET = "America/New_York"
OPEN_MIN, CLOSE_MIN = 9 * 60 + 30, 16 * 60
DEFAULT_PROFILE = np.linspace(0, 1, 27) ** 0.85  # 분포를 못 구했을 때 대충 쓰는 값


def volume_profile(bars15: pd.DataFrame) -> np.ndarray:
    """장 시작부터 15분 단위로 하루 거래량이 누적 몇 % 찼는지 (27개 값, 0→1)"""
    if bars15 is None or bars15.empty:
        return DEFAULT_PROFILE
    b = bars15.copy()
    et = pd.to_datetime(b["ts"], utc=True).dt.tz_convert(ET)
    b["date"] = et.dt.date
    b["k"] = ((et.dt.hour * 60 + et.dt.minute) - OPEN_MIN) // 15
    b = b[(b["k"] >= 0) & (b["k"] < 26)]
    full = b.groupby(["sym", "date"])["k"].transform("nunique") == 26  # 온전한 날만
    b = b[full]
    if b.empty:
        return DEFAULT_PROFILE
    piv = b.pivot_table(index=["sym", "date"], columns="k", values="v", aggfunc="sum").fillna(0)
    frac = piv.cumsum(axis=1).div(piv.sum(axis=1), axis=0)
    prof = np.concatenate([[0.0], frac.median().values])
    return np.maximum.accumulate(np.clip(prof, 0, 1))


def profile_at(profile: np.ndarray, minutes_since_open: float) -> float:
    x = np.clip(minutes_since_open / 15.0, 0, 26)
    return float(max(np.interp(x, np.arange(27), profile), 0.02))


def _et_date(ts) -> object:
    return pd.Timestamp(ts).tz_convert(ET).date()


def rt_table(snaps: dict, daily_sip: pd.DataFrame, daily_iex: pd.DataFrame, symbols: list[str],
             profile: np.ndarray, now: datetime, market_open: bool) -> pd.DataFrame:
    """종목별 현재가·등락률·실시간 상대거래량"""
    rows = []
    sip = daily_sip.copy() if daily_sip is not None and not daily_sip.empty else pd.DataFrame(
        columns=["ts", "sym", "c", "v"])
    iex = daily_iex.copy() if daily_iex is not None and not daily_iex.empty else pd.DataFrame(
        columns=["ts", "sym", "c", "v"])
    for d in (sip, iex):
        if len(d):
            d["date"] = pd.to_datetime(d["ts"], utc=True).dt.tz_convert(ET).dt.date
    now_et = pd.Timestamp(now).tz_convert(ET)
    mins = now_et.hour * 60 + now_et.minute - OPEN_MIN
    for sym in symbols:
        sn = (snaps or {}).get(sym) or {}
        db = sn.get("dailyBar") or {}
        lt = sn.get("latestTrade") or {}
        if not db:
            rows.append({"sym": sym})
            continue
        bar_day = _et_date(db["t"])
        live_today = market_open and bar_day == now_et.date()
        price = float(lt.get("p") or db["c"]) if live_today else float(db["c"])
        s = sip[(sip["sym"] == sym) & (sip["date"] < bar_day)] if len(sip) else sip
        prev = float(s.sort_values("date")["c"].iloc[-1]) if len(s) else (
            float((sn.get("prevDailyBar") or {}).get("c") or np.nan))
        i = iex[(iex["sym"] == sym) & (iex["date"] < bar_day)] if len(iex) else iex
        avg_iex = float(i.sort_values("date")["v"].tail(config.RVOL_DAYS).mean()) if len(i) else np.nan
        frac = profile_at(profile, mins) if live_today else 1.0
        rvol = float(db["v"]) / (avg_iex * frac) if avg_iex and avg_iex > 0 else np.nan
        rows.append({"sym": sym, "price": price, "prev": prev,
                     "chg": price / prev - 1 if prev and prev == prev else np.nan,
                     "rvol": rvol, "iex_vol": float(db["v"]), "day": bar_day, "live": live_today})
    return pd.DataFrame(rows)


def breadth(rt: pd.DataFrame, members: list[str]) -> dict:
    t = rt[rt["sym"].isin(members)].dropna(subset=["chg"]) if rt is not None and len(rt) and "chg" in rt else pd.DataFrame()
    n = len(t)
    if n == 0:
        return {"n": 0}
    down = int((t["chg"] < 0).sum())
    dump = int(((t["chg"] <= config.BREADTH_DROP) & (t["rvol"] >= config.BREADTH_RVOL)).sum())
    return {"n": n, "down": down, "dump": dump, "dump_share": dump / n,
            "avg_chg": float(t["chg"].mean())}
