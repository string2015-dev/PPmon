"""종 데이터: 1세대 151종 + 기존 계통에 쓰던 추가 종, 타입 상성표, 진화 계통(CHAINS), 희귀도.
digipet.py 가 불러다 씀. 스프라이트 파일 이름 = slug (sprites/mons/{slug}.png, 이로치는 sprites/mons/shiny/{slug}.png)."""

# ───────── 타입 ─────────
TYPE_KO = {
    "normal": "노말", "fire": "불꽃", "water": "물", "electric": "전기", "grass": "풀", "ice": "얼음",
    "fighting": "격투", "poison": "독", "ground": "땅", "flying": "비행", "psychic": "에스퍼", "bug": "벌레",
    "rock": "바위", "ghost": "고스트", "dragon": "드래곤", "dark": "악", "steel": "강철", "fairy": "페어리",
}
TYPE_COLOR = {
    "normal": "#a8a878", "fire": "#f08030", "water": "#6890f0", "electric": "#f8d030", "grass": "#78c850",
    "ice": "#98d8d8", "fighting": "#c03028", "poison": "#a040a0", "ground": "#e0c068", "flying": "#a890f0",
    "psychic": "#f85888", "bug": "#a8b820", "rock": "#b8a038", "ghost": "#705898", "dragon": "#7038f8",
    "dark": "#705848", "steel": "#b8b8d0", "fairy": "#ee99ac",
}
# 스킬 이름(타입별)
SKILL_KO = {
    "normal": "몸통박치기", "fire": "불꽃세례", "water": "물대포", "electric": "전기쇼크", "grass": "덩굴채찍",
    "ice": "얼음뭉치", "fighting": "공중제비", "poison": "독침", "ground": "진흙뿌리기", "flying": "바람일으키기",
    "psychic": "염동력", "bug": "벌레의저항", "rock": "락블라스트", "ghost": "나쁜짓", "dragon": "용의숨결",
    "dark": "물어뜯기", "steel": "메탈클로", "fairy": "요정의바람",
}
# 공격 타입 -> {방어 타입: 배율}  (명시하지 않은 조합은 1배)
_CHART = {
    "normal": {"rock": .5, "ghost": 0, "steel": .5},
    "fire": {"fire": .5, "water": .5, "grass": 2, "ice": 2, "bug": 2, "rock": .5, "dragon": .5, "steel": 2},
    "water": {"fire": 2, "water": .5, "grass": .5, "ground": 2, "rock": 2, "dragon": .5},
    "electric": {"water": 2, "electric": .5, "grass": .5, "ground": 0, "flying": 2, "dragon": .5},
    "grass": {"fire": .5, "water": 2, "grass": .5, "poison": .5, "ground": 2, "flying": .5, "bug": .5, "rock": 2,
              "dragon": .5, "steel": .5},
    "ice": {"fire": .5, "water": .5, "grass": 2, "ice": .5, "ground": 2, "flying": 2, "dragon": 2, "steel": .5},
    "fighting": {"normal": 2, "ice": 2, "poison": .5, "flying": .5, "psychic": .5, "bug": .5, "rock": 2, "ghost": 0,
                 "dark": 2, "steel": 2, "fairy": .5},
    "poison": {"grass": 2, "poison": .5, "ground": .5, "rock": .5, "ghost": .5, "steel": 0, "fairy": 2},
    "ground": {"fire": 2, "electric": 2, "grass": .5, "poison": 2, "flying": 0, "bug": .5, "rock": 2, "steel": 2},
    "flying": {"electric": .5, "grass": 2, "fighting": 2, "bug": 2, "rock": .5, "steel": .5},
    "psychic": {"fighting": 2, "poison": 2, "psychic": .5, "dark": 0, "steel": .5},
    "bug": {"fire": .5, "grass": 2, "fighting": .5, "poison": .5, "flying": .5, "psychic": 2, "ghost": .5, "dark": 2,
            "steel": .5, "fairy": .5},
    "rock": {"fire": 2, "ice": 2, "fighting": .5, "ground": .5, "flying": 2, "bug": 2, "steel": .5},
    "ghost": {"normal": 0, "psychic": 2, "ghost": 2, "dark": .5},
    "dragon": {"dragon": 2, "steel": .5, "fairy": 0},
    "dark": {"fighting": .5, "psychic": 2, "ghost": 2, "dark": .5, "fairy": .5},
    "steel": {"fire": .5, "water": .5, "electric": .5, "ice": 2, "rock": 2, "steel": .5, "fairy": 2},
    "fairy": {"fire": .5, "fighting": 2, "poison": .5, "dragon": 2, "dark": 2, "steel": .5},
}


