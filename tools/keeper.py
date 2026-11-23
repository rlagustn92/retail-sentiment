"""수집 순환 (keeper) — GitHub Actions 'keeper' 워크플로가 실행해요.

이 저장소에선 GitHub 예약(cron)이 거의 걸리지 않아서(2026-11-23 확인: 26분 동안 5분 예약 0번),
한 번 시작하면 스스로 이어 가는 방식으로 수집해요.

- 한 실행은 최대 --minutes분 동안 아래 시각표(예전 cron과 같음, UTC)대로 collector.py를 돌리고 저장해요.
- 시작 10분 뒤 다음 실행을 미리 대기열에 걸어 둬요(workflow_dispatch). 같은 concurrency 그룹이라
  지금 실행이 끝나거나 죽으면 바로 이어받아요. 대기열엔 늘 하나만 남아요.
- main에 새 코드가 올라오면 새 코드로 다음 실행을 다시 걸고, 하던 일만 마치고 넘겨줘요.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

# (이름, collector 모드, UTC 요일(월=0), UTC 시, 분 조건)
SLOTS = [
    ("kr", "kr", {0, 1, 2, 3, 4}, set(range(0, 7)), lambda m: m % 10 == 3),          # 한국 9:03~15:53, 10분마다
    ("kr_daily", "kr_daily", {0, 1, 2, 3, 4}, {7}, lambda m: m == 17),               # 한국 16:17 장 마감 정리
    ("kr_vol", "kr_vol", {6, 0, 1, 2, 3}, {23}, lambda m: m == 37),                  # 한국 08:37 전날 KRX 확정치
    ("us", "intraday", {0, 1, 2, 3, 4}, set(range(13, 22)), lambda m: m % 15 == 4),  # 미국 장중 15분마다
    ("us_daily", "daily", {0, 1, 2, 3, 4}, {21}, lambda m: m == 40),                 # 미국 장 마감 정리
]


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def matches(t: datetime) -> list[tuple[str, str]]:
    return [(name, mode) for name, mode, days, hours, mins in SLOTS
            if t.weekday() in days and t.hour in hours and mins(t.minute)]


def next_due(now: datetime) -> datetime:
    t = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(60 * 24 * 4):
        if matches(t):
            return t
        t += timedelta(minutes=1)
    return t


def sh(cmd: list[str], timeout: int) -> int:
    try:
        return subprocess.run(cmd, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        log("시간 초과:", " ".join(cmd))
        return -1


def dispatch(repo: str) -> bool:
    """다음 실행을 대기열에 (GITHUB_TOKEN으로 건 workflow_dispatch는 새 실행을 만들어요)"""
    for i in range(3):
        if sh(["gh", "workflow", "run", "keeper.yml", "--ref", "main", "-R", repo], 60) == 0:
            log("다음 실행을 대기열에 걸었어요")
            return True
        time.sleep(10 * (i + 1))
    log("다음 실행 걸기 실패 — 예비 예약이나 수동 실행으로 다시 시작해야 해요")
    return False


def main_sha(repo: str) -> str | None:
    try:
        out = subprocess.run(["git", "ls-remote", f"https://github.com/{repo}.git", "refs/heads/main"],
                             capture_output=True, text=True, timeout=30).stdout
        return out.split()[0] if out.strip() else None
    except Exception:
        return None


def run_slot(name: str, mode: str, data: str):
    log(f"=== {name} ({mode})")
    # 다른 수집(수동 실행 등)이 먼저 올렸을 수 있으니 최신 data 브랜치에서 시작
    sh(["git", "-C", data, "fetch", "-q", "--depth", "1", "origin", "data"], 120)
    sh(["git", "-C", data, "reset", "-q", "--hard", "FETCH_HEAD"], 60)
    sh([sys.executable, "collector.py", mode, "--data", data], 40 * 60)
    sh(["bash", "tools/save_data.sh", name], 10 * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--minutes", type=int, default=330)
    args = ap.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "rlagustn92/retail-sentiment")
    my_sha = os.environ.get("GITHUB_SHA")
    start = datetime.now(timezone.utc)
    deadline = start + timedelta(minutes=args.minutes)
    log(f"수집 순환 시작 · {args.minutes}분 · 다음 할 일 {next_due(start):%H:%M} UTC")
    dispatched, done, last_check = False, set(), start
    while True:
        now = datetime.now(timezone.utc)
        if not dispatched and now - start >= timedelta(minutes=10):
            dispatched = dispatch(repo)
        if now - last_check >= timedelta(minutes=5):  # 새 코드가 올라왔으면 새 코드로 넘겨줘요
            last_check = now
            sha = main_sha(repo)
            if my_sha and sha and sha != my_sha:
                log(f"main에 새 코드({sha[:7]}) — 새 코드로 다음 실행을 걸고 넘겨줘요")
                dispatch(repo)
                return
        # 지난 6분 안에 지나간 시각표 중 아직 안 한 것 (앞 작업이 길어 밀린 경우)
        for k in range(6, -1, -1):
            t = (now - timedelta(minutes=k)).replace(second=0, microsecond=0)
            for name, mode in matches(t):
                if (name, t) not in done:
                    done.add((name, t))
                    if datetime.now(timezone.utc) < start + timedelta(minutes=args.minutes + 5):
                        run_slot(name, mode, args.data)
        now = datetime.now(timezone.utc)
        if now >= deadline:
            break
        wait = (min(next_due(now), deadline) - now).total_seconds()
        time.sleep(max(5.0, min(wait, 60.0)))
    if not dispatched:
        dispatch(repo)
    log("수집 순환 끝 — 대기열의 다음 실행이 이어받아요")


if __name__ == "__main__":
    main()
