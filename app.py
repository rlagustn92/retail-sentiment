"""개인투심체크 — 미국 지수·섹터별 개인 투매 대시보드 (Streamlit)

실행: streamlit run app.py
키가 없으면 데모 데이터로 화면을 보여줍니다. 주소 뒤에 ?demo=1 을 붙여도 데모가 나와요.
"""
from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Streamlit Cloud는 새 코드를 받아도 core 모듈을 예전 것으로 들고 있을 때가 있어요(그러면 KeyError 등으로 멈춤).
# 모듈 파일이 바뀌었거나 이 서버에서 처음 실행이면 의존 순서대로 다시 읽고 캐시를 비워요.
_MODS = ["core.config", "core.scoring", "core.news", "core.retail_flow", "core.realtime", "core.store",
         "core.cboe", "core.stocktwits", "core.alpaca", "core.finra", "core.fred", "core.finnhub",
         "core.metrics", "core.sources", "ui"]


def _fresh_modules():
    mods = [importlib.import_module(n) for n in _MODS]
    stamp = tuple(os.path.getmtime(m.__file__) for m in mods)
    holder = sys.modules["core"]
    if getattr(holder, "_app_stamp", None) != stamp:
        for m in mods:
            importlib.reload(m)
        st.cache_data.clear()
        st.cache_resource.clear()
        holder._app_stamp = stamp


_fresh_modules()

import ui  # noqa: E402  (위에서 새로 읽은 모듈을 가져와요)
from core import config, sources
from core import news as newsmod
from core import retail_flow as rf
from core.alpaca import Alpaca
from core.metrics import ET, MarketData, build_all, market_summary
from core.scoring import level
from core.store import GitHubStore, LocalStore, NullStore

KST = "Asia/Seoul"
SHORT = {"retail": "개인 순매도", "volume": "거래량", "inverse": "인버스", "social": "Stocktwits",
         "putcall": "풋/콜", "vix": "VIX/VIX3M", "breadth": "종목 전반", "short": "장외 공매도",
         "credit": "하이일드"}

st.set_page_config(page_title="개인투심체크", page_icon="📉", layout="centered",
                   initial_sidebar_state="collapsed")