def type_mult(atk, def_types):
    """공격 타입 atk 가 방어 타입들(1~2개)에 주는 배율. 0 / 0.25 / 0.5 / 1 / 2 / 4"""
    m = 1.0
    for d in def_types:
        m *= _CHART.get(atk, {}).get(d, 1.0)
    return m


def best_type(types, def_types):
    """자신의 타입 중 상대에게 가장 효과적인 타입."""
    return max(types, key=lambda t: type_mult(t, def_types))


# ───────── 1세대 151종 (도감 번호 순): slug, 한글 이름, 타입 ─────────
GEN1 = [
    ("bulbasaur", "이상해씨", ("grass", "poison")), ("ivysaur", "이상해풀", ("grass", "poison")),
    ("venusaur", "이상해꽃", ("grass", "poison")), ("charmander", "파이리", ("fire",)),
    ("charmeleon", "리자드", ("fire",)), ("charizard", "리자몽", ("fire", "flying")),
    ("squirtle", "꼬부기", ("water",)), ("wartortle", "어니부기", ("water",)), ("blastoise", "거북왕", ("water",)),
    ("caterpie", "캐터피", ("bug",)), ("metapod", "단데기", ("bug",)), ("butterfree", "버터플", ("bug", "flying")),
    ("weedle", "뿔충이", ("bug", "poison")), ("kakuna", "딱충이", ("bug", "poison")),
    ("beedrill", "독침붕", ("bug", "poison")), ("pidgey", "구구", ("normal", "flying")),
    ("pidgeotto", "피존", ("normal", "flying")), ("pidgeot", "피존투", ("normal", "flying")),
    ("rattata", "꼬렛", ("normal",)), ("raticate", "레트라", ("normal",)), ("spearow", "깨비참", ("normal", "flying")),
    ("fearow", "깨비드릴조", ("normal", "flying")), ("ekans", "아보", ("poison",)), ("arbok", "아보크", ("poison",)),
    ("pikachu", "피카츄", ("electric",)), ("raichu", "라이츄", ("electric",)), ("sandshrew", "모래두지", ("ground",)),
    ("sandslash", "고지", ("ground",)), ("nidoran-f", "니드런♀", ("poison",)), ("nidorina", "니드리나", ("poison",)),
    ("nidoqueen", "니드퀸", ("poison", "ground")), ("nidoran-m", "니드런♂", ("poison",)),
    ("nidorino", "니드리노", ("poison",)), ("nidoking", "니드킹", ("poison", "ground")),
    ("clefairy", "삐삐", ("fairy",)), ("clefable", "픽시", ("fairy",)), ("vulpix", "식스테일", ("fire",)),
    ("ninetales", "나인테일", ("fire",)), ("jigglypuff", "푸린", ("normal", "fairy")),
    ("wigglytuff", "푸크린", ("normal", "fairy")), ("zubat", "주뱃", ("poison", "flying")),
    ("golbat", "골뱃", ("poison", "flying")), ("oddish", "뚜벅쵸", ("grass", "poison")),
    ("gloom", "냄새꼬", ("grass", "poison")), ("vileplume", "라플레시아", ("grass", "poison")),
    ("paras", "파라스", ("bug", "grass")), ("parasect", "파라섹트", ("bug", "grass")),
    ("venonat", "콘팡", ("bug", "poison")), ("venomoth", "도나리", ("bug", "poison")), ("diglett", "디그다", ("ground",)),
    ("dugtrio", "닥트리오", ("ground",)), ("meowth", "나옹", ("normal",)), ("persian", "페르시온", ("normal",)),
    ("psyduck", "고라파덕", ("water",)), ("golduck", "골덕", ("water",)), ("mankey", "망키", ("fighting",)),
    ("primeape", "성원숭", ("fighting",)), ("growlithe", "가디", ("fire",)), ("arcanine", "윈디", ("fire",)),
    ("poliwag", "발챙이", ("water",)), ("poliwhirl", "슈륙챙이", ("water",)),
    ("poliwrath", "강챙이", ("water", "fighting")), ("abra", "캐이시", ("psychic",)),
    ("kadabra", "윤겔라", ("psychic",)), ("alakazam", "후딘", ("psychic",)), ("machop", "알통몬", ("fighting",)),
    ("machoke", "근육몬", ("fighting",)), ("machamp", "괴력몬", ("fighting",)),
    ("bellsprout", "모다피", ("grass", "poison")), ("weepinbell", "우츠동", ("grass", "poison")),
    ("victreebel", "우츠보트", ("grass", "poison")), ("tentacool", "왕눈해", ("water", "poison")),
    ("tentacruel", "독파리", ("water", "poison")), ("geodude", "꼬마돌", ("rock", "ground")),
    ("graveler", "데구리", ("rock", "ground")), ("golem", "딱구리", ("rock", "ground")), ("ponyta", "포니타", ("fire",)),
    ("rapidash", "날쌩마", ("fire",)), ("slowpoke", "야돈", ("water", "psychic")),
    ("slowbro", "야도란", ("water", "psychic")), ("magnemite", "코일", ("electric", "steel")),
    ("magneton", "레어코일", ("electric", "steel")), ("farfetchd", "파오리", ("normal", "flying")),
    ("doduo", "두리", ("normal", "flying")), ("dodrio", "두트리오", ("normal", "flying")), ("seel", "쥬쥬", ("water",)),
    ("dewgong", "쥬레곤", ("water", "ice")), ("grimer", "질퍽이", ("poison",)), ("muk", "질뻐기", ("poison",)),
    ("shellder", "셀러", ("water",)), ("cloyster", "파르셀", ("water", "ice")), ("gastly", "고오스", ("ghost", "poison")),
    ("haunter", "고우스트", ("ghost", "poison")), ("gengar", "팬텀", ("ghost", "poison")),
    ("onix", "롱스톤", ("rock", "ground")), ("drowzee", "슬리프", ("psychic",)), ("hypno", "슬리퍼", ("psychic",)),
    ("krabby", "크랩", ("water",)), ("kingler", "킹크랩", ("water",)), ("voltorb", "찌리리공", ("electric",)),
    ("electrode", "붐볼", ("electric",)), ("exeggcute", "아라리", ("grass", "psychic")),
    ("exeggutor", "나시", ("grass", "psychic")), ("cubone", "탕구리", ("ground",)), ("marowak", "텅구리", ("ground",)),
    ("hitmonlee", "시라소몬", ("fighting",)), ("hitmonchan", "홍수몬", ("fighting",)),
    ("lickitung", "내루미", ("normal",)), ("koffing", "또가스", ("poison",)), ("weezing", "또도가스", ("poison",)),
    ("rhyhorn", "뿔카노", ("ground", "rock")), ("rhydon", "코뿌리", ("ground", "rock")), ("chansey", "럭키", ("normal",)),
    ("tangela", "덩쿠리", ("grass",)), ("kangaskhan", "캥카", ("normal",)), ("horsea", "쏘드라", ("water",)),
    ("seadra", "시드라", ("water",)), ("goldeen", "콘치", ("water",)), ("seaking", "왕콘치", ("water",)),
    ("staryu", "별가사리", ("water",)), ("starmie", "아쿠스타", ("water", "psychic")),
    ("mr-mime", "마임맨", ("psychic", "fairy")), ("scyther", "스라크", ("bug", "flying")),
    ("jynx", "루주라", ("ice", "psychic")), ("electabuzz", "에레브", ("electric",)), ("magmar", "마그마", ("fire",)),
    ("pinsir", "쁘사이저", ("bug",)), ("tauros", "켄타로스", ("normal",)), ("magikarp", "잉어킹", ("water",)),
    ("gyarados", "갸라도스", ("water", "flying")), ("lapras", "라프라스", ("water", "ice")),
    ("ditto", "메타몽", ("normal",)), ("eevee", "이브이", ("normal",)), ("vaporeon", "샤미드", ("water",)),
    ("jolteon", "쥬피썬더", ("electric",)), ("flareon", "부스터", ("fire",)), ("porygon", "폴리곤", ("normal",)),
    ("omanyte", "암나이트", ("rock", "water")), ("omastar", "암스타", ("rock", "water")),
    ("kabuto", "투구", ("rock", "water")), ("kabutops", "투구푸스", ("rock", "water")),
    ("aerodactyl", "프테라", ("rock", "flying")), ("snorlax", "잠만보", ("normal",)),
    ("articuno", "프리져", ("ice", "flying")), ("zapdos", "썬더", ("electric", "flying")),
    ("moltres", "파이어", ("fire", "flying")), ("dratini", "미뇽", ("dragon",)), ("dragonair", "신뇽", ("dragon",)),
    ("dragonite", "망나뇽", ("dragon", "flying")), ("mewtwo", "뮤츠", ("psychic",)), ("mew", "뮤", ("psychic",)),
]
# 기존 진화 계통에 쓰던 1세대 밖의 종
EXTRA = [
    ("pichu", "피츄", ("electric",)), ("togepi", "토게피", ("fairy",)), ("togetic", "토게틱", ("fairy", "flying")),
    ("togekiss", "토게키스", ("fairy", "flying")), ("espeon", "에브이", ("psychic",)), ("umbreon", "블래키", ("dark",)),
    ("larvitar", "애버라스", ("rock", "ground")), ("pupitar", "데기라스", ("rock", "ground")),
    ("tyranitar", "마기라스", ("rock", "dark")), ("ralts", "랄토스", ("psychic", "fairy")),
    ("kirlia", "킬리아", ("psychic", "fairy")), ("gardevoir", "가디안", ("psychic", "fairy")),
    ("gallade", "엘레이드", ("psychic", "fighting")), ("riolu", "리오르", ("fighting",)),
    ("lucario", "루카리오", ("fighting", "steel")), ("bagon", "아공이", ("dragon",)), ("shelgon", "쉘곤", ("dragon",)),
    ("salamence", "보만다", ("dragon", "flying")), ("mareep", "메리프", ("electric",)),
    ("flaaffy", "보송송", ("electric",)), ("ampharos", "전룡", ("electric",)),
]
SPECIES = {slug: dict(ko=ko, types=types, gen1=(i < len(GEN1) and True)) for i, (slug, ko, types) in
           enumerate(GEN1 + EXTRA)}
