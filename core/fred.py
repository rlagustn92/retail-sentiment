"""FRED (세인트루이스 연준) 경제 데이터.

키가 있으면 공식 API를, 없으면 키 없이 받을 수 있는 CSV 주소를 써요.
"""
from __future__ import annotations

import io
import time
from datetime import date

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36", "Accept": "text/csv,*/*"}
API = "https://api.stlouisfed.org/fred/series/observations"
CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
COLS = ["date", "series", "value"]


def _frame(series_id: str, dates, values) -> pd.DataFrame:
    df = pd.DataFrame({"date": pd.to_datetime(dates, utc=True), "series": series_id,
                       "value": pd.to_numeric(values, errors="coerce")})
    return df.dropna(subset=["value"]).reset_index(drop=True)


def parse_csv(series_id: str, text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text))
    date_col = df.columns[0]  # observation_date (예전엔 DATE)
    return _frame(series_id, df[date_col], df[series_id])


def _get(url: str, params: dict, headers: dict | None = None, tries: int = 3) -> requests.Response:
    """FRED는 클라우드 서버에서 가끔 응답이 느려요. 시간 넉넉히, 몇 번 다시 시도."""
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=(10, 90))
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))
    raise RuntimeError("unreachable")


def series(series_id: str, start: date, key: str | None = None) -> pd.DataFrame:
    if key:
        r = _get(API, {"series_id": series_id, "api_key": key, "file_type": "json",
                       "observation_start": start.isoformat()})
        obs = r.json().get("observations", [])
        return _frame(series_id, [o["date"] for o in obs], [o["value"] for o in obs])  # 빈 값은 "."
    r = _get(CSV, {"id": series_id, "cosd": start.isoformat()}, headers=UA)
    return parse_csv(series_id, r.text)
