"""기록 저장소. 수집기는 로컬 폴더에 쓰고(GitHub Actions가 data 브랜치에 커밋),
앱은 GitHub API로 data 브랜치의 CSV를 읽습니다."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

FILES = {
    "retail": "retail_flow.csv",     # bucket, sym, retail_buy, retail_sell, n
    "putcall": "putcall.csv",        # date, equity_pc
    "stocktwits": "stocktwits.csv",  # ts, sym, msgs_per_hour, bull, bear, bear_ratio
    "score": "score.csv",            # ts, group, panic, bad_news, chg
    "news": "news.csv",              # id, ts, headline, source, url, symbols, tone
    "finra": "finra_short.csv",      # date, sym, short, total, ratio (FINRA 장외 공매도)
    "fred": "fred.csv",              # date, series, value
}
KEYS = {"retail": ["bucket", "sym"], "putcall": ["date"], "stocktwits": ["ts", "sym"],
        "score": ["ts", "group"], "news": ["id"], "finra": ["date", "sym"], "fred": ["date", "series"]}
DATE_COLS = {"retail": ["bucket"], "stocktwits": ["ts"], "score": ["ts"], "putcall": ["date"],
             "news": ["ts"], "finra": ["date"], "fred": ["date"]}


def _parse(name: str, text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), dtype={"id": str} if name == "news" else None)
    for c in DATE_COLS.get(name, []):
        if c in df:
            df[c] = pd.to_datetime(df[c], utc=True)
    return df


class LocalStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def read(self, name: str) -> pd.DataFrame:
        p = self.root / FILES[name]
        return _parse(name, p.read_text()) if p.exists() else pd.DataFrame()

    def write(self, name: str, df: pd.DataFrame) -> None:
        df.to_csv(self.root / FILES[name], index=False)

    def append(self, name: str, rows: pd.DataFrame) -> pd.DataFrame:
        if rows is None or rows.empty:
            return self.read(name)
        old = self.read(name)
        df = pd.concat([old, rows], ignore_index=True) if not old.empty else rows
        key = KEYS[name]
        df = df.drop_duplicates(key, keep="last").sort_values(key)
        self.write(name, df)
        return df


class GitHubStore:
    """비공개 저장소면 token(읽기 전용 권한)이 필요합니다."""

    def __init__(self, repo: str, branch: str = "data", token: str | None = None):
        self.repo, self.branch = repo, branch
        self.h = {"Accept": "application/vnd.github.raw"}
        if token:
            self.h["Authorization"] = f"Bearer {token}"

    def read(self, name: str) -> pd.DataFrame:
        url = f"https://api.github.com/repos/{self.repo}/contents/{FILES[name]}"
        r = requests.get(url, params={"ref": self.branch}, headers=self.h, timeout=20)
        if r.status_code != 200:
            return pd.DataFrame()
        return _parse(name, r.text)


class NullStore:
    def read(self, name: str) -> pd.DataFrame:
        return pd.DataFrame()