for _i, (_slug, _ko, _t) in enumerate(EXTRA):
    SPECIES[_slug]["gen1"] = False
DEX_ORDER = [slug for slug, _, _ in GEN1]  # 도감 번호 순(1~151)
KO = {slug: v["ko"] for slug, v in SPECIES.items()}
KO["egg"] = "알"
TYPES = {slug: v["types"] for slug, v in SPECIES.items()}

# ───────── 진화 계통 ─────────
# forms: 1~3단계 (분기 진화는 "@이름"), rar: C 일반 / U 희귀 / R 매우 희귀 / L 전설
# 주의: 기존 저장 파일이 계통을 번호로 기억하므로 앞쪽 순서를 바꾸지 말고 뒤에만 추가할 것.
_BRANCH = ("@eevee", "@ralts")
BRANCH_OPTIONS = {"@eevee": ["vaporeon", "jolteon", "flareon", "espeon", "umbreon"],
                  "@ralts": ["gardevoir", "gallade"]}
_RAR = {}  # 첫 번째 형태 slug -> 희귀도 (기본 C)
for _r, _names in {
    "L": "articuno zapdos moltres mewtwo mew",
    "R": "dratini larvitar bagon lapras aerodactyl omanyte kabuto porygon snorlax chansey ditto hitmonlee hitmonchan "
         "kangaskhan",
    "U": "charmander squirtle bulbasaur pichu eevee togepi abra machop gastly ralts riolu growlithe ponyta vulpix "
         "clefairy jigglypuff magnemite slowpoke cubone exeggcute electabuzz magmar jynx tauros mr-mime farfetchd "
         "lickitung tangela scyther pinsir magikarp mareep geodude",
}.items():
    for _n in _names.split():
        _RAR[_n] = _r

