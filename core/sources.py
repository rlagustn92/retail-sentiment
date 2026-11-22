"""원자료 수집 함수 + 데모 데이터."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import cboe, config, realtime, stocktwits
from . import news as newsmod
from .alpaca import Alpaca
from .metrics import MarketData

ET = "America/New_York"


def bars_frame(raw: dict[str, list[dict]]) -> pd.DataFrame:
    rows = [{"ts": b["t"], "sym": sym, "c": b["c"], "v": b["v"], "vw": b.get("vw", b["c"])}
            for sym, bs in raw.items() for b in bs]
    df = pd.DataFrame(rows, columns=["ts", "sym", "c", "v", "vw"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def fetch_bars15(a: Alpaca, now: datetime) -> pd.DataFrame:
    """레버리지·인버스·섹터 ETF의 SIP 15분봉 (기준치용, 15분 지연)"""
    start = now - timedelta(days=int(config.BASELINE_DAYS * 1.5) + 5)
    return bars_frame(a.bars(config.bar_symbols(), "15Min", start, Alpaca.sip_end(now)))


def fetch_daily(a: Alpaca, now: datetime, feed: str) -> pd.DataFrame:
    start = now - timedelta(days=int(config.RVOL_DAYS * 1.6) + 7)
    end = Alpaca.sip_end(now) if feed == "sip" else now
    return bars_frame(a.bars(config.all_symbols(), "1Day", start, end, feed=feed))


def fetch_snapshots(a: Alpaca) -> dict:
    return a.snapshots(config.all_symbols(), feed="iex")


def news_symbols() -> list[str]:
    s = set()
    for g in config.GROUPS.values():
        s.update(g["members"])
        s.add(g["etf"])
    return sorted(s)


def fetch_news(a: Alpaca, start: datetime, end: datetime | None = None, max_pages: int = 80) -> pd.DataFrame:
    return newsmod.to_frame(a.news(news_symbols(), start, end, max_pages=max_pages))


def fetch_vix() -> dict:
    return {"vix_hist": cboe.index_history("VIX"), "vix3m_hist": cboe.index_history("VIX3M"),
            "vix_now": cboe.index_quote("VIX"), "vix3m_now": cboe.index_quote("VIX3M")}


def fetch_stocktwits(sym: str) -> dict:
    msgs, covered = stocktwits.fetch_recent(sym, max_pages=4)
    return stocktwits.summarize(msgs, covered)


def putcall_backfill(days: list[date]) -> pd.DataFrame:
    rows = []
    for d in days:
        try:
            v = cboe.equity_putcall_daily(d)
        except Exception:
            v = None
        if v is not None:
            rows.append({"date": pd.Timestamp(d, tz="UTC"), "equity_pc": v})
    return pd.DataFrame(rows, columns=["date", "equity_pc"])


# ---------------------------------------------------------------- 데모
DEMO_INTENSITY = {"semi": 0.95, "tech": 0.75, "ndx": 0.62, "disc": 0.28, "comm": 0.3, "spx": 0.4,
                  "bio": 0.22, "indu": 0.18, "fin": 0.22, "mat": 0.2, "energy": 0.14, "re": 0.1,
                  "health": 0.1, "staples": 0.04, "util": 0.06}


def demo_market(seed: int = 7) -> MarketData:
    """API 키 없이 화면을 볼 수 있는 가짜 데이터 (반도체·테크발 투매가 나온 날 가정)"""
    rng = np.random.default_rng(seed)
    now = datetime.now(timezone.utc)
    et_today = pd.Timestamp(now).tz_convert(ET).normalize().tz_localize(None)
    days = pd.bdate_range(end=et_today, periods=70)
    last_day = days[-1]
    n_today = 18

    inten: dict[str, float] = {}
    for k in config.SECTOR_KEYS + config.INDEX_KEYS:  # 종목은 자기 섹터의 강도를 따름
        g = config.GROUPS[k]
        for s in [g["etf"], g["flow"]] + ([g["inv"]] if g.get("inv") else []):
            inten[s] = DEMO_INTENSITY[k]
        for s in g["members"]:
            inten.setdefault(s, DEMO_INTENSITY[k])

    rows = []
    for k, g in config.GROUPS.items():
        lvl = DEMO_INTENSITY[k]
        for sym in [g["flow"]] + ([g["inv"]] if g.get("inv") else []):
            is_inv = sym == g.get("inv")
            price = 50.0
            for i, d in enumerate(days):
                last = d == last_day
                base_v = 2e6 * float(rng.lognormal(0, 0.35))
                for kk in range(n_today if last else 26):
                    ts = (pd.Timestamp(d).tz_localize(ET) + pd.Timedelta(minutes=570 + 15 * kk)).tz_convert("UTC")
                    drift = (-0.004 * lvl * (-1 if is_inv else 1)) if last else rng.normal(0, 0.005)
                    price *= 1 + drift + rng.normal(0, 0.002)
                    u = 1.6 - 0.9 * np.sin(np.pi * kk / 25)
                    mult = (1 + 1.25 * lvl * (1.1 if is_inv else 1)) if last else 1
                    rows.append({"ts": ts, "sym": sym, "c": price, "v": base_v * u * mult / 26,
                                 "vw": price * (0.25 if is_inv else 1)})
    bars = pd.DataFrame(rows).drop_duplicates(["ts", "sym"])

    rrows = []
    for k, g in config.GROUPS.items():
        lvl = DEMO_INTENSITY[k]
        for i, d in enumerate(days[-40:]):
            last = d == last_day
            for kk in range(n_today if last else 26):
                b = (pd.Timestamp(d).tz_localize(ET) + pd.Timedelta(minutes=570 + 15 * kk)).tz_convert("UTC")
                tot = 3e5 * (1 + rng.normal(0, 0.2))
                tilt = rng.normal(0, 0.09) + ((0.16 * lvl - 0.05 + 0.006 * kk * lvl) if last else 0)
                rrows.append({"bucket": b, "sym": g["flow"], "retail_buy": tot * (0.5 - tilt / 2),
                              "retail_sell": tot * (0.5 + tilt / 2), "n": 900})
    retail = pd.DataFrame(rrows).drop_duplicates(["bucket", "sym"])

    rt_rows = []
    for sym in config.all_symbols():
        lvl = inten.get(sym, 0.2)
        is_inv = any(g.get("inv") == sym for g in config.GROUPS.values())
        lev = 3 if any(g["flow"] == sym and g["flow"] != g["etf"] for g in config.GROUPS.values()) or is_inv else 1
        chg = (-0.045 * lvl * lev + rng.normal(0, 0.006)) * (-1 if is_inv else 1)
        if lvl < 0.1:
            chg = abs(rng.normal(0.004, 0.004))
        rvol = max(0.5, 0.8 + 2.0 * lvl + rng.normal(0, 0.35))
        price = float(rng.uniform(30, 600))
        rt_rows.append({"sym": sym, "price": price, "prev": price / (1 + chg), "chg": chg, "rvol": rvol,
                        "iex_vol": 1e5, "day": last_day.date(), "live": True})
    rt = pd.DataFrame(rt_rows)

    vdates = pd.bdate_range(end=et_today, periods=260)
    vix = pd.Series(16 + rng.normal(0, 1.5, len(vdates)).cumsum() * 0.2, index=vdates).clip(11, 40)
    vix3m = vix * 1.1 + rng.normal(0, 1.1, len(vdates))
    pc = pd.Series(0.64 + rng.normal(0, 0.12, 60), index=pd.bdate_range(end=et_today, periods=60))
    st_rows = []
    for sym in config.social_symbols():
        for t in pd.date_range(end=now, periods=300, freq="15min"):
            st_rows.append({"ts": t, "sym": sym, "msgs_per_hour": float(rng.lognormal(4.1, 0.45)),
                            "bear_ratio": float(np.clip(rng.normal(0.34, 0.11), 0.05, 0.9))})
    st_hist = pd.DataFrame(st_rows)
    st_now = {"SOXL": {"msgs_per_hour": 150.0, "bull": 26, "bear": 32, "bear_ratio": 32 / 58},
              "QQQ": {"msgs_per_hour": 110.0, "bull": 30, "bear": 26, "bear_ratio": 26 / 56},
              "SPY": {"msgs_per_hour": 80.0, "bull": 31, "bear": 20, "bear_ratio": 20 / 51}}

    heads = [
        ("Chip stocks slide as traders take profits after record run", -8, ["NVDA", "AMD", "SOXX"]),
        ("Nvidia supplier says AI demand remains strong", -25, ["NVDA", "TSM"]),
        ("Semiconductor ETF sees heavy outflows amid volatility", -41, ["SOXX", "MU"]),
        ("Oracle gains after new cloud partnership announcement", -55, ["ORCL"]),
        ("Micron shares tumble in broad tech selloff", -70, ["MU", "AAPL"]),
        ("Exxon steady as oil prices hold", -80, ["XOM"]),
        ("Banks mixed ahead of Fed minutes", -90, ["JPM", "BAC"]),
    ]
    items = [{"id": 10_000 + i, "created_at": (now + timedelta(minutes=m)).isoformat(), "headline": h,
              "source": "benzinga", "url": "https://www.benzinga.com", "symbols": s}
             for i, (h, m, s) in enumerate(heads)]
    pool = news_symbols()
    for j in range(1500):
        t = now - timedelta(hours=float(rng.uniform(1, 24 * 3)))
        items.append({"id": j, "created_at": t.isoformat(), "headline": str(rng.choice(
            ["Stock rises on demand", "Company update", "Shares fall on outlook", "Market wrap"])) + f" #{j}",
            "source": "benzinga", "url": "", "symbols": list(rng.choice(pool, 2))})
    news = newsmod.to_frame(items)

    sc_rows = []
    for k in config.GROUPS:
        lvl = DEMO_INTENSITY[k]
        for kk in range(n_today):
            ts = (pd.Timestamp(last_day).tz_localize(ET) + pd.Timedelta(minutes=585 + 15 * kk)).tz_convert("UTC")
            sc_rows.append({"ts": ts, "group": k,
                            "panic": float(np.clip(20 + (kk / n_today) * 80 * lvl + rng.normal(0, 4), 0, 100)),
                            "bad_news": float(np.clip(25 + rng.normal(0, 6), 0, 100))})
    return MarketData(now=now, market_open=True, bars=bars, rt=rt, retail=retail, vix_hist=vix, vix3m_hist=vix3m,
                      vix_now=float(vix.iloc[-1]) * 1.13, vix3m_now=float(vix3m.iloc[-1]), putcall_hist=pc,
                      putcall_now=0.84, putcall_intraday=True, st_now=st_now, st_hist=st_hist, news=news,
                      score_hist=pd.DataFrame(sc_rows), demo=True)


def rt_from(a_snaps, daily_sip, daily_iex, bars15, now, market_open) -> pd.DataFrame:
    prof = realtime.volume_profile(bars15)
    return realtime.rt_table(a_snaps, daily_sip, daily_iex, config.all_symbols(), prof, now, market_open)
