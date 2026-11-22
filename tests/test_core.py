"""오프라인 테스트: python -m pytest -q"""
from datetime import datetime, timedelta, timezone

import pandas as pd

from core import news, retail_flow as rf, scoring
from core import config, realtime
from core.metrics import build_all, market_summary
from core.sources import demo_market


def test_bjzz_classify():
    trades = [
        {"x": "D", "p": 80.1290, "s": 100},   # 0.90 → 매수
        {"x": "D", "p": 80.1210, "s": 50},    # 0.10 → 매도
        {"x": "D", "p": 80.1250, "s": 70},    # 0.50 중간 → 제외
        {"x": "D", "p": 80.12, "s": 999},     # 딱 떨어짐 → 제외
        {"x": "V", "p": 80.1290, "s": 300},   # 거래소 체결 → 제외
    ]
    buy, sell, n = rf.classify(trades)
    assert (buy, sell, n) == (100, 50, 2)
    assert abs(rf.net_sell_ratio(buy, sell) - (-1 / 3)) < 1e-9


def test_float_edge_cases():
    # 부동소수 오차로 0.9999 같은 값이 잘못 분류되지 않는지
    assert rf.classify([{"x": "D", "p": 12.3499, "s": 1}])[0] == 1   # 0.99 → 매수
    assert rf.classify([{"x": "D", "p": 12.3401, "s": 1}])[1] == 1   # 0.01 → 매도


def test_percentile_and_fixed():
    hist = list(range(100))
    assert scoring.percentile(95, hist) > 90
    assert scoring.percentile(5, hist) < 10
    assert scoring.percentile(5, hist[:5]) is None  # 기록 부족
    assert scoring.fixed(1.05, "vix") == 100
    assert scoring.fixed(0.85, "vix") == 0


def test_news_tone():
    assert news.tone("Micron shares plunge after weak guidance") < 0
    assert news.tone("Nvidia beats estimates, raises guidance") > 0
    assert news.tone("Semiconductor conference schedule") == 0


def test_interpret_matrix():
    assert scoring.interpret(80, 20, -0.05)[0] == "뉴스 없는 투매"
    assert scoring.interpret(80, 80, -0.05)[0] == "악재 반영 투매"
    assert scoring.interpret(50, 80, -0.05)[0] == "악재에 흔들리는 중"
    assert scoring.interpret(50, 10, -0.05)[0] == "투매 조짐"
    assert scoring.interpret(20, 80, -0.01)[0].startswith("악재는")
    assert scoring.interpret(10, 10, 0.02)[0] == "평온"


def test_demo_build_all_groups():
    res = build_all(demo_market())
    assert set(res) == set(config.GROUPS)
    semi = res["semi"]
    assert semi.panic is not None and 0 <= semi.panic <= 100
    assert set(semi.indicators) >= {"retail", "volume", "inverse", "breadth", "social"}
    assert "vix" not in res["tech"].indicators          # 섹터는 시장 전체 지표 제외
    assert "vix" in res["spx"].indicators               # 지수는 포함
    assert res["semi"].panic > res["util"].panic         # 데모: 반도체발 투매
    assert len(semi.members) == len(config.GROUPS["semi"]["members"])
    assert market_summary(res)["hot"][0].key in ("semi", "tech")


def test_volume_profile_and_rt():
    import numpy as np
    prof = realtime.volume_profile(demo_market().bars)
    assert len(prof) == 27 and prof[0] == 0 and abs(prof[-1] - 1) < 1e-9
    assert np.all(np.diff(prof) >= 0) and prof[13] > 0.35   # 장 중반이면 절반 가까이 참
    now = datetime(2026, 11, 20, 17, 0, tzinfo=timezone.utc)  # 미국 동부 12:00
    snaps = {"AAA": {"dailyBar": {"t": "2026-11-20T05:00:00Z", "c": 9.0, "v": 500},
                     "latestTrade": {"p": 9.0}}}
    daily = pd.DataFrame({"ts": pd.to_datetime(["2026-11-18T05:00:00Z", "2026-11-19T05:00:00Z"], utc=True),
                          "sym": ["AAA", "AAA"], "c": [11.0, 10.0], "v": [1000, 1000]})
    rt = realtime.rt_table(snaps, daily, daily, ["AAA"], prof, now, True)
    row = rt.iloc[0]
    assert abs(row["chg"] - (-0.1)) < 1e-9
    frac = realtime.profile_at(prof, 150)
    assert abs(row["rvol"] - 500 / (1000 * frac)) < 1e-9