_OLD = [
    ["charmander", "charmeleon", "charizard"], ["squirtle", "wartortle", "blastoise"],
    ["bulbasaur", "ivysaur", "venusaur"], ["pichu", "pikachu", "raichu"], ["gastly", "haunter", "gengar"],
    ["dratini", "dragonair", "dragonite"], ["eevee", "@eevee"], ["togepi", "togetic", "togekiss"],
    ["abra", "kadabra", "alakazam"], ["machop", "machoke", "machamp"], ["geodude", "graveler", "golem"],
    ["magikarp", "gyarados"], ["larvitar", "pupitar", "tyranitar"], ["ralts", "kirlia", "@ralts"],
    ["riolu", "lucario"], ["bagon", "shelgon", "salamence"], ["mareep", "flaaffy", "ampharos"],
]
_NEW = [
    ["caterpie", "metapod", "butterfree"], ["weedle", "kakuna", "beedrill"], ["pidgey", "pidgeotto", "pidgeot"],
    ["rattata", "raticate"], ["spearow", "fearow"], ["ekans", "arbok"], ["sandshrew", "sandslash"],
    ["nidoran-f", "nidorina", "nidoqueen"], ["nidoran-m", "nidorino", "nidoking"], ["clefairy", "clefable"],
    ["vulpix", "ninetales"], ["jigglypuff", "wigglytuff"], ["zubat", "golbat"],
    ["oddish", "gloom", "vileplume"], ["paras", "parasect"], ["venonat", "venomoth"], ["diglett", "dugtrio"],
    ["meowth", "persian"], ["psyduck", "golduck"], ["mankey", "primeape"], ["growlithe", "arcanine"],
    ["poliwag", "poliwhirl", "poliwrath"], ["bellsprout", "weepinbell", "victreebel"],
    ["tentacool", "tentacruel"], ["ponyta", "rapidash"], ["slowpoke", "slowbro"], ["magnemite", "magneton"],
    ["doduo", "dodrio"], ["seel", "dewgong"], ["grimer", "muk"], ["shellder", "cloyster"], ["drowzee", "hypno"],
    ["krabby", "kingler"], ["voltorb", "electrode"], ["exeggcute", "exeggutor"], ["cubone", "marowak"],
    ["koffing", "weezing"], ["rhyhorn", "rhydon"], ["horsea", "seadra"], ["goldeen", "seaking"],
    ["staryu", "starmie"], ["omanyte", "omastar"], ["kabuto", "kabutops"],
    ["onix"], ["farfetchd"], ["hitmonlee"], ["hitmonchan"], ["lickitung"], ["chansey"], ["tangela"], ["kangaskhan"],
    ["mr-mime"], ["scyther"], ["jynx"], ["electabuzz"], ["magmar"], ["pinsir"], ["tauros"], ["lapras"], ["ditto"],
    ["porygon"], ["aerodactyl"], ["snorlax"], ["articuno"], ["zapdos"], ["moltres"], ["mewtwo"], ["mew"],
]
# 내장 도트 폴백 색(0 불꽃/1 물/2 풀/3 어둠)
_COLOR_BY_TYPE = {"fire": 0, "fighting": 0, "electric": 0, "rock": 0, "ground": 0, "normal": 0, "dragon": 1,
                  "water": 1, "ice": 1, "flying": 1, "steel": 1, "grass": 2, "bug": 2, "poison": 3, "ghost": 3,
                  "psychic": 3, "dark": 3, "fairy": 0}
