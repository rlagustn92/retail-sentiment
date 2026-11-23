"""기록 수집기 — GitHub Actions가 실행합니다 (내 PC에서도 실행 가능).

python collector.py intraday           장중 15분마다: 개인 수급·Stocktwits·뉴스·그룹별 투매 점수 기록
python collector.py daily              장 마감 후: 남은 개인 수급 구간, 오늘 풋/콜 확정치, 오래된 기록 정리
python collector.py backfill --days 10 처음 한 번: 과거 N거래일 개인 수급, 풋/콜, 뉴스 채우기

환경변수: ALPACA_KEY, ALPACA_SECRET (필수), FINNHUB_KEY (있으면 뉴스 보충), FRED_KEY (권장, 없으면 키 없는 주소로 시도)
FINRA 장외 공매도는 키 없이 받아요. 빠진 날짜는 다음 실행 때 자동으로 채워요.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

import requests

from core import bottom, cboe, config, finra, fred, kr, sources
from core import news as newsmod
from core import retail_flow as rf
from core.finnhub import Finnhub
from core.finnhub import to_frame as finnhub_frame
from core.alpaca import Alpaca
from core.metrics import ET, MarketData, build_all
from core.store import LocalStore

KEEP_DAYS = {"runs": 30, "retail": 100, "stocktwits": 60, "score": 45, "putcall": 400, "news": 4, "finra": 400, "fred": 800,
             "kr_intraday": 15, "kr_market": 800}
DATE_COL = {"runs": "ts", "retail": "bucket", "stocktwits": "ts", "score": "ts", "putcall": "date", "news": "ts",
            "finra": "date", "fred": "date", "kr_intraday": "ts", "kr_market": "date"}


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
        etfs = old["sym"].isin(config.etf_symbols())
        done = old[~etfs | old["inst_buy"].notna()] if "inst_buy" in old else old[~etfs]  # 대표 ETF는 기관 칸까지 있어야 완료
        have = set(zip(pd.to_datetime(done["bucket"], utc=True), done["sym"]))
    total = 0
    for sym in symbols or config.trade_symbols():
        parts = []
        b = rf.floor_bucket(o, config.BUCKET_MIN)
        while b + timedelta(minutes=config.BUCKET_MIN) <= end:
            if (pd.Timestamp(b), sym) not in have:
                try:
                    df = rf.compute_buckets(a, sym, b, b + timedelta(minutes=config.BUCKET_MIN), config.BUCKET_MIN)
                    parts.append(df.assign(sym=sym))
                except Exception as e:  # 이 구간만 건너뛰고 다음 실행 때 다시 채워요
                    log("체결 계산 실패", sym, b, str(e)[:120])
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


def update_finnhub_news(st: LocalStore, now: datetime):
    """Finnhub 종목 뉴스로 알파카 뉴스를 보충 (FINNHUB_KEY가 없으면 건너뜀)"""
    key = os.environ.get("FINNHUB_KEY")
    if not key:
        log("Finnhub 키 없음 — 뉴스 보충 건너뜀")
        return
    key = key.strip()
    log(f"Finnhub 키 길이 {len(key)}자")  # 값은 남기지 않고 길이만 (잘못 붙여넣었는지 확인용)
    old = st.read("news")
    has_fh = not old.empty and old["id"].astype(str).str.startswith("fh-").any()
    start = (now - timedelta(days=1 if has_fh else config.NEWS_BASELINE_DAYS)).date()
    end = now.date()  # Finnhub는 미래 날짜(to)를 주면 400 Bad Request를 돌려줘요
    fh = Finnhub(key)
    syms = sorted({s for g in config.GROUPS.values() for s in g["members"]})
    parts, fails, first_err = [], 0, None
    for sym in syms:
        try:
            parts.append(finnhub_frame(fh.company_news(sym, start, end), sym))
        except Exception as e:
            fails += 1
            resp = getattr(e, "response", None)
            code = getattr(resp, "status_code", None)
            if first_err is None:
                body = (resp.text[:150] if resp is not None else "")
                first_err = f"{sym}: {type(e).__name__} {code or ''} {str(e)[:150]} {body}"
                log("Finnhub 첫 오류", first_err)
            if code in (401, 403):
                log("Finnhub 키가 맞지 않거나 권한이 없어요 — 중단", code)
                return
            if fails >= 5 and not parts:
                log("Finnhub 처음 5종목이 모두 실패 — 중단")
                return
    new = newsmod.merge(*parts)
    st.append("news", new)
    log(f"Finnhub 뉴스 {len(new)}건 ({len(syms)}종목, 실패 {fails})")


def update_finra(a: Alpaca, st: LocalStore, now: datetime):
    """최근 FINRA_LOOKBACK 거래일 중 빠진 날의 장외 공매도 파일을 받아요 (처음엔 과거까지 자동으로 채움)"""
    old = st.read("finra")
    have = set(pd.to_datetime(old["date"], utc=True).dt.date) if not old.empty else set()
    et_now = pd.Timestamp(now).tz_convert(ET)
    want = []
    for d in sessions(a, config.FINRA_LOOKBACK)[-config.FINRA_LOOKBACK:]:
        day = pd.Timestamp(d["date"]).date()
        if day > et_now.date() or (day == et_now.date() and et_now.hour < 18):
            continue  # FINRA는 미국 동부 오후 6시 전에 그날 파일을 올려요
        if day not in have:
            want.append(day)
    parts = []
    for day in want:
        try:
            df = finra.daily(day, config.bar_symbols())
        except Exception as e:
            log("FINRA 실패", day, e)
            continue
        if df is not None and len(df):
            parts.append(df)
    if parts:
        st.append("finra", pd.concat(parts, ignore_index=True))
    log(f"FINRA 장외 공매도 {len(parts)}일 추가 (빠진 날 {len(want)}일)")


def update_fred(st: LocalStore, now: datetime):
    key = os.environ.get("FRED_KEY") or None
    for sid in config.FRED_SERIES.values():
        df = fred.series(sid, (now - timedelta(days=400)).date(), key)
        st.append("fred", df)
        log(f"FRED {sid} {len(df)}개, 최근 {df['date'].max().date() if len(df) else '-'}")


def update_kr(st: LocalStore, now: datetime, daily: bool):
    """한국 지수 투자자별 순매수: 장중엔 10분마다 스냅샷, 장 마감 뒤엔 일별 확정치"""
    rows = []
    for m in kr.MARKETS:
        x = kr.index_now(m)
        rows.append({k: x[k] for k in ("market", "personal", "foreign", "inst", "price", "chg")}
                    | {"ts": pd.Timestamp(now), "date": pd.Timestamp(x["date"], tz="UTC") if x["date"] else None,
                       "status": x["status"]})
    df = pd.DataFrame(rows)
    if daily:
        st.append("kr_market", df.drop(columns=["ts", "status"]).dropna(subset=["date"]))
        log("한국 일별", df[["market", "date", "foreign", "inst", "personal"]].to_dict("records"))
    elif (df["status"] == "OPEN").any():
        st.append("kr_intraday", df.drop(columns=["date", "status"]))
        log("한국 장중", df[["market", "foreign", "inst", "personal"]].to_dict("records"))
    else:
        raise Skip("한국 장 닫힘")


def sp500_symbols() -> list[str]:
    """S&P500 구성종목 (위키백과 목록)"""
    import io
    r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                     headers={"User-Agent": "Mozilla/5.0 (retail-sentiment dashboard)"}, timeout=30)
    r.raise_for_status()
    t = pd.read_html(io.StringIO(r.text))[0]
    return sorted({str(s).strip().replace("-", ".") for s in t["Symbol"] if str(s).strip()})


def update_us_breadth(a: Alpaca, st: LocalStore, since=None):
    """미국 시장 폭(S&P500 구성종목 일봉) + 신용(HYG·IEF·LQD) 일별 기록. since가 없으면 최근 것만 이어 붙여요"""
    now = datetime.now(timezone.utc)
    old = st.read("us_breadth")
    if since is None:
        if old.empty:
            since = pd.Timestamp("2016-01-01").date()
            keep_from = since
        else:
            keep_from = (pd.to_datetime(old["date"]).max() - pd.Timedelta(days=10)).date()
            since = keep_from - timedelta(days=420)  # 200일선·52주 계산용
    else:
        keep_from = since
    start = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)
    t0 = datetime.now(timezone.utc)
    syms = sp500_symbols()
    raw = a.bars(syms + ["HYG", "IEF", "LQD", "SPY"], "1Day", start, Alpaca.sip_end(now))
    bars = sources.bars_frame(raw)
    bars["date"] = pd.to_datetime(bars["ts"], utc=True).dt.tz_convert(ET).dt.normalize().dt.tz_localize(None)
    close = bars.pivot_table(index="date", columns="sym", values="c", aggfunc="last")
    br = bottom.breadth_from_closes(close[[s for s in syms if s in close]])
    cr = close[[c for c in ("HYG", "IEF", "LQD", "SPY") if c in close]].rename(columns=str.lower).reset_index()
    for df in (br, cr):
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC")
    cut = pd.Timestamp(keep_from, tz="UTC")
    st.append("us_breadth", br[br["date"] >= cut])
    st.append("us_credit", cr[cr["date"] >= cut])
    log(f"미국 시장 폭 {len(syms)}종목 {keep_from}~: {len(br[br['date'] >= cut])}일 "
        f"(최근 50일선 위 {br['above50'].iloc[-1]:.0%}) · {(datetime.now(timezone.utc) - t0).seconds}초")


def update_kr_rank(st: LocalStore):
    """누가 뭘 팔고 샀나: 시총 상위 300 종목 + ETF 150개의 최근 거래일 투자자별 순매수 (앱이 바로 읽게)"""
    t0 = datetime.now(timezone.utc)
    u, e = kr.universe(), kr.etf_universe()
    trends = kr.all_trends(days=6, workers=8, codes=list(u["code"]) + list(e["code"]))
    tbl = pd.concat([kr.rank_table(u, trends, "종목"), kr.rank_table(e, trends, "ETF")], ignore_index=True)
    tbl["collected"] = pd.Timestamp(t0).isoformat()
    if len(tbl):
        st.write("kr_rank", tbl)
    log(f"한국 순위표 {len(tbl)}종목 ({(datetime.now(timezone.utc) - t0).seconds}초)")


def update_kr_hist(st: LocalStore, since):
    """한국 과거 수급(시총 상위 300 합·섹터별·지수 등락)을 since부터 채우고, 이미 있으면 최근 것만 이어 붙여요"""
    old = st.read("kr_hist_market")
    start = since
    if not old.empty:
        last = old[old["market"] == "전체"].sort_values("date").tail(1)
        if len(last) and int(last["n"].iloc[0]) >= 270 and not st.read("kr_breadth").empty:  # 거의 다 받아져 있으면 최근 것만 이어 붙여요
            start = max(since, (pd.to_datetime(old["date"]).max() - pd.Timedelta(days=14)).date())
        else:
            log(f"한국 과거 수급이 덜 채워져 있어서({int(last['n'].iloc[0]) if len(last) else 0}종목) 처음부터 다시 받아요")
    t0 = datetime.now(timezone.utc)
    fetch_from = start if start == since else max(since, start - timedelta(days=400))  # 200일선·52주 계산용으로 넉넉히
    mk, sec, idx, br = kr.build_history(fetch_from)
    cut = pd.Timestamp(start, tz="UTC")
    for name, df in (("kr_hist_market", mk), ("kr_hist_sector", sec), ("kr_index", idx), ("kr_breadth", br)):
        if len(df):
            st.append(name, df if name != "kr_breadth" or start == since else df[df["date"] >= cut])
    log(f"한국 과거 수급 {start}~: 시장 {len(mk)}행 · 섹터 {len(sec)}행 · 지수 {len(idx)}행 · 시장 폭 {len(br)}행 "
        f"({(datetime.now(timezone.utc) - t0).seconds}초)")


def attempt(name: str, fn, *args):
    """한 가지가 실패해도 나머지 수집은 계속"""
    try:
        fn(*args)
    except Exception as e:
        log(f"{name} 실패", e)


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
                   st_hist=st.read("stocktwits"), news=newsmod.merge(st.read("news")),
                   finra=st.read("finra"), fred=st.read("fred"))
    res = build_all(m)
    rows = pd.DataFrame([{"ts": pd.Timestamp(now), "group": k, "panic": r.panic, "bad_news": r.bad_news,
                          "chg": r.chg} for k, r in res.items()])
    st.append("score", rows)
    log("점수", {k: (None if r.panic is None else round(r.panic)) for k, r in res.items()}, "실패", list(err))


class Skip(Exception):
    """할 일이 없어서 정상적으로 건너뜀 (예: 장 닫힘)"""


def main():
    """실행할 때마다 runs.csv에 (시각, 모드, 성공 여부, 걸린 시간)을 남겨요 → 앱 '데이터 상태'에서 확인"""
    t0 = datetime.now(timezone.utc)
    mode = sys.argv[1] if len(sys.argv) > 1 else "?"
    data = sys.argv[sys.argv.index("--data") + 1] if "--data" in sys.argv else "data"
    ok, note = True, ""
    try:
        run()
    except Skip as e:
        note = f"건너뜀: {e}"
        log(note)
    except SystemExit as e:
        ok, note = (e.code in (0, None)), str(e.code or "")
        raise
    except Exception as e:
        ok, note = False, f"{type(e).__name__}: {str(e)[:150]}"
        raise
    finally:
        try:
            LocalStore(data).append("runs", pd.DataFrame([{
                "ts": pd.Timestamp(t0), "mode": mode, "ok": ok,
                "secs": int((datetime.now(timezone.utc) - t0).total_seconds()), "note": note}]))
        except Exception:
            pass


def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["intraday", "daily", "backfill", "breadth", "kr", "kr_daily", "kr_hist"])
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--data", default="data")
    ap.add_argument("--since", default="2020-01-01", help="kr_hist: 이 날짜부터 한국 과거 수급을 채워요")
    args = ap.parse_args()

    if args.mode in ("kr", "kr_daily", "kr_hist"):  # 한국 시장은 알파카 키 없이
        st = LocalStore(args.data)
        now = datetime.now(timezone.utc)
        if args.mode != "kr_hist":
            update_kr(st, now, daily=args.mode == "kr_daily")
        if args.mode == "kr_daily" or (args.mode == "kr" and now.minute < 10 and kr.is_open(now)):
            attempt("한국 순위표", update_kr_rank, st)  # 장 마감 뒤 + 장중엔 한 시간에 한 번
        if args.mode in ("kr_daily", "kr_hist"):
            attempt("한국 과거 수급", update_kr_hist, st, pd.Timestamp(args.since).date())
            trim(st)
        return

    key, secret = os.environ.get("ALPACA_KEY"), os.environ.get("ALPACA_SECRET")
    if not key or not secret:
        sys.exit("ALPACA_KEY / ALPACA_SECRET 환경변수가 필요해요")
    # 수집기는 앱과 같은 키를 나눠 써요: 조금 느리게(분당 ~170회), 한도에 걸리면 더 오래 기다리며 재시도
    a = Alpaca(key, secret, min_interval=0.36, retries=10)
    st = LocalStore(args.data)
    now = datetime.now(timezone.utc)

    if args.mode == "intraday":
        if not a.clock().get("is_open"):
            raise Skip("미국 장 닫힘")
        o, c = session_bounds(sessions(a, 1)[-1])
        log(f"개인 수급 {fill_retail(a, st, o, c, now)}개 구간 추가")
        st_now = {}
        for sym in config.social_symbols():
            try:
                st_now[sym] = sources.fetch_stocktwits(sym)
                st.append("stocktwits", pd.DataFrame([dict(st_now[sym], ts=pd.Timestamp(now), sym=sym)]))
            except Exception as e:
                log("Stocktwits 실패", sym, e)
        attempt("뉴스", update_news, a, st, now)
        attempt("Finnhub 뉴스", update_finnhub_news, st, now)
        attempt("FINRA", update_finra, a, st, now)
        attempt("FRED", update_fred, st, now)
        record_scores(a, st, now, st_now)

    elif args.mode == "daily":
        day = sessions(a, 1)[-1]
        o, c = session_bounds(day)
        log(f"개인 수급 {fill_retail(a, st, o, c, now)}개 구간 추가 ({day['date']})")
        pc = sources.putcall_backfill([pd.Timestamp(day["date"]).date()])
        st.append("putcall", pc)
        log(f"풋/콜 {pc.to_dict('records')}")
        attempt("FINRA", update_finra, a, st, now)
        attempt("FRED", update_fred, st, now)
        attempt("미국 시장 폭", update_us_breadth, a, st)
        trim(st)

    elif args.mode == "breadth":  # 미국 시장 폭·신용 과거 기록 채우기
        update_us_breadth(a, st, pd.Timestamp(args.since if args.since != "2020-01-01" else "2016-01-01").date())

    else:  # backfill
        cal = sessions(a, max(args.days, 60))
        done = [d for d in cal if session_bounds(d)[1] < Alpaca.sip_end(now)]
        for d in done[-args.days:]:
            o, c = session_bounds(d)
            log(f"{d['date']} 개인 수급 {fill_retail(a, st, o, c, now)}개 구간")
        pc = sources.putcall_backfill([pd.Timestamp(d["date"]).date() for d in done[-60:]])
        st.append("putcall", pc)
        log(f"풋/콜 {len(pc)}일")
        attempt("뉴스", update_news, a, st, now)
        attempt("Finnhub 뉴스", update_finnhub_news, st, now)
        attempt("FINRA", update_finra, a, st, now)
        attempt("FRED", update_fred, st, now)
        trim(st)


if __name__ == "__main__":
    main()
