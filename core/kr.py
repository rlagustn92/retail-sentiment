"""한국 시장: 외국인·기관·개인 수급 (네이버 증권 공개 데이터, 키 없음).

- 지수(코스피·코스닥): 오늘 투자자별 순매수 금액(억원). 장중엔 잠정치로 계속 바뀌어요.
- 섹터: 대표 종목들의 투자자별 순매수(주식수 × 종가 → 억원)를 더해요. 종목별 최근 60거래일이 있어서
  '평소 대비 얼마나 많이 던졌나'(백분위)를 바로 계산해요.
- 한국 시장은 외국인+기관+개인+기타법인 순매수 합이 거의 0이에요. 그래서 '누가 파냐'보다
  '큰손(외국인+기관)이 평소보다 얼마나 세게 파는지, 개인이 그걸 받는지 같이 던지는지'를 봐요.
"""
from __future__ import annotations

import time
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


def _get(path: str, params: dict | None = None, tries: int = 4):
    """네이버는 한꺼번에 많이 부르면 가끔 막아요: 잠깐 쉬었다가 다시"""
    for i in range(tries):
        try:
            r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=15)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code}", response=r)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


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
    return _trend_frame(code, _get(f"stock/{code}/trend", {"pageSize": days}))


def stock_history(code: str, since, max_pages: int = 40) -> pd.DataFrame:
    """since까지 거슬러 올라가며 60거래일씩 받아요 (네이버 bizdate=그 날짜 이전 60거래일)"""
    rows, bizdate = [], None
    for _ in range(max_pages):
        params = {"pageSize": 60} | ({"bizdate": bizdate} if bizdate else {})
        page = _get(f"stock/{code}/trend", params)
        if not page:
            break
        rows += page
        oldest = page[-1]["bizdate"]
        if pd.Timestamp(oldest).date() <= since or oldest == bizdate:
            break
        bizdate = oldest
    df = _trend_frame(code, rows)
    return df[df["date"] >= since].drop_duplicates("date") if len(df) else df


def _trend_frame(code: str, rows: list) -> pd.DataFrame:
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


def index_history(market: str, since) -> pd.DataFrame:
    """지수 일별 종가·등락률 (since 이후)"""
    out = []
    for page in range(1, 80):
        rows = _get(f"index/{market}/price", {"pageSize": 60, "page": page})
        if not rows:
            break
        for r in rows:
            out.append({"date": pd.Timestamp(r["localTradedAt"]).date(), "market": MARKETS[market],
                        "close": num(r.get("closePrice")), "chg": (num(r.get("fluctuationsRatio")) or 0) / 100})
        if pd.Timestamp(rows[-1]["localTradedAt"]).date() < since:
            break
    df = pd.DataFrame(out, columns=["date", "market", "close", "chg"])
    return df[df["date"] >= since].drop_duplicates(["date", "market"]) if len(df) else df