CHAINS = []
for _forms in _OLD + _NEW:
    _first = _forms[0]
    CHAINS.append(dict(color=_COLOR_BY_TYPE[TYPES[_first][0]], forms=_forms, rar=_RAR.get(_first, "C")))

RARITY_KO = {"C": "일반", "U": "희귀", "R": "매우 희귀", "L": "전설"}
RARITY_STARS = {"C": "★", "U": "★★", "R": "★★★", "L": "★★★★"}
RARITY_PCT = {"C": 60.0, "U": 28.0, "R": 10.5, "L": 1.5}  # 부화 시 등급별 확률(%), 등급 안에서는 균등
SHINY_CHANCE = 1 / 40  # 이로치(색이 다른 개체) 확률

# 단계(tier) 계산: 계통 길이 L, 형태 번호 i -> tier = 4 - L + i
TIER = {}
for _ch in CHAINS:
    _L = len(_ch["forms"])
    for _i, _f in enumerate(_ch["forms"]):
        if _f.startswith("@"):
            for _o in BRANCH_OPTIONS[_f]:
                TIER[_o] = 4 - _L + _i
        else:
            TIER[_f] = 4 - _L + _i
LEGENDARY = {"articuno", "zapdos", "moltres", "mewtwo", "mew"}

# ───────── 전투 상대(1세대만) ─────────
FOE_POOL = {1: [], 2: [], 3: []}
for _slug in DEX_ORDER:
    FOE_POOL[TIER[_slug]].append(_slug)
