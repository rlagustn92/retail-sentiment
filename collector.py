"""기록 수집기 — GitHub Actions가 실행합니다 (내 PC에서도 실행 가능).

python collector.py intraday           장중 15분마다: 개인 수급·Stocktwits·뉴스·그룹별 투매 점수 기록
python collector.py daily              장 마감 후: 남은 개인 수급 구간, 오늘 풋/콜 확정치, 오래된 기록 정리
python collector.py backfill --days 10 처음 한 번: 과거 N거래일 개인 수급, 풋/콜, 뉴스 채우기

환경변수: ALPACA_KEY, ALPACA_SECRET
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

from core import cboe, config, sources
from core import retail_flow as rf
from core.alpaca import Alpaca
from core.metrics import ET, MarketData, build_all
from core.store import LocalStore

KEEP_DAYS = {"retail": 100, "stocktwits": 60, "score": 45, "putcall": 400, "news": 4}
DATE_COL = {"retail": "bucket", "stocktwits": "ts", "score": "ts", "putcall": "date", "news": "ts"}


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def session_bounds(day: dict) -> tuple[datetime, datetime]:
    o = pd.Timestamp(f"{day['date']} {day['open']}", tz=ET).tz_convert("UTC").to_pydatetime()
    c = pd.Timestamp(f"{day['date']} {day['close']}", tz=ET).tz_convert("UTC").to_pydatetime()
    return o, c


def sessions(a: Alpaca, days_back: int) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    return a.calendar((today - timedelta(days=days_back * 2 + 10)).isoformat(), today.isoformat())


def fill_retail(a: Alpaca, st: LocalStore, o: datetime, c: datetime, now: datetime,
                symbols: list[str] | None = None) -> int:
    """o~c 세션에서 아직 기록 안 된 (구간, 종목)을 계산해 저장"""
    end = min(c, Alpaca.sip_end(now))
    old = st.read("retail")
    have = set()
    if not old.empty:
        have = set(zip(pd.to_datetime(old["bucket"], utc=True), old["sym"]))
    total = 0
    for sym in symbols or config.flow_symbols():
        parts = []
        b = rf.floor_bucket(o, config.BUCKET_MIN)
        while b + timedelta(minutes=config.BUCKET_MIN) <= end:
            if (pd.Timestamp(b), sym) not in have:
                df = rf.compute_buckets(a, sym, b, b + timedelta(minutes=config.BUCKET_MIN), config.BUCKET_MIN)
                parts.append(df.assign(sym=sym))
            b += timedelta(minutes=config.BUCKET_MIN)
        if parts:
            st.append("retail", pd.concat(parts, ignore_index=True))
            total += len(parts)
    return total


def update_news(a: Alpaca, st: LocalStore, now: datetime):
    old = st.read("news")
    start = now - timedelta(days=config.NEWS_BASELINE_DAYS)
    if not old.empty:
        start = max(start, pd.to_datetime(old["ts"], utc=True).max().to_pydatetime() - timedelta(minutes=5))
    new = sources.fetch_news(a, start, max_pages=120)
    st.append("news", new)
    log(f"뉴스 {len(new)}건")


def trim(st: LocalStore):
    now = pd.Timestamp.now(tz="UTC")
    for name, col in DATE_COL.items():
        df = st.read(name)
        if df.empty or col not in df:
            continue
        st.write(name, df[pd.to_datetime(df[col], utc=True) >= now - pd.Timedelta(days=KEEP_DAYS[name])])


def record_scores(a: Alpaca, st: LocalStore, now: datetime, st_now: dict):
    err: dict = {}

    def safe(name, fn, *args):
        try:
            return fn(*args)
        except Exception as e:
            err[name] = str(e)[:100]
            return None

    bars = safe("bars", sources.fetch_bars15, a, now)
    bars = bars if bars is not None else pd.DataFrame(columns=["ts", "sym", "c", "v", "vw"])
    snaps = safe("snapshots", sources.fetch_snapshots, a) or {}
    dsip = safe("daily_sip", sources.fetch_daily, a, now, "sip")
    diex = safe("daily_iex", sources.fetch_daily, a, now, "iex")
    rt = sources.rt_from(snaps, dsip, diex, bars, now, True)
    vix = safe("vix", sources.fetch_vix) or {}
    pc = st.read("putcall")
    m = MarketData(now=now, market_open=True, bars=bars, rt=rt, retail=st.read("retail"),
                   vix_hist=vix.get("vix_hist"), vix3m_hist=vix.get("vix3m_hist"),
                   vix_now=vix.get("vix_now"), vix3m_now=vix.get("vix3m_now"),
                   putcall_hist=pc.set_index("date")["equity_pc"].sort_index() if not pc.empty else None,
                   putcall_now=safe("putcall", cboe.equity_putcall_intraday), st_now=st_now,
                   st_hist=st.read("stocktwits"), news=st.read("news"))
    res = build_all(m)
    rows = pd.DataFrame([{"ts": pd.Timestamp(now), "group": k, "panic": r.panic, "bad_news": r.bad_news,
                          "chg": r.chg} for k, r in res.items()])
    st.append("score", rows)
    log("점수", {k: (None if r.panic is None else round(r.panic)) for k, r in res.items()}, "실패", list(err))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["intraday", "daily", "backfill"])
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--data", default="data")
    args = ap.parse_args()

    key, secret = os.environ.get("ALPACA_KEY"), os.environ.get("ALPACA_SECRET")
    if not key or not secret:
        sys.exit("ALPACA_KEY / ALPACA_SECRET 환경변수가 필요해요")
    a = Alpaca(key, secret)
    st = LocalStore(args.data)
    now = datetime.now(timezone.utc)

    if args.mode == "intraday":
        if not a.clock().get("is_open"):
            log("장 닫힘 — 건너뜀")
            return
        o, c = session_bounds(sessions(a, 1)[-1])
        log(f"개인 수급 {fill_retail(a, st, o, c, now)}개 구간 추가")
        st_now = {}
        for sym in config.social_symbols():
            try:
                st_now[sym] = sources.fetch_stocktwits(sym)
                st.append("stocktwits", pd.DataFrame([dict(st_now[sym], ts=pd.Timestamp(now), sym=sym)]))
            except Exception as e:
                log("Stocktwits 실패", sym, e)
        try:
            update_news(a, st, now)
        except Exception as e:
            log("뉴스 실패", e)
        record_scores(a, st, now, st_now)

    elif args.mode == "daily":
        day = sessions(a, 1)[-1]
        o, c = session_bounds(day)
        log(f"개인 수급 {fill_retail(a, st, o, c, now)}개 구간 추가 ({day['date']})")
        pc = sources.putcall_backfill([pd.Timestamp(day["date"]).date()])
        st.append("putcall", pc)
        log(f"풋/콜 {pc.to_dict('records')}")
        trim(st)

    else:  # backfill
        cal = sessions(a, max(args.days, 60))
        done = [d for d in cal if session_bounds(d)[1] < Alpaca.sip_end(now)]
        for d in done[-args.days:]:
            o, c = session_bounds(d)
            log(f"{d['date']} 개인 수급 {fill_retail(a, st, o, c, now)}개 구간")
        pc = sources.putcall_backfill([pd.Timestamp(d["date"]).date() for d in done[-60:]])
        st.append("putcall", pc)
        log(f"풋/콜 {len(pc)}일")
        try:
            update_news(a, st, now)
        except Exception as e:
            log("뉴스 실패", e)
        trim(st)


if __name__ == "__main__":
    main()
