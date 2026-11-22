"""지표 → 0~100점 변환, 종합 점수, 자동 해석 문장."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import config

MIN_HISTORY = 20  # 이보다 과거 데이터가 적으면 고정 눈금 사용


def percentile(value: float | None, history, higher_is_panic: bool = True) -> float | None:
    """과거 분포에서 현재 값의 위치(0~100). 클수록 공포."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    h = np.asarray([x for x in history if x is not None and not np.isnan(x)], dtype=float)
    if len(h) < MIN_HISTORY:
        return None
    p = (np.sum(h < value) + 0.5 * np.sum(h == value)) / len(h) * 100
    return float(p if higher_is_panic else 100 - p)


def fixed(value: float | None, key: str) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    lo, hi = config.FALLBACK_SCALE[key]
    return float(np.clip((value - lo) / (hi - lo) * 100, 0, 100))


def score(value, history, key: str) -> tuple[float | None, str]:
    """(점수, 방식) — 방식은 '백분위' 또는 '고정 눈금'"""
    p = percentile(value, history) if history is not None else None
    if p is not None:
        return p, "백분위"
    return fixed(value, key), "고정 눈금"


def level(s: float | None) -> tuple[str, str]:
    if s is None:
        return "데이터 없음", "#8b95a1"
    for th, name, color in config.LEVELS:
        if s >= th:
            return name, color
    return config.LEVELS[-1][1], config.LEVELS[-1][2]


@dataclass
class Indicator:
    key: str
    title: str
    value: float | None
    display: str            # 화면에 보일 값 (예: "1.08", "+12%")
    score: float | None     # 0~100, 클수록 공포
    method: str             # 백분위 / 고정 눈금
    caption: str            # 한 줄 요약 (예: "평소보다 높음")
    what: str               # 이 숫자가 뭔지
    how: str                # 어떻게 읽는지
    delay: str              # 데이터 지연
    extra: dict = field(default_factory=dict)


def caption_for(s: float | None, method: str) -> str:
    """신호등 경계(40/70)와 같은 기준으로 한 줄 요약"""
    if s is None:
        return "데이터를 못 받았어요"
    if method == "백분위":
        top = max(1, round(100 - s))
        if s >= 70:
            return f"평소보다 높아요 · 상위 {top}%"
        if s >= 40:
            return f"조금 높은 편이에요 · 상위 {top}%"
        return "평소 수준이에요"
    tail = " · 기준치 쌓는 중"
    return ("높아요" if s >= 70 else "조금 높은 편이에요" if s >= 40 else "보통이에요") + tail


def composite(inds: dict[str, Indicator]) -> float | None:
    tot = wsum = 0.0
    for k, w in config.WEIGHTS.items():
        ind = inds.get(k)
        if ind is None or ind.score is None:
            continue
        tot += ind.score * w
        wsum += w
    return None if wsum == 0 else tot / wsum


def interpret(panic: float | None, bad_news: float | None, price_chg: float | None) -> tuple[str, str]:
    """(제목, 설명) — 투매 점수와 악재 점수의 조합으로 상황을 한 문장으로. 경계값은 신호등과 같아요(40/70)."""
    if panic is None:
        return "데이터를 기다리는 중", "장이 열리면 점수가 계산돼요."
    hi_n = (bad_news or 0) >= 60
    down = price_chg is not None and price_chg < 0
    if panic >= 70 and not hi_n:
        return ("뉴스 없는 투매",
                "큰 악재 없이 개인이 겁먹고 던지고 있어요. 심리성 과매도일 가능성이 커요.")
    if panic >= 70:
        return ("악재 반영 투매",
                "악재 뉴스와 함께 개인이 던지고 있어요. 하락이 더 이어질 수 있어요.")
    if panic >= 40 and hi_n:
        return ("악재에 흔들리는 중",
                "악재 뉴스에 개인이 동요하기 시작했어요. 투매로 번지는지 지켜볼 구간이에요.")
    if panic >= 40:
        return ("투매 조짐",
                "몇몇 지표에서 던지는 움직임이 보여요. 아직 본격적인 투매는 아니에요.")
    if hi_n:
        return ("악재는 있는데 아직 덤덤",
                "악재가 나왔지만 개인은 아직 안 던졌어요. 하락 초입일 수 있어요.")
    if down:
        return ("평온한 조정", "가격은 빠지지만 공포는 크지 않아요.")
    return ("평온", "개인 투매 신호가 없어요.")


