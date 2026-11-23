"""KRX Open API (한국거래소 openapi.krx.co.kr).

- 키(KRX_KEY)가 있어야 하고, 서비스마다 이용 승인을 따로 받아야 해요 (승인 안 된 서비스는 401).
- 한 번 부를 때 하루치만 줘요. 키 하나로 하루 10,000번까지.
- 약관: 받은 데이터를 제3자에게 그대로 제공하면 안 되고, 화면엔 'KRX 정보데이터' 출처를 밝혀야 해요.
  우리 data 브랜치는 공개라서, 원본은 키에서 만든 비밀번호로 암호화해 두고 공개 파일엔 계산한 신호만 남겨요.
"""
from __future__ import annotations

import base64
import hashlib
import io
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data-dbg.krx.co.kr/svc/apis"
VKOSPI = "코스피200변동성지수"   # 응답 IDX_NM은 "코스피 200 변동성지수" (띄어쓰기 빼고 비교)
VKOSPI_START = date(2010, 1, 4)    # Open API가 주는 첫날
COLS = ["date", "open", "high", "low", "close"]


class NotApproved(Exception):
    """KRX에서 이 서비스 이용 승인을 아직 안 받았어요"""


def _num(x) -> float | None:
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _get(path: str, day: date, key: str, tries: int = 4) -> list[dict]:
    """키는 헤더로만 보내요 (오류 문구·주소에 키가 안 남게)"""
    for i in range(tries):
        try:
            r = requests.get(f"{BASE}/{path}", params={"basDd": day.strftime("%Y%m%d")},
                             headers={"AUTH_KEY": key}, timeout=30)
            if r.status_code == 401:
                raise NotApproved(f"{path} 이용 승인 안 됨 (401)")
            r.raise_for_status()
            return r.json().get("OutBlock_1") or []
        except NotApproved:
            raise
        except (requests.RequestException, ValueError):
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    return []


def vkospi_day(day: date, key: str) -> dict | None:
    """그날 VKOSPI 시·고·저·종가. 휴장일이거나 아직 안 나왔으면 None"""
    for x in _get("idx/drvprod_dd_trd", day, key):
        if str(x.get("IDX_NM", "")).replace(" ", "") == VKOSPI:
            close = _num(x.get("CLSPRC_IDX"))
            if close is None:
                return None
            return {"date": pd.Timestamp(day), "open": _num(x.get("OPNPRC_IDX")), "high": _num(x.get("HGPRC_IDX")),
                    "low": _num(x.get("LWPRC_IDX")), "close": close}
    return None


