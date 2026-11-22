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
