"""FINRA 일별 공매도 거래량 (키 없이 공개, 하루 1번).

거래소 밖(장외)에서 체결된 거래 중 공매도로 신고된 물량이에요.
개인이 사면 증권사(마켓메이커)가 공매도로 물량을 대주는 경우가 많아서,
장외 공매도 비율은 개인 매수가 많을수록 올라가고 개인이 팔수록 내려가요.
"""
from __future__ import annotations

import io
from datetime import date

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (retail-sentiment dashboard)"}
URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{:%Y%m%d}.txt"
COLS = ["date", "sym", "short", "total", "ratio"]


def parse(text: str, symbols: list[str]) -> pd.DataFrame:
    """FINRA 파일(Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market) → 필요한 종목만"""
    df = pd.read_csv(io.StringIO(text), sep="|", dtype={"Date": str, "Symbol": str})
    df = df[df["Symbol"].isin(symbols) & df["TotalVolume"].notna()]
    if df.empty:
        return pd.DataFrame(columns=COLS)
    out = pd.DataFrame({
        "date": pd.to_datetime(df["Date"], format="%Y%m%d", utc=True),
        "sym": df["Symbol"],
        "short": df["ShortVolume"].astype(float),
        "total": df["TotalVolume"].astype(float),
    })
    out = out[out["total"] > 0]
    out["ratio"] = out["short"] / out["total"]
    return out.reset_index(drop=True)


def daily(d: date, symbols: list[str]) -> pd.DataFrame | None:
    """그날 파일이 아직 안 올라왔으면 None (FINRA는 미국 동부 오후 6시 전에 올려요)"""
    r = requests.get(URL.format(d), headers=UA, timeout=30)
    if r.status_code in (403, 404):
        return None
    r.raise_for_status()
    return parse(r.text, symbols)
