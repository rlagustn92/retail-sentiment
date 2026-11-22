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
