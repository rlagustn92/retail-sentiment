#!/usr/bin/env bash
# data 폴더(=data 브랜치)의 변경을 커밋하고 올려요.
# 미국·한국 수집이 동시에 돌아 다른 쪽이 먼저 올렸으면, 최신본 위에 '내가 바꾼 파일만' 다시 얹어서 올려요.
set -u
cd data || { echo "data 폴더 없음"; exit 0; }
git config user.name "collector-bot"
git config user.email "collector-bot@users.noreply.github.com"
git add -A
git commit -q -m "data $(date -u +%Y-%m-%dT%H:%MZ) ${1:-}" || { echo "변경 없음"; exit 0; }
OURS=$(git rev-parse HEAD)
if git rev-parse -q --verify HEAD~1 >/dev/null; then
  CHANGED=$(git diff --name-only HEAD~1 HEAD)
else
  CHANGED=$(git ls-files)
fi
for i in 1 2 3 4 5 6; do
  if git push -q origin HEAD:data; then
    echo "저장 완료 ($(echo "$CHANGED" | wc -w)개 파일)"
    exit 0
  fi
  echo "다른 수집이 먼저 저장했어요 — 최신본 위에 내 파일만 다시 얹어요 ($i)"
  sleep $((i * 3))
  git fetch -q --depth 1 origin data || continue
  git reset -q --hard FETCH_HEAD
  for f in $CHANGED; do git checkout -q "$OURS" -- "$f"; done
  git add -A
  git commit -q -m "data $(date -u +%Y-%m-%dT%H:%MZ) ${1:-}" || { echo "변경 없음"; exit 0; }
done
echo "저장 실패"
exit 1