class FakeAlpaca:
    """compute_buckets가 부르는 trades()만 흉내"""

    def trades(self, symbol, start, end):
        yield [{"x": "D", "p": 50.0091, "s": 10}, {"x": "D", "p": 50.0011, "s": 30}]


def test_compute_buckets():
    s = datetime(2026, 11, 20, 14, 30, tzinfo=timezone.utc)
    df = rf.compute_buckets(FakeAlpaca(), "SOXL", s, s + timedelta(minutes=45), 15)
    assert len(df) == 3
    assert df["retail_buy"].sum() == 30 and df["retail_sell"].sum() == 90
    roll = rf.rolling_ratio(df)
    assert abs(roll.iloc[-1] - 0.5) < 1e-9


# ---------------------------------------------------------------- FINRA · FRED · Finnhub
from core import finnhub, finra, fred
from core.metrics import MarketData, build_group
from core.store import LocalStore


def test_finra_parse():
    text = ("Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n"
            "20261120|SOXL|127.5|20|200|B,Q,N\n"
            "20261120|AAPL|10|0|40|B,Q,N\n"
            "20261120|TQQQ|0|0|0|B,Q,N\n"
            "12414\n")
    df = finra.parse(text, ["SOXL", "TQQQ"])
    assert list(df["sym"]) == ["SOXL"]                      # 거래량 0인 종목·마지막 줄(건수)은 제외
    assert abs(df["ratio"].iloc[0] - 127.5 / 200) < 1e-9
    assert df["date"].iloc[0] == pd.Timestamp("2026-11-20", tz="UTC")


def test_fred_parse_csv():
    df = fred.parse_csv("BAMLH0A0HYM2", "observation_date,BAMLH0A0HYM2\n2026-11-02,3.43\n2026-11-03,\n")
    assert len(df) == 1 and df["value"].iloc[0] == 3.43 and df["series"].iloc[0] == "BAMLH0A0HYM2"


def test_finnhub_frame_and_merge_dedup():
    items = [{"id": 1, "datetime": 1795000000, "headline": "Nvidia shares tumble on export curbs",
              "source": "Yahoo", "url": "u", "related": "NVDA"},
             {"id": 2, "datetime": 1795000100, "headline": "", "related": "NVDA"}]     # 제목 없음 → 제외
    fh = finnhub.to_frame(items, "AMD")
    assert list(fh["id"]) == ["fh-1"] and fh["symbols"].iloc[0] == ",NVDA,AMD,"
    alp = news.to_frame([{"id": 1, "created_at": "2026-11-18T09:00:00Z", "symbols": ["NVDA"],
                          "headline": "NVIDIA shares tumble on export curbs!"}])     # 같은 기사, 먼저 나옴
    merged = news.merge(fh, alp)
    assert len(merged) == 1 and merged["id"].iloc[0] == "1"          # id가 같아도(1 vs fh-1) 안 섞이고, 제목으로 중복 제거


def test_news_ids_survive_csv(tmp_path):
    st = LocalStore(tmp_path)
    st.append("news", news.to_frame([{"id": 5, "created_at": "2026-11-18T09:00:00Z", "headline": "a", "symbols": []}]))
    st.append("news", finnhub.to_frame([{"id": 5, "datetime": 1795000000, "headline": "b"}], "AMD"))
    st.append("news", news.to_frame([{"id": 5, "created_at": "2026-11-18T09:00:00Z", "headline": "a", "symbols": []}]))
    assert sorted(st.read("news")["id"]) == ["5", "fh-5"]              # 다시 읽어도 같은 기사는 하나