def build_history(since, workers: int = 4) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(시장 합계, 섹터별, 지수, 시장 폭) 일별 기록. 시장 합계 = 지금 시총 상위 300 종목의 합(코스피 200·코스닥 100)"""
    idx = []
    for m in MARKETS:  # 지수는 먼저(가벼움)
        try:
            idx.append(index_history(m, since))
        except Exception:
            pass
    u = universe()
    codes = sorted(set(u["code"]) | {c for sct in SECTORS.values() for c in sct["members"]})

    def one(c):
        try:
            return stock_history(c, since)
        except Exception:
            return None

    with ThreadPoolExecutor(workers) as ex:
        parts = [x for x in ex.map(one, codes) if x is not None and len(x)]
    if not parts:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    t = pd.concat(parts, ignore_index=True)
    cols = ["foreign", "inst", "personal"]
    tu = t.merge(u[["code", "market"]], on="code")
    mk = tu.groupby(["date", "market"])[cols].sum()
    mk["n"] = tu.groupby(["date", "market"])["code"].nunique()
    allm = tu.groupby("date")[cols].sum()
    allm["n"] = tu.groupby("date")["code"].nunique()
    allm["market"] = "전체"
    market = pd.concat([mk.reset_index(), allm.reset_index()], ignore_index=True)
    secs = []
    for key, sct in SECTORS.items():
        x = t[t["code"].isin(sct["members"])]
        if x.empty:
            continue
        g = x.groupby("date")[cols].sum()
        g["chg"] = x.groupby("date")["chg"].mean()
        g["sector"] = key
        secs.append(g.reset_index())
    sector = pd.concat(secs, ignore_index=True) if secs else pd.DataFrame()
    index = pd.concat(idx, ignore_index=True) if idx else pd.DataFrame()
    from .bottom import breadth_from_closes
    close = tu.pivot_table(index="date", columns="code", values="close", aggfunc="last")
    close.index = pd.to_datetime(close.index)
    breadth = breadth_from_closes(close)
    for df in (market, sector, index, breadth):
        if len(df):
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC")
    return market, sector, index, breadth


# 한국 과거 폭락: 그 기간 큰손 순매도가 가장 셌던 날과 비교
KR_EVENTS = [
    ("2020 코로나 폭락", "2020-02-20", "2020-03-31"),
    ("2022 금리 인상 하락장", "2022-01-01", "2022-10-31"),
    ("2024 8월 블랙먼데이", "2024-08-01", "2024-08-09"),
    ("2024 12월 계엄 사태", "2024-12-03", "2024-12-20"),
    ("2025 4월 관세 쇼크", "2025-04-01", "2025-04-15"),
]


def _naive_dates(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s)
    return d.dt.tz_localize(None) if d.dt.tz is not None else d


def history_compare(hist_market: pd.DataFrame, index: pd.DataFrame | None, market: str = "전체") -> dict | None:
    """가장 최근 거래일 큰손 순매도를 과거와 비교. 금액은 시대마다 커져서 '평소(직전 60거래일 평균 크기)의 몇 배'로 봐요"""
    if hist_market is None or hist_market.empty or "market" not in hist_market:
        return None
    h = hist_market[hist_market["market"] == market].copy()
    if len(h) < 80:
        return None
    h["date"] = _naive_dates(h["date"])
    h = h.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    h["big"] = h["foreign"] + h["inst"]
    scale = h["big"].abs().rolling(60, min_periods=40).mean().shift(1)
    h["mult"] = -h["big"] / scale                       # +면 평소보다 몇 배 세게 팔았나
    h["big5"] = h["big"].rolling(5).sum()
    h["kospi"] = np.nan
    if index is not None and len(index) and "market" in index:
        ix = index[index["market"] == "코스피"].copy()
        ix["date"] = _naive_dates(ix["date"])
        h["kospi"] = ix.drop_duplicates("date").set_index("date")["chg"].reindex(h.index)
    cur = h.iloc[-1]
    rows = []
    for name, a, b in KR_EVENTS:
        w = h[(h.index >= a) & (h.index <= b)].dropna(subset=["mult"])
        if w.empty:
            continue
        d = w["mult"].idxmax()
        r = w.loc[d]
        rows.append({"name": name, "date": d, "big": float(r["big"]), "personal": float(r["personal"]),
                     "mult": float(r["mult"]), "kospi": None if pd.isna(r["kospi"]) else float(r["kospi"]),
                     "big5": float(w["big5"].min())})
    valid = h["mult"].dropna()
    pct = float((valid < cur["mult"]).mean() * 100) if len(valid) and not pd.isna(cur["mult"]) else None
    return {"date": h.index[-1], "big": float(cur["big"]), "personal": float(cur["personal"]),
            "foreign": float(cur["foreign"]), "inst": float(cur["inst"]),
            "mult": None if pd.isna(cur["mult"]) else float(cur["mult"]), "big5": float(cur["big5"]),
            "kospi": None if pd.isna(cur["kospi"]) else float(cur["kospi"]), "pct": pct,
            "since": int(h.index.min().year), "rows": rows}


def history_text(c: dict) -> str:
    if not c:
        return ""
    d = c["date"]
    s = f"{d.month}월 {d.day}일 큰손(외국인+기관) 순매수는 {fmt_eok(c['big'])}"
    if c["mult"] is not None and c["mult"] > 0:
        s += f"로, 평소의 {c['mult']:.1f}배 강도로 팔았어요"
        if c["pct"] is not None:
            top = 100 - c["pct"]
            s += f" ({c['since']}년 이후 상위 {top:.0f}%)" if top >= 1 else f" ({c['since']}년 이후 가장 센 1% 안)"
        s += "."
    else:
        s += "로, 매도 쪽이 아니에요."
    s += f" 그날 개인은 {fmt_eok(c['personal'])}."
    rows = c["rows"]
    if c["mult"] and c["mult"] > 0 and rows:
        worse = [r for r in rows if r["mult"] > c["mult"]]
        lo, hi = min(r["mult"] for r in rows), max(r["mult"] for r in rows)
        if len(worse) == len(rows):
            s += f" 과거 폭락 {len(rows)}번의 최악의 날(평소의 {lo:.1f}~{hi:.1f}배)보다는 약해요."
        elif worse:
            s += " " + ", ".join(f"'{r['name']}'" for r in worse) + " 최악의 날보다는 약하고, 나머지보다는 세요."
        else:
            s += f" 과거 폭락 {len(rows)}번의 최악의 날(평소의 {lo:.1f}~{hi:.1f}배)보다도 세요."
    if rows and c.get("big5") is not None:
        lo5, hi5 = min(r["big5"] for r in rows), max(r["big5"] for r in rows)
        s += f" 최근 5일 큰손 합계는 {fmt_eok(c['big5'])}(과거 폭락 때 5일 최저 {fmt_eok(hi5)}~{fmt_eok(lo5)})."
    return s


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
            foreign_sell_days: int | None = None, ndays: int = 5, big_score: float | None = None,
            base_days: int = 60) -> tuple[str, str]:
    if big_side is None and retail_side is None:
        return "수급 데이터를 기다리는 중", "장이 열리면 계산돼요."
    title, desc = KR_TEXT[(big_side or "flat", retail_side or "flat")]
    if big_score is not None and big_side == "sell":
        span = "최근 1년" if base_days >= 200 else f"최근 {base_days}거래일"
        desc += f" 큰손 매도 강도는 {span} 중 상위 {max(1, round(100 - big_score))}%예요."
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


def sector_summary(key: str, trends: pd.DataFrame, hist_sector: pd.DataFrame | None = None) -> dict | None:
    sec = SECTORS[key]
    t = trends[trends["code"].isin(sec["members"])] if not trends.empty else trends
    if t.empty:
        return None
    daily = t.groupby("date")[["foreign", "inst", "personal"]].sum().sort_index()
    daily["big"] = daily["foreign"] + daily["inst"]
    day = daily.index.max()
    cur, hist = daily.loc[day], daily.iloc[:-1].tail(60)
    base_days = len(hist)
    if hist_sector is not None and len(hist_sector) and "sector" in hist_sector:
        hs = hist_sector[hist_sector["sector"] == key].copy()
        hs["date"] = pd.to_datetime(hs["date"]).dt.date
        hs = hs[hs["date"] < day].drop_duplicates("date", keep="last").sort_values("date").tail(250)
        if len(hs) >= 120:  # 과거 기록이 있으면 최근 1년(약 250거래일)을 기준치로
            hs["big"] = hs["foreign"] + hs["inst"]
            hist, base_days = hs.set_index("date"), len(hs)
    big_sc = _score_series(float(cur["big"]), hist["big"].tolist())
    ret_sc = _score_series(float(cur["personal"]), hist["personal"].tolist())
    last5 = daily.tail(5)
    fsd = int((last5["foreign"] < 0).sum())
    title, desc = verdict(side(float(cur["big"]), big_sc), side(float(cur["personal"]), ret_sc),
                          float(cur["foreign"]), float(cur["inst"]), fsd, len(last5), big_sc, base_days)
    mem = t[t["date"] == day].copy()
    mem["name"] = mem["code"].map(sec["members"])
    mem5 = t[t["date"].isin(last5.index)].groupby("code")[["foreign", "inst", "personal"]].sum()
    mem = mem.join(mem5.add_suffix("_5d"), on="code").sort_values("chg", na_position="last")
    return {"key": key, "name": sec["name"], "date": day, "base_days": base_days, "foreign": float(cur["foreign"]), "inst": float(cur["inst"]),
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


def rank_table(names: pd.DataFrame, trends: pd.DataFrame, kind: str) -> pd.DataFrame:
    """종목별 가장 최근 거래일 순매수 + 5일 합계 (수집기가 미리 만들어 kr_rank.csv로 저장)"""
    if names is None or names.empty or trends is None or trends.empty:
        return pd.DataFrame()
    t = trends[trends["code"].isin(names["code"])]
    if t.empty:
        return pd.DataFrame()
    day = t["date"].max()
    last5 = sorted(t["date"].unique())[-5:]
    cols = ["foreign", "inst", "personal"]
    cur = t[t["date"] == day].set_index("code")[cols + ["chg"]]
    five = t[t["date"].isin(last5)].groupby("code")[cols].sum().add_prefix("five_")
    out = cur.join(five).join(names.set_index("code")[["name", "market"]]).reset_index()
    out["kind"], out["date"] = kind, str(day)
    return out


def rankings_from_table(tbl: pd.DataFrame, kind: str, who: str, side: str, n: int = 15):
    """미리 계산된 순위표 → (표, 기준일)"""
    t = tbl[tbl["kind"] == kind].copy() if tbl is not None and len(tbl) and "kind" in tbl else pd.DataFrame()
    if t.empty:
        return pd.DataFrame(), None
    day = pd.to_datetime(t["date"]).dt.date.max()
    t = t[(t[who] < 0) if side == "sell" else (t[who] > 0)].sort_values(who, ascending=(side == "sell")).head(n)
    t["five"] = t[f"five_{who}"]
    t.attrs["collected"] = pd.Timestamp(tbl["collected"].iloc[0]) if "collected" in tbl and len(tbl) else None
    return t.reset_index(drop=True), day


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
