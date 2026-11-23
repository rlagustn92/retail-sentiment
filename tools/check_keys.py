"""FRED·KRX 키가 실제로 되는지 점검 (GitHub Actions '키 점검'에서 실행).

키 값은 절대 출력하지 않아요. 상태 코드, 받은 개수, 마지막 날짜만 보여줘요.
KRX는 서비스마다 이용 승인을 따로 받아야 해서, 우리가 쓸 서비스를 하나씩 불러봐요.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import requests

KRX = "https://data-dbg.krx.co.kr/svc/apis"
KRX_SERVICES = [
    ("idx/drvprod_dd_trd", "파생상품지수 시세정보 (VKOSPI)"),
    ("drv/opt_bydd_trd", "옵션 일별매매정보 (풋/콜)"),
    ("sto/stk_bydd_trd", "유가증권 일별매매정보 (전 종목)"),
    ("sto/ksq_bydd_trd", "코스닥 일별매매정보 (전 종목)"),
]


def last_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def check_fred(key: str | None):
    print("=== FRED")
    if not key:
        print("  FRED_KEY 없음")
        return
    for sid in ("BAMLH0A0HYM2", "STLFSI4", "NFCI"):
        try:
            r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                             params={"series_id": sid, "api_key": key, "file_type": "json"}, timeout=60)
            obs = r.json().get("observations", []) if r.ok else []
            vals = [o for o in obs if o["value"] != "."]
            print(f"  {sid}: HTTP {r.status_code} · {len(vals)}개 · "
                  f"{vals[0]['date'] + ' ~ ' + vals[-1]['date'] + ' = ' + vals[-1]['value'] if vals else '-'}")
        except requests.RequestException as e:
            print(f"  {sid}: 연결 실패 ({type(e).__name__})")  # 예외 문구엔 키가 든 주소가 있어서 종류만


def check_krx(key: str | None):
    print("=== KRX")
    if not key:
        print("  KRX_KEY 없음")
        return
    print(f"  키 길이 {len(key)}자")
    d = last_weekday(date.today())
    for _ in range(5):  # 휴장일이면 하루씩 앞으로
        r = requests.get(f"{KRX}/idx/drvprod_dd_trd", params={"basDd": d.strftime("%Y%m%d")},
                         headers={"AUTH_KEY": key}, timeout=60)
        if r.ok and r.json().get("OutBlock_1"):
            break
        if not r.ok:
            break
        d = last_weekday(d)
    print(f"  기준일 {d}")
    for path, name in KRX_SERVICES:
        try:
            r = requests.get(f"{KRX}/{path}", params={"basDd": d.strftime("%Y%m%d")},
                             headers={"AUTH_KEY": key}, timeout=60)
        except requests.RequestException as e:
            print(f"  {name}: 연결 실패 ({type(e).__name__})")
            continue
        rows = []
        try:
            rows = r.json().get("OutBlock_1") or []
        except ValueError:
            pass
        msg = "" if rows else " · 응답: " + r.text[:160].replace("\n", " ")
        print(f"  {name}: HTTP {r.status_code} · {len(rows)}줄{msg}")
        if path.endswith("drvprod_dd_trd"):
            for x in rows:
                if "변동성" in x.get("IDX_NM", ""):
                    print(f"    {x['IDX_NM']}: 종가 {x['CLSPRC_IDX']} (시 {x['OPNPRC_IDX']} 고 {x['HGPRC_IDX']} 저 {x['LWPRC_IDX']})")
        if path.endswith("opt_bydd_trd") and rows:
            prods = sorted({x.get("PROD_NM", "") for x in rows})
            print(f"    상품: {', '.join(prods[:12])}")


if __name__ == "__main__":
    check_fred(os.environ.get("FRED_KEY") or None)
    check_krx(os.environ.get("KRX_KEY") or None)