def _finra_hist(sym: str, last: float) -> pd.DataFrame:
    days = pd.bdate_range(end="2026-11-20", periods=61, tz="UTC")
    ratios = [0.60 + 0.01 * ((i * 7) % 5) for i in range(60)] + [last]
    return pd.DataFrame({"date": days, "sym": sym, "short": ratios, "total": 1.0, "ratio": ratios})


def test_short_indicator_direction():
    now = datetime(2026, 11, 23, 15, tzinfo=timezone.utc)
    low = build_group(MarketData(now=now, finra=_finra_hist("SOXL", 0.40)), "semi").indicators["short"]
    high = build_group(MarketData(now=now, finra=_finra_hist("SOXL", 0.80)), "semi").indicators["short"]
    assert low.score > 90 and high.score < 10                       # 공매도 비율이 낮을수록(개인 매도) 공포
    assert "11월 20일" in low.delay and low.display == "40%"


def test_credit_indicator_only_for_index_groups():
    now = datetime(2026, 11, 23, 15, tzinfo=timezone.utc)
    days = pd.bdate_range(end="2026-11-20", periods=260, tz="UTC")
    vals = [3.0 + 0.002 * i for i in range(259)] + [5.0]
    fr = pd.DataFrame({"date": days, "series": config.FRED_SERIES["credit"], "value": vals})
    m = MarketData(now=now, fred=fr)
    spx = build_group(m, "spx").indicators["credit"]
    assert spx.score > 95 and spx.display == "5.00%p"
    assert "credit" not in build_group(m, "semi").indicators


# ---------------------------------------------------------------- 기관(대량 체결) 수급 · 누가 던지나 · 역사 비교
from core import history
from core.scoring import flow_verdict


def test_classify_inst_tick_rule():
    st = rf.TickState()
    trades = [
        {"p": 100.00, "s": 100, "c": ["@"]},            # 기준가
        {"p": 100.10, "s": 3000, "c": ["@"]},           # 업틱 · 30만 달러 → 기관 매수
        {"p": 100.10, "s": 2500, "c": ["@"]},           # 같은 가격 → 직전 방향(매수) 유지
        {"p": 100.00, "s": 5000, "c": ["@", "F"]},      # 다운틱 · 50만 달러 → 기관 매도 (ISO 포함)
        {"p": 99.00, "s": 9000, "c": ["6"]},            # 종가 단일가 → 제외 (가격도 기억 안 함)
        {"p": 99.90, "s": 100, "c": ["@"]},             # 작은 체결: 방향만 갱신
        {"p": 99.95, "s": 1000, "c": ["@"]},            # 10만 달러 → 기준 미달
    ]
    buy, sell, n = rf.classify_inst(trades, st)
    assert (buy, sell, n) == (5500, 5000, 3)


def test_compute_buckets_has_inst_columns():
    s = datetime(2026, 11, 20, 14, 30, tzinfo=timezone.utc)
    df = rf.compute_buckets(FakeAlpaca(), "SOXX", s, s + timedelta(minutes=30), 15)
    assert list(df.columns) == rf.COLS and (df["inst_buy"] == 0).all()


def test_flow_verdict_matrix():
    t, _ = flow_verdict(0.30, 90, [-0.20], [10])
    assert t == "기관이 던지고 개인이 받는 중"
    t, _ = flow_verdict(0.30, 90, [0.20, 0.15], [90, 80])
    assert t == "기관·개인 같이 던지는 중"
    t, _ = flow_verdict(-0.30, 5, [0.20], [95])
    assert t == "개인이 던지고 기관이 받는 중"
    t, _ = flow_verdict(0.30, 90, [0.20, -0.20], [90, 10])               # 레버리지·본체가 엇갈리면 개인은 중립
    assert t == "기관 주도 매도"
    _, d = flow_verdict(0.30, 90, [-0.2], [10], (0.2, 5, 5))
    assert "5일 중 5일 매도 우위" in d
    assert flow_verdict(None, None, [], [])[0] == "수급 데이터를 기다리는 중"