st.markdown(ui.CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ 설정
def secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


KEY, SECRET = secret("ALPACA_KEY"), secret("ALPACA_SECRET")
DEMO = (not KEY or not SECRET) or st.query_params.get("demo") == "1"
GROUP = st.query_params.get("g", "all")
if GROUP != "all" and GROUP not in config.GROUPS:
    GROUP = "all"


@st.cache_resource
def client() -> Alpaca:
    return Alpaca(KEY, SECRET)


@st.cache_resource
def store():
    repo = secret("GH_REPO")
    if repo:
        return GitHubStore(repo, secret("DATA_BRANCH", "data"), secret("GH_TOKEN"))
    return LocalStore("data") if os.path.isdir("data") else NullStore()


# ------------------------------------------------------------------ 캐시된 수집 함수
@st.cache_data(ttl=60, show_spinner=False)
def c_clock():
    return client().clock()


@st.cache_data(ttl=300, show_spinner=False)
def c_bars15():
    return sources.fetch_bars15(client(), datetime.now(timezone.utc))


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def c_daily(feed: str):
    return sources.fetch_daily(client(), datetime.now(timezone.utc), feed)


@st.cache_data(ttl=30, show_spinner=False)
def c_snaps():
    return sources.fetch_snapshots(client())


@st.cache_data(ttl=300, show_spinner=False)
def c_store(name: str):
    return store().read(name)


@st.cache_data(ttl=6 * 3600, show_spinner=False, max_entries=500)
def c_retail_bucket(sym: str, start_iso: str):
    start = datetime.fromisoformat(start_iso)
    df = rf.compute_buckets(client(), sym, start, start + timedelta(minutes=config.BUCKET_MIN),
                            config.BUCKET_MIN)
    return df.assign(sym=sym)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def c_vix_hist():
    from core import cboe
    return {"vix_hist": cboe.index_history("VIX"), "vix3m_hist": cboe.index_history("VIX3M")}


@st.cache_data(ttl=60, show_spinner=False)
def c_vix_now():
    from core import cboe
    return {"vix_now": cboe.index_quote("VIX"), "vix3m_now": cboe.index_quote("VIX3M")}


@st.cache_data(ttl=600, show_spinner=False)
def c_putcall_intraday():
    from core import cboe
    return cboe.equity_putcall_intraday()


@st.cache_data(ttl=300, show_spinner=False)
def c_stocktwits(sym: str):
    return sources.fetch_stocktwits(sym)


@st.cache_data(ttl=120, show_spinner=False)
def c_news_recent():
    now = datetime.now(timezone.utc)
    return sources.fetch_news(client(), now - timedelta(hours=3), max_pages=10)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def c_news_base():
    now = datetime.now(timezone.utc)
    return sources.fetch_news(client(), now - timedelta(days=config.NEWS_BASELINE_DAYS), max_pages=80)


@st.cache_data(ttl=60, show_spinner=False)
def c_demo():
    return sources.demo_market()


def safe(errors: dict, name: str, fn, *args, default=None):
    try:
        return fn(*args)
    except Exception as e:  # 한 곳이 실패해도 화면은 계속
        errors[name] = f"{type(e).__name__}: {str(e)[:120]}"
        return default


def retail_live(stored: pd.DataFrame, bars: pd.DataFrame, sym: str, now: datetime, errors: dict) -> pd.DataFrame:
    """보고 있는 그룹만: 저장된 기록 이후 빠진 최근 구간(최대 2시간)을 직접 계산"""
    b = bars[bars["sym"] == sym] if not bars.empty else bars
    if b.empty:
        return stored
    last_day = pd.to_datetime(b["ts"], utc=True).dt.tz_convert(ET).dt.date.max()
    open_utc = pd.Timestamp(f"{last_day} 09:30", tz=ET).tz_convert("UTC").to_pydatetime()
    close_utc = pd.Timestamp(f"{last_day} 16:00", tz=ET).tz_convert("UTC").to_pydatetime()
    end = min(Alpaca.sip_end(now), close_utc)
    start = open_utc
    mine = stored[stored["sym"] == sym] if not stored.empty and "sym" in stored else pd.DataFrame()
    if not mine.empty:
        start = max(start, pd.to_datetime(mine["bucket"], utc=True).max().to_pydatetime()
                    + timedelta(minutes=config.BUCKET_MIN))
    start = max(start, rf.floor_bucket(end, config.BUCKET_MIN) - timedelta(minutes=config.BUCKET_MIN * 8))
    parts = []
    t = rf.floor_bucket(start, config.BUCKET_MIN)
    while t + timedelta(minutes=config.BUCKET_MIN) <= end:
        if t >= open_utc:
            df = safe(errors, "개인 수급", c_retail_bucket, sym, t.isoformat())
            if df is not None and len(df):
                parts.append(df)
        t += timedelta(minutes=config.BUCKET_MIN)
    if not parts:
        return stored
    new = pd.concat(parts, ignore_index=True)
    return pd.concat([stored, new], ignore_index=True) if not stored.empty else new


def live_market(group: str) -> MarketData:
    now = datetime.now(timezone.utc)
    err: dict = {}
    clock = safe(err, "장 시간", c_clock, default={}) or {}
    is_open = bool(clock.get("is_open"))
    bars = safe(err, "시세(15분봉)", c_bars15, default=None)
    bars = bars if bars is not None else pd.DataFrame(columns=["ts", "sym", "c", "v", "vw"])
    snaps = safe(err, "실시간 시세", c_snaps, default={}) or {}
    dsip = safe(err, "일봉", c_daily, "sip", default=pd.DataFrame())
    diex = safe(err, "일봉", c_daily, "iex", default=pd.DataFrame())
    rt = sources.rt_from(snaps, dsip, diex, bars, now, is_open)
    retail = c_store("retail")
    if group != "all":
        retail = retail_live(retail, bars, config.GROUPS[group]["flow"], now, err)
    vix = {**(safe(err, "VIX", c_vix_hist, default={}) or {}), **(safe(err, "VIX", c_vix_now, default={}) or {})}
    pc_df = c_store("putcall")
    pc_hist = pc_df.set_index("date")["equity_pc"].sort_index() if not pc_df.empty else None
    pc_now = safe(err, "풋/콜", c_putcall_intraday) if is_open else None
    st_hist = c_store("stocktwits")
    st_now = {}
    for sym in config.social_symbols():
        v = safe(err, "Stocktwits", c_stocktwits, sym)
        if v is None and not st_hist.empty and "sym" in st_hist:  # 직접 못 받으면 수집기 기록 사용
            h = st_hist[st_hist["sym"] == sym].sort_values("ts")
            if len(h) and pd.Timestamp(now) - h["ts"].iloc[-1] < pd.Timedelta(minutes=40):
                v = {k: h[k].iloc[-1] for k in ("msgs_per_hour", "bull", "bear", "bear_ratio")}
        if v:
            st_now[sym] = v
    if st_now:
        err.pop("Stocktwits", None)
    stored_news = c_store("news")
    base = stored_news if len(stored_news) > 200 else safe(err, "뉴스", c_news_base, default=pd.DataFrame())
    news = newsmod.merge(base, safe(err, "뉴스", c_news_recent, default=pd.DataFrame()))
    return MarketData(now=now, market_open=is_open, bars=bars, rt=rt, retail=retail,
                      vix_hist=vix.get("vix_hist"), vix3m_hist=vix.get("vix3m_hist"),
                      vix_now=vix.get("vix_now"), vix3m_now=vix.get("vix3m_now"),
                      putcall_hist=pc_hist, putcall_now=pc_now, putcall_intraday=pc_now is not None,
                      st_now=st_now, st_hist=st_hist, news=news, score_hist=c_store("score"),
                      finra=c_store("finra"), fred=c_store("fred"), errors=err)


# ------------------------------------------------------------------ 차트
def fmt_time(ts) -> str:
    t = pd.Timestamp(ts).tz_convert(KST)
    now = pd.Timestamp.now(tz=KST)
    return t.strftime("%H:%M") if t.date() == now.date() else t.strftime("%m/%d %H:%M")


AXIS = dict(labelColor="#8b95a1", titleColor="#8b95a1", gridColor="rgba(139,149,161,0.15)",
            domain=False, ticks=False, labelFontSize=12,
            labelFont="Pretendard Variable, Pretendard, -apple-system, sans-serif")


def trend_chart(hist: pd.DataFrame, groups: list[str], panic, now, live: bool):
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
        y=alt.Y("panic:Q", title=None, scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(values=[0, 40, 70, 100], **AXIS)))
    area = base.mark_area(color=color, opacity=0.12, interpolate="monotone")
    line = base.mark_line(color=color, strokeWidth=3, interpolate="monotone")
    pt = alt.Chart(df.tail(1)).mark_circle(size=90, color=color).encode(x="t:T", y="panic:Q")
    rules = alt.Chart(pd.DataFrame({"y": [40, 70]})).mark_rule(
        strokeDash=[4, 4], color="#8b95a1", opacity=0.5).encode(y="y:Q")
    return (area + line + rules + pt).properties(height=170, background="transparent").configure_view(strokeWidth=0)


