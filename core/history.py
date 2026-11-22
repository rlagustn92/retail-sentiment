"""역사 속 지금: 지금 공포 수준을 과거 큰 폭락 때와 비교해요.

시장 전체 공포(VIX)는 1990년부터 같은 방식으로 계산돼서 시대가 달라도 비교할 만해요.
개인 수급은 2019년 수수료 무료화, 2020년 개인 투자자 급증, 0DTE 옵션 등장으로 구조가 크게 바뀌어서
과거와 직접 비교하지 않아요.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# (이름, 시작, 끝) — 이 기간 VIX 종가 최고치를 비교해요
EVENTS = [
    ("1998 LTCM 사태", "1998-08-01", "1998-10-31"),
    ("2001 9·11 테러", "2001-09-10", "2001-10-31"),
    ("2002 닷컴 버블 바닥", "2002-07-01", "2002-10-31"),
    ("2008 리먼 사태", "2008-09-01", "2008-12-31"),
    ("2010 플래시 크래시", "2010-05-01", "2010-06-30"),
    ("2011 미국 신용등급 강등", "2011-08-01", "2011-10-31"),
    ("2015 위안화 쇼크", "2015-08-10", "2015-09-30"),
    ("2018 변동성 쇼크", "2018-02-01", "2018-02-28"),
    ("2018 연말 급락", "2018-12-01", "2018-12-31"),
    ("2020 코로나 폭락", "2020-02-20", "2020-04-30"),
    ("2022 금리 인상 하락장", "2022-01-01", "2022-10-31"),
    ("2024 엔캐리 청산", "2024-07-25", "2024-08-20"),
    ("2025 관세 쇼크", "2025-03-25", "2025-05-15"),
]


def _naive(s: pd.Series) -> pd.Series:
    s = s.dropna().astype(float)
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.Series(s.values, index=idx).sort_index()


def compare(vix: pd.Series | None, vix3m: pd.Series | None, now_vix: float | None = None,
            now_ratio: float | None = None) -> dict | None:
    """과거 사건별 VIX(·VIX/VIX3M) 최고치와 지금 값의 위치"""
    if vix is None or len(vix) < 250:
        return None
    v = _naive(vix)
    ratio = None
    if vix3m is not None and len(vix3m):
        ratio = (v / _naive(vix3m)).dropna()
    rows = []
    for name, a, b in EVENTS:
        w = v[(v.index >= a) & (v.index <= b)]
        if w.empty:
            continue
        rw = ratio[(ratio.index >= a) & (ratio.index <= b)] if ratio is not None else pd.Series(dtype=float)
        rows.append({"name": name, "vix": float(w.max()), "date": w.idxmax(),
                     "ratio": float(rw.max()) if len(rw) else None})
    now = float(now_vix) if now_vix else float(v.iloc[-1])
    pct = float((v < now).mean() * 100)                     # 1990년 이후 하루하루 중 지금보다 낮았던 날 비율
    below = sorted([r for r in rows if r["vix"] < now], key=lambda r: -r["vix"])
    above = sorted([r for r in rows if r["vix"] >= now], key=lambda r: r["vix"])
    return {"rows": rows, "now": now, "now_ratio": now_ratio, "pct": pct, "since": int(v.index.min().year),
            "max": float(max([r["vix"] for r in rows] + [now])),
            "just_below": below[0] if below else None, "next_above": above[0] if above else None,
            "year_max": float(v[v.index >= v.index.max() - pd.Timedelta(days=365)].max())}


def summary(c: dict) -> str:
    if not c:
        return ""
    top = 100 - c["pct"]
    rank = f"상위 {top:.0f}%" if top >= 1 else "가장 높은 1% 안"
    s = f"지금 VIX {c['now']:.1f}는 {c['since']}년 이후 거래일 중 {rank} 수준이에요."
    lo, hi = c["just_below"], c["next_above"]
    if lo and hi:
        s += f" 과거 폭락 때 최고치와 비교하면 '{lo['name']}'(최고 {lo['vix']:.0f})보다 높고 '{hi['name']}'(최고 {hi['vix']:.0f})보다 낮아요."
    elif hi:
        s += f" 아래 폭락들의 최고치보다는 아직 낮아요. 가장 가까운 건 '{hi['name']}'(최고 {hi['vix']:.0f}) 수준이에요."
    else:
        s += " 아래 비교한 모든 폭락의 최고치보다 높아요."
    return s


def bar_width(x: float, mx: float) -> float:
    return float(np.clip(x / mx * 100, 2, 100)) if mx else 0.0