def test_demo_who_is_selling():
    res = build_all(demo_market())
    semi = res["semi"]
    assert semi.inst is not None and semi.inst > 70 and semi.flow["rows"][0]["label"].startswith("기관 · SOXX")
    assert "retail_etf" in semi.indicators and "retail_etf" not in res["comm"].indicators   # XLC는 본체=레버리지
    assert market_summary(res)["inst"] is not None


def test_history_compare():
    idx = pd.bdate_range("2007-01-01", "2026-11-20")
    vix = pd.Series(15.0, index=idx)
    vix[pd.Timestamp("2008-11-20")] = 80.9
    vix[pd.Timestamp("2020-03-16")] = 82.7
    vix[pd.Timestamp("2018-12-24")] = 36.1
    c = history.compare(vix, None, now_vix=36.0)
    names = {r["name"]: r["vix"] for r in c["rows"]}
    assert names["2020 코로나 폭락"] == 82.7 and names["2008 리먼 사태"] == 80.9
    assert c["next_above"]["name"] == "2018 연말 급락" and c["pct"] > 99
    assert "2018 연말 급락" in history.summary(c)


# ---------------------------------------------------------------- 한국 시장 (네이버 데이터 모양만 흉내)
from core import kr


def test_kr_num_and_fmt():
    assert kr.num("+15,381") == 15381 and kr.num("-2,299,994") == -2299994 and kr.num("45.86%") == 45.86
    assert kr.fmt_eok(15381) == "+1.5조" and kr.fmt_eok(-9330) == "-9,330억" and kr.fmt_eok(None) == "–"


def test_kr_stock_trend_parse(monkeypatch):
    rows = [{"bizdate": "20261120", "foreignerPureBuyQuant": "-1,000,000", "organPureBuyQuant": "+500,000",
             "individualPureBuyQuant": "+500,000", "closePrice": "180,000", "compareToPreviousClosePrice": "-20,000"}]
    monkeypatch.setattr(kr, "_get", lambda path, params=None: rows)
    df = kr.stock_trend("005930")
    assert abs(df["foreign"].iloc[0] - (-1800)) < 1e-6          # 100만주 × 18만원 = 1,800억
    assert abs(df["chg"].iloc[0] - (-0.1)) < 1e-9


def _kr_trends(last_big: float, last_personal: float) -> pd.DataFrame:
    days = [d.date() for d in pd.bdate_range(end="2026-11-20", periods=40)]
    rows = []
    for i, d in enumerate(days):
        big = last_big if d == days[-1] else (i % 7 - 3) * 10.0
        per = last_personal if d == days[-1] else -big
        rows.append({"date": d, "code": "005930", "foreign": big * 0.6, "inst": big * 0.4, "personal": per,
                     "close": 1.0, "chg": -0.05 if d == days[-1] else 0.0})
    return pd.DataFrame(rows)


def test_kr_sector_verdicts():
    s = kr.sector_summary("semi", _kr_trends(-500, +500))
    assert s["big_score"] > 95 and s["title"] == "큰손이 던지고 개인이 받는 중"
    s = kr.sector_summary("semi", _kr_trends(+500, -500))
    assert s["title"] == "개인이 던지고 큰손이 받는 중" and s["members"]["name"].iloc[0] == "삼성전자"
    assert kr.sector_summary("auto", _kr_trends(-500, 500)) is None        # 해당 종목 데이터 없음