def retail_chart(rt: pd.DataFrame):
    if rt is None or rt.empty or "net" not in rt:
        return None
    df = rt.dropna(subset=["net"]).copy()
    if df.empty:
        return None
    df["buy_pct"] = -df["net"] * 100  # +면 개인 매수 우위
    df["t"] = df["bucket"].dt.tz_convert(KST).dt.strftime("%H:%M")
    df["side"] = df["buy_pct"].map(lambda v: "매수 우위" if v >= 0 else "매도 우위")
    return alt.Chart(df).mark_bar(cornerRadius=4, size=12).encode(
        x=alt.X("t:N", title=None, sort=None, axis=alt.Axis(**AXIS, labelAngle=0, labelOverlap=True)),
        y=alt.Y("buy_pct:Q", title=None, axis=alt.Axis(**AXIS, format="+.0f", tickCount=4)),
        color=alt.Color("side:N", scale=alt.Scale(domain=["매수 우위", "매도 우위"],
                                                  range=["#f04452", "#3182f6"]), legend=None),
        tooltip=[alt.Tooltip("t:N", title="시각"), alt.Tooltip("buy_pct:Q", title="개인 순매수 %", format="+.1f")],
    ).properties(height=170, background="transparent").configure_view(strokeWidth=0)


# ------------------------------------------------------------------ 화면
def page_all(m: MarketData, res: dict):
    sm = market_summary(res)
    spx = res["spx"]
    with st.container(key="card_hero"):
        st.markdown(ui.market_hero(sm["panic"], sm["title"], sm["detail"], sm["hot"],
                                   spx.session_label or "장 대기"), unsafe_allow_html=True)
    ch = trend_chart(m.score_hist, config.INDEX_KEYS, sm["panic"], m.now, m.market_open and not m.demo)
    if ch is not None:
        with st.container(key="card_trend"):
            st.markdown(ui.section("시장 투매 지수 흐름", "S&P500·나스닥 평균 · 점선: 경계 40 · 투매 70"),
                        unsafe_allow_html=True)
            st.altair_chart(ch, width="stretch")
    with st.container(key="card_sectors"):
        sec = sorted([res[k] for k in config.SECTOR_KEYS],
                     key=lambda r: -(r.panic if r.panic is not None else -1))
        st.markdown(ui.section("섹터별 투매 지도", "점수 높은 순 · 누르면 섹터 상세") + ui.tiles(sec),
                    unsafe_allow_html=True)
    with st.container(key="card_index"):
        st.markdown(ui.section("지수") + ui.index_rows([res[k] for k in config.INDEX_KEYS]),
                    unsafe_allow_html=True)
    mk = [spx.indicators[k] for k in ("vix", "putcall", "credit") if k in spx.indicators]
    if mk:
        with st.container(key="card_fear"):
            st.markdown(ui.indicator_rows(mk, "시장 전체 공포", "모든 지수에 공통으로 반영돼요"),
                        unsafe_allow_html=True)