FOE_WEIGHT = {s: (0.12 if s in LEGENDARY else 1.0) for s in DEX_ORDER}  # 전설은 아주 가끔만 등장
FOE_POWER = {s: (1.3 if s in LEGENDARY else 1.0) for s in DEX_ORDER}


def _catch_base(slug):
    if slug in LEGENDARY:
        return 0.06
    return {1: 0.75, 2: 0.5, 3: 0.3}[TIER[slug]]


CATCH_BASE = {s: _catch_base(s) for s in DEX_ORDER}
for _s in ("snorlax", "dragonite", "lapras", "aerodactyl", "kabutops", "omastar", "porygon", "chansey", "ditto"):
    CATCH_BASE[_s] = min(CATCH_BASE[_s], 0.18)  # 잡기 어려운 종


def all_slugs():
    return sorted(set(SPECIES) | {"egg"})


if __name__ == "__main__":  # 자체 점검
    assert len(GEN1) == 151 and len(set(s for s, _, _ in GEN1)) == 151
    covered = set()
    for ch in CHAINS:
        for f in ch["forms"]:
            covered |= set(BRANCH_OPTIONS[f]) if f.startswith("@") else {f}
    missing = [s for s in DEX_ORDER if s not in covered]
    print("1세대 중 계통에 없는 종:", missing)
    print("계통 수:", len(CHAINS), "| 등급별:", {r: sum(c["rar"] == r for c in CHAINS) for r in "CURL"})
    print("전투 풀:", {t: len(v) for t, v in FOE_POOL.items()})
