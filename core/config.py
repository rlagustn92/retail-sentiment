"""설정값 모음. 종목·가중치·경계값을 바꾸고 싶으면 여기만 고치면 됩니다."""

# ------------------------------------------------------------------ 그룹(지수·섹터)
# etf   : 대표 ETF (가격·등락률 표시)
# flow  : 개인 수급(BJZZ)·거래량을 보는 종목. 개인이 몰리는 레버리지 ETF가 있으면 그걸 씀
# inv   : 반대 방향 ETF (있으면 '갈아타기' 지표 계산)
# social: Stocktwits 심리를 볼 종목 (요청 제한 때문에 주요 그룹만)
# market: True면 시장 전체 공포 지표(VIX, 풋/콜)를 점수에 포함
# members: 종목별 현황 · 종목 전반 투매 · 뉴스 수집 대상
GROUPS = {
    "spx": dict(name="S&P500", kind="index", etf="SPY", flow="SPXL", inv="SPXS", social="SPY", market=True,
                members=["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK.B", "AVGO", "TSLA", "JPM", "LLY", "V"]),
    "ndx": dict(name="나스닥", kind="index", etf="QQQ", flow="TQQQ", inv="SQQQ", social="QQQ", market=True,
                members=["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "NFLX", "COST", "PLTR", "AMD"]),
    "tech": dict(name="테크", kind="sector", etf="XLK", flow="TECL", inv="TECS",
                 members=["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "AMD", "CSCO", "IBM", "NOW", "PLTR"]),
    "semi": dict(name="반도체", kind="sector", etf="SOXX", flow="SOXL", inv="SOXS", social="SOXL",
                 members=["NVDA", "AVGO", "AMD", "MU", "TSM", "INTC", "QCOM", "TXN", "AMAT", "LRCX", "KLAC",
                          "MRVL", "ADI", "ASML", "ARM", "ON", "MCHP", "NXPI"]),
    "comm": dict(name="커뮤니케이션", kind="sector", etf="XLC", flow="XLC",
                 members=["META", "GOOGL", "NFLX", "DIS", "TMUS", "T", "VZ", "CMCSA", "EA", "TTWO"]),
    "disc": dict(name="경기소비재", kind="sector", etf="XLY", flow="XLY",
                 members=["AMZN", "TSLA", "HD", "MCD", "BKNG", "LOW", "TJX", "SBUX", "NKE", "ABNB"]),
    "fin": dict(name="금융", kind="sector", etf="XLF", flow="FAS", inv="FAZ",
                members=["JPM", "BAC", "WFC", "GS", "MS", "C", "V", "MA", "AXP", "BRK.B", "SCHW", "BLK"]),
    "health": dict(name="헬스케어", kind="sector", etf="XLV", flow="XLV",
                   members=["LLY", "UNH", "JNJ", "ABBV", "MRK", "PFE", "TMO", "ABT", "ISRG", "AMGN"]),
    "bio": dict(name="바이오", kind="sector", etf="XBI", flow="LABU", inv="LABD",
                members=["VRTX", "REGN", "MRNA", "BIIB", "ALNY", "INCY", "EXEL", "NBIX", "SRPT", "BMRN"]),
    "energy": dict(name="에너지", kind="sector", etf="XLE", flow="XLE",
                   members=["XOM", "CVX", "COP", "EOG", "SLB", "OXY", "MPC", "PSX", "VLO", "KMI"]),
    "indu": dict(name="산업재", kind="sector", etf="XLI", flow="XLI",
                 members=["GE", "CAT", "RTX", "UBER", "HON", "BA", "UNP", "DE", "LMT", "ETN"]),
    "staples": dict(name="필수소비재", kind="sector", etf="XLP", flow="XLP",
                    members=["PG", "COST", "WMT", "KO", "PEP", "PM", "MO", "MDLZ", "CL"]),
    "util": dict(name="유틸리티", kind="sector", etf="XLU", flow="XLU",
                 members=["NEE", "SO", "DUK", "CEG", "VST", "AEP", "SRE", "D"]),
    "mat": dict(name="소재", kind="sector", etf="XLB", flow="XLB",
                members=["LIN", "SHW", "APD", "ECL", "FCX", "NEM", "DOW", "NUE"]),
    "re": dict(name="부동산", kind="sector", etf="XLRE", flow="XLRE",
               members=["PLD", "AMT", "EQIX", "WELL", "SPG", "O", "PSA", "CCI"]),
}
INDEX_KEYS = [k for k, g in GROUPS.items() if g["kind"] == "index"]
SECTOR_KEYS = [k for k, g in GROUPS.items() if g["kind"] == "sector"]

# 종목 한글 이름 (없으면 티커 그대로)
NAMES = {
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "AMZN": "아마존", "GOOGL": "알파벳",
    "META": "메타", "BRK.B": "버크셔", "AVGO": "브로드컴", "TSLA": "테슬라", "JPM": "JP모건", "LLY": "일라이릴리",
    "V": "비자", "NFLX": "넷플릭스", "COST": "코스트코", "PLTR": "팔란티어", "AMD": "AMD", "ORCL": "오라클",
    "CRM": "세일즈포스", "ADBE": "어도비", "CSCO": "시스코", "IBM": "IBM", "NOW": "서비스나우", "MU": "마이크론",
    "TSM": "TSMC", "INTC": "인텔", "QCOM": "퀄컴", "TXN": "텍사스인스트루먼트", "AMAT": "어플라이드머티리얼즈",
    "LRCX": "램리서치", "KLAC": "KLA", "MRVL": "마벨", "ADI": "아날로그디바이스", "ASML": "ASML", "ARM": "ARM",
    "ON": "온세미", "MCHP": "마이크로칩", "NXPI": "NXP", "DIS": "디즈니", "TMUS": "T모바일", "T": "AT&T",
    "VZ": "버라이즌", "CMCSA": "컴캐스트", "EA": "EA", "TTWO": "테이크투", "HD": "홈디포", "MCD": "맥도날드",
    "BKNG": "부킹", "LOW": "로우스", "TJX": "TJX", "SBUX": "스타벅스", "NKE": "나이키", "ABNB": "에어비앤비",
    "BAC": "뱅크오브아메리카", "WFC": "웰스파고", "GS": "골드만삭스", "MS": "모건스탠리", "C": "씨티",
    "MA": "마스터카드", "AXP": "아멕스", "SCHW": "찰스슈왑", "BLK": "블랙록", "UNH": "유나이티드헬스",
    "JNJ": "존슨앤드존슨", "ABBV": "애브비", "MRK": "머크", "PFE": "화이자", "TMO": "써모피셔", "ABT": "애보트",
    "ISRG": "인튜이티브서지컬", "AMGN": "암젠", "VRTX": "버텍스", "REGN": "리제네론", "MRNA": "모더나",
    "BIIB": "바이오젠", "ALNY": "앨나일람", "INCY": "인사이트", "EXEL": "엑셀리시스", "NBIX": "뉴로크린",
    "SRPT": "사렙타", "BMRN": "바이오마린", "XOM": "엑슨모빌", "CVX": "셰브론", "COP": "코노코필립스",
    "EOG": "EOG", "SLB": "SLB", "OXY": "옥시덴탈", "MPC": "마라톤페트롤리엄", "PSX": "필립스66", "VLO": "발레로",
    "KMI": "킨더모건", "GE": "GE에어로", "CAT": "캐터필러", "RTX": "RTX", "UBER": "우버", "HON": "하니웰",
    "BA": "보잉", "UNP": "유니언퍼시픽", "DE": "디어", "LMT": "록히드마틴", "ETN": "이튼", "PG": "P&G",
    "WMT": "월마트", "KO": "코카콜라", "PEP": "펩시코", "PM": "필립모리스", "MO": "알트리아", "MDLZ": "몬델리즈",
    "CL": "콜게이트", "NEE": "넥스트에라", "SO": "서던", "DUK": "듀크에너지", "CEG": "컨스텔레이션",
    "VST": "비스트라", "AEP": "AEP", "SRE": "셈프라", "D": "도미니언", "LIN": "린데", "SHW": "셔윈윌리엄스",
    "APD": "에어프로덕츠", "ECL": "에코랩", "FCX": "프리포트", "NEM": "뉴몬트", "DOW": "다우", "NUE": "뉴코어",
    "PLD": "프로로지스", "AMT": "아메리칸타워", "EQIX": "에퀴닉스", "WELL": "웰타워", "SPG": "사이먼프로퍼티",
    "O": "리얼티인컴", "PSA": "퍼블릭스토리지", "CCI": "크라운캐슬",
}


def name(sym: str) -> str:
    return NAMES.get(sym, sym)


def flow_symbols() -> list[str]:
    return sorted({g["flow"] for g in GROUPS.values()})


def bar_symbols() -> list[str]:
    s = set()
    for g in GROUPS.values():
        s.add(g["flow"])
        if g.get("inv"):
            s.add(g["inv"])
    return sorted(s)


def all_symbols() -> list[str]:
    s = set(bar_symbols())
    for g in GROUPS.values():
        s.add(g["etf"])
        s.update(g["members"])
    return sorted(s)


def trade_symbols() -> list[str]:
    """체결 데이터로 개인·기관 수급을 계산할 종목: 레버리지(개인용) + 대표 ETF(기관용)"""
    return sorted({g["flow"] for g in GROUPS.values()} | {g["etf"] for g in GROUPS.values()})


def etf_symbols() -> list[str]:
    return sorted({g["etf"] for g in GROUPS.values()})


def social_symbols() -> list[str]:
    return sorted({g["social"] for g in GROUPS.values() if g.get("social")})


# ------------------------------------------------------------------ 계산 설정
BASELINE_DAYS = 60       # 백분위 기준 기간(거래일)
NEWS_BASELINE_DAYS = 3   # 뉴스 기준치 기간(일)
BUCKET_MIN = 15          # 개인 수급 집계 단위(분)
RVOL_DAYS = 20           # 실시간 거래량 기준 평균 기간(거래일)

# 투매 점수 가중치. 데이터가 없거나 해당 없는 항목은 빠지고 나머지로 100점 환산
WEIGHTS = {
    "retail": 25,   # 개인 순매도 추정 (15분 지연)
    "volume": 20,   # 거래량 (장중 실시간 추정)
    "breadth": 15,  # 구성 종목 전반 투매
    "social": 15,   # Stocktwits
    "inverse": 10,  # 인버스 갈아타기
    "vix": 10,      # VIX/VIX3M (지수 그룹만)
    "putcall": 5,   # 주식 풋/콜 (지수 그룹만)
    "retail_etf": 10,  # 대표 ETF(SOXX 등)의 개인 순매도 (레버리지와 다를 때만)
    "short": 5,     # FINRA 장외 공매도 비율 (전일, 낮을수록 개인 매도)
    "credit": 5,    # 하이일드 채권 스프레드 (FRED, 지수 그룹만)
}

# FRED에서 받는 시리즈: 하이일드 채권 스프레드 (ICE BofA US High Yield OAS, %p)
FRED_SERIES = {"credit": "BAMLH0A0HYM2"}
FINRA_LOOKBACK = 70     # FINRA 장외 공매도: 최근 몇 거래일을 채워 둘지

# 기준치(과거 기록)가 부족할 때 쓰는 고정 눈금: (0점 값, 100점 값)
FALLBACK_SCALE = {
    "retail": (-0.05, 0.25),
    "volume": (1.0, 3.0),
    "inverse": (0.1, 0.6),
    "vix": (0.85, 1.05),
    "putcall": (0.5, 1.0),
    "bear": (0.2, 0.6),
    "velocity": (1.0, 4.0),
    "breadth": (0.0, 0.5),
    "news_count": (1.0, 3.0),
    "news_neg": (0.15, 0.5),
    "credit": (3.0, 6.0),
    "inst": (0.0, 0.35),
}

# 기관 매도 지수: 대표 ETF 대량 체결(20만 달러 이상)의 순매도 비율로 따로 계산 (투매 지수와 별개)
# 수급 판정: 순매도 비율이 이 값보다 크고 백분위 점수도 높으면 '매도', 반대면 '매수'
FLOW_SIDE_RATIO = 0.05
FLOW_SIDE_SCORE = (40, 60)   # (이하면 매수 쪽, 이상이면 매도 쪽)

# 종목 전반 투매: 이 정도 빠지면서 거래량이 이만큼 터진 종목 비율
BREADTH_DROP = -0.02
BREADTH_RVOL = 1.5

LEVELS = [(70, "투매", "#e5484d"), (40, "경계", "#f5a524"), (0, "평온", "#30a46c")]
REFRESH_SEC = 60
