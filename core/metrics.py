"""원자료(MarketData) → 그룹별 지표·점수. 앱과 수집기가 같이 씁니다."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from . import config
from . import news as newsmod
from . import realtime
from . import retail_flow as rf
from .scoring import Indicator, caption_for, composite, fixed, interpret, percentile, score

ET = "America/New_York"


@dataclass
class MarketData:
    now: datetime
    market_open: bool = False
    bars: pd.DataFrame = field(default_factory=pd.DataFrame)     # ts, sym, c, v, vw (SIP 15분봉)
    rt: pd.DataFrame = field(default_factory=pd.DataFrame)       # sym, price, chg, rvol (IEX 실시간)
    retail: pd.DataFrame = field(default_factory=pd.DataFrame)   # bucket, sym, retail_buy, retail_sell
    vix_hist: pd.Series | None = None
    vix3m_hist: pd.Series | None = None
    vix_now: float | None = None
    vix3m_now: float | None = None
    putcall_hist: pd.Series | None = None
    putcall_now: float | None = None
    putcall_intraday: bool = False
    st_now: dict = field(default_factory=dict)                   # sym → {msgs_per_hour, bear_ratio..}
    st_hist: pd.DataFrame = field(default_factory=pd.DataFrame)
    news: pd.DataFrame = field(default_factory=pd.DataFrame)
    score_hist: pd.DataFrame = field(default_factory=pd.DataFrame)
    errors: dict = field(default_factory=dict)
    demo: bool = False


@dataclass
class Result:
    key: str
    name: str
    panic: float | None
    bad_news: float | None
    headline: str
    detail: str
    etf: str
    price: float | None
    chg: float | None
    flow_chg: float | None
    session_label: str
    indicators: dict[str, Indicator]
    news_ind: Indicator | None
    retail_today: pd.DataFrame
    headlines: pd.DataFrame
    members: pd.DataFrame
    breadth: dict


# ---------------------------------------------------------------- 시세 계열 (SIP 15분봉)
def _session_bars(bars: pd.DataFrame) -> pd.DataFrame:
    if bars is None or bars.empty:
        return pd.DataFrame(columns=["ts", "sym", "c", "v", "vw", "date", "tod"])
    b = bars.copy()
    et = pd.to_datetime(b["ts"], utc=True).dt.tz_convert(ET)
    b["date"] = et.dt.date
    b["tod"] = et.dt.hour * 60 + et.dt.minute
    return b[(b["tod"] >= 570) & (b["tod"] < 960)]


def volume_metrics(sb: pd.DataFrame, main: str, inv: str | None):
    """(SIP 상대거래량, 과거 값들, 인버스 비율, 과거 값들, 기준 날짜)"""
    m = sb[sb["sym"] == main]
    if m.empty:
        return None
    today = m["date"].max()
    cut = m.loc[m["date"] == today, "tod"].max()
    syms = [main] + ([inv] if inv else [])
    upto = sb[(sb["tod"] <= cut) & (sb["sym"].isin(syms))]
    vol = upto.pivot_table(index="date", columns="sym", values="v", aggfunc="sum")
    past = vol.index[vol.index < today][-config.BASELINE_DAYS:]
    mv = vol.loc[past, main].mean() if len(past) else np.nan
    ok = bool(mv and mv > 0)
    rvol = float(vol.loc[today, main] / mv) if ok else None
    rhist = list((vol.loc[past, main] / mv).values) if ok else []
    inv_v, inv_hist = None, []
    if inv and inv in vol:
        d = upto.assign(d=upto["v"] * upto["vw"]).pivot_table(index="date", columns="sym", values="d",
                                                              aggfunc="sum")
        if inv in d and main in d:
            ratio = d[inv] / d[main]
            inv_v = float(ratio.get(today, np.nan))
            inv_hist = list(ratio.loc[past].values)
    last = m[m["date"] == today].sort_values("tod")["c"]
    prev = m[m["date"] < today].sort_values(["date", "tod"])["c"]
    sip_chg = float(last.iloc[-1] / prev.iloc[-1] - 1) if len(last) and len(prev) else None
    return rvol, rhist, inv_v, inv_hist, today, sip_chg


# ---------------------------------------------------------------- 개인 수급
def retail_metrics(retail: pd.DataFrame, sym: str, today):
    if retail is None or retail.empty or today is None:
        return None, [], pd.DataFrame()
    r = retail[retail["sym"] == sym].copy() if "sym" in retail else pd.DataFrame()
    if r.empty:
        return None, [], pd.DataFrame()
    r["bucket"] = pd.to_datetime(r["bucket"], utc=True)
    r = r.sort_values("bucket").drop_duplicates("bucket", keep="last")
    r["date"] = r["bucket"].dt.tz_convert(ET).dt.date
    parts = []
    for _, g in r.groupby("date"):
        g = g.copy()
        g["roll"] = rf.rolling_ratio(g)
        tot = (g["retail_sell"] + g["retail_buy"]).where(lambda x: x > 0)
        g["net"] = (g["retail_sell"] - g["retail_buy"]) / tot
        parts.append(g)
    r = pd.concat(parts)
    t = r[r["date"] == today]
    hist = r[r["date"] < today].tail(config.BASELINE_DAYS * 26)["roll"].dropna().tolist()
    value = float(t["roll"].dropna().iloc[-1]) if t["roll"].notna().any() else None
    return value, hist, t


# ---------------------------------------------------------------- 뉴스
def news_metrics(df: pd.DataFrame, now: datetime):
    if df is None or df.empty:
        return None, None, {}
    cur = newsmod.current(df, now)
    h = newsmod.hourly(df[df["ts"] < pd.Timestamp(now).floor("h")])
    near = h
    if not h.empty:
        hod = now.hour
        near = h[h["hour"].dt.hour.isin([(hod + d) % 24 for d in (-2, -1, 0, 1, 2)])]
        near = near[near["hour"].dt.dayofweek < 5]
    base = near["count"].mean() if len(near) else None
    ratio = cur["count"] / base if base else None
    s_cnt = percentile(cur["count"], near["count"].tolist()) if len(near) >= 20 else fixed(ratio, "news_count")
    nn = near[near["count"] >= 3]
    s_neg = (percentile(cur["neg_share"], nn["neg_share"].tolist()) if len(nn) >= 20
             else fixed(cur["neg_share"], "news_neg"))
    if cur["count"] < 2:
        s_neg = 0.0 if s_neg is None else s_neg * 0.3
    parts = [x for x in (s_cnt, s_neg) if x is not None]
    bad = float(np.mean(parts)) if parts else None
    return bad, dict(cur, base=base, ratio=ratio), {"count": s_cnt, "neg": s_neg}


def fmt_pct(x, sign: bool = True) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x * 100:+.0f}%" if sign else f"{x * 100:.0f}%"


def _rt_row(rt: pd.DataFrame, sym: str) -> dict:
    if rt is None or rt.empty or "price" not in rt:
        return {}
    r = rt[rt["sym"] == sym]
    return {} if r.empty else {k: (None if pd.isna(v) else v) for k, v in r.iloc[0].to_dict().items()}


# ---------------------------------------------------------------- 그룹 하나
def build_group(m: MarketData, key: str, sb: pd.DataFrame | None = None) -> Result:
    g = config.GROUPS[key]
    flow, inv = g["flow"], g.get("inv")
    sb = _session_bars(m.bars) if sb is None else sb
    inds: dict[str, Indicator] = {}
    etf_rt, flow_rt = _rt_row(m.rt, g["etf"]), _rt_row(m.rt, flow)

    vm = volume_metrics(sb, flow, inv)
    today = None
    if vm:
        rvol_sip, rhist, inv_v, inv_hist, today, sip_chg = vm
        rvol, delay = rvol_sip, "15분 지연"
        if flow_rt.get("live") and flow_rt.get("rvol"):
            rvol, delay = flow_rt["rvol"], "실시간 추정"
        chg = flow_rt.get("chg") if flow_rt.get("chg") is not None else sip_chg
        sc, mth = score(rvol, rhist, "volume")
        if sc is not None and (chg is None or chg >= 0):
            sc = min(sc, 40.0)  # 오르는 날 거래량은 투매가 아님
        inds["volume"] = Indicator(
            "volume", f"{flow} 거래량", rvol, f"{rvol:.1f}배" if rvol else "–", sc, mth, caption_for(sc, mth),
            f"지금 시각까지 쌓인 {flow} 오늘 거래량이 평소 같은 시각의 몇 배인지예요. 장중에는 IEX 실시간 체결로 추정해요.",
            "하락하면서 2배 이상이면 던지는 물량이 많다는 뜻이에요. 오르는 날의 거래량은 점수를 낮게 줘요.",
            delay)
        if inv:
            ok = inv_v is not None and not np.isnan(inv_v)
            sc, mth = score(inv_v if ok else None, inv_hist, "inverse")
            inds["inverse"] = Indicator(
                "inverse", f"{inv} 갈아타기", inv_v, f"{inv_v:.2f}" if ok else "–", sc, mth, caption_for(sc, mth),
                f"반대로 움직이는 {inv} 거래대금 ÷ {flow} 거래대금이에요.",
                f"높아질수록 {flow}를 던지고 하락 쪽으로 갈아타는 사람이 많다는 뜻이에요.", "15분 지연")

    rv, rh, rtoday = retail_metrics(m.retail, flow, today)
    sc, mth = score(rv, rh, "retail")
    inds["retail"] = Indicator(
        "retail", f"{flow} 개인 순매도", rv, fmt_pct(rv), sc, mth, caption_for(sc, mth),
        "최근 1시간 동안 개인으로 추정되는 체결 중 매도가 얼마나 더 많았는지예요. +면 파는 쪽, -면 사는 쪽이에요.",
        "거래소 밖에서 1센트 미만 단위로 체결된 주문(개인 주문의 흔적)을 매수·매도로 나눠요. 평소보다 크게 +로 치우치면 개인 투매예요.",
        "15분 지연")

    # 구성 종목 전반
    br = realtime.breadth(m.rt, g["members"])
    if br.get("n"):
        sc = fixed(br["dump_share"], "breadth")
        inds["breadth"] = Indicator(
            "breadth", "종목 전반 투매", br["dump_share"], f"{br['dump']}/{br['n']}개", sc, "고정 눈금",
            f"하락 {br['down']}개 · 평균 {fmt_pct(br['avg_chg'])}",
            f"구성 종목 {br['n']}개 중 {abs(config.BREADTH_DROP) * 100:.0f}% 넘게 빠지면서 거래량이 평소의 {config.BREADTH_RVOL}배를 넘은 종목 수예요.",
            "한두 종목이 아니라 섹터 전체에서 동시에 던지면 숫자가 커져요. 절반 가까이면 섹터 투매예요.",
            "실시간 추정")

    if g.get("market"):
        if m.vix_hist is not None and m.vix3m_hist is not None and len(m.vix_hist):
            rh_ = (m.vix_hist / m.vix3m_hist).dropna().tail(252)
            vnow = m.vix_now or float(m.vix_hist.iloc[-1])
            v3 = m.vix3m_now or float(m.vix3m_hist.iloc[-1])
            vr = vnow / v3 if v3 else None
            sc, mth = score(vr, rh_.tolist(), "vix")
            inds["vix"] = Indicator(
                "vix", "단기 공포 (VIX/VIX3M)", vr, f"{vr:.2f}" if vr else "–", sc, mth, caption_for(sc, mth),
                "앞으로 1개월 공포(VIX) ÷ 3개월 공포(VIX3M)예요.",
                "보통은 1보다 작아요. 1을 넘으면 당장의 공포가 더 크다는 뜻이라 패닉 구간이에요.",
                "15분 지연" if m.vix_now else "전일 종가", {"vix": vnow, "vix3m": v3})
        if m.putcall_now is not None or (m.putcall_hist is not None and len(m.putcall_hist)):
            pc = m.putcall_now if m.putcall_now is not None else float(m.putcall_hist.iloc[-1])
            hist = m.putcall_hist.tail(config.BASELINE_DAYS).tolist() if m.putcall_hist is not None else []
            sc, mth = score(pc, hist, "putcall")
            inds["putcall"] = Indicator(
                "putcall", "풋/콜 비율", pc, f"{pc:.2f}", sc, mth, caption_for(sc, mth),
                "미국 주식 옵션에서 하락 베팅(풋) 거래량 ÷ 상승 베팅(콜) 거래량이에요.",
                "평소 0.6 안팎이에요. 0.9~1을 넘으면 하락 대비 수요가 몰린 공포 구간이에요.",
                "30분 단위" if m.putcall_intraday else "전일 확정치")

    soc = g.get("social")
    if soc and m.st_now.get(soc):
        s_now = m.st_now[soc]
        hist = m.st_hist[m.st_hist["sym"] == soc] if "sym" in m.st_hist else pd.DataFrame()
        br_, mph = s_now.get("bear_ratio"), s_now.get("msgs_per_hour")
        sb_, mb = score(br_, hist["bear_ratio"].tolist() if "bear_ratio" in hist else None, "bear")
        vel = None
        if "msgs_per_hour" in hist and hist["msgs_per_hour"].dropna().size >= 10:
            med = hist["msgs_per_hour"].dropna().median()
            vel = mph / med if med else None
        sv = percentile(mph, hist["msgs_per_hour"].tolist()) if "msgs_per_hour" in hist else None
        if sv is None:
            sv = fixed(vel, "velocity")
        parts = [(x, w) for x, w in ((sb_, 0.6), (sv, 0.4)) if x is not None]
        sc = sum(x * w for x, w in parts) / sum(w for _, w in parts) if parts else None
        cap = caption_for(sc, mb)
        if vel:
            cap = f"글 속도 {vel:.1f}배 · " + (cap.split(" · ")[-1] if " · " in cap else cap)
        inds["social"] = Indicator(
            "social", f"Stocktwits {soc}", br_, f"약세 {fmt_pct(br_, False)}" if br_ is not None else "태그 부족",
            sc, mb, cap,
            f"미국 개인투자자 커뮤니티 Stocktwits의 {soc} 글 중 약세 태그 비율과 글 올라오는 속도예요.",
            "약세 비율이 50%를 넘고 글이 평소보다 몇 배 빨리 올라오면 사람들이 겁먹은 상태예요.",
            "실시간", {"msgs_per_hour": mph, "velocity": vel})

    gnews = newsmod.for_symbols(m.news, g["members"] + [g["etf"], flow])
    bad, ninfo, nsc = news_metrics(gnews, m.now)
    news_ind = None
    if ninfo:
        r_ = ninfo.get("ratio")
        news_ind = Indicator(
            "news", "악재 뉴스", bad, f"{ninfo['count']}건", bad, "",
            (f"평소의 {r_:.1f}배 · " if r_ else "") + f"악재 {fmt_pct(ninfo['neg_share'], False)}",
            "최근 1시간 이 그룹 종목 뉴스 건수와, 그중 악재 헤드라인 비율이에요.",
            "투매 점수는 높은데 악재 점수가 낮으면 '뉴스 없는 투매' → 심리성 과매도일 가능성이 커요.",
            "실시간", dict(ninfo, **nsc))

    panic = composite(inds)
    chg = etf_rt.get("chg")
    title, detail = interpret(panic, bad, chg)
    label = ""
    day = etf_rt.get("day") or today
    if day is not None:
        label = "실시간" if m.market_open else f"{day.month}월 {day.day}일 장 마감 기준"
    mem = m.rt[m.rt["sym"].isin(g["members"])].copy() if m.rt is not None and "chg" in m.rt else pd.DataFrame()
    if len(mem):
        mem = mem.sort_values("chg", na_position="last")
    heads = gnews.head(6) if gnews is not None and not gnews.empty else pd.DataFrame()
    return Result(key, g["name"], panic, bad, title, detail, g["etf"], etf_rt.get("price"), chg,
                  flow_rt.get("chg"), label, inds, news_ind, rtoday, heads, mem, br)


def build_all(m: MarketData) -> dict[str, Result]:
    sb = _session_bars(m.bars)
    return {k: build_group(m, k, sb) for k in config.GROUPS}


def market_summary(res: dict[str, Result]) -> dict:
    idx = [res[k] for k in config.INDEX_KEYS if res[k].panic is not None]
    panic = float(np.mean([r.panic for r in idx])) if idx else None
    bads = [r.bad_news for r in idx if r.bad_news is not None]
    bad = float(np.mean(bads)) if bads else None
    chg = res["spx"].chg if "spx" in res else None
    title, detail = interpret(panic, bad, chg)
    hot = sorted([res[k] for k in config.SECTOR_KEYS if res[k].panic is not None], key=lambda r: -r.panic)
    return {"panic": panic, "bad": bad, "title": title, "detail": detail, "hot": hot[:3]}
