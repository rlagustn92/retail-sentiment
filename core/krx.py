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
