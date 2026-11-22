"""FRED (세인트루이스 연준) 경제 데이터.

키가 있으면 공식 API를, 없으면 키 없이 받을 수 있는 CSV 주소를 써요.
"""
from __future__ import annotations

import io
from datetime import date

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (retail-sentiment dashboard)"}
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


def series(series_id: str, start: date, key: str | None = None) -> pd.DataFrame:
    if key:
        r = requests.get(API, params={"series_id": series_id, "api_key": key, "file_type": "json",
                                      "observation_start": start.isoformat()}, timeout=30)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        return _frame(series_id, [o["date"] for o in obs], [o["value"] for o in obs])  # 빈 값은 "."
    r = requests.get(CSV, params={"id": series_id, "cosd": start.isoformat()}, headers=UA, timeout=30)
    r.raise_for_status()
    return parse_csv(series_id, r.text)
