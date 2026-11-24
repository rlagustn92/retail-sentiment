"""화면 조각(HTML/CSS). 토스 스타일: 큰 글씨, 둥근 카드, 여백, 최소한의 색."""
from __future__ import annotations

import html as _h

from core.scoring import level

CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
:root{--bg:#f2f4f6;--card:#ffffff;--text:#191f28;--sub:#6b7684;--faint:#8b95a1;--line:#e5e8eb;
--chip:#f2f4f6;--up:#f04452;--down:#3182f6;--track:#eef0f3;}
@media (prefers-color-scheme: dark){:root{--bg:#101012;--card:#1c1c20;--text:#ececef;--sub:#a3a3ab;
--faint:#7c7c85;--line:#2b2b31;--chip:#2a2a30;--track:#2a2a30;}}
html,body,.stApp,[class*="css"]{font-family:'Pretendard Variable',Pretendard,-apple-system,BlinkMacSystemFont,system-ui,sans-serif!important;}
.stApp{background:var(--bg)!important;color:var(--text);}
header[data-testid="stHeader"],#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"]{display:none!important;}
.block-container{max-width:600px!important;padding:14px 16px 48px!important;}
[data-testid="stVerticalBlock"]{gap:12px!important;}
[class*="st-key-card_"]{background:var(--card);border-radius:24px;padding:22px 20px 22px!important;}
[class*="st-key-card_"] [data-testid="stVerticalBlock"]{gap:6px!important;}
.top{display:flex;justify-content:space-between;align-items:center;padding:6px 4px 2px;}
.brand{font-size:19px;font-weight:800;letter-spacing:-0.4px;color:var(--text);}
.live{font-size:13px;color:var(--sub);display:flex;align-items:center;gap:6px;font-weight:500;}
.dot{width:7px;height:7px;border-radius:50%;background:#30a46c;display:inline-block;}
.dot.off{background:var(--faint);}
.demo{background:#fff4e5;color:#b25e00;border-radius:14px;padding:10px 14px;font-size:14px;font-weight:600;margin-bottom:4px;}
@media (prefers-color-scheme: dark){.demo{background:#3a2a12;color:#ffb44a;}}
.label{font-size:15px;color:var(--sub);font-weight:600;letter-spacing:-0.2px;}
.big{display:flex;align-items:baseline;gap:12px;margin:2px 0 4px;}
.num{font-size:68px;font-weight:800;letter-spacing:-2.5px;line-height:1.05;}
.unit{font-size:22px;font-weight:700;color:var(--faint);margin-left:-6px;}
.chip{font-size:15px;font-weight:700;padding:6px 12px;border-radius:999px;}
.gauge{position:relative;height:10px;border-radius:999px;background:var(--track);margin:14px 0 6px;overflow:visible;}
.gfill{position:absolute;left:0;top:0;bottom:0;border-radius:999px;}
.gticks{position:relative;height:16px;font-size:12px;color:var(--faint);font-weight:500;}
.gticks span{position:absolute;top:0;white-space:nowrap;}
.gmark{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--card);}
.drv{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px;}
.drv span{font-size:13px;font-weight:600;padding:6px 10px;border-radius:10px;background:var(--chip);color:var(--sub);}
.drv b{color:var(--text);font-weight:700;}
.head{font-size:24px;font-weight:800;letter-spacing:-0.6px;margin-top:18px;line-height:1.3;}
.desc{font-size:16px;color:var(--sub);line-height:1.55;margin-top:6px;font-weight:500;}
.hr{height:1px;background:var(--line);margin:18px 0 14px;}
.pair{display:flex;gap:10px;margin-bottom:6px;}
.pair.three{gap:8px;}.pair.three .mini{padding:12px 10px 10px;min-width:0;}.pair.three .mini .v{font-size:20px;}
.verdict{background:var(--chip);border-radius:14px;padding:12px 14px;margin:8px 0 10px;}
.verdict .vt{font-size:18px;font-weight:800;letter-spacing:-0.4px;}
.verdict .vd{font-size:14px;color:var(--sub);margin-top:4px;line-height:1.55;font-weight:500;}
.ftab{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:4px;}
.ftab th,.ftab td{padding:8px 3px;border-top:1px solid var(--line);text-align:right;font-weight:700;white-space:nowrap;}
.ftab th:first-child{text-align:left;font-weight:600;color:var(--sub);white-space:normal;}
.ftab thead th{font-size:12px;color:var(--faint);font-weight:600;border-top:none;padding-top:0;}
.vrow{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-top:1px solid var(--line);}
.vrow .a{font-size:15px;font-weight:700;}.vrow .b{font-size:13px;color:var(--sub);margin-top:2px;line-height:1.45;}
.vrow .sc{font-size:20px;font-weight:800;white-space:nowrap;}
.hrow{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) auto;gap:8px;align-items:center;padding:7px 0;font-size:13px;}
.hrow .n{font-weight:600;color:var(--sub);}.hrow.now .n{color:var(--text);font-weight:800;}
.hrow .v{font-weight:800;text-align:right;min-width:34px;}
.hrow .bar{height:8px;}
.tile .q{font-size:12px;font-weight:700;margin-top:3px;color:var(--faint);}
.mkt{display:flex;gap:6px;margin:2px 0 10px;}
.mkt a{font-size:14px;font-weight:800;padding:7px 14px;border-radius:12px;background:var(--card);color:var(--sub)!important;text-decoration:none!important;}
.mkt a.on{background:var(--text);color:var(--bg)!important;}
.kr3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px;}
.kr3 div{background:var(--chip);border-radius:14px;padding:10px 10px 9px;}
.kr3 .k{font-size:12px;color:var(--sub);font-weight:700;}.kr3 .v{font-size:18px;font-weight:800;margin-top:3px;letter-spacing:-0.4px;}
.kr3 .s{font-size:11px;color:var(--faint);font-weight:600;margin-top:2px;}
.krm{padding:14px 0;border-top:1px solid var(--line);}.krm:first-of-type{border-top:none;}
.krm .h{display:flex;justify-content:space-between;align-items:baseline;}
.krm .h .n{font-size:18px;font-weight:800;}.krm .h .p{font-size:15px;font-weight:800;}
.ktile{display:block;border-radius:18px;padding:13px 13px 11px;text-decoration:none!important;background:var(--chip);color:var(--text)!important;}
.ktile .n{font-size:15px;font-weight:800;}.ktile .t{font-size:13px;font-weight:700;margin-top:4px;line-height:1.35;}
.ktile .f{font-size:12px;color:var(--sub);font-weight:600;margin-top:5px;line-height:1.5;}
.mini{flex:1;background:var(--chip);border-radius:16px;padding:14px 14px 12px;}
.mini .k{font-size:13px;color:var(--sub);font-weight:600;}
.mini .v{font-size:22px;font-weight:800;letter-spacing:-0.5px;margin-top:4px;}
.mini .s{font-size:13px;font-weight:700;margin-top:2px;}
.sect{font-size:19px;font-weight:800;letter-spacing:-0.4px;margin-bottom:2px;}
.sectsub{font-size:14px;color:var(--faint);font-weight:500;margin-bottom:8px;}
details.row{border-top:1px solid var(--line);}
details.row:first-of-type{border-top:none;}
details.row summary{list-style:none;display:flex;justify-content:space-between;align-items:center;padding:15px 0;cursor:pointer;gap:12px;}
details.row summary::-webkit-details-marker{display:none;}
.rl .t{font-size:17px;font-weight:700;letter-spacing:-0.3px;color:var(--text);}
.rl .c{font-size:14px;color:var(--faint);margin-top:3px;font-weight:500;}
.rr{text-align:right;min-width:92px;}
.rr .v{font-size:20px;font-weight:800;letter-spacing:-0.4px;}
.bar{height:6px;border-radius:999px;background:var(--track);margin-top:7px;position:relative;width:92px;margin-left:auto;}
.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:999px;}
.body{background:var(--chip);border-radius:16px;padding:14px 16px;margin:0 0 14px;font-size:15px;line-height:1.6;color:var(--text);}
.body b{font-weight:700;}
.body .meta{color:var(--faint);font-size:13px;margin-top:8px;}
.news{display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--line);align-items:flex-start;}
.news:first-of-type{border-top:none;}
.tag{font-size:12px;font-weight:700;padding:3px 8px;border-radius:8px;white-space:nowrap;margin-top:2px;}
.news a{color:var(--text)!important;text-decoration:none;font-size:15px;font-weight:600;line-height:1.45;}
.news .m{font-size:12px;color:var(--faint);margin-top:3px;}
.foot{font-size:13px;color:var(--faint);line-height:1.6;padding:6px 6px 0;}
.empty{font-size:15px;color:var(--faint);padding:10px 0;}
.stAltairChart,.vega-embed{background:transparent!important;}
.nav{display:flex;gap:8px;overflow-x:auto;padding:4px 2px 6px;scrollbar-width:none;-webkit-overflow-scrolling:touch;}
.nav::-webkit-scrollbar{display:none;}
@media (hover:hover) and (pointer:fine){.stApp .nav{flex-wrap:wrap;overflow-x:visible;}}
.nav a{flex:0 0 auto;font-size:15px;font-weight:700;padding:9px 15px;border-radius:999px;background:var(--card);color:var(--sub)!important;text-decoration:none!important;letter-spacing:-0.2px;}
.nav a.on{background:var(--text);color:var(--bg)!important;}
.nav a .d{display:inline-block;width:6px;height:6px;border-radius:50%;margin-left:6px;vertical-align:middle;}
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;}
@media (min-width:560px){.tiles{grid-template-columns:repeat(3,1fr);}}
.tile{display:block;border-radius:18px;padding:14px 14px 12px;text-decoration:none!important;background:var(--chip);}
.tile .n{font-size:15px;font-weight:700;color:var(--text);letter-spacing:-0.3px;}
.tile .s{font-size:30px;font-weight:800;letter-spacing:-1px;margin-top:4px;line-height:1.1;}
.tile .c{font-size:13px;font-weight:700;margin-top:4px;}
.tile .l{font-size:12px;font-weight:700;float:right;margin-top:2px;}
.irow{display:flex;justify-content:space-between;align-items:center;padding:14px 0;border-top:1px solid var(--line);text-decoration:none!important;}
.irow:first-of-type{border-top:none;}
.irow .t{font-size:17px;font-weight:700;color:var(--text);}
.irow .c{font-size:14px;color:var(--faint);margin-top:2px;font-weight:500;}
.irow .r{text-align:right;}
.irow .v{font-size:24px;font-weight:800;letter-spacing:-0.6px;}
.irow .p{font-size:13px;font-weight:700;}
.mrow{display:flex;align-items:center;gap:10px;padding:11px 0;border-top:1px solid var(--line);}
.mrow:first-of-type{border-top:none;}
.mrow .nm{flex:1;min-width:0;}
.mrow .nm .a{font-size:16px;font-weight:700;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.mrow .nm .b{font-size:12px;color:var(--faint);font-weight:600;}
.mrow .ch{width:72px;text-align:right;font-size:16px;font-weight:800;}
.mrow .rv{width:86px;text-align:right;}
.mrow .rv .x{font-size:13px;font-weight:700;color:var(--sub);}
.mrow .rv .bar{width:70px;}
.sum{display:flex;gap:8px;margin:2px 0 8px;flex-wrap:wrap;}
.sum span{font-size:13px;font-weight:700;padding:6px 10px;border-radius:10px;background:var(--chip);color:var(--sub);}
.stElementContainer:has(iframe[height="0"]){display:none;}
details.sig summary{display:block;padding:16px 0 14px;}
.sh{display:flex;justify-content:space-between;align-items:center;gap:10px;}
.sh .st{font-size:16px;font-weight:700;letter-spacing:-0.3px;color:var(--text);}
.pill{font-size:13px;font-weight:800;padding:4px 11px;border-radius:999px;white-space:nowrap;}
.sv{display:flex;align-items:baseline;gap:10px;margin-top:6px;flex-wrap:wrap;}
.sbig{font-size:32px;font-weight:800;letter-spacing:-1px;line-height:1.1;}
.srule{font-size:13px;color:var(--faint);font-weight:600;}
.ssay{font-size:15px;font-weight:700;color:var(--text);margin-top:5px;line-height:1.45;letter-spacing:-0.2px;}
.seff{display:flex;justify-content:space-between;gap:8px;font-size:13px;font-weight:700;margin-top:6px;}
.seff .more{color:var(--faint);font-weight:600;white-space:nowrap;}
details.sig[open] .seff .more{visibility:hidden;}
.body .ftab th:first-child{white-space:nowrap;}
.snum{font-size:13px;color:var(--sub);font-weight:600;margin-top:3px;line-height:1.45;}
.gz{margin:10px 0 2px;}
.gz .ge{display:flex;justify-content:space-between;font-size:11px;font-weight:700;color:var(--faint);margin-bottom:4px;}
.gz .gt{position:relative;height:8px;border-radius:999px;background:var(--track);}
.gz .mk{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--faint);opacity:.7;}
.gz .dot{position:absolute;top:50%;width:14px;height:14px;border-radius:50%;transform:translate(-50%,-50%);border:2px solid var(--card);}
.gz .gm{position:relative;height:15px;font-size:11px;font-weight:700;color:var(--faint);}
.gz .gm span{position:absolute;top:3px;transform:translateX(-50%);white-space:nowrap;}
.easy{background:var(--card);border-radius:12px;padding:12px 14px;margin-bottom:10px;line-height:1.6;}
.easy .h{font-weight:800;margin-bottom:4px;}
.hl{display:flex;gap:8px;align-items:flex-start;margin-top:5px;}
.hl .tg{font-size:12px;font-weight:800;padding:2px 8px;border-radius:8px;white-space:nowrap;margin-top:2px;}
.back{font-size:15px;font-weight:700;color:var(--sub)!important;text-decoration:none!important;}
</style>
"""


def esc(s) -> str:
    return _h.escape(str(s))


def tint(hex_: str, a: float = 0.14) -> str:
    h = hex_.lstrip("#")
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
    return f"rgba({r},{g},{b},{a})"


def flat(s: str) -> str:
    """st.markdown이 들여쓰기를 코드블록으로 오해하지 않게 한 줄로"""
    return "".join(line.strip() for line in s.splitlines())


def top(updated: str, live: bool) -> str:
    return flat(f"""<div class="top"><div class="brand">개인투심체크</div>
<div class="live"><span class="dot{'' if live else ' off'}"></span>{esc(updated)}</div></div>""")


def inst_level(s) -> tuple[str, str]:
    """기관 매도 지수용 이름 (색은 신호등과 같게)"""
    if s is None:
        return "데이터 없음", "var(--faint)"
    _, color = level(s)
    return ("매우 높음" if s >= 70 else "높음" if s >= 40 else "보통"), color


def _side(x) -> tuple[str, str]:
    """순매도 비율(+면 매도) → 글자, 색 (매도 파랑 · 매수 빨강)"""
    if x is None or x != x:
        return "–", "var(--faint)"
    if abs(x) < 0.005:
        return "균형", "var(--sub)"
    return (f"매도 {abs(x) * 100:.0f}%", "var(--down)") if x > 0 else (f"매수 {abs(x) * 100:.0f}%", "var(--up)")


def market_switch(cur: str) -> str:
    """미국 / 한국 / 바닥 신호 전환"""
    return flat(f'''<div class="mkt"><a href="?" target="_self" class="{"on" if cur == "us" else ""}">🇺🇸 미국</a>
<a href="?m=kr" target="_self" class="{"on" if cur == "kr" else ""}">🇰🇷 한국</a>
<a href="?m=bottom" target="_self" class="{"on" if cur == "bottom" else ""}">🧭 바닥 신호</a></div>''')


def _won(x) -> tuple[str, str]:
    """억원 순매수 → 글자, 색 (매수 빨강 · 매도 파랑)"""
    from core.kr import fmt_eok
    if x is None or x != x:
        return "–", "var(--faint)"
    return fmt_eok(x), ("var(--up)" if x > 0 else "var(--down)" if x < 0 else "var(--sub)")


def kr_three(foreign, inst, personal, sub: str = "") -> str:
    cells = []
    for k, v in (("외국인", foreign), ("기관", inst), ("개인", personal)):
        t, c = _won(v)
        cells.append(f'<div><div class="k">{k}</div><div class="v" style="color:{c}">{esc(t)}</div>'
                     + (f'<div class="s">{esc(sub)}</div>' if sub else "") + "</div>")
    return '<div class="kr3">' + "".join(cells) + "</div>"


def kr_market_card(items: list[dict], label: str) -> str:
    out = []
    for x in items:
        ct, cc = _chg(x.get("chg"))
        sc = x.get("big_score")
        scs = "" if sc is None else f' · 큰손 매도 강도 <b style="color:{level(sc)[1]}">{sc:.0f}</b>'
        out.append(f"""<div class="krm"><div class="h"><div class="n">{esc(x['name'])}</div>
<div class="p">{'' if x.get('price') is None else f"{x['price']:,.2f}"} <span style="color:{cc}">{ct}</span></div></div>
{kr_three(x.get('foreign'), x.get('inst'), x.get('personal'))}
<div class="verdict"><div class="vt">{esc(x['title'])}</div><div class="vd">{esc(x['desc'])}{scs}</div></div></div>""")
    return flat(f"""<div class="label">한국 시장 수급 · {esc(label)}</div>{''.join(out)}
<div class="sectsub">오늘 누적 순매수(억원) · 빨강 매수 · 파랑 매도 · 외국인+기관 = 큰손</div>""")


def kr_tiles(secs: list[dict]) -> str:
    out = []
    for s in secs:
        sc = s.get("big_score")
        col = level(sc)[1] if sc is not None else "var(--faint)"
        bg = tint(col, 0.10) if sc is not None and sc >= 60 else "var(--chip)"
        ct, cc = _chg(s.get("chg"))
        f_, fc = _won(s["foreign"])
        i_, ic = _won(s["inst"])
        p_, pc = _won(s["personal"])
        out.append(f"""<a class="ktile" href="?m=kr&k={s['key']}" target="_self" style="background:{bg}">
<div class="n">{esc(s['name'])} <span style="color:{cc};font-size:13px">{ct}</span>
<span style="float:right;color:{col};font-size:13px">{'' if sc is None else f'매도 강도 {sc:.0f}'}</span></div>
<div class="t">{esc(s['title'])}</div>
<div class="f">외 <b style="color:{fc}">{esc(f_)}</b> · 기 <b style="color:{ic}">{esc(i_)}</b> · 개 <b style="color:{pc}">{esc(p_)}</b></div></a>""")
    return flat('<div class="tiles">' + "".join(out) + "</div>")


def kr_sector_hero(s: dict) -> str:
    sc = s.get("big_score")
    name, color = level(sc)
    val = "–" if sc is None else f"{sc:.0f}"
    w = 0 if sc is None else max(3, sc)
    ct, cc = _chg(s.get("chg"))
    d = s["date"]
    five = s["five"]
    return flat(f"""<div class="label">{esc(s['name'])} 큰손 매도 강도 · {d.month}월 {d.day}일 기준 · 평균 등락 <span style="color:{cc}">{ct}</span></div>
<div class="big"><span class="num" style="color:{color}">{val}</span><span class="unit">/100</span></div>
<div class="gauge"><div class="gfill" style="width:{w}%;background:{color}"></div>
<div class="gmark" style="left:40%"></div><div class="gmark" style="left:70%"></div></div>
<div class="gticks"><span style="left:0">평소</span><span style="left:40%;transform:translateX(-50%)">40</span>
<span style="left:70%;transform:translateX(-50%)">70</span></div>
<div class="head">{esc(s['title'])}</div><div class="desc">{esc(s['desc'])}</div>
<div class="label" style="margin-top:14px">오늘</div>{kr_three(s['foreign'], s['inst'], s['personal'])}
<div class="label" style="margin-top:12px">최근 {s['ndays']}일 합계</div>{kr_three(five['foreign'], five['inst'], five['personal'])}
<div class="sectsub" style="margin-top:8px">큰손 매도 강도: 외국인+기관 순매수가 최근 60거래일 중 얼마나 낮은지(많이 팔았는지)예요.</div>""")


def kr_members(mem) -> str:
    rows = []
    for _, r in mem.iterrows():
        ct, cc = _chg(r.get("chg"))
        cells = "".join(f'<td style="color:{_won(r[k])[1]}">{esc(_won(r[k])[0])}</td>' for k in ("foreign", "inst", "personal"))
        rows.append(f'<tr><th>{esc(r["name"])} <span style="color:{cc}">{ct}</span></th>{cells}</tr>')
    return flat(f"""<div class="sect">종목별 수급</div><div class="sectsub">많이 빠진 순 · 그날 순매수(억원)</div>
<table class="ftab"><thead><tr><th></th><th>외국인</th><th>기관</th><th>개인</th></tr></thead><tbody>{''.join(rows)}</tbody></table>""")


def kr_history_card(c: dict, text: str) -> str:
    items = [dict(r, now=False) for r in c["rows"]] + [{
        "name": "지금", "date": c["date"], "big": c["big"], "personal": c["personal"], "mult": c["mult"] or 0,
        "kospi": c["kospi"], "big5": c.get("big5"), "now": True}]
    items.sort(key=lambda r: -(r["mult"] or 0))
    mx = max([r["mult"] or 0 for r in items] + [1]) * 1.05
    rows = []
    for r in items:
        m = r["mult"] or 0
        sc = min(100.0, max(0.0, (m - 1) / 4 * 100))   # 1배=0, 5배 이상=100
        col = level(sc)[1] if r["now"] else "var(--faint)"
        w = max(2.0, min(100.0, m / mx * 100))
        d = r["date"]
        kc = "" if r.get("kospi") is None else f" · 코스피 {_chg(r['kospi'])[0]}"
        rows.append(f"""<div class="hrow{' now' if r['now'] else ''}"><div class="n">{esc(r['name'])}
<div style="font-size:11px;color:var(--faint);font-weight:600">{d.year % 100:02d}.{d.month:02d}.{d.day:02d} · 큰손 {esc(_won(r['big'])[0])} · 개인 {esc(_won(r['personal'])[0])}{esc(kc)}{'' if r.get('big5') is None else ' · 5일 ' + esc(_won(r['big5'])[0])}</div></div>
<div class="bar"><i style="width:{w:.0f}%;background:{col}"></i></div>
<div class="v" style="color:{col if r['now'] else 'var(--sub)'}">{m:.1f}배</div></div>""")
    return flat(f"""<div class="sect">역사 속 지금 (한국)</div>
<div class="sectsub">큰손(외국인+기관) 하루 순매도 강도 = 그날 순매도 ÷ 직전 60거래일 평균 크기 · 시총 상위 300 종목 합</div>
<div class="desc" style="font-size:15px;margin:2px 0 8px">{esc(text)}</div>{''.join(rows)}
<div class="sectsub" style="margin-top:10px">시장 규모가 커져서 금액 대신 '평소의 몇 배'로 비교해요. 과거 폭락은 그 기간 중 큰손이 가장 세게 판 날이에요.</div>""")


def kr_rank(df, who: str, side: str, day) -> str:
    if df is None or df.empty:
        return flat('<div class="empty">데이터를 못 받았어요</div>')
    rows = []
    for i, (_, r) in enumerate(df.iterrows(), 1):
        ct, cc = _chg(r.get("chg"))
        a, ac = _won(r[who])
        b, bc = _won(r.get("five"))
        rows.append(f'''<tr><th><span style="color:var(--faint);font-weight:700">{i}</span> {esc(r["name"])}
<span style="color:var(--faint);font-size:11px">{esc(r.get("market", ""))}</span></th>
<td style="color:{cc}">{ct}</td><td style="color:{ac}">{esc(a)}</td><td style="color:{bc}">{esc(b)}</td></tr>''')
    d = f"{day.month}월 {day.day}일" if day is not None else ""
    return flat(f"""<table class="ftab"><thead><tr><th>{esc(d)}</th><th>등락</th><th>그날</th><th>5일 합계</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>""")


def flow_card(flow: dict, inst) -> str:
    rows = []
    for r in flow.get("rows", []):
        cells = "".join(f'<td style="color:{_side(r[k])[1]}">{esc(_side(r[k])[0])}</td>' for k in ("now", "day", "five"))
        rows.append(f'<tr><th>{esc(r["label"])}</th>{cells}</tr>')
    nm, col = inst_level(inst)
    sc = "" if inst is None else f' · 기관 매도 지수 <b style="color:{col}">{inst:.0f}</b> ({esc(nm)})'
    return flat(f"""<div class="sect">누가 던지고 누가 받나</div>
<div class="sectsub">20만 달러 넘는 대량 체결 = 기관·큰손 추정{sc}</div>
<div class="verdict"><div class="vt">{esc(flow.get("title", ""))}</div><div class="vd">{esc(flow.get("desc", ""))}</div></div>
<table class="ftab"><thead><tr><th></th><th>최근 1시간</th><th>오늘</th><th>최근 5일</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<div class="sectsub" style="margin-top:6px">아래 선: 1시간 순매수 흐름 (+ 매수 우위 · − 매도 우위) · 15분 지연</div>""")


def flow_summary(results, inst_hot) -> str:
    rows = []
    for r in results:
        nm, col = inst_level(r.inst)
        val = "–" if r.inst is None else f"{r.inst:.0f}"
        rows.append(f"""<a class="vrow" href="?g={r.key}" target="_self" style="text-decoration:none;color:inherit">
<div><div class="a">{esc(r.name)} · {esc(r.flow.get("title", ""))}</div><div class="b">{esc(r.flow.get("desc", ""))}</div></div>
<div style="text-align:right"><div class="sc" style="color:{col}">{val}</div><div class="b">기관 매도</div></div></a>""")
    hot = ""
    if inst_hot:
        hot = ('<div class="label" style="margin-top:12px">기관 매도가 큰 섹터</div><div class="drv">' + "".join(
            f'<span>{esc(h.name)} <b style="color:{inst_level(h.inst)[1]}">{h.inst:.0f}</b></span>' for h in inst_hot)
               + "</div>")
    return flat(f"""<div class="sect">누가 던지고 누가 받나</div>
<div class="sectsub">대표 ETF 대량 체결(기관·큰손) vs 개인 · 기관 매도 지수 0~100 · 눌러서 자세히</div>
{''.join(rows)}{hot}""")


def history_card(c: dict, text: str) -> str:
    mx = c["max"] * 1.05
    items = [dict(r, now=False) for r in c["rows"]] + [{"name": "지금", "vix": c["now"], "ratio": c.get("now_ratio"),
                                                       "now": True}]
    items.sort(key=lambda r: -r["vix"])
    rows = []
    for r in items:
        sc = min(100.0, max(0.0, (r["vix"] - 12) / (50 - 12) * 100))
        col = level(sc)[1] if r["now"] else "var(--faint)"
        w = max(2.0, min(100.0, r["vix"] / mx * 100))
        rt = "" if not r.get("ratio") else f" · {r['ratio']:.2f}"
        rows.append(f"""<div class="hrow{' now' if r['now'] else ''}"><div class="n">{esc(r['name'])}</div>
<div class="bar"><i style="width:{w:.0f}%;background:{col}"></i></div>
<div class="v" style="color:{col if r['now'] else 'var(--sub)'}">{r['vix']:.0f}<span style="font-weight:600;color:var(--faint);font-size:11px">{esc(rt)}</span></div></div>""")
    return flat(f"""<div class="sect">역사 속 지금</div>
<div class="sectsub">과거 폭락 때 VIX 종가 최고치와 비교 · 작은 숫자는 VIX/VIX3M 최고치</div>
<div class="desc" style="font-size:15px;margin:2px 0 8px">{esc(text)}</div>{''.join(rows)}
<div class="sectsub" style="margin-top:10px">VIX 같은 시장 전체 공포는 시대가 달라도 비교할 만해요. 개인 수급은 수수료 무료화(2019)·개인 투자자 급증(2020)·0DTE 옵션 등으로 구조가 바뀌어 과거와 직접 비교하지 않아요.</div>""")


def hero(panic, head, desc, price, chg, bad, session, drivers=None, title="", etf="", flow="", flow_chg=None,
         inst=None) -> str:
    name, color = level(panic)
    val = "–" if panic is None else f"{panic:.0f}"
    w = 0 if panic is None else max(3, panic)
    if chg is None:
        pc, arrow, pcol = "", "", "var(--sub)"
    else:
        pcol = "var(--up)" if chg > 0 else "var(--down)" if chg < 0 else "var(--sub)"
        arrow = "▲" if chg > 0 else "▼" if chg < 0 else ""
        pc = f"{arrow} {abs(chg) * 100:.1f}%"
    bname, bcolor = level(bad)
    bval = "–" if bad is None else f"{bad:.0f}"
    ptxt = "–" if price is None else f"${price:,.2f}"
    fl = ""
    if flow and flow != etf and flow_chg is not None:
        fl = f'<span style="color:var(--faint);font-weight:600"> · {esc(flow)} {_chg(flow_chg)[0]}</span>'
    drv = ""
    if drivers:
        drv = '<div class="drv">' + "".join(
            f"<span>{esc(t)} <b>{esc(v)}</b></span>" for t, v in drivers) + "</div>"
    return flat(f"""
<div class="label">{esc(title)} 투매 지수 · {esc(session)}</div>
<div class="big"><span class="num" style="color:{color}">{val}</span><span class="unit">/100</span>
<span class="chip" style="background:{tint(color)};color:{color}">{esc(name)}</span></div>
<div class="gauge"><div class="gfill" style="width:{w}%;background:{color}"></div>
<div class="gmark" style="left:40%"></div><div class="gmark" style="left:70%"></div></div>
<div class="gticks"><span style="left:0">평온</span><span style="left:40%;transform:translateX(-50%)">경계 40</span>
<span style="left:70%;transform:translateX(-50%)">투매 70</span></div>
<div class="head">{esc(head)}</div>
<div class="desc">{esc(desc)}</div>{drv}
<div class="hr"></div>
<div class="pair three">
<div class="mini"><div class="k">{esc(etf)}</div><div class="v">{ptxt}</div><div class="s" style="color:{pcol}">{pc or '–'}{fl}</div></div>
<div class="mini"><div class="k">기관 매도 지수</div><div class="v" style="color:{inst_level(inst)[1]}">{'–' if inst is None else f'{inst:.0f}'}</div><div class="s" style="color:{inst_level(inst)[1]}">{esc(inst_level(inst)[0])}</div></div>
<div class="mini"><div class="k">악재 뉴스 지수</div><div class="v" style="color:{bcolor}">{bval}</div><div class="s" style="color:{bcolor}">{esc(bname)}</div></div>
</div>""")


def indicator_rows(inds, title: str = "지표별로 보기", sub: str = "눌러서 설명 보기 · 막대가 길수록 공포") -> str:
    out = []
    for ind in inds:
        name, color = level(ind.score)
        w = 0 if ind.score is None else max(4, ind.score)
        how = f"<b>읽는 법</b> {esc(ind.how)}"
        meta = f"{esc(ind.delay)}"
        if ind.method:
            meta += f" · {'최근 기록 대비 위치' if ind.method == '백분위' else '고정 기준'}로 점수화"
        if ind.score is not None:
            meta += f" · 점수 {ind.score:.0f}"
        out.append(f"""<details class="row"><summary>
<div class="rl"><div class="t">{esc(ind.title)}</div><div class="c">{esc(ind.caption)}</div></div>
<div class="rr"><div class="v" style="color:{color if ind.score is not None and ind.score >= 40 else 'var(--text)'}">{esc(ind.display)}</div>
<div class="bar"><i style="width:{w}%;background:{color}"></i></div></div></summary>
<div class="body"><b>이게 뭐예요</b> {esc(ind.what)}<br>{how}<div class="meta">{meta}</div></div></details>""")
    return flat(f"""<div class="sect">{esc(title)}</div>
<div class="sectsub">{esc(sub)}</div>{''.join(out)}""")


def news_list(df, fmt_time) -> str:
    if df is None or df.empty:
        return flat('<div class="sect">최근 반도체 뉴스</div><div class="empty">최근 뉴스가 없어요</div>')
    rows = []
    for _, r in df.iterrows():
        t = r["tone"]
        if t < 0:
            tag = '<span class="tag" style="background:rgba(49,130,246,.13);color:#3182f6">악재</span>'
        elif t > 0:
            tag = '<span class="tag" style="background:rgba(240,68,82,.12);color:#f04452">호재</span>'
        else:
            tag = '<span class="tag" style="background:var(--chip);color:var(--sub)">중립</span>'
        link = esc(r.get("url") or "#")
        rows.append(f"""<div class="news">{tag}<div><a href="{link}" target="_blank">{esc(r['headline'])}</a>
<div class="m">{esc(fmt_time(r['ts']))} · {esc(r.get('source', ''))}</div></div></div>""")
    return flat(f"""<div class="sect">최근 반도체 뉴스</div>
<div class="sectsub">헤드라인 단어로 악재·호재를 자동 분류해요</div>{''.join(rows)}""")


def section(title: str, sub: str = "") -> str:
    return flat(f'<div class="sect">{esc(title)}</div>' + (f'<div class="sectsub">{esc(sub)}</div>' if sub else ""))


def data_status(rows: list[dict]) -> str:
    """rows: name, basis(기준), age(몇 분 전), state('정상'|'지연'|'멈춤'|'장 마감'|'없음'), note"""
    color = {"정상": "#30a46c", "장 마감": "var(--sub)", "지연": "#f5a524", "멈춤": "#e5484d", "없음": "var(--faint)",
             "갱신 필요": "#f5a524", "만료": "#e5484d"}
    bad = [r for r in rows if r["state"] in ("지연", "멈춤", "갱신 필요", "만료")]
    head = "모두 정상" if not bad else f"{len(bad)}개 확인 필요"
    hc = "#30a46c" if not bad else "#f5a524"
    trs = "".join(
        f'<tr><th>{esc(r["name"])}<div style="font-size:11px;color:var(--faint);font-weight:500">{esc(r.get("note", ""))}</div></th>'
        f'<td style="text-align:left;font-weight:600">{esc(r["basis"])}</td>'
        f'<td style="color:{color.get(r["state"], "var(--sub)")}">{esc(r["state"])}</td></tr>' for r in rows)
    return flat(f"""<details class="row"{' open' if bad else ''}><summary>
<div class="rl"><div class="t">데이터 상태</div><div class="c">언제 기준 숫자인지 · 수집기가 제때 돌았는지</div></div>
<div class="rr"><div class="v" style="color:{hc};font-size:15px">{esc(head)}</div></div></summary>
<div class="body"><table class="ftab"><thead><tr><th>항목</th><th style="text-align:left">기준</th><th>상태</th></tr></thead>
<tbody>{trs}</tbody></table></div></details>""")


def footer(lines: list[str]) -> str:
    return flat('<div class="foot">' + "<br>".join(esc(x) for x in lines) + "</div>")


def _chg(x) -> tuple[str, str]:
    if x is None or x != x:
        return "–", "var(--sub)"
    col = "var(--up)" if x > 0 else "var(--down)" if x < 0 else "var(--sub)"
    return f"{'+' if x > 0 else ''}{x * 100:.1f}%", col


def nav(current: str, items: list[tuple[str, str, float | None]]) -> str:
    """가로 스크롤 탭. items = [(key, 이름, 점수)]"""
    out = []
    for key, nm, sc in items:
        dot = ""
        if sc is not None and sc >= 40:
            dot = f'<span class="d" style="background:{level(sc)[1]}"></span>'
        out.append(f'<a href="?g={key}" target="_self" class="{"on" if key == current else ""}">{esc(nm)}{dot}</a>')
    return flat('<div class="nav">' + "".join(out) + "</div>")


def tiles(results) -> str:
    out = []
    for r in results:
        name, color = level(r.panic)
        val = "–" if r.panic is None else f"{r.panic:.0f}"
        ct, cc = _chg(r.chg)
        bg = tint(color, 0.10) if r.panic is not None and r.panic >= 40 else "var(--chip)"
        out.append(f"""<a class="tile" href="?g={r.key}" target="_self" style="background:{bg}">
<div class="n">{esc(r.name)}<span class="l" style="color:{color}">{esc(name)}</span></div>
<div class="s" style="color:{color}">{val}</div>
<div class="c" style="color:{cc}">{esc(r.etf)} {ct}</div>
<div class="q">기관 매도 <b style="color:{inst_level(r.inst)[1]}">{'–' if r.inst is None else f'{r.inst:.0f}'}</b></div></a>""")
    return flat('<div class="tiles">' + "".join(out) + "</div>")


def index_rows(results) -> str:
    out = []
    for r in results:
        name, color = level(r.panic)
        ct, cc = _chg(r.chg)
        val = "–" if r.panic is None else f"{r.panic:.0f}"
        out.append(f"""<a class="irow" href="?g={r.key}" target="_self"><div><div class="t">{esc(r.name)}</div>
<div class="c">{esc(r.headline)}</div></div><div class="r"><div class="v" style="color:{color}">{val}</div>
<div class="p" style="color:{cc}">{esc(r.etf)} {ct}</div></div></a>""")
    return flat("".join(out))


def market_hero(panic, title, detail, hot, session, inst=None, inst_hot=None) -> str:
    name, color = level(panic)
    val = "–" if panic is None else f"{panic:.0f}"
    w = 0 if panic is None else max(3, panic)
    hot_html = ""
    if hot:
        hot_html = '<div class="drv">' + "".join(
            f'<span>{esc(h.name)} <b style="color:{level(h.panic)[1]}">{h.panic:.0f}</b></span>' for h in hot) + "</div>"
    return flat(f"""
<div class="label">미국 시장 투매 지수 · {esc(session)}</div>
<div class="big"><span class="num" style="color:{color}">{val}</span><span class="unit">/100</span>
<span class="chip" style="background:{tint(color)};color:{color}">{esc(name)}</span></div>
<div class="gauge"><div class="gfill" style="width:{w}%;background:{color}"></div>
<div class="gmark" style="left:40%"></div><div class="gmark" style="left:70%"></div></div>
<div class="gticks"><span style="left:0">평온</span><span style="left:40%;transform:translateX(-50%)">경계 40</span>
<span style="left:70%;transform:translateX(-50%)">투매 70</span></div>
<div class="head">{esc(title)}</div><div class="desc">{esc(detail)}</div>
{'<div class="label" style="margin-top:16px">공포가 가장 큰 섹터</div>' + hot_html if hot else ''}
{'' if inst is None else f'<div class="label" style="margin-top:12px">기관 매도 지수 (S&P500·나스닥) <b style="color:{inst_level(inst)[1]}">{inst:.0f}</b> · {esc(inst_level(inst)[0])}</div>'}""")


def members(df, br: dict, name_fn) -> str:
    if df is None or df.empty:
        return flat('<div class="sect">종목별 현황</div><div class="empty">데이터가 없어요</div>')
    sm = ""
    if br.get("n"):
        sm = (f'<div class="sum"><span>하락 <b>{br["down"]}</b>/{br["n"]}</span>'
              f'<span>투매형 <b>{br["dump"]}</b>개</span><span>평균 <b>{_chg(br["avg_chg"])[0]}</b></span></div>')
    rows = []
    for _, r in df.iterrows():
        ct, cc = _chg(r.get("chg"))
        rv = r.get("rvol")
        rvs = "–" if rv is None or rv != rv else f"{rv:.1f}배"
        sc = None if rv is None or rv != rv else min(100, max(0, (rv - 1) / 2 * 100))
        col = level(sc)[1] if sc is not None and (r.get("chg") or 0) < 0 else "var(--faint)"
        w = 0 if sc is None else max(4, sc)
        rows.append(f"""<div class="mrow"><div class="nm"><div class="a">{esc(name_fn(r['sym']))}</div>
<div class="b">{esc(r['sym'])}</div></div><div class="ch" style="color:{cc}">{ct}</div>
<div class="rv"><div class="x">거래량 {rvs}</div><div class="bar"><i style="width:{w}%;background:{col}"></i></div></div></div>""")
    return flat(f"""<div class="sect">종목별 현황</div>
<div class="sectsub">많이 빠진 순 · 거래량은 평소 같은 시각 대비 (실시간 추정)</div>{sm}{''.join(rows)}""")


# ---------------------------------------------------------------- 바닥 신호 탭
STATE_STYLE = {"켜짐": ("#30a46c", "켜짐"), "진행 중": ("#f5a524", "진행 중"), "아직": ("var(--faint)", "아직"),
               "데이터 없음": ("var(--faint)", "기록 쌓는 중"), "참고": ("var(--sub)", "참고")}
EFFECT_COLOR = {"과거 효과 있음": "#30a46c", "과거 효과 약함": "var(--sub)", "과거엔 오히려 나빴음": "#e5484d",
                "표본 적음": "var(--faint)"}


def _pct(x, sign=True):
    if x is None or x != x:
        return "–"
    return f"{x * 100:+.1f}%" if sign else f"{x * 100:.0f}%"


def bottom_badge(us: dict, kr: dict) -> str:
    """시장 탭 위쪽: 바닥 신호 요약 → 누르면 바닥 신호 탭"""
    def part(name, v):
        c = v["cnt"]
        return f'{name} 항복 <b>{c["항복"][0]}/{c["항복"][1]}</b> · 확인 <b>{c["확인"][0]}/{c["확인"][1]}</b>'
    return flat(f"""<a class="vrow" href="?m=bottom" target="_self" style="text-decoration:none;color:inherit;border-top:none;padding:4px 0">
<div><div class="a">🧭 바닥 신호 · {esc(us['title'])}</div><div class="b">{part('미국', us)} &nbsp;|&nbsp; {part('한국', kr)}</div></div>
<div class="sc" style="font-size:15px;color:var(--sub)">자세히 ›</div></a>""")


def bottom_hero(fg: dict | None, us: dict, kr: dict) -> str:
    fgs = "–" if not fg or fg.get("score") is None else f"{fg['score']:.0f}"
    from core.bottom import RATING_KO
    fgr = "" if not fg else RATING_KO.get(fg.get("rating"), fg.get("rating") or "")

    def col(v):
        return "#30a46c" if v["cnt"]["확인"][0] else "#f5a524" if v["cnt"]["항복"][0] else "var(--sub)"
    return flat(f"""<div class="label">바닥 신호 · 월가는 바닥을 맞히지 않고 '반등 확인'을 기다려요</div>
<div class="pair" style="margin-top:12px">
<div class="mini"><div class="k">개미 계기판 · CNN 공포탐욕</div><div class="v">{esc(fgs)}</div>
<div class="s" style="color:var(--sub)">{esc(fgr)} · 지난 한 달 백미러</div></div>
<div class="mini"><div class="k">월가식 체크리스트 · 미국</div><div class="v" style="color:{col(us)}">{us['cnt']['항복'][0] + us['cnt']['확인'][0]}개 켜짐</div>
<div class="s" style="color:var(--sub)">항복 {us['cnt']['항복'][0]}/{us['cnt']['항복'][1]} · 확인 {us['cnt']['확인'][0]}/{us['cnt']['확인'][1]}</div></div>
</div>
<div class="head" style="font-size:21px">{esc(us['title'])}</div><div class="desc">{esc(us['desc'])}</div>""")


# 신호마다: num = 이 숫자가 뭔지(늘 보임), easy = 쉽게 말하면, hi/lo = 높으면/낮으면,
# gauge = (왼쪽 끝 값, 오른쪽 끝 값, [(눈금 값, 글자)], 왼쪽 뜻, 오른쪽 뜻)
def _wash(who: str) -> dict:
    return {"num": f"{who} 회사 중, 주가가 최근 50일 평균보다 높은 회사의 비율",
            "easy": f"반 학생들 중 '요즘 평균 점수보다 잘 본 학생'이 몇 %인지 세는 것과 같아요. 평소엔 절반 넘게(50~70%)가 "
                    "평균 위에 있어요. 15% 아래면 거의 모든 회사 주가가 무너진 거예요 — 사람들이 겁에 질려 다 같이 팔아 버린 "
                    "'투매' 바닥에서 자주 나와요.",
            "hi": "높을수록 시장이 튼튼해요 (바닥과는 거리가 멀어요)", "lo": "15% 아래면 거의 다 무너진 바닥권",
            "gauge": (0.0, 1.0, [(0.15, "15%"), (0.5, "50%")], "다 무너짐", "대부분 튼튼")}


def _zbt(who: str) -> dict:
    return {"num": f"{who} 중 그날 주가가 오른 회사 비율의 10일 평균",
            "easy": "매일 '오늘 오른 회사가 몇 %?'를 세서 10일 평균을 내요. 보통은 절반(50%) 근처예요. 40% 아래로 떨어졌다는 건 "
                    "열흘 내내 거의 다 떨어졌다는 뜻이고, 그러다 10일 안에 61.5% 넘게 확 올라가면 '다 같이 사러 몰려왔다'는 뜻이에요. "
                    "이렇게 짧은 시간에 분위기가 완전히 뒤집히는 건 드물어서, 하락이 끝났다는 강한 증거로 봐요.",
            "hi": "61.5% 넘게 치솟으면 다 같이 사러 몰려옴 (강한 반등 신호)", "lo": "40% 아래면 열흘 내내 다 같이 떨어짐 (준비 조건)",
            "gauge": (0.25, 0.75, [(0.40, "40%"), (0.615, "61.5%")], "다 같이 하락", "다 같이 상승")}


EXPLAIN = {
    "us_washout": _wash("S&P500 500개"),
    "kr_washout": _wash("코스피·코스닥 시총 상위 300개"),
    "us_zbt": _zbt("S&P500 회사"),
    "kr_zbt": _zbt("시총 상위 300개 회사"),
    "us_retail": {
        "num": "그날 SPY(S&P500 ETF)에서 개인이 판 돈이 산 돈보다 얼마나 많았나 (거래 중 비율)",
        "easy": "주식을 사고파는 사람을 두 무리로 나눠 봐요. 일반인(개인)과 큰 회사·펀드(기관)예요. 바닥에선 겁먹은 개인이 던지고, "
                "기관이 그걸 싸게 주워 가는 일이 많아요. 그래서 '개인은 많이 팔고 기관은 사는 날'을 찾아요.",
        "hi": "개인 매도가 크고 기관이 사면: 항복 물량이 넘어가는 바닥 모습", "lo": "개인이 별로 안 팔거나 기관도 같이 팔면: 아직"},
    "vix_resolve": {
        "num": "'이번 달 무서움'(VIX) ÷ '석 달 무서움'(VIX3M)",
        "easy": "VIX는 '앞으로 한 달 동안 주가가 얼마나 출렁일까' 하는 걱정 점수, VIX3M은 '석 달 동안'의 걱정 점수예요. 평소엔 먼 "
                "미래가 더 불확실하니까 석 달 걱정이 더 커서, 나눈 값이 1보다 작아요. 1을 넘으면 '석 달 뒤보다 당장 이번 달이 더 "
                "무섭다' — 사람들이 지금 겁에 질렸다는 뜻이에요. 그러다 다시 1 아래로 내려오면 '급한 공포가 지나갔다'는 뜻이라, "
                "월가는 바로 이때를 반등 확인으로 봐요.",
        "hi": "1보다 크면 지금 당장 겁에 질린 상태 (공포 한가운데)", "lo": "1보다 작으면 평소 상태 · 1 위에 있다가 내려오는 순간이 신호",
        "gauge": (0.8, 1.3, [(1.0, "1")], "평온", "당장 패닉")},
    "credit": {
        "num": "위험한 회사 채권(HYG) ÷ 안전한 국채(IEF)가 최근 석 달 최고점보다 얼마나 떨어졌나",
        "easy": "돈을 빌려준 사람들이 '회사들이 망할까' 겁나면, 위험한 회사 채권부터 팔고 안전한 나라 채권으로 도망가요. 그래서 이 "
                "값이 크게 떨어질수록 공포가 주식을 넘어 '부도 걱정'까지 번졌다는 뜻이에요. 주식만 빠지고 이게 멀쩡하면 아직 진짜 "
                "위기는 아니에요.",
        "hi": "0에 가까우면 신용 시장은 멀쩡해요", "lo": "크게 마이너스면 부도 걱정까지 번진 진짜 공포"},
    "stress": {
        "num": "연준이 18가지 금융 숫자로 매주 재는 '금융 시스템 체온' (0 = 평소 체온)",
        "easy": "금융 시스템의 체온계라고 생각하면 돼요. 0이 평소 체온이고, 1을 넘으면 열이 나는 거예요. 2008년 금융위기 땐 9.7, "
                "코로나 땐 5.6까지 올랐어요. 주가가 빠져도 이 체온이 낮으면 은행·금융 쪽은 아직 멀쩡하다는 뜻이에요.",
        "hi": "1 넘으면 금융 시스템에 열이 남 (위기 쪽)", "lo": "0 아래면 평소보다 차분 (위기 아님)",
        "gauge": (-1.5, 3.0, [(0.0, "0 평소"), (1.0, "1")], "차분", "금융 위기")},
    "fg": {
        "num": "CNN이 7가지 숫자로 만든 0~100 시장 분위기 점수 (0 = 극단적 공포)",
        "easy": "시장 분위기 점수예요. 0에 가까울수록 다들 겁먹었고, 100에 가까울수록 다들 신났어요. 다만 지난 한 달 동안 일어난 "
                "일을 모아 만든 '백미러' 점수라, 앞으로 오를지 내릴지는 잘 못 맞혀요. 그래서 개수에 안 넣어요.",
        "hi": "75 넘으면 다들 신남 (탐욕)", "lo": "25 아래면 다들 겁먹음 (공포)",
        "gauge": (0.0, 100.0, [(25.0, "25"), (75.0, "75")], "극단적 공포", "극단적 탐욕")},
    "kr_panic": {
        "num": "외국인+기관이 하루에 판 돈 ÷ 평소(최근 60일) 하루 크기 — 최근 5일 중 가장 센 날",
        "easy": "큰손(외국인과 기관)이 하루에 판 돈이 평소의 몇 배인지예요. 1배면 평소만큼, 3배면 평소의 세 배를 한꺼번에 던진 "
                "거예요. 이렇게 겁에 질려 한꺼번에 던지는 날이 공포의 꼭대기인 경우가 많았어요.",
        "hi": "3배 넘으면 큰손이 한꺼번에 투매 (공포 정점 후보)", "lo": "1배 근처면 평소 수준",
        "gauge": (0.0, 5.0, [(1.0, "1배"), (3.0, "3배")], "평소", "한꺼번에 투매")},
    "kr_foreign": {
        "num": "외국인이 며칠 연속으로 '산 것보다 판 게 많은' 날이었는지",
        "easy": "외국인이 며칠째 계속 팔다가 처음으로 사는 날을 봐요. 흔히 '외국인이 팔다 멈추면 반등'이라고 하는데, 2020년 이후 "
                "실제 데이터로 확인해 보니 효과가 없었어요. 그래서 참고로만 보여줘요.",
        "hi": "연속 매도가 길면 외국인이 계속 빠져나가는 중", "lo": "순매수로 바뀌면 매도가 멈춤 (다만 반등 효과는 없었어요)"},
    "kr_vkospi": {
        "num": "한국판 공포 지수 — 앞으로 한 달 코스피가 얼마나 출렁일지 옵션 시장이 예상한 값 (눈금은 올해 평소 대비 몇 배)",
        "easy": "VKOSPI는 한국 주식시장의 '걱정 점수'예요. 사람들이 겁먹을수록 높아지고, 2010년 이후 보통은 17 근처였어요. "
                "여기선 '올해 평소보다 얼마나 높나'를 봐요. 평소의 1.5배 넘게 뛰면 공포 급등, 다시 1.2배 아래로 내려오면 공포가 "
                "꺾인 걸로 봐요.",
        "hi": "평소의 1.5배 넘으면 공포 급등", "lo": "1배 근처면 올해 평소 수준",
        "gauge": (0.5, 2.0, [(1.0, "평소"), (1.5, "1.5배")], "평소보다 잠잠", "크게 겁먹음")},
    "kr_etf": {
        "num": "5일 동안 레버리지(오르면 2배)로 들어온 돈 − 곱버스·인버스(내리면 돈 버는 상품)로 들어온 돈",
        "easy": "레버리지는 '오른다'에 거는 상품, 곱버스는 '떨어진다'에 거는 상품이에요. 둘 중 어디로 개인 돈이 더 들어갔는지 보면 "
                "개인이 어느 쪽에 걸고 있는지 알 수 있어요. +면 '오른다'에 더 걸었고, −면 '떨어진다'에 더 걸었어요. 눈금은 "
                "지난 1년 중 어디쯤인지예요.",
        "hi": "오른쪽 끝(상위 10%): '오른다'에 돈이 몰림 — 과거 폭락 때 흔했어요", "lo": "왼쪽 끝(하위 10%): '떨어진다'에 돈이 몰림",
        "gauge": (0.0, 1.0, [(0.1, "10%"), (0.5, "중간"), (0.9, "90%")], "하락에 베팅", "상승에 베팅")},
}


def _gauge(r: dict, color: str) -> str:
    ex = EXPLAIN.get(r["key"], {})
    g = ex.get("gauge")
    v = r.get("val")
    if r["key"] == "credit" and v is not None and r.get("p98") is not None:   # 신용은 기준선이 데이터에서 나와요
        g = (min(r["p98"] * 1.4, v - 0.01), 0.005, [(r["p98"], "항복"), (r["p90"], "긴장")], "부도 걱정 큼", "멀쩡")
    if not g or v is None or v != v:
        return ""
    lo, hi, marks, left, right = g

    def pos(x):
        return max(0.0, min(100.0, (x - lo) / (hi - lo) * 100))
    mk = "".join(f'<i class="mk" style="left:{pos(x):.1f}%"></i>' for x, _ in marks)
    ml = "".join(f'<span style="left:{pos(x):.1f}%">{esc(t)}</span>' for x, t in marks)
    return (f'<div class="gz"><div class="ge"><span>← {esc(left)}</span><span>{esc(right)} →</span></div>'
            f'<div class="gt">{mk}<b class="dot" style="left:{pos(v):.1f}%;background:{color}"></b></div>'
            f'<div class="gm">{ml}</div></div>')


def _past_line(r: dict) -> str:
    """'과거 9번 · 3개월 뒤 오른 확률 89% (평소 77%)'"""
    st, bs = (r.get("stats") or {}).get("3개월"), (r.get("base") or {}).get("3개월")
    if not st or not bs or not st.get("n"):
        return ""
    return f"과거 {st['n']}번 · 3개월 뒤 오른 확률 {st['up']:.0%} (평소 {bs['up']:.0%})"


def signal_rows(rows: list[dict], title: str, sub: str, verdict: dict | None = None) -> str:
    """신호 한 줄: 제목·상태 / 큰 수치 + 켜지는 기준 / 한 줄 요약 / 과거 성적 → 누르면 자세한 설명과 표"""
    groups = [("항복", "① 항복이 나왔나 (바닥권)"), ("확인", "② 반등이 확인됐나"), ("참고", "참고 (개수에 안 넣어요)")]
    out = [f'<div class="sect">{esc(title)}</div><div class="sectsub">{esc(sub)}</div>']
    if verdict:
        out.append(f'<div class="verdict"><div class="vt">{esc(verdict["title"])}</div><div class="vd">{esc(verdict["desc"])}</div></div>')
    for g, gname in groups:
        rs = [r for r in rows if r["group"] == g]
        if not rs:
            continue
        out.append(f'<div class="label" style="margin:14px 0 0">{esc(gname)}</div>')
        for r in rs:
            c, label = STATE_STYLE.get(r["state"], ("var(--sub)", r["state"]))
            hot = c.startswith("#")
            pill = (f'<span class="pill" style="color:{c};background:{tint(c, 0.15) if hot else "var(--chip)"}">'
                    f'{esc(label)}</span>')
            big_c = c if hot else "var(--text)"
            ex = EXPLAIN.get(r["key"], {})
            if r.get("big"):
                mid = (f'<div class="sv"><span class="sbig" style="color:{big_c}">{esc(r["big"])}</span>'
                       f'<span class="srule">{esc(r.get("rule") or "")}</span></div>')
                if ex.get("num"):
                    mid += f'<div class="snum">이 숫자는 → {esc(ex["num"])}</div>'
                mid += _gauge(r, c if hot else "var(--text)")
            else:
                mid = f'<div class="srule" style="margin-top:4px">{esc(r["now"])}</div>'
            say = f'<div class="ssay">{esc(r["say"])}</div>' if r.get("say") else ""
            eff = r.get("effect") or ""
            past = _past_line(r) or ("과거 통계는 아직 없어요" if r["state"] != "데이터 없음" and not r.get("stats") else "")
            effl = " · ".join(x for x in (eff, past) if x)
            effc = EFFECT_COLOR.get(eff, "var(--sub)")
            stats = ""
            if r.get("stats") and r.get("base"):
                trs = []
                for h in ("1개월", "3개월", "6개월", "1년"):
                    st_, b = r["stats"].get(h), r["base"].get(h)
                    if not st_ or not st_["n"]:
                        continue
                    trs.append(f"<tr><th>{h} 뒤</th><td>{_pct(st_['up'], False)} · {_pct(st_['median'])}</td>"
                               f"<td style='color:var(--faint)'>{_pct(st_['worst'])}</td>"
                               f"<td style='color:var(--sub)'>{_pct(b['up'], False)} · {_pct(b['median'])}</td></tr>")
                cmp_ = ""
                if r.get("compare"):
                    lbl, cs = r["compare"]
                    x = cs.get("1개월") or {}
                    cmp_ = (f"<div class='meta'>비교: {esc(lbl)} 1개월 뒤 오른 확률 {_pct(x.get('up'), False)} · "
                            f"중간 {_pct(x.get('median'))} · 최악 {_pct(x.get('worst'))}</div>")
                stats = (f"<table class='ftab' style='margin-top:8px'><thead><tr><th></th><th>이 신호 뒤 (오른 확률·중간)</th>"
                         f"<th>최악</th><th>평소(아무 날)</th></tr></thead><tbody>{''.join(trs)}</tbody></table>"
                         f"<div class='meta'>{esc(r['market'])} 기준 · 표본 {esc(r['sample'])} · 신호 다음 날 종가에 샀다고 계산</div>{cmp_}")
            easy = ""
            if ex.get("easy"):
                easy = (f'<div class="easy"><div class="h">💡 쉽게 말하면</div>{esc(ex["easy"])}'
                        f'<div class="hl"><span class="tg" style="color:#e5484d;background:{tint("#e5484d", 0.12)}">높으면</span>'
                        f'<span>{esc(ex["hi"])}</span></div>'
                        f'<div class="hl"><span class="tg" style="color:#3e63dd;background:{tint("#3e63dd", 0.12)}">낮으면</span>'
                        f'<span>{esc(ex["lo"])}</span></div></div>')
            body = easy + (f"<b>지금</b> {esc(r['now'])}<br><b>정확히는</b> {esc(r['what'])}<br><b>읽는 법</b> {esc(r['how'])}"
                           if r.get("what") else f"<b>지금</b> {esc(r['now'])}")
            out.append(f"""<details class="row sig"><summary>
<div class="sh"><div class="st">{esc(r['title'])}</div>{pill}</div>{mid}{say}
<div class="seff"><span style="color:{effc}">{esc(effl)}</span><span class="more">쉬운 설명 ›</span></div></summary>
<div class="body">{body}{stats}</div></details>""")
    return flat("".join(out))


# ---------------------------------------------------------------- 한국: 레버리지·곱버스 자금 흐름
def kr_etf_flow_card(sm: dict, title: str, desc: str, basis: str) -> str:
    """ETF 상장좌수 변화로 계산한 순유입 (억원). 빨강 = 들어옴, 파랑 = 빠짐"""
    def cell(x):
        t, c = _won(x)
        return f'<td style="color:{c}">{esc(t)}</td>'
    trs = []
    for r in sm["lines"]:
        p = r["pos5"]
        ptxt = "–" if p != p else (f"상위 {max(1 - p, 0.01):.0%}" if p >= 0.5 else f"하위 {max(p, 0.01):.0%}")
        trs.append(f"<tr><th>{esc(r['name'])}<div style='font-size:11px;color:var(--faint)'>{esc(r['kind'])} · 순자산 "
                   f"{esc(_won(r['aum'])[0].lstrip('+'))}</div></th>{cell(r['day'])}{cell(r['d5'])}{cell(r['d20'])}"
                   f"<td style='color:var(--sub)'>{esc(ptxt)}</td></tr>")
    bp = sm.get("bet_pos5")
    btxt = "–" if bp is None or bp != bp else (f"상위 {max(1 - bp, 0.01):.0%}" if bp >= 0.5 else f"하위 {max(bp, 0.01):.0%}")
    trs.append(f"<tr><th><b style='color:var(--text)'>상승 베팅 − 하락 베팅</b>"
               f"<div style='font-size:11px;color:var(--faint)'>레버리지 유입 − 인버스·곱버스 유입</div></th>"
               f"{cell(sm['bet_day'])}{cell(sm['bet5'])}{cell(sm['bet20'])}<td style='color:var(--sub)'>{esc(btxt)}</td></tr>")
    return flat(f"""<div class="sect">레버리지·곱버스 자금 흐름</div>
<div class="sectsub">{esc(basis)} · ETF 상장좌수 변화 × NAV = 실제로 들어오고 나간 돈(억원) · 빨강 들어옴 · 파랑 빠짐</div>
<div class="verdict"><div class="vt">{esc(title)}</div><div class="vd">{esc(desc)}</div></div>
<table class="ftab"><thead><tr><th></th><th>그날</th><th>5일</th><th>20일</th><th>5일 합 1년 중</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table>
<div class="sectsub" style="margin-top:6px">레버리지·인버스 ETF는 개인 거래 비중이 높아서 개인이 어느 쪽에 거는지 보는 데 써요. 네이버 순매수와 달리 LP 물량에 흔들리지 않아요.
설정·환매가 좌수에 반영되는 데 하루쯤 걸릴 수 있어요.</div>""")
