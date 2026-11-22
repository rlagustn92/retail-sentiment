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
    "kr_intraday": "kr_intraday.csv",  # ts, market, personal, foreign, inst, price, chg (한국 장중 10분마다)
    "kr_market": "kr_market.csv",      # date, market, personal, foreign, inst, price, chg (한국 일별)
}
KEYS = {"retail": ["bucket", "sym"], "putcall": ["date"], "stocktwits": ["ts", "sym"],
        "score": ["ts", "group"], "news": ["id"], "finra": ["date", "sym"], "fred": ["date", "series"],
        "kr_intraday": ["ts", "market"], "kr_market": ["date", "market"]}
DATE_COLS = {"retail": ["bucket"], "stocktwits": ["ts"], "score": ["ts"], "putcall": ["date"],
             "news": ["ts"], "finra": ["date"], "fred": ["date"], "kr_intraday": ["ts"], "kr_market": ["date"]}


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
    """data 브랜치의 CSV를 읽어요. 토큰이 틀렸거나 저장소 이름이 이상해도 공개 저장소면 토큰 없이·raw 주소로 다시 시도해요.
    마지막 실패 이유는 errors에 남겨 화면 아래에 보여줘요."""

    def __init__(self, repo: str, branch: str = "data", token: str | None = None):
        self.repo = (repo or "").strip().removeprefix("https://github.com/").strip("/")
        self.branch = branch or "data"
        self.token = (token or "").strip() or None
        self.errors: dict[str, str] = {}

    def _try(self, url: str, params: dict | None, headers: dict) -> requests.Response | None:
        try:
            return requests.get(url, params=params, headers=headers, timeout=20)
        except requests.RequestException:
            return None

    def read(self, name: str) -> pd.DataFrame:
        path = FILES[name]
        api = f"https://api.github.com/repos/{self.repo}/contents/{path}"
        raw = {"Accept": "application/vnd.github.raw"}
        tries = []
        if self.token:
            tries.append(("토큰", api, {"ref": self.branch}, dict(raw, Authorization=f"Bearer {self.token}")))
        tries.append(("토큰 없이", api, {"ref": self.branch}, raw))
        tries.append(("raw", f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/{path}", None, {}))
        fails = []
        for label, url, params, headers in tries:
            r = self._try(url, params, headers)
            if r is not None and r.status_code == 200 and r.text.strip():
                if fails:
                    self.errors[name] = " · ".join(fails)
                else:
                    self.errors.pop(name, None)
                return _parse(name, r.text)
            code = "연결 실패" if r is None else r.status_code
            if code == 404 and label != "토큰":
                if name == "retail":  # 수집기가 제일 먼저 만드는 파일인데 없으면 GH_REPO·DATA_BRANCH가 틀린 것
                    self.errors[name] = f"404 — GH_REPO '{self.repo}' · DATA_BRANCH '{self.branch}' 확인"
                else:
                    self.errors.pop(name, None)  # 아직 안 만들어진 파일 (정상)
                return pd.DataFrame()
            fails.append(f"{label} {code}")
        self.errors[name] = " · ".join(fails)
        return pd.DataFrame()


class NullStore:
    def read(self, name: str) -> pd.DataFrame:
        return pd.DataFrame()