def weekdays(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def vkospi_range(days: list[date], key: str, workers: int = 4) -> tuple[pd.DataFrame, list[date]]:
    """여러 날 한꺼번에 (휴장일은 빈칸이라 건너뜀). (기록, 실패한 날짜)"""
    fails: list[date] = []

    def one(d):
        try:
            return vkospi_day(d, key)
        except NotApproved:
            raise
        except Exception:
            fails.append(d)
            return None

    with ThreadPoolExecutor(workers) as ex:
        rows = [r for r in ex.map(one, days) if r]
    df = pd.DataFrame(rows, columns=COLS)
    return df.sort_values("date").reset_index(drop=True), sorted(fails)


# ---------------------------------------------------------------- ETF 자금 흐름 (레버리지·곱버스)
ETF_START = date(2016, 1, 1)   # 곱버스(코스피200 인버스2X)가 2016년 9월에 나와서 그 앞쪽만 조금 넉넉히
ETF_GROUPS = {   # 공개 파일엔 이 묶음별 합계(계산한 결과)만 남겨요
    "k200_lev": "코스피200 레버리지",
    "k200_inv2": "코스피200 곱버스(인버스2X)",
    "k200_inv": "코스피200 인버스(1배)",
    "kq_lev": "코스닥150 레버리지",
    "kq_inv": "코스닥150 인버스",
    "other_lev": "그 밖의 레버리지 (업종·해외)",
    "other_inv": "그 밖의 인버스 (업종·해외)",
}


def etf_group(name: str, index_name: str) -> str | None:
    """종목명·기초지수로 묶음 정하기. 레버리지·인버스가 아니면 None"""
    import re
    text = f"{name} {index_name}"
    inv = "인버스" in text or "곱버스" in text
    lev = not inv and ("레버리지" in text or re.search(r"\b2X\b", name) is not None)
    if not inv and not lev:
        return None
    k200 = re.search(r"(코스피|KOSPI)\s*200|200\s*선물|F-KOSPI\s*200", text, re.I) is not None or name.split()[-1] in ("레버리지", "인버스")
    kq = re.search(r"(코스닥|KOSDAQ)\s*150", text, re.I) is not None
    if kq:
        return "kq_lev" if lev else "kq_inv"
    if k200:
        if lev:
            return "k200_lev"
        return "k200_inv2" if re.search(r"2X", text, re.I) else "k200_inv"
    return "other_lev" if lev else "other_inv"


def etf_day(day: date, key: str) -> pd.DataFrame:
    """그날 레버리지·인버스 ETF만: code, name, idx, group, units(상장좌수), nav, aum(순자산총액). 휴장일이면 빈 표"""
    rows = []
    for x in _get("etp/etf_bydd_trd", day, key):
        g = etf_group(str(x.get("ISU_NM", "")), str(x.get("IDX_IND_NM", "")))
        units, nav = _num(x.get("LIST_SHRS")), _num(x.get("NAV"))
        if g and units and nav:
            rows.append({"code": x.get("ISU_CD"), "name": x.get("ISU_NM"), "idx": x.get("IDX_IND_NM"), "group": g,
                         "units": units, "nav": nav, "aum": _num(x.get("INVSTASST_NETASST_TOTAMT")) or units * nav})
    return pd.DataFrame(rows, columns=["code", "name", "idx", "group", "units", "nav", "aum"])


def etf_flows(prev: pd.DataFrame, cur: pd.DataFrame, day: date) -> list[dict]:
    """전 거래일 대비 늘어난 좌수 × 오늘 NAV = 순유입(원). 새로 상장한 날·분할/병합한 날은 빼요"""
    m = cur.merge(prev[["code", "units", "nav"]], on="code", how="left", suffixes=("", "_p"))
    du = m["units"] - m["units_p"]
    ur, nr = m["units"] / m["units_p"], m["nav"] / m["nav_p"]
    split = ((ur >= 1.8) | (ur <= 0.55)) & ((ur * nr) > 0.7) & ((ur * nr) < 1.3)   # 좌수 2배·NAV 절반 = 분할
    m["flow"] = (du * m["nav"]).where(m["units_p"].notna() & ~split, 0.0)
    out = []
    for g in ETF_GROUPS:
        x = m[m["group"] == g]
        out.append({"date": pd.Timestamp(day), "group": g, "flow": round(float(x["flow"].sum()) / 1e8, 2),
                    "aum": round(float(x["aum"].sum()) / 1e8, 1), "n": int(len(x))})
    return out


def etf_range(days: list[date], key: str, workers: int = 4) -> tuple[list[tuple[date, pd.DataFrame]], list[date]]:
    fails: list[date] = []

    def one(d):
        try:
            return d, etf_day(d, key)
        except NotApproved:
            raise
        except Exception:
            fails.append(d)
            return d, None

    with ThreadPoolExecutor(workers) as ex:
        got = [(d, df) for d, df in ex.map(one, days) if df is not None and len(df)]
    return sorted(got, key=lambda t: t[0]), sorted(fails)


# ---------------------------------------------------------------- 원본 암호화 보관
def _fernet(key: str):
    from cryptography.fernet import Fernet
    k = hashlib.sha256(b"retail-sentiment/krx-raw:" + key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(k))


def save_raw(df: pd.DataFrame, path: Path, key: str) -> None:
    path.write_bytes(_fernet(key).encrypt(df.to_csv(index=False).encode("utf-8")))


def load_raw(path: Path, key: str) -> pd.DataFrame | None:
    """없거나 키가 바뀌어 못 풀면 None (그땐 처음부터 다시 받아요)"""
    if not path.exists():
        return None
    from cryptography.fernet import InvalidToken
    try:
        text = _fernet(key).decrypt(path.read_bytes()).decode("utf-8")
    except InvalidToken:
        return None
    df = pd.read_csv(io.StringIO(text))
    df["date"] = pd.to_datetime(df["date"])
    return df
