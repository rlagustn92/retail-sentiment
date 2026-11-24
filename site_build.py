"""GitHub Pages용 정적 페이지 만들기 — pages 워크플로가 수집할 때마다 실행해요.

    python site_build.py --data data --out site

Streamlit 앱(app.py)과 같은 계산(core·ui)을 쓰고, 화면만 HTML 파일로 내보내요.
서버가 없어서 열자마자 뜨고, 탭 전환도 브라우저 안에서 바로 돼요. 숫자는 수집 시각 기준이에요.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd

import ui
from core import bottom, cboe, config, history, kr, krx, sources
from core import news as newsmod
from core.alpaca import Alpaca
from core.finra import freshness as finra_fresh
from core.metrics import ET, MarketData, build_all, market_summary, side_metrics
from core.scoring import level
from core.store import LocalStore

KST = "Asia/Seoul"
NOW = datetime.now(timezone.utc)
SHORT = {"retail": "개인 순매도", "volume": "거래량", "inverse": "인버스", "social": "Stocktwits",
         "putcall": "풋/콜", "vix": "VIX/VIX3M", "breadth": "종목 전반", "short": "장외 공매도",
         "credit": "하이일드", "retail_etf": "본체 ETF 개인", "inst": "기관 대량 매도"}
AXIS = dict(labelColor="#8b95a1", titleColor="#8b95a1", gridColor="rgba(139,149,161,0.15)",
            domain=False, ticks=False, labelFontSize=12,
            labelFont="Pretendard Variable, Pretendard, -apple-system, sans-serif")
STREAMLIT = "https://tusimcheck.streamlit.app"


# ------------------------------------------------------------------ 공통
def safe(err: dict, name: str, fn, *args, default=None):
    try:
        return fn(*args)
    except Exception as e:
        err[name] = f"{type(e).__name__}: {str(e)[:120]}"
        return default


def _ts(x):
    if x is None:
        return None
    t = pd.Timestamp(x)
    if pd.isna(t):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t


def ago(t) -> str:
    """페이지는 만들어 둔 뒤에 보니까 '몇 분 전' 대신 시각을 적어요"""
    t = _ts(t)
    if t is None:
        return "–"
    k = t.tz_convert(KST)
    return f"{k:%H:%M}" if k.date() == pd.Timestamp(NOW).tz_convert(KST).date() else f"{k:%m/%d %H:%M}"


def state(t, limit_min: float, open_now: bool) -> str:
    t = _ts(t)
    if t is None:
        return "없음"
    age = (pd.Timestamp(NOW) - t).total_seconds() / 60
    if not open_now:
        return "장 마감" if age < 4 * 24 * 60 else "멈춤"
    return "정상" if age <= limit_min else "지연" if age <= limit_min * 3 else "멈춤"


def links(h: str) -> str:
    """Streamlit 주소(?m=…, ?g=…)를 정적 파일 이름으로"""
    h = h.replace('href="?m=kr&k=all"', 'href="kr.html"')
    h = re.sub(r'href="\?m=kr&(?:amp;)?k=([\w-]+)"', r'href="kr-\1.html"', h)
    h = h.replace('href="?m=kr"', 'href="kr.html"').replace('href="?m=bottom"', 'href="bottom.html"')
    h = h.replace('href="?"', 'href="index.html"').replace('href="?g=all"', 'href="index.html"')
    return re.sub(r'href="\?g=([\w-]+)"', r'href="us-\1.html"', h)


EXTRA_CSS = """<style>
body{margin:0;background:var(--bg);color:var(--text);font-family:'Pretendard Variable',Pretendard,-apple-system,BlinkMacSystemFont,system-ui,sans-serif;-webkit-font-smoothing:antialiased;}
.wrap{max-width:600px;margin:0 auto;padding:14px 16px 48px;}
.card{background:var(--card);border-radius:24px;padding:22px 20px;margin-bottom:12px;overflow:hidden;}
.chart{width:100%;margin-top:6px;}
.seg{display:flex;gap:6px;margin:4px 0 8px;flex-wrap:wrap;}
.seg button{font:inherit;font-size:14px;font-weight:700;padding:7px 13px;border-radius:12px;border:0;background:var(--chip);color:var(--sub);cursor:pointer;}
.seg button.on{background:var(--text);color:var(--bg);}
.pane{display:none;}.pane.on{display:block;}
.mkt,.nav{margin-bottom:10px;}
.upd{display:flex;justify-content:flex-end;align-items:center;gap:8px;font-size:12px;color:var(--faint);font-weight:600;margin:-2px 4px 8px;}
.upd button{font:inherit;font-size:12px;font-weight:800;padding:5px 11px;border-radius:10px;border:0;background:var(--card);color:var(--sub);cursor:pointer;}
</style>"""
# GitHub Pages는 페이지를 최대 10분 캐시해요 → 주소에 시각을 붙여 늘 최신을 받아요.
# 열어 둔 화면은 5분마다, 다른 앱에 갔다 5분 넘어 돌아오면 바로 새로 읽어요.
REFRESH_JS = """<script>var T0=Date.now();function rf(){location.replace(location.pathname+'?t='+Date.now());}
setInterval(function(){if(!document.hidden)rf();},300000);
document.addEventListener('visibilitychange',function(){if(!document.hidden&&Date.now()-T0>300000)rf();});</script>"""


class Page:
    def __init__(self, title: str):
        self.title, self.parts, self.charts = title, [], []

    def add(self, *htmls: str):
        self.parts.append("".join(h for h in htmls if h))

    def card(self, *htmls: str):
        self.parts.append('<div class="card">' + "".join(h for h in htmls if h) + "</div>")

    def chart(self, ch) -> str:
        if ch is None:
            return ""
        cid = f"c{len(self.charts)}"
        spec = ch.to_dict()
        spec["width"] = "container"
        spec["autosize"] = {"type": "fit-x", "contains": "padding"}
        self.charts.append((cid, spec))
        return f'<div id="{cid}" class="chart"></div>'

    def html(self) -> str:
        js = ""
        if self.charts:
            js = ('<script src="https://cdn.jsdelivr.net/npm/vega@6"></script>'
                  '<script src="https://cdn.jsdelivr.net/npm/vega-lite@6.4.1"></script>'
                  '<script src="https://cdn.jsdelivr.net/npm/vega-embed@7"></script><script>'
                  + "".join(f"vegaEmbed('#{cid}',{json.dumps(spec, ensure_ascii=False, default=str)},"
                            "{actions:false,renderer:'svg'}).catch(()=>{});" for cid, spec in self.charts)
                  + "</script>")
        seg_js = """<script>window.R={k:'종목',w:'외국인',s:'순매도'};function seg(g,v){document.querySelectorAll('.seg[data-g="'+g+'"] button').forEach(b=>b.classList.toggle('on',b.dataset.v==v));R[g]=v;document.querySelectorAll('.pane').forEach(p=>p.classList.toggle('on',p.dataset.k==R.k&&p.dataset.w==R.w&&p.dataset.s==R.s));}</script>"""
        body = links("".join(self.parts))
        return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                f'<title>{ui.esc(self.title)} · 개인투심체크</title>'
                f'<link rel="manifest" href="manifest.webmanifest"><link rel="icon" href="icon.svg">'
                f'<link rel="apple-touch-icon" href="icon-192.png"><meta name="theme-color" content="#191f28">'
                f'<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">'
                f'<meta name="apple-mobile-web-app-title" content="투심체크">'
                f'{ui.CSS}{EXTRA_CSS}</head><body><div class="wrap">{body}</div>{seg_js}{REFRESH_JS}{js}</body></html>')


def next_update() -> str:
    """수집 순환 시각표상 다음 수집 + 페이지 만드는 데 걸리는 몇 분"""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from keeper import next_due
    k = pd.Timestamp(next_due(NOW) + timedelta(minutes=4)).tz_convert(KST)
    return f"{k:%H:%M}" if k.date() == pd.Timestamp(NOW).tz_convert(KST).date() else f"{k:%m/%d %H:%M}"


def top(live: bool) -> str:
    return (ui.top(pd.Timestamp(NOW).tz_convert(KST).strftime("%m/%d %H:%M 기준"), live)
            + f'<div class="upd">다음 갱신 {next_update()}쯤 <button onclick="rf()">새로고침</button></div>')


def last_run(runs: pd.DataFrame, prefix: tuple) -> dict:
    if runs is None or runs.empty or "mode" not in runs:
        return {}
    r = runs[runs["mode"].astype(str).str.startswith(prefix)].sort_values("ts")
    return {} if r.empty else r.iloc[-1].to_dict()


def run_row(runs, prefix, name):
    r = last_run(runs, prefix)
    if not r:
        return []
    return [{"name": name, "basis": f"{ago(r['ts'])} · {r['mode']}",
             "state": "정상" if str(r.get("ok")) in ("True", "true", "1") else "멈춤",
             "note": ("" if pd.isna(r.get("note")) else str(r.get("note")))[:60]}]


# ------------------------------------------------------------------ 차트 (app.py와 같은 모양)
def trend_chart(hist, groups, panic, now, live):
    df = pd.DataFrame(columns=["ts", "panic"])
    if hist is not None and not hist.empty and "group" in hist:
        h = hist[hist["group"].isin(groups)].copy()
        if len(h):
            h["ts"] = pd.to_datetime(h["ts"], utc=True)
            day = h["ts"].dt.tz_convert(ET).dt.date.max()
            h = h[h["ts"].dt.tz_convert(ET).dt.date == day]
            df = h.groupby("ts", as_index=False)["panic"].mean()
    if panic is not None and live:
        df = pd.concat([df, pd.DataFrame({"ts": [pd.Timestamp(now)], "panic": [panic]})])
    if len(df) < 2:
        return None
    df["t"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(KST).dt.tz_localize(None)
    _, color = level(panic if panic is not None else df["panic"].iloc[-1])
    base = alt.Chart(df).encode(
        x=alt.X("t:T", title=None, axis=alt.Axis(format="%H:%M", **AXIS, tickCount=5)),
        y=alt.Y("panic:Q", title=None, scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(values=[0, 40, 70, 100], **AXIS)))
    area = base.mark_area(color=color, opacity=0.12, interpolate="monotone")
    line = base.mark_line(color=color, strokeWidth=3, interpolate="monotone")
    pt = alt.Chart(df.tail(1)).mark_circle(size=90, color=color).encode(x="t:T", y="panic:Q")
    rules = alt.Chart(pd.DataFrame({"y": [40, 70]})).mark_rule(strokeDash=[4, 4], color="#8b95a1", opacity=0.5).encode(y="y:Q")
    return (area + line + rules + pt).properties(height=170, background="transparent").configure_view(strokeWidth=0)


def flow_chart(flow: dict):
    parts = []
    for key, label in (("inst_today", f"기관 · {flow.get('etf', '')}"), ("retail_today", "개인")):
        d = flow.get(key)
        if d is None or d.empty or "roll" not in d:
            continue
        x = d.dropna(subset=["roll"])
        parts.append(pd.DataFrame({"t": x["bucket"].dt.tz_convert(KST).dt.tz_localize(None), "v": -x["roll"] * 100, "who": label}))
    if not parts:
        return None
    df = pd.concat(parts, ignore_index=True)
    if df["t"].nunique() < 2:
        return None
    who = list(dict.fromkeys(df["who"]))
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#8b95a1", opacity=0.5).encode(y="y:Q")
    line = alt.Chart(df).mark_line(strokeWidth=3, interpolate="monotone", point=alt.OverlayMarkDef(size=28)).encode(
        x=alt.X("t:T", title=None, axis=alt.Axis(format="%H:%M", **AXIS, tickCount=5)),
        y=alt.Y("v:Q", title=None, axis=alt.Axis(**AXIS, format="+.0f", tickCount=4)),
        color=alt.Color("who:N", scale=alt.Scale(domain=who, range=["#7c5cff", "#f5a524"][:len(who)]),
                        legend=alt.Legend(orient="top", title=None, labelColor="#8b95a1", labelFontSize=12)),
        tooltip=[alt.Tooltip("t:T", title="시각", format="%H:%M"), alt.Tooltip("who:N", title="누가"),
                 alt.Tooltip("v:Q", title="1시간 순매수 %", format="+.1f")])
    return (zero + line).properties(height=190, background="transparent").configure_view(strokeWidth=0)


def retail_chart(rt):
    if rt is None or rt.empty or "net" not in rt:
        return None
    df = rt.dropna(subset=["net"]).copy()
    if df.empty:
        return None
    df["buy_pct"] = -df["net"] * 100
    df["t"] = df["bucket"].dt.tz_convert(KST).dt.strftime("%H:%M")
    df["side"] = df["buy_pct"].map(lambda v: "매수 우위" if v >= 0 else "매도 우위")
    return alt.Chart(df[["t", "buy_pct", "side"]]).mark_bar(cornerRadius=4, size=12).encode(
        x=alt.X("t:N", title=None, sort=None, axis=alt.Axis(**AXIS, labelAngle=0, labelOverlap=True)),
        y=alt.Y("buy_pct:Q", title=None, axis=alt.Axis(**AXIS, format="+.0f", tickCount=4)),
        color=alt.Color("side:N", scale=alt.Scale(domain=["매수 우위", "매도 우위"], range=["#f04452", "#3182f6"]), legend=None),
        tooltip=[alt.Tooltip("t:N", title="시각"), alt.Tooltip("buy_pct:Q", title="개인 순매수 %", format="+.1f")],
    ).properties(height=170, background="transparent").configure_view(strokeWidth=0)


def kr_flow_chart(intra, market):
    if intra is None or intra.empty or "market" not in intra:
        return None
    d = intra[intra["market"] == market].copy()
    if d.empty:
        return None
    d["t"] = pd.to_datetime(d["ts"], utc=True).dt.tz_convert(KST)
    d = d[d["t"].dt.date == d["t"].dt.date.max()]
    if len(d) < 2:
        return None
    long = d.melt(id_vars=["t"], value_vars=["foreign", "inst", "personal"], var_name="who", value_name="v")
    long["who"] = long["who"].map({"foreign": "외국인", "inst": "기관", "personal": "개인"})
    long["t"] = long["t"].dt.tz_localize(None)
    return alt.Chart(long).mark_line(strokeWidth=3, interpolate="monotone").encode(
        x=alt.X("t:T", title=None, axis=alt.Axis(format="%H:%M", **AXIS, tickCount=5)),
        y=alt.Y("v:Q", title=None, axis=alt.Axis(**AXIS, format=",.0f", tickCount=4)),
        color=alt.Color("who:N", scale=alt.Scale(domain=["외국인", "기관", "개인"], range=["#7c5cff", "#00a3bf", "#f5a524"]),
                        legend=alt.Legend(orient="top", title=None, labelColor="#8b95a1", labelFontSize=12)),
        tooltip=[alt.Tooltip("t:T", title="시각", format="%H:%M"), alt.Tooltip("who:N", title="누가"),
                 alt.Tooltip("v:Q", title="누적 순매수(억원)", format=",.0f")],
    ).properties(height=190, background="transparent").configure_view(strokeWidth=0)


def bars2(d: pd.DataFrame, cols: dict, colors: list[str], fmt="%m/%d"):
    """날짜별 두 묶음 막대 (억원)"""
    long = d.melt(id_vars=["date"], value_vars=list(cols), var_name="who", value_name="v")
    long["who"] = long["who"].map(cols)
    dom = list(cols.values())
    return alt.Chart(long).mark_bar(cornerRadius=2).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format=fmt, **AXIS, tickCount=6)),
        xOffset="who:N",
        y=alt.Y("v:Q", title=None, axis=alt.Axis(**AXIS, format=",.0f", tickCount=4)),
        color=alt.Color("who:N", scale=alt.Scale(domain=dom, range=colors),
                        legend=alt.Legend(orient="top", title=None, labelColor="#8b95a1", labelFontSize=12)),
        tooltip=[alt.Tooltip("date:T", title="날짜", format="%m/%d"), alt.Tooltip("who:N", title="누가"),
                 alt.Tooltip("v:Q", title="억원", format=",.0f")],
    ).properties(height=190, background="transparent").configure_view(strokeWidth=0)


def kr_daily_chart(daily):
    if daily is None or len(daily) < 2:
        return None
    d = daily.reset_index().rename(columns={"index": "date"})
    d["date"] = pd.to_datetime(d["date"])
    return bars2(d, {"big": "큰손(외국인+기관)", "personal": "개인"}, ["#7c5cff", "#f5a524"])


def kr_etf_chart(flow, days=40):
    t = krx.flow_table(flow)
    if t is None:
        return None
    piv = t[0].tail(days)
    d = pd.DataFrame({"date": piv.index, "up": piv[[g for g in krx.UP_GROUPS if g in piv]].sum(axis=1).values,
                      "down": piv[[g for g in krx.DOWN_GROUPS if g in piv]].sum(axis=1).values})
    return bars2(d, {"up": "레버리지(상승)", "down": "인버스·곱버스(하락)"}, ["#e5484d", "#3e63dd"])


# ------------------------------------------------------------------ 바닥 신호 (미국·한국)
def us_flow_state(r: pd.DataFrame) -> dict | None:
    if r is None or r.empty or "inst_buy" not in r:
        return None
    today = pd.to_datetime(r["bucket"], utc=True).dt.tz_convert(ET).dt.date.max()
    parts, cap = [], False
    for etf, lev in (("SPY", "SPXL"), ("QQQ", "TQQQ")):
        ins = side_metrics(r, etf, today, "inst")
        rets = [x["day"] for x in (side_metrics(r, lev, today, "retail"), side_metrics(r, etf, today, "retail"))
                if x and x["day"] is not None]
        if not ins or ins["day"] is None or not rets:
            continue
        rd = sum(rets) / len(rets)
        if rd > 0.10 and ins["day"] < -0.05:
            cap = True
        parts.append(f"{etf}: 개인 {'매도' if rd > 0 else '매수'} {abs(rd):.0%} · 기관 {'매도' if ins['day'] > 0 else '매수'} {abs(ins['day']):.0%}")
    return {"capitulation": cap, "text": f"{today.month}/{today.day} " + " / ".join(parts)} if parts else None


def bottom_data(S, err) -> dict:
    spx, vix, v3 = (safe(err, "CBOE", bottom.cboe_hist, n) for n in ("SPX", "VIX", "VIX3M"))
    vn = {"vix_now": safe(err, "VIX", cboe.index_quote, "VIX"), "vix3m_now": safe(err, "VIX", cboe.index_quote, "VIX3M")}
    ratio = vn["vix_now"] / vn["vix3m_now"] if vn["vix_now"] and vn["vix3m_now"] else None
    fg = safe(err, "CNN 공포탐욕", bottom.fear_greed)
    us_rows = bottom.with_effect(bottom.checklist_us(spx, vix, v3, ratio, S("us_breadth"), S("us_credit"),
                                                     safe(err, "미국 수급", us_flow_state, S("retail")), fg,
                                                     S("fred"), S("us_stress")))
    kr_rows = bottom.with_effect(bottom.checklist_kr(S("kr_hist_market"), S("kr_index"), S("kr_breadth"),
                                                     S("kr_vol_ep"), S("kr_vol_now"), S("kr_etf_flow")))

    def last(name, col="date", where=None):
        df = S(name)
        if df.empty or col not in df:
            return None
        if where:
            df = df[df[where[0]] == where[1]]
        return pd.to_datetime(df[col]).max() if len(df) else None
    ut, ud, uc = bottom.verdict(us_rows)
    kt, kd, kc = bottom.verdict(kr_rows)
    return {"us": {"rows": us_rows, "title": ut, "desc": ud, "cnt": uc},
            "kr": {"rows": kr_rows, "title": kt, "desc": kd, "cnt": kc}, "fg": fg,
            "dates": {"spx": spx.index.max() if spx is not None else None, "us_breadth": last("us_breadth"),
                      "kr_breadth": last("kr_breadth"), "kr_hist": last("kr_hist_market"), "vkospi": last("kr_vol_now"),
                      "hy": last("fred", where=("series", "BAMLH0A0HYM2")), "stress": last("us_stress", where=("series", "STLFSI4"))}}


def page_bottom(b: dict) -> Page:
    p = Page("바닥 신호")
    p.add(top(False), ui.market_switch("bottom"))
    p.card(ui.bottom_hero(b["fg"], b["us"], b["kr"]))
    p.card(ui.signal_rows(b["us"]["rows"], "🇺🇸 미국", "S&P500 기준 · 신호마다 '과거에 이 신호 뒤엔 어땠나'를 아무 날과 비교"))
    p.card(ui.signal_rows(b["kr"]["rows"], "🇰🇷 한국", "코스피 기준 · 수급·시장 폭은 2020년, VKOSPI는 2010년 이후 기록으로 계산",
                          {"title": b["kr"]["title"], "desc": b["kr"]["desc"]}))
    d = b["dates"]

    def dd(x):
        return "–" if x is None or pd.isna(x) else f"{pd.Timestamp(x):%m/%d}"
    rows = [{"name": "S&P500·VIX (CBOE)", "basis": f"{dd(d['spx'])} 종가까지", "state": "정상" if d["spx"] is not None else "없음",
             "note": "VIX 기간구조는 페이지 만들 때 값(15분 지연) 포함"},
            {"name": "미국 시장 폭 (S&P500 503종목)", "basis": f"{dd(d['us_breadth'])}까지",
             "state": "정상" if d["us_breadth"] is not None else "없음", "note": "매일 미국 장 마감 뒤 이어 붙여요"},
            {"name": "한국 수급·시장 폭 (2020~)", "basis": f"수급 {dd(d['kr_hist'])} · 시장 폭 {dd(d['kr_breadth'])}까지",
             "state": "정상" if d["kr_hist"] is not None else "없음", "note": "매일 한국 장 마감 뒤(16:17) 이어 붙여요"},
            {"name": "VKOSPI (KRX Open API)", "basis": f"{dd(d['vkospi'])} 확정치까지", "state": "정상" if d["vkospi"] is not None else "없음",
             "note": "KRX가 하루 뒤에 줘요 (아침 8:37·오후 4:17에 받아요)"},
            {"name": "하이일드 스프레드 · 금융 스트레스 (FRED)", "basis": f"스프레드 {dd(d['hy'])} · 스트레스 {dd(d['stress'])} 주까지",
             "state": "정상" if d["hy"] is not None or d["stress"] is not None else "없음", "note": "스프레드는 매일, 스트레스 지수는 매주"},
            {"name": "CNN 공포탐욕", "basis": "페이지 만들 때 받아요", "state": "정상" if b["fg"] else "없음", "note": ""}]
    rows += krx.expiry_rows()
    p.card(ui.data_status(rows))
    p.add(ui.footer([
        "월가 체크리스트를 우리가 무료로 구할 수 있는 데이터로 옮긴 거예요. BofA 펀드매니저 현금 비중, 골드만 패닉 지수, CTA 포지션처럼 기관 내부 자료는 빠져 있어요.",
        "과거 통계는 표본이 적고 미래를 보장하지 않아요. 매수·매도 신호가 아니라 지금이 과거의 어떤 상황과 닮았는지 보는 참고예요.",
        "시장 폭은 지금 S&P500·시총 상위 300 종목으로 과거를 계산해서 그 사이 빠진 종목은 안 들어가 있어요(생존 편향).",
        "VKOSPI·레버리지 자금 흐름: KRX 정보데이터시스템(한국거래소 Open API) 자료를 이용했어요. 하이일드 스프레드: ICE BofA US High Yield Index OAS "
        "(ICE Data Indices, LLC), 금융 스트레스: St. Louis Fed Financial Stress Index · Chicago Fed NFCI — 모두 FRED에서 받아요."]))
    return p


# ------------------------------------------------------------------ 미국
def us_market(S, err) -> MarketData | None:
    key, sec = os.environ.get("ALPACA_KEY"), os.environ.get("ALPACA_SECRET")
    if not key or not sec:
        return None
    a = Alpaca(key, sec, min_interval=0.36, retries=3)
    clock = safe(err, "장 시간", a.clock, default={}) or {}
    is_open = bool(clock.get("is_open"))
    bars = safe(err, "시세(15분봉)", sources.fetch_bars15, a, NOW)
    bars = bars if bars is not None else pd.DataFrame(columns=["ts", "sym", "c", "v", "vw"])
    snaps = safe(err, "실시간 시세", sources.fetch_snapshots, a, default={}) or {}
    dsip = safe(err, "일봉", sources.fetch_daily, a, NOW, "sip", default=pd.DataFrame())
    diex = safe(err, "일봉", sources.fetch_daily, a, NOW, "iex", default=pd.DataFrame())
    rt = sources.rt_from(snaps, dsip, diex, bars, NOW, is_open)
    vix = safe(err, "VIX", sources.fetch_vix, default={}) or {}
    pc = S("putcall")
    pc_now = safe(err, "풋/콜", cboe.equity_putcall_intraday) if is_open else None
    st_hist = S("stocktwits")
    st_now = {}
    if not st_hist.empty and "sym" in st_hist:
        for sym in config.social_symbols():
            h = st_hist[st_hist["sym"] == sym].sort_values("ts")
            if len(h) and pd.Timestamp(NOW) - h["ts"].iloc[-1] < pd.Timedelta(minutes=40):
                st_now[sym] = {k: h[k].iloc[-1] for k in ("msgs_per_hour", "bull", "bear", "bear_ratio")}
    return MarketData(now=NOW, market_open=is_open, bars=bars, rt=rt, retail=S("retail"),
                      vix_hist=vix.get("vix_hist"), vix3m_hist=vix.get("vix3m_hist"),
                      vix_now=vix.get("vix_now"), vix3m_now=vix.get("vix3m_now"),
                      putcall_hist=pc.set_index("date")["equity_pc"].sort_index() if not pc.empty else None,
                      putcall_now=pc_now, putcall_intraday=pc_now is not None, st_now=st_now, st_hist=st_hist,
                      news=newsmod.merge(S("news")), score_hist=S("score"), finra=S("finra"), fred=S("fred"), errors=err)


def us_status(m: MarketData, runs) -> list[dict]:
    open_ = m.market_open
    rb = m.retail["bucket"].max() if m.retail is not None and not m.retail.empty and "bucket" in m.retail else None
    nw = m.news["ts"].max() if m.news is not None and not m.news.empty else None
    fr = m.finra["date"].max() if m.finra is not None and not m.finra.empty else None
    rows = [{"name": "시세·거래량 (알파카)", "basis": f"{ago(NOW)} 페이지 만들 때", "state": "정상", "note": "장중 15분 지연(SIP)·실시간(IEX)"},
            {"name": "개인·기관 체결 수급", "basis": f"마지막 구간 {ago(rb)}", "state": state(rb, 50, open_), "note": "15분 지연 + 수집기 15분마다"},
            {"name": "뉴스 (알파카·Finnhub)", "basis": ago(nw), "state": state(nw, 120, open_), "note": ""},
            {"name": "FINRA 장외 공매도", "basis": f"{_ts(fr):%m/%d} 거래일" if fr is not None else "–",
             "state": finra_fresh(fr, NOW), "note": "미국 저녁 6시쯤 그날 파일이 나와요 (한국 아침 8시 반쯤 받아요)"}]
    return rows + run_row(runs, ("intraday", "daily", "backfill", "breadth"), "미국 수집기 마지막 실행")


def snap_label(lbl: str | None) -> str:
    """Streamlit의 '실시간'은 페이지에선 만든 시각 기준이라 시각으로 바꿔 적어요"""
    if not lbl:
        return "장 대기"
    return lbl.replace("실시간", f"{pd.Timestamp(NOW).tz_convert(KST):%H:%M} 기준")


def us_pages(m: MarketData, res: dict, b: dict | None, runs) -> dict[str, Page]:
    sm = market_summary(res)
    items = [("all", "전체", sm["panic"])] + [(k, config.GROUPS[k]["name"], res[k].panic)
                                              for k in config.INDEX_KEYS + config.SECTOR_KEYS]
    status = ui.data_status(us_status(m, runs))
    notes = ["투매 지수는 상황 판단을 돕는 참고 지표예요. 매수·매도 신호가 아니에요.",
             "수집기가 돌 때마다(장중 15분) 페이지를 새로 만들어요. 열어 둔 화면은 5분마다 새로 읽어요.",
             f"섹터 개인 수급을 지금 바로 다시 계산해 보려면 Streamlit 버전: {STREAMLIT}"]
    if m.errors:
        notes.append("못 받은 데이터: " + ", ".join(sorted(set(m.errors))))
    pages = {}
    # 전체
    p = Page("미국")
    p.add(top(m.market_open), ui.market_switch("us"), ui.nav("all", items))
    if b:
        p.add(ui.bottom_badge(b["us"], b["kr"]))
    spx = res["spx"]
    p.card(ui.market_hero(sm["panic"], sm["title"], sm["detail"], sm["hot"], snap_label(spx.session_label), sm["inst"], sm["inst_hot"]))
    idx_flow = [res[k] for k in config.INDEX_KEYS if res[k].flow]
    if idx_flow:
        p.card(ui.flow_summary(idx_flow, sm["inst_hot"]))
    ch = trend_chart(m.score_hist, config.INDEX_KEYS, sm["panic"], m.now, m.market_open)
    if ch is not None:
        p.card(ui.section("시장 투매 지수 흐름", "S&P500·나스닥 평균 · 점선: 경계 40 · 투매 70"), p.chart(ch))
    sec = sorted([res[k] for k in config.SECTOR_KEYS], key=lambda r: -(r.panic if r.panic is not None else -1))
    p.card(ui.section("섹터별 투매 지도", "점수 높은 순 · 누르면 섹터 상세") + ui.tiles(sec))
    p.card(ui.section("지수") + ui.index_rows([res[k] for k in config.INDEX_KEYS]))
    mk = [spx.indicators[k] for k in ("vix", "putcall", "credit") if k in spx.indicators]
    if mk:
        p.card(ui.indicator_rows(mk, "시장 전체 공포", "모든 지수에 공통으로 반영돼요"))
    vx = spx.indicators.get("vix")
    hc = history.compare(m.vix_hist, m.vix3m_hist, (vx.extra or {}).get("vix") if vx else None, vx.value if vx else None)
    if hc:
        p.card(ui.history_card(hc, history.summary(hc)))
    p.card(status)
    p.add(ui.footer(notes))
    pages["index.html"] = p
    # 그룹별
    for k in config.INDEX_KEYS + config.SECTOR_KEYS:
        r, g = res[k], config.GROUPS[k]
        p = Page(r.name)
        p.add(top(m.market_open), ui.market_switch("us"), ui.nav(k, items))
        tops = sorted([i for i in r.indicators.values() if i.score is not None and i.score >= 60], key=lambda i: -i.score)[:3]
        p.card(ui.hero(r.panic, r.headline, r.detail, r.price, r.chg, r.bad_news, snap_label(r.session_label),
                       [(SHORT.get(i.key, i.title), i.display) for i in tops], title=r.name, etf=r.etf, flow=g["flow"],
                       flow_chg=r.flow_chg, inst=r.inst))
        if r.flow:
            p.card(ui.flow_card(r.flow, r.inst), p.chart(flow_chart(r.flow)))
        ch = trend_chart(m.score_hist, [k], r.panic, m.now, m.market_open)
        if ch is not None:
            p.card(ui.section(f"{r.name} 투매 지수 흐름", "15분마다 기록 · 점선: 경계 40 · 투매 70"), p.chart(ch))
        order = ["retail", "retail_etf", "volume", "breadth", "inverse", "short", "social", "vix", "putcall", "credit"]
        inds = [r.indicators[x] for x in order if x in r.indicators]
        if r.inst_ind:
            inds.insert(0, r.inst_ind)
        if r.news_ind:
            inds.append(r.news_ind)
        p.card(ui.indicator_rows(inds))
        p.card(ui.members(r.members, r.breadth, config.name))
        rc = retail_chart(r.retail_today)
        p.card(ui.section(f"{g['flow']} 개인 순매수 흐름", "15분 단위 · 빨강 매수 우위 · 파랑 매도 우위 · 15분 지연"),
               p.chart(rc) if rc is not None else '<div class="empty">장이 열리면 15분 뒤부터 표시돼요</div>')
        p.card(ui.news_list(r.headlines, lambda ts: ago(ts)))
        p.card(status)
        p.add(ui.footer(notes))
        pages[f"us-{k}.html"] = p
    return pages


# ------------------------------------------------------------------ 한국
def kr_trends(cache: Path, live: bool, err: dict) -> pd.DataFrame:
    """섹터 대표 종목 60일 수급(네이버): 장중 20분, 그 밖엔 3시간 동안 다시 쓰기"""
    f = cache / "kr_trends.pkl"
    if f.exists() and time.time() - f.stat().st_mtime < (20 * 60 if live else 3 * 3600):
        try:
            return pickle.loads(f.read_bytes())
        except Exception:
            pass
    t = safe(err, "섹터 수급", kr.all_trends, default=pd.DataFrame())
    if t is not None and len(t):
        cache.mkdir(parents=True, exist_ok=True)
        f.write_bytes(pickle.dumps(t))
    return t if t is not None else pd.DataFrame()


def kr_pages(S, err, b: dict | None, runs, cache: Path) -> dict[str, Page]:
    mk = []
    for mkt in kr.MARKETS:
        x = safe(err, "지수 수급", kr.index_now, mkt)
        if x:
            mk.append(kr.market_summary(x, S("kr_market")))
    live = any(x.get("status") == "OPEN" for x in mk)
    trends = kr_trends(cache, live, err)
    hist_sec = S("kr_hist_sector")
    secs = [s for s in (kr.sector_summary(k, trends, hist_sec) for k in kr.SECTORS) if s] if len(trends) else []
    now_kst = pd.Timestamp(NOW).tz_convert(KST)
    items = [("all", "전체", None)] + [(s["key"], s["name"], s["big_score"]) for s in secs]

    def nav(cur):
        return ui.nav(cur, items).replace('href="?g=', 'href="?m=kr&k=')
    # 데이터 상태
    rows = []
    if mk:
        rows.append({"name": "지수 수급 (네이버)", "basis": ("장중 잠정 " if live else "장 마감 ") + ago(mk[0].get("time")),
                     "state": "정상" if mk[0].get("time") is not None else "없음", "note": "페이지 만들 때 받아요"})
    ki = S("kr_intraday")
    kt = ki["ts"].max() if len(ki) else None
    rows.append({"name": "장중 기록 (10분마다)", "basis": ago(kt), "state": state(kt, 25, live), "note": "코스피 장중 그래프"})
    rk = S("kr_rank")
    rc = rk["collected"].iloc[0] if len(rk) and "collected" in rk else None
    rows.append({"name": "누가 뭘 팔고 샀나 (순위표)", "basis": (f"{pd.to_datetime(rk['date']).max():%m/%d} 기준 · {ago(rc)} 수집" if rc is not None else "–"),
                 "state": state(rc, 75, live), "note": "장중 1시간마다 · 장 마감 뒤 16:17"})
    if secs:
        rows.append({"name": "섹터 수급 (종목별 일별)", "basis": f"{secs[0]['date']:%m/%d} 거래일", "state": "정상", "note": "장중 20분마다 다시 받아요"})
    hmk = S("kr_hist_market")
    if len(hmk):
        rows.append({"name": "과거 수급 기록 (2020~)", "basis": f"{pd.to_datetime(hmk['date']).max():%m/%d}까지", "state": "정상",
                     "note": "매일 장 마감 뒤 이어 붙여요"})
    ef = S("kr_etf_flow")
    if len(ef):
        rows.append({"name": "레버리지·곱버스 자금 흐름 (KRX)", "basis": f"{pd.to_datetime(ef['date']).max():%m/%d} 확정치까지",
                     "state": "정상", "note": "KRX가 하루 뒤에 줘요 (아침 8:37·오후 4:17에 받아요)"})
    rows += krx.expiry_rows()
    rows += run_row(runs, ("kr",), "한국 수집기 마지막 실행")
    status = ui.data_status(rows)
    notes = ["네이버 증권 공개 데이터예요. 지수 수급은 장중 잠정치, 섹터 수급은 대표 종목들의 일별 투자자 순매수를 더한 값이에요.",
             "레버리지·곱버스 자금 흐름: KRX 정보데이터시스템(한국거래소 Open API) 자료로 계산했어요.",
             "수급 판정은 상황 판단을 돕는 참고예요. 매수·매도 신호가 아니에요."]
    if err:
        notes.append("못 받은 데이터: " + ", ".join(sorted(err)))
    pages = {}
    # 전체
    p = Page("한국")
    p.add(top(live), ui.market_switch("kr"), nav("all"))
    if b:
        p.add(ui.bottom_badge(b["us"], b["kr"]))
    if mk:
        d = mk[0].get("date")
        label = (f"장중 잠정 · {mk[0]['time'].strftime('%H:%M')}" if live and mk[0].get("time") is not None
                 else f"{d.month}월 {d.day}일 장 마감 기준" if d else "")
        ch = kr_flow_chart(ki, "KOSPI")
        p.card(ui.kr_market_card(mk, label),
               (ui.section("코스피 장중 누적 순매수", "10분마다 기록 · 억원") + p.chart(ch)) if ch is not None else "")
    hc = kr.history_compare(hmk, S("kr_index"))
    if hc:
        p.card(ui.kr_history_card(hc, kr.history_text(hc)))
    idx = S("kr_index")
    kospi = (pd.Series(idx[idx["market"] == "코스피"]["close"].values, index=pd.to_datetime(idx[idx["market"] == "코스피"]["date"]))
             if len(idx) else None)
    sm = krx.flow_summary(ef, kospi) if len(ef) else None
    if sm:
        t, dsc = krx.flow_text(sm, safe(err, "ETF 자금 흐름", bottom.etf_bet, ef, idx))
        p.card(ui.kr_etf_flow_card(sm, t, dsc, f"{sm['date']:%m/%d} 기준 · 전 거래일 확정 (KRX)"),
               ui.section("최근 40거래일 하루 순유입", "억원 · 빨강 레버리지 · 파랑 인버스·곱버스"), p.chart(kr_etf_chart(ef)))
    if secs:
        ss = sorted(secs, key=lambda s: -(s["big_score"] if s["big_score"] is not None else -1))
        d = secs[0]["date"]
        sb = ("오늘 장 마감 확정" if d == now_kst.date() and not live else "오늘 장중 잠정" if d == now_kst.date()
              else "전 거래일 확정 · 오늘 종목별 수급은 장 마감 뒤 반영")
        p.card(ui.section("섹터별 수급 지도", f"기준 {d.month}월 {d.day}일 · {sb} · 큰손 매도 강도 높은 순") + ui.kr_tiles(ss))
    # 누가 뭘 팔고 샀나: 12가지 조합을 미리 만들어 두고 버튼으로 바꿔 보기
    panes, basis = [], ""
    for kind in ("종목", "ETF"):
        for who_lbl in ("외국인", "기관", "개인"):
            who = next(k for k, v in kr.INVESTORS.items() if v == who_lbl)
            for side_lbl, side in (("순매도", "sell"), ("순매수", "buy")):
                df, day = kr.rankings_from_table(rk, kind, who, side, 15)
                on = " on" if (kind, who_lbl, side_lbl) == ("종목", "외국인", "순매도") else ""
                if df is not None and not df.empty and not basis:
                    col = df.attrs.get("collected")
                    bs = "오늘 장 마감 확정" if day == now_kst.date() and not live else "오늘 장중 잠정" if day == now_kst.date() else "전 거래일 확정"
                    basis = f"기준: {day.month}월 {day.day}일 · {bs}" + (f" · {ago(col)} 수집" if col is not None else "")
                panes.append(f'<div class="pane{on}" data-k="{kind}" data-w="{who_lbl}" data-s="{side_lbl}">'
                             + ui.kr_rank(df, who, side_lbl, day) + "</div>")

    def seg(g, opts):
        return (f'<div class="seg" data-g="{g}">' + "".join(
            f'<button class="{"on" if i == 0 else ""}" data-v="{v}" onclick="seg(\'{g}\',\'{v}\')">{lbl}</button>'
            for i, (v, lbl) in enumerate(opts)) + "</div>")
    p.card(ui.section("누가 뭘 팔고 샀나", "코스피 시총 상위 200 + 코스닥 100 종목 · ETF 150개 · 그날 순매수(억원)"),
           seg("k", [("종목", "종목"), ("ETF", "ETF")]),
           seg("w", [("외국인", "외국인"), ("기관", "기관"), ("개인", "개인")]),
           seg("s", [("순매도", "순매도"), ("순매수", "순매수")]),
           f'<div class="sectsub">{ui.esc(basis)}</div>' if basis else "", "".join(panes),
           ui.footer(["ETF의 '기관'에는 LP(유동성공급자, 증권사) 물량이 섞여 있어요. ETF에서는 개인·외국인 쏠림 위주로 보세요."]))
    p.card(status)
    p.add(ui.footer(notes))
    pages["kr.html"] = p
    # 섹터별
    for s in secs:
        p = Page(s["name"])
        p.add(top(live), ui.market_switch("kr"), nav(s["key"]))
        p.card(ui.kr_sector_hero(s))
        ch = kr_daily_chart(s["daily"])
        if ch is not None:
            p.card(ui.section("최근 30거래일 순매수", "억원 · 보라 큰손 · 주황 개인"), p.chart(ch))
        p.card(ui.kr_members(s["members"]))
        p.card(status)
        p.add(ui.footer(notes))
        pages[f"kr-{s['key']}.html"] = p
    return pages


# ------------------------------------------------------------------ 앱처럼 쓰기 (홈 화면에 추가)
MANIFEST = {"name": "개인투심체크", "short_name": "투심체크", "start_url": "index.html", "display": "standalone",
            "background_color": "#f2f4f6", "theme_color": "#191f28",
            "icons": [{"src": "icon.svg", "sizes": "any", "type": "image/svg+xml"},
                      {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}]}
ICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect width="96" height="96" rx="22" fill="#191f28"/>'
        '<path d="M18 30 L38 52 L52 40 L78 68" fill="none" stroke="#f04452" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="78" cy="68" r="6" fill="#f04452"/></svg>')


def icon_png(size: int = 192) -> bytes:
    """홈 화면 아이콘(PNG) — 외부 라이브러리 없이 단색 배경 + 빨간 꺾은선"""
    import struct
    import zlib
    px = [[(0x19, 0x1f, 0x28)] * size for _ in range(size)]
    pts = [(0.19, 0.31), (0.40, 0.54), (0.54, 0.42), (0.81, 0.71)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for i in range(400):
            t = i / 399
            cx, cy = (x0 + (x1 - x0) * t) * size, (y0 + (y1 - y0) * t) * size
            r = size * 0.045
            for yy in range(int(cy - r), int(cy + r) + 1):
                for xx in range(int(cx - r), int(cx + r) + 1):
                    if 0 <= xx < size and 0 <= yy < size and (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                        px[yy][xx] = (0xf0, 0x44, 0x52)
    raw = b"".join(b"\x00" + bytes(c for p in row for c in p) for row in px)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# ------------------------------------------------------------------ 실행
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="site")
    ap.add_argument("--cache", default=".cache")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    st = LocalStore(args.data)
    memo: dict = {}

    def S(name):
        if name not in memo:
            try:
                memo[name] = st.read(name)
            except Exception:
                memo[name] = pd.DataFrame()
        return memo[name]
    runs = S("runs")
    pages: dict[str, Page] = {}
    b = None
    for name, job in (("bottom", None), ("us", None), ("kr", None)):
        t0 = time.time()
        err: dict = {}
        try:
            if name == "bottom":
                b = bottom_data(S, err)
                pages["bottom.html"] = page_bottom(b)
            elif name == "us":
                m = us_market(S, err)
                if m is not None:
                    pages.update(us_pages(m, build_all(m), b, runs))
            else:
                pages.update(kr_pages(S, err, b, runs, Path(args.cache)))
            print(f"{name}: {time.time() - t0:.0f}초 · 못 받은 것 {sorted(err)}", flush=True)
        except Exception:
            print(f"{name} 페이지 실패\n{traceback.format_exc()}", flush=True)
    for fn, p in pages.items():
        (out / fn).write_text(p.html(), encoding="utf-8")
    if not (out / "index.html").exists():  # 미국 페이지를 못 만들었으면 바닥 신호를 첫 화면으로
        src = out / ("bottom.html" if (out / "bottom.html").exists() else "kr.html")
        if src.exists():
            (out / "index.html").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "manifest.webmanifest").write_text(json.dumps(MANIFEST, ensure_ascii=False), encoding="utf-8")
    (out / "icon.svg").write_text(ICON, encoding="utf-8")
    if not (out / "icon-192.png").exists():
        (out / "icon-192.png").write_bytes(icon_png())
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"페이지 {len(pages)}개 → {out}", flush=True)


if __name__ == "__main__":
    main()