def test_kr_market_summary_fixed_threshold():
    now = {"market": "KOSPI", "date": pd.Timestamp("2026-11-20").date(), "foreign": -10956, "inst": -9330,
           "personal": 15381}
    m = kr.market_summary(now)
    assert m["title"] == "큰손이 던지고 개인이 받는 중" and m["big"] == -20286 and m["big_score"] is None
    quiet = kr.market_summary(dict(now, foreign=-100, inst=50, personal=60))
    assert quiet["title"] == "뚜렷한 쏠림 없음"


def test_kr_is_open():
    assert kr.is_open(pd.Timestamp("2026-11-23 01:00", tz="UTC"))          # 월 10시 (한국)
    assert not kr.is_open(pd.Timestamp("2026-11-22 01:00", tz="UTC"))      # 일요일
    assert not kr.is_open(pd.Timestamp("2026-11-23 07:00", tz="UTC"))      # 16시


def test_kr_rankings():
    rows = []
    for d in pd.bdate_range(end="2026-11-20", periods=6):
        for code, f in (("A", -100.0), ("B", 50.0), ("C", -300.0)):
            rows.append({"date": d.date(), "code": code, "foreign": f, "inst": 0.0, "personal": -f, "close": 1.0, "chg": -0.01})
    names = pd.DataFrame({"code": ["A", "B", "C"], "name": ["가", "나", "다"], "market": ["코스피"] * 3})
    df, day = kr.rankings(pd.DataFrame(rows), names, "foreign", "sell", 5)
    assert list(df["name"]) == ["다", "가"] and df["five"].iloc[0] == -1500 and str(day) == "2026-11-20"
    df, _ = kr.rankings(pd.DataFrame(rows), names, "personal", "buy", 5)
    assert list(df["name"]) == ["다", "가"]


def test_kr_stock_history_pages(monkeypatch):
    days = [d for d in pd.bdate_range("2026-01-01", "2026-11-20")][::-1]          # 최신 → 과거

    def fake_get(path, params=None):
        bd = params.get("bizdate")
        pool = [d for d in days if bd is None or d.strftime("%Y%m%d") < bd][:60]
        return [{"bizdate": d.strftime("%Y%m%d"), "foreignerPureBuyQuant": "-1", "organPureBuyQuant": "0",
                 "individualPureBuyQuant": "+1", "closePrice": "100,000,000", "compareToPreviousClosePrice": "0"}
                for d in pool]

    monkeypatch.setattr(kr, "_get", fake_get)
    df = kr.stock_history("005930", pd.Timestamp("2026-03-02").date())
    assert df["date"].min() == pd.Timestamp("2026-03-02").date() and df["date"].is_unique
    assert len(df) == len([d for d in days if d >= pd.Timestamp("2026-03-02")])


def test_kr_history_compare():
    dates = pd.bdate_range("2019-12-02", "2026-11-20")
    big = pd.Series(-100.0, index=dates)
    big[::2] = 100.0                                   # 평소 크기 100억
    big[pd.Timestamp("2020-03-12")] = -900             # 코로나: 평소의 9배
    big[pd.Timestamp("2024-08-05")] = -500             # 블랙먼데이: 5배
    big[dates[-1]] = -600                              # 지금: 6배
    hm = pd.DataFrame({"date": dates, "market": "전체", "foreign": big * 0.5, "inst": big * 0.5, "personal": -big, "n": 300})
    ix = pd.DataFrame({"date": dates, "market": "코스피", "close": 1.0, "chg": -0.01})
    c = kr.history_compare(hm, ix)
    names = {r["name"]: r for r in c["rows"]}
    assert round(names["2020 코로나 폭락"]["mult"]) == 9 and round(names["2024 8월 블랙먼데이"]["mult"]) == 5
    assert round(c["mult"]) == 6 and c["pct"] > 99 and c["kospi"] == -0.01
    t = kr.history_text(c)
    assert "평소의 6.0배" in t and "'2020 코로나 폭락'의 최악의 날보다는 약해요" in t
