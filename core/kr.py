"""한국 시장: 외국인·기관·개인 수급 (네이버 증권 공개 데이터, 키 없음).

- 지수(코스피·코스닥): 오늘 투자자별 순매수 금액(억원). 장중엔 잠정치로 계속 바뀌어요.
- 섹터: 대표 종목들의 투자자별 순매수(주식수 × 종가 → 억원)를 더해요. 종목별 최근 60거래일이 있어서
  '평소 대비 얼마나 많이 던졌나'(백분위)를 바로 계산해요.
- 한국 시장은 외국인+기관+개인+기타법인 순매수 합이 거의 0이에요. 그래서 '누가 파냐'보다
  '큰손(외국인+기관)이 평소보다 얼마나 세게 파는지, 개인이 그걸 받는지 같이 던지는지'를 봐요.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
import pandas as pd
import requests

from .scoring import percentile

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36"}
API = "https://m.stock.naver.com/api"
KST = "Asia/Seoul"
MARKETS = {"KOSPI": "코스피", "KOSDAQ": "코스닥"}
# 지수 순매수 '큰 매도' 기준(억원) — 기록이 20일 쌓이기 전까지 쓰는 고정 기준
MARKET_BIG = {"KOSPI": 3000, "KOSDAQ": 800}

# 섹터 = 시가총액 큰 대표 종목들. 바꾸고 싶으면 여기만 고치면 돼요.
SECTORS = {
    "semi": dict(name="반도체", members={"005930": "삼성전자", "000660": "SK하이닉스", "042700": "한미반도체",
                                         "000990": "DB하이텍", "058470": "리노공업", "403870": "HPSP",
                                         "039030": "이오테크닉스"}),
    "battery": dict(name="2차전지", members={"373220": "LG에너지솔루션", "006400": "삼성SDI", "247540": "에코프로비엠",
                                             "086520": "에코프로", "003670": "포스코퓨처엠", "066970": "엘앤에프",
                                             "051910": "LG화학"}),
    "auto": dict(name="자동차", members={"005380": "현대차", "000270": "기아", "012330": "현대모비스",
                                         "204320": "HL만도", "018880": "한온시스템"}),
    "bio": dict(name="바이오", members={"207940": "삼성바이오로직스", "068270": "셀트리온", "196170": "알테오젠",
                                        "000100": "유한양행", "028300": "HLB", "141080": "리가켐바이오",
                                        "326030": "SK바이오팜"}),
    "fin": dict(name="금융", members={"105560": "KB금융", "055550": "신한지주", "086790": "하나금융지주",
                                       "316140": "우리금융지주", "138040": "메리츠금융지주", "032830": "삼성생명",
                                       "000810": "삼성화재"}),
    "ship": dict(name="조선", members={"009540": "HD한국조선해양", "329180": "HD현대중공업", "042660": "한화오션",
                                        "010140": "삼성중공업"}),
    "defense": dict(name="방산", members={"012450": "한화에어로스페이스", "064350": "현대로템",
                                           "079550": "LIG디펜스앤에어로스페이스", "047810": "한국항공우주",
                                           "272210": "한화시스템"}),
    "power": dict(name="전력·원전", members={"267260": "HD현대일렉트릭", "298040": "효성중공업", "010120": "LS ELECTRIC",
                                             "034020": "두산에너빌리티", "015760": "한국전력"}),
    "net": dict(name="인터넷·게임", members={"035420": "NAVER", "035720": "카카오", "259960": "크래프톤",
                                              "036570": "NC", "251270": "넷마블"}),
    "ent": dict(name="엔터", members={"352820": "하이브", "035900": "JYP Ent.", "041510": "에스엠",
                                       "122870": "와이지엔터테인먼트"}),
    "steel": dict(name="철강·화학", members={"005490": "POSCO홀딩스", "004020": "현대제철", "011170": "롯데케미칼",
                                              "010130": "고려아연"}),
}


def num(x) -> float | None:
    """'+15,381' · '-2,299,994' · '45.86%' → 숫자"""
    if x is None:
        return None
    try:
        return float(str(x).replace(",", "").replace("%", "").replace("+", "").strip())
    except ValueError:
        return None


def _get(path: str, params: dict | None = None):
    r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=15)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- 받기
def index_now(market: str) -> dict:
    """지수 값·등락률과 오늘 투자자별 순매수(억원)"""
    b = _get(f"index/{market}/basic")
    t = _get(f"index/{market}/trend")
    return {"market": market, "name": MARKETS.get(market, market), "price": num(b.get("closePrice")),
            "chg": (num(b.get("fluctuationsRatio")) or 0) / 100, "status": b.get("marketStatus"),
            "time": pd.Timestamp(b["localTradedAt"]) if b.get("localTradedAt") else None,
            "date": pd.Timestamp(t["bizdate"]).date() if t.get("bizdate") else None,
            "personal": num(t.get("personalValue")), "foreign": num(t.get("foreignValue")),
            "inst": num(t.get("institutionalValue"))}


def stock_trend(code: str, days: int = 60) -> pd.DataFrame:
    """종목별 일별 투자자 순매수 → 억원 (주식수 × 그날 종가)"""
    rows = _get(f"stock/{code}/trend", {"pageSize": days})
    out = []
    for r in rows:
        close, diff = num(r.get("closePrice")), num(r.get("compareToPreviousClosePrice"))
        if not close:
            continue
        unit = close / 1e8
        out.append({"date": pd.Timestamp(r["bizdate"]).date(), "code": code,
                    "foreign": (num(r.get("foreignerPureBuyQuant")) or 0) * unit,
                    "inst": (num(r.get("organPureBuyQuant")) or 0) * unit,
                    "personal": (num(r.get("individualPureBuyQuant")) or 0) * unit,
                    "close": close, "chg": (diff / (close - diff)) if diff is not None and close != diff else None})
    return pd.DataFrame(out, columns=["date", "code", "foreign", "inst", "personal", "close", "chg"])


_PREF = ("우", "우B", "우C", "우(전환)")


def universe(kospi: int = 200, kosdaq: int = 100) -> pd.DataFrame:
    """시가총액 상위 종목 (ETF·우선주 제외): code, name, market"""
    rows = []
    for market, n in (("KOSPI", kospi), ("KOSDAQ", kosdaq)):
        got, page = 0, 1
        while got < n and page <= 6:
            j = _get(f"stocks/marketValue/{market}", {"page": page, "pageSize": 100})
            for x in j.get("stocks", []):
                nm = x.get("stockName", "")
                if x.get("stockEndType") != "stock" or nm.endswith(_PREF) or got >= n:
                    continue
                rows.append({"code": x["itemCode"], "name": nm, "market": MARKETS[market]})
                got += 1
            if not j.get("stocks"):
                break
            page += 1
    return pd.DataFrame(rows, columns=["code", "name", "market"])


def etf_universe(n: int = 150) -> pd.DataFrame:
    """시가총액 상위 ETF: code, name, market='ETF'"""
    rows, page = [], 1
    while len(rows) < n and page <= 5:
        j = _get("stocks/etf", {"page": page, "pageSize": 100})
        st = j.get("stocks", [])
        if not st:
            break
        rows += [{"code": x["itemCode"], "name": x.get("stockName", ""), "market": "ETF"} for x in st]
        page += 1
    return pd.DataFrame(rows[:n], columns=["code", "name", "market"])


def all_trends(days: int = 60, workers: int = 8, codes: list[str] | None = None) -> pd.DataFrame:
    codes = sorted(set(codes or []) | {c for s in SECTORS.values() for c in s["members"]})

    def one(c):
        try:
            return stock_trend(c, days)
        except Exception:
            return None

    with ThreadPoolExecutor(workers) as ex:
        parts = [p for p in ex.map(one, codes) if p is not None and len(p)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


# ---------------------------------------------------------------- 판정
KR_TEXT = {
    ("sell", "buy"): ("큰손이 던지고 개인이 받는 중",
                      "외국인·기관이 크게 팔고, 그 물량을 개인이 받고 있어요. 개인 항복(투매)은 아직 안 나온 모습이에요."),
    ("sell", "sell"): ("다 같이 던지는 중", "큰손과 개인이 함께 팔고 있어요. 본격 투매 구간의 수급이에요."),
    ("sell", "flat"): ("큰손 주도 매도", "외국인·기관 매도가 이끌고 있어요. 개인이 따라 던지기 시작하는지 지켜볼 구간이에요."),
    ("buy", "sell"): ("개인이 던지고 큰손이 받는 중",
                      "개인이 크게 팔고, 그 물량을 외국인·기관이 받아 가고 있어요. 항복 구간에서 자주 보이는 수급이에요."),
    ("buy", "buy"): ("다 같이 사는 중", "큰손과 개인 모두 사는 쪽이에요."),
    ("buy", "flat"): ("큰손 매수 우위", "외국인·기관이 사는 쪽이에요."),
    ("flat", "sell"): ("개인만 던지는 중", "큰손은 평소 수준인데 개인 매도가 많아요."),
    ("flat", "buy"): ("개인만 사는 중", "큰손은 평소 수준인데 개인이 많이 사고 있어요."),
    ("flat", "flat"): ("뚜렷한 쏠림 없음", "외국인·기관·개인 모두 평소 수준이에요."),
}


def side(net: float | None, sell_score: float | None, big: float | None = None) -> str | None:
    """순매수(억원)와 '매도 강도' 백분위 → sell / buy / flat. 기록이 없으면 big(억원) 고정 기준으로."""
    if net is None:
        return None
    if sell_score is None:
        if big is None:
            return "flat"
        return "sell" if net <= -big else "buy" if net >= big else "flat"
    if net < 0 and sell_score >= 60:
        return "sell"
    if net > 0 and sell_score <= 40:
        return "buy"
    return "flat"


def verdict(big_side: str | None, retail_side: str | None, foreign: float | None, inst: float | None,
            foreign_sell_days: int | None = None, ndays: int = 5, big_score: float | None = None) -> tuple[str, str]:
    if big_side is None and retail_side is None:
        return "수급 데이터를 기다리는 중", "장이 열리면 계산돼요."
    title, desc = KR_TEXT[(big_side or "flat", retail_side or "flat")]
    if big_score is not None and big_side == "sell":
        desc += f" 큰손 매도 강도는 최근 60거래일 중 상위 {max(1, round(100 - big_score))}%예요."
    if big_side == "sell" and foreign is not None and inst is not None and foreign < 0 and inst < 0:
        lead = "외국인" if foreign < inst else "기관"
        desc += f" 매도는 {lead}이 더 커요."
    if foreign_sell_days is not None and foreign_sell_days >= 4:
        desc += f" 외국인은 최근 {ndays}일 중 {foreign_sell_days}일 순매도예요."
    return title, desc


def _score_series(today: float | None, hist: list[float]) -> float | None:
    """매도 강도 백분위: 순매수가 평소보다 낮을수록(많이 팔수록) 높아요"""
    if today is None:
        return None
    return percentile(-today, [-x for x in hist])


def sector_summary(key: str, trends: pd.DataFrame) -> dict | None:
    sec = SECTORS[key]
    t = trends[trends["code"].isin(sec["members"])] if not trends.empty else trends
    if t.empty:
        return None
    daily = t.groupby("date")[["foreign", "inst", "personal"]].sum().sort_index()
    daily["big"] = daily["foreign"] + daily["inst"]
    day = daily.index.max()
    cur, hist = daily.loc[day], daily.iloc[:-1].tail(60)
    big_sc = _score_series(float(cur["big"]), hist["big"].tolist())
    ret_sc = _score_series(float(cur["personal"]), hist["personal"].tolist())
    last5 = daily.tail(5)
    fsd = int((last5["foreign"] < 0).sum())
    title, desc = verdict(side(float(cur["big"]), big_sc), side(float(cur["personal"]), ret_sc),
                          float(cur["foreign"]), float(cur["inst"]), fsd, len(last5), big_sc)
    mem = t[t["date"] == day].copy()
    mem["name"] = mem["code"].map(sec["members"])
    mem5 = t[t["date"].isin(last5.index)].groupby("code")[["foreign", "inst", "personal"]].sum()
    mem = mem.join(mem5.add_suffix("_5d"), on="code").sort_values("chg", na_position="last")
    return {"key": key, "name": sec["name"], "date": day, "foreign": float(cur["foreign"]), "inst": float(cur["inst"]),
            "personal": float(cur["personal"]), "big": float(cur["big"]), "big_score": big_sc, "retail_score": ret_sc,
            "five": {c: float(last5[c].sum()) for c in ("foreign", "inst", "personal", "big")},
            "foreign_sell_days": fsd, "ndays": len(last5),
            "chg": float(mem["chg"].mean()) if mem["chg"].notna().any() else None,
            "title": title, "desc": desc, "members": mem, "daily": daily.tail(30)}


def market_summary(now: dict, hist: pd.DataFrame | None = None) -> dict:
    """지수 하나: 오늘 순매수와 판정. hist(일별 기록)가 20일 넘게 쌓이면 백분위로."""
    big = (now.get("foreign") or 0) + (now.get("inst") or 0) if now.get("foreign") is not None else None
    big_sc = ret_sc = None
    if hist is not None and not hist.empty:
        h = hist[(hist["market"] == now["market"]) & (pd.to_datetime(hist["date"]).dt.date != now.get("date"))]
        if len(h) >= 20:
            big_sc = _score_series(big, (h["foreign"] + h["inst"]).tolist())
            ret_sc = _score_series(now.get("personal"), h["personal"].tolist())
    thr = MARKET_BIG.get(now["market"])
    title, desc = verdict(side(big, big_sc, thr), side(now.get("personal"), ret_sc, thr * 0.7 if thr else None),
                          now.get("foreign"), now.get("inst"), big_score=big_sc)
    return dict(now, big=big, big_score=big_sc, retail_score=ret_sc, title=title, desc=desc)


INVESTORS = {"foreign": "외국인", "inst": "기관", "personal": "개인"}


def rankings(trends: pd.DataFrame, names: pd.DataFrame, who: str, side: str, n: int = 15) -> tuple[pd.DataFrame, object]:
    """그날 투자자별 순매도(side='sell')·순매수('buy') 상위 종목. (표, 기준일)"""
    if trends is None or trends.empty:
        return pd.DataFrame(), None
    t = trends[trends["code"].isin(names["code"])] if names is not None and len(names) else trends
    day = t["date"].max()
    cur = t[t["date"] == day].set_index("code")
    last5 = sorted(t["date"].unique())[-5:]
    five = t[t["date"].isin(last5)].groupby("code")[who].sum()
    df = cur[[who, "chg"]].join(five.rename("five"))
    df = df.sort_values(who, ascending=(side == "sell")).head(n)
    df = df[(df[who] < 0) if side == "sell" else (df[who] > 0)]
    info = names.set_index("code") if names is not None and len(names) else pd.DataFrame()
    df["name"] = [info["name"].get(c, c) if len(info) else c for c in df.index]
    df["market"] = [info["market"].get(c, "") if len(info) else "" for c in df.index]
    return df.reset_index(), day


def is_open(now=None) -> bool:
    """한국 정규장(평일 9:00~15:30) 여부. 공휴일은 네이버 marketStatus로 따로 확인해요."""
    t = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC")
    t = (t.tz_localize("UTC") if t.tzinfo is None else t).tz_convert(KST)
    m = t.hour * 60 + t.minute
    return t.dayofweek < 5 and 540 <= m <= 930


def fmt_eok(x: float | None) -> str:
    """억원 → '+1.2조' / '-3,456억'"""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    a = abs(x)
    if a < 0.5:
        return "0억"
    sign = "+" if x > 0 else "-"
    return f"{sign}{a / 10000:.1f}조" if a >= 10000 else f"{sign}{a:,.0f}억"