def _side(ratio: float | None, sc: float | None) -> str | None:
    """순매도 비율·백분위 점수 → 'sell' / 'buy' / 'flat'"""
    if ratio is None:
        return None
    lo, hi = config.FLOW_SIDE_SCORE
    if ratio > config.FLOW_SIDE_RATIO and (sc is None or sc >= hi):
        return "sell"
    if ratio < -config.FLOW_SIDE_RATIO and (sc is None or sc <= lo):
        return "buy"
    return "flat"


FLOW_TEXT = {
    ("sell", "buy"): ("기관이 던지고 개인이 받는 중",
                      "대량 매도가 나오는데 개인은 사고 있어요. 개인 항복(투매)은 아직 안 나온 모습이라, 하락 초·중반에 자주 보이는 수급이에요."),
    ("sell", "sell"): ("기관·개인 같이 던지는 중", "큰손과 개인이 함께 팔고 있어요. 본격 투매 구간의 수급이에요."),
    ("sell", "flat"): ("기관 주도 매도",
                       "큰손 매도가 이끌고 있고 개인은 아직 크게 움직이지 않았어요. 개인이 따라 던지기 시작하는지 지켜볼 구간이에요."),
    ("buy", "sell"): ("개인이 던지고 기관이 받는 중",
                      "개인 투매 물량을 큰손이 받아 가고 있어요. 하락 막바지(항복 구간)에 자주 보이는 수급이에요."),
    ("buy", "buy"): ("기관·개인 같이 사는 중", "큰손과 개인 모두 매수 쪽이에요."),
    ("buy", "flat"): ("기관 매수 우위", "큰손이 사는 쪽이고 개인은 뚜렷한 방향이 없어요."),
    ("flat", "sell"): ("개인만 던지는 중", "큰손은 조용한데 개인 매도가 많아요. 개인 공포가 먼저 나온 모습이에요."),
    ("flat", "buy"): ("개인만 사는 중", "큰손은 조용한데 개인이 사고 있어요."),
    ("flat", "flat"): ("뚜렷한 쏠림 없음", "큰손도 개인도 한쪽으로 크게 쏠리지 않았어요."),
}


def flow_verdict(inst_ratio, inst_score, retail_ratios: list, retail_scores: list, inst_trend=None) -> tuple[str, str]:
    """누가 던지고 누가 받는지 한 문장으로. 매수·매도 신호가 아니라 지금 수급 모습을 설명해요."""
    inst = _side(inst_ratio, inst_score)
    scores = list(retail_scores) + [None] * len(retail_ratios)
    sides = {_side(r, scores[i]) for i, r in enumerate(retail_ratios)} - {None}
    if sides in ({"sell"}, {"sell", "flat"}):
        retail = "sell"
    elif sides in ({"buy"}, {"buy", "flat"}):
        retail = "buy"
    else:
        retail = "flat" if sides else None  # 레버리지와 본체가 엇갈리면 '쏠림 없음'으로
    if inst is None and retail is None:
        return "수급 데이터를 기다리는 중", "장이 열리고 15분 뒤부터 계산돼요."
    title, desc = FLOW_TEXT[(inst or "flat", retail or "flat")]
    if inst_trend:
        five, sell_days, ndays = inst_trend
        if ndays >= 3 and five is not None:
            if five > config.FLOW_SIDE_RATIO and sell_days >= max(3, ndays - 1):
                desc += f" 기관은 최근 {ndays}일 중 {sell_days}일 매도 우위로, 며칠째 물량을 내놓고 있어요."
            elif five < -config.FLOW_SIDE_RATIO and ndays - sell_days >= max(3, ndays - 1):
                desc += f" 기관은 최근 {ndays}일 중 {ndays - sell_days}일 매수 우위예요."
    return title, desc