def page_group(m: MarketData, r):
    g = config.GROUPS[r.key]
    with st.container(key="card_hero"):
        top = sorted([i for i in r.indicators.values() if i.score is not None and i.score >= 60],
                     key=lambda i: -i.score)[:3]
        st.markdown(ui.hero(r.panic, r.headline, r.detail, r.price, r.chg, r.bad_news,
                            r.session_label or "장 대기", [(SHORT.get(i.key, i.title), i.display) for i in top],
                            title=r.name, etf=r.etf, flow=g["flow"], flow_chg=r.flow_chg),
                    unsafe_allow_html=True)
    ch = trend_chart(m.score_hist, [r.key], r.panic, m.now, m.market_open and not m.demo)
    if ch is not None:
        with st.container(key="card_trend"):
            st.markdown(ui.section(f"{r.name} 투매 지수 흐름", "15분마다 기록 · 점선: 경계 40 · 투매 70"),
                        unsafe_allow_html=True)
            st.altair_chart(ch, width="stretch")
    order = ["retail", "volume", "breadth", "inverse", "short", "social", "vix", "putcall", "credit"]
    inds = [r.indicators[k] for k in order if k in r.indicators]
    if r.news_ind:
        inds.append(r.news_ind)
    with st.container(key="card_inds"):
        st.markdown(ui.indicator_rows(inds), unsafe_allow_html=True)
    with st.container(key="card_members"):
        st.markdown(ui.members(r.members, r.breadth, config.name), unsafe_allow_html=True)
    rc = retail_chart(r.retail_today)
    with st.container(key="card_retail"):
        st.markdown(ui.section(f"{g['flow']} 개인 순매수 흐름", "15분 단위 · 빨강 매수 우위 · 파랑 매도 우위 · 15분 지연"),
                    unsafe_allow_html=True)
        if rc is not None:
            st.altair_chart(rc, width="stretch")
        else:
            st.markdown('<div class="empty">장이 열리면 15분 뒤부터 표시돼요</div>', unsafe_allow_html=True)
    with st.container(key="card_news"):
        st.markdown(ui.news_list(r.headlines, fmt_time), unsafe_allow_html=True)


@st.fragment(run_every=config.REFRESH_SEC)
def render():
    m = c_demo() if DEMO else live_market(GROUP)
    res = build_all(m)
    now_kst = pd.Timestamp(m.now).tz_convert(KST)
    st.markdown(ui.top(("데모 · " if m.demo else "") + now_kst.strftime("%H:%M 업데이트"), m.market_open),
                unsafe_allow_html=True)
    items = [("all", "전체", market_summary(res)["panic"])] + [
        (k, config.GROUPS[k]["name"], res[k].panic) for k in config.INDEX_KEYS + config.SECTOR_KEYS]
    st.markdown(ui.nav(GROUP, items), unsafe_allow_html=True)
    if GROUP != "all":  # 선택한 탭이 화면 밖에 있으면 보이게 스크롤
        js = """<script>setTimeout(()=>{const a=window.parent.document.querySelector('.nav a.on');
if(a){a.scrollIntoView({inline:'center',block:'nearest'});}},300);</script>"""
        if hasattr(st, "iframe"):  # 새 버전 Streamlit (components.html은 없어질 예정)
            st.iframe(js, height=1)
        else:
            components.html(js, height=0)
    if m.demo:
        st.markdown('<div class="demo">데모 데이터예요. 알파카 키를 넣으면 실제 데이터로 바뀌어요.</div>',
                    unsafe_allow_html=True)
    if GROUP == "all":
        page_all(m, res)
    else:
        page_group(m, res[GROUP])

    notes = ["투매 지수는 상황 판단을 돕는 참고 지표예요. 매수·매도 신호가 아니에요.",
             f"{config.REFRESH_SEC}초마다 자동으로 새로고침돼요."]
    if m.errors:
        notes.append("못 받은 데이터: " + ", ".join(sorted(set(m.errors.keys()))))
        if any(("401" in v or "403" in v) for k, v in m.errors.items() if k in ("시세(15분봉)", "장 시간", "실시간 시세")):
            notes.append("알파카 키가 맞는지 확인해 주세요 (모의계좌 키, Secrets 설정).")
    st.markdown(ui.footer(notes), unsafe_allow_html=True)


render()
