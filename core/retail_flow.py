"""개인 매수/매도 추정 (BJZZ 방식, Boehmer·Jones·Zhang·Zhang 2021).

개인 주문은 대부분 도매업체(시타델 등)가 거래소 밖에서 체결하고, 이때 1센트 미만의
가격 개선을 해 줍니다. 그래서 거래소 밖(FINRA TRF, 알파카 거래소 코드 'D') 체결 중
- 센트 아래 끝자리가 0.6~1.0 → 개인 매수
- 센트 아래 끝자리가 0.0~0.4 → 개인 매도
로 분류합니다. 0.4~0.6(중간값 체결)과 딱 떨어지는 가격은 제외합니다.

한계: 개인 주문을 전부 잡지 못하고 방향도 가끔 틀립니다. 그래서 절대값보다
"평소 대비 얼마나 치우쳤는지"(백분위)로 봅니다.

기관(큰손) 추정도 같은 체결 데이터로 합니다.
- 한 건에 INST_MIN_USD(20만 달러) 이상 체결된 대량 체결만 봅니다.
- 방향은 틱 규칙: 직전 체결가보다 높으면 매수, 낮으면 매도, 같으면 직전 방향을 따릅니다.
- 시가·종가 단일가, 평균가·파생가 체결, 장외시간 체결처럼 방향이 없는 체결은 뺍니다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

OFF_EXCHANGE = "D"


def classify(trades: list[dict]) -> tuple[float, float, int]:
    """체결 리스트 → (개인 매수 주식수, 개인 매도 주식수, 분류된 건수)"""
    buy = sell = 0.0
    n = 0
    for t in trades:
        if t.get("x") != OFF_EXCHANGE:
            continue
        p = float(t["p"])
        cents = round(p * 100, 4)
        z = round(cents - int(cents), 4)  # 센트 아래 끝자리 (0~1)
        if 0 < z < 0.4:
            sell += t.get("s", 0)
            n += 1
        elif 0.6 < z < 1:
            buy += t.get("s", 0)
            n += 1
    return buy, sell, n


INST_MIN_USD = 200_000
# 방향을 알 수 없는 체결 조건 (SIP 조건 코드): 파생·평균가·단일가(시가/종가)·장외시간·순서 뒤바뀜 등
SKIP_COND = set("4567BCHMNOPQRTUVWXZ")


class TickState:
    """틱 규칙용으로 직전 체결가·방향을 기억 (구간·페이지가 바뀌어도 이어짐)"""

    def __init__(self):
        self.px: float | None = None
        self.dir = 0


def classify_inst(trades: list[dict], state: TickState, min_usd: float = INST_MIN_USD) -> tuple[float, float, int]:
    """체결 리스트 → (대량 매수 주식수, 대량 매도 주식수, 대량 체결 건수)"""
    buy = sell = 0.0
    n = 0
    for t in trades:
        if any(c in SKIP_COND for c in (t.get("c") or [])):
            continue
        p = float(t["p"])
        if state.px is not None:
            if p > state.px:
                state.dir = 1
            elif p < state.px:
                state.dir = -1
        state.px = p
        size = t.get("s", 0)
        if size * p < min_usd or state.dir == 0:
            continue
        n += 1
        if state.dir > 0:
            buy += size
        else:
            sell += size
    return buy, sell, n


def floor_bucket(dt: datetime, minutes: int) -> datetime:
    dt = dt.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return dt - timedelta(minutes=dt.minute % minutes)


def compute_buckets(alpaca, symbol: str, start: datetime, end: datetime,
                    minutes: int = 15) -> pd.DataFrame:
    """start~end 구간을 minutes 단위로 나눠 개인 매수/매도와 기관(대량 체결) 매수/매도를 집계합니다."""
    rows = []
    state = TickState()
    b = floor_bucket(start, minutes)
    while b + timedelta(minutes=minutes) <= end:
        b_end = b + timedelta(minutes=minutes)
        buy = sell = ib = isl = 0.0
        n = ni = 0
        for page in alpaca.trades(symbol, b, b_end):
            page = page or []
            pb, ps, pn = classify(page)
            qb, qs, qn = classify_inst(page, state)
            buy, sell, n = buy + pb, sell + ps, n + pn
            ib, isl, ni = ib + qb, isl + qs, ni + qn
        rows.append({"bucket": b, "retail_buy": buy, "retail_sell": sell, "n": n,
                     "inst_buy": ib, "inst_sell": isl, "n_inst": ni})
        b = b_end
    return pd.DataFrame(rows, columns=COLS)


COLS = ["bucket", "retail_buy", "retail_sell", "n", "inst_buy", "inst_sell", "n_inst"]


def net_sell_ratio(buy: float, sell: float) -> float | None:
    """(매도-매수)/(매도+매수). +면 개인이 파는 쪽, -면 사는 쪽."""
    tot = buy + sell
    return None if tot <= 0 else (sell - buy) / tot


def rolling_ratio(df: pd.DataFrame, window: int = 4, who: str = "retail") -> pd.Series:
    """최근 window개 구간(기본 1시간)을 합친 순매도 비율. who='retail'(개인) 또는 'inst'(기관·대량 체결)"""
    b = df[f"{who}_buy"].rolling(window, min_periods=1).sum()
    s = df[f"{who}_sell"].rolling(window, min_periods=1).sum()
    tot = (b + s).where(lambda x: x > 0)
    return (s - b) / tot
