#!/usr/bin/env python3
"""DigiPet - 바탕화면 방치형 디지털 펫 (다마고치 + 디지몬 스타일)

- 창을 닫아도(꺼도) 시간이 흐른 만큼 따라잡기(오프라인 진행, 최대 8시간)
- 방치해도 알아서 탐험/배틀/성장. 돌봐줄수록 좋은 형태로 진화.
- 더블클릭: 미니 모드(펫만 바탕화면에 떠있음) <-> 전체 화면 전환
- 우클릭: 설정 메뉴.   실행 옵션: --fast (시간 60배, 테스트용)
"""
import json
import math
import os
import random
import re
import shutil
import sys
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    USER32 = ctypes.windll.user32
    USER32.GetAncestor.restype = ctypes.c_void_p
    USER32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    USER32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    USER32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    USER32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
else:
    USER32 = None
try:
    import winutil  # 트레이, 단일 실행, 모니터 작업 영역 (Windows)
except Exception:
    winutil = None

try:
    import winsound
except ImportError:  # 비윈도우
    winsound = None

if getattr(sys, "frozen", False):  # PyInstaller 실행파일: 저장은 exe 옆, 스프라이트는 exe 안에 포함
    HERE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    APP_DIR = os.path.dirname(sys.executable)
else:
    HERE = APP_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE = os.path.join(APP_DIR, "save.json")
CRASH_LOG = os.path.join(APP_DIR, "crash.log")
_last_err = ("", 0.0)


def log_exception(exc_type, exc, tb):
    """pythonw/exe 에서는 오류가 화면에 안 보이므로 crash.log 에 기록(같은 오류는 1분에 한 번만)."""
    global _last_err
    import traceback
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    if text == _last_err[0] and time.time() - _last_err[1] < 60:
        return
    _last_err = (text, time.time())
    try:
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n{text}\n")
    except OSError:
        pass

FAST = 60 if "--fast" in sys.argv else 1
KEY = "#ff00ff"  # 투명 처리 색
FONT = "Malgun Gothic"
MAX_OFFLINE = 8 * 3600

# ───────────────────────── 데이터 ─────────────────────────
# 단계(tier): 0 알 / 1~3 포켓몬 본가 진화 단계. 2단 진화 계통은 tier 2부터 시작해 항상 tier 3이 최종 형태.
STAGES = ["알", "기본", "1진화", "2진화"]
STAGE_TIME = [60, 2 * 3600, 10 * 3600, None]  # 다음 단계까지(초)
HUNGER_EMPTY = [None, 3600, 5400, 7200]  # 배부름 100→0 걸리는 초
BASE_POWER = [0, 6, 16, 32]
WIN_NEED = {2: 3, 3: 10}  # 해당 단계로 진화하기 위한 승리 횟수

# 본가 진화 계통. color = 내장 도트 폴백 색(0 불꽃 / 1 물 / 2 풀 / 3 어둠)
CHAINS = [
    dict(color=0, forms=["charmander", "charmeleon", "charizard"]),
    dict(color=1, forms=["squirtle", "wartortle", "blastoise"]),
    dict(color=2, forms=["bulbasaur", "ivysaur", "venusaur"]),
    dict(color=0, forms=["pichu", "pikachu", "raichu"]),
    dict(color=3, forms=["gastly", "haunter", "gengar"]),
    dict(color=1, forms=["dratini", "dragonair", "dragonite"]),
    dict(color=0, forms=["eevee", "@eevee"]),  # 이브이: 친밀도가 높으면 에브이/블래키(낮/밤), 아니면 훈련 스탯에 따라
    dict(color=0, forms=["togepi", "togetic", "togekiss"]),
    dict(color=3, forms=["abra", "kadabra", "alakazam"]),
    dict(color=0, forms=["machop", "machoke", "machamp"]),
    dict(color=2, forms=["geodude", "graveler", "golem"]),
    dict(color=1, forms=["magikarp", "gyarados"]),
    dict(color=2, forms=["larvitar", "pupitar", "tyranitar"]),
    dict(color=3, forms=["ralts", "kirlia", "@ralts"]),  # 힘 > 지능이면 엘레이드, 아니면 가디안
    dict(color=1, forms=["riolu", "lucario"]),
    dict(color=1, forms=["bagon", "shelgon", "salamence"]),
    dict(color=0, forms=["mareep", "flaaffy", "ampharos"]),
]
KO = {
    "charmander": "파이리", "charmeleon": "리자드", "charizard": "리자몽",
    "squirtle": "꼬부기", "wartortle": "어니부기", "blastoise": "거북왕",
    "bulbasaur": "이상해씨", "ivysaur": "이상해풀", "venusaur": "이상해꽃",
    "pichu": "피츄", "pikachu": "피카츄", "raichu": "라이츄",
    "gastly": "고오스", "haunter": "고우스트", "gengar": "팬텀",
    "dratini": "미뇽", "dragonair": "신뇽", "dragonite": "망나뇽",
    "eevee": "이브이", "vaporeon": "샤미드", "jolteon": "쥬피썬더", "flareon": "부스터",
    "espeon": "에브이", "umbreon": "블래키",
    "togepi": "토게피", "togetic": "토게틱", "togekiss": "토게키스",
    "abra": "캐이시", "kadabra": "윤겔라", "alakazam": "후딘",
    "machop": "알통몬", "machoke": "근육몬", "machamp": "괴력몬",
    "geodude": "꼬마돌", "graveler": "데구리", "golem": "딱구리",
    "magikarp": "잉어킹", "gyarados": "갸라도스",
    "larvitar": "애버라스", "pupitar": "데기라스", "tyranitar": "마기라스",
    "ralts": "랄토스", "kirlia": "킬리아", "gardevoir": "가디안", "gallade": "엘레이드",
    "riolu": "리오르", "lucario": "루카리오",
    "bagon": "아공이", "shelgon": "쉘곤", "salamence": "보만다",
    "mareep": "메리프", "flaaffy": "보송송", "ampharos": "전룡",
    "rattata": "꼬렛", "pidgey": "구구", "caterpie": "캐터피", "zubat": "주뱃", "ekans": "아보",
    "onix": "롱스톤", "arcanine": "윈디", "snorlax": "잠만보", "egg": "알",
}
BRANCH_OPTIONS = {"@eevee": ["vaporeon", "jolteon", "flareon", "espeon", "umbreon"],
                  "@ralts": ["gardevoir", "gallade"]}
BRANCH_FORMS = ["vaporeon", "jolteon", "flareon", "espeon", "umbreon", "gardevoir", "gallade"]
# 전투 상대: 펫 단계(tier)별 풀
FOE_POOL = {
    1: ["rattata", "pidgey", "caterpie", "zubat"],
    2: ["ekans", "zubat", "geodude", "machop", "pidgey"],
    3: ["onix", "arcanine", "snorlax", "machamp", "alakazam", "gyarados", "tyranitar", "dragonite"],
}
# 포획: 종별 기본 포획률, 볼 종류 {키: (이름, 가격, 배율)}
CATCH_BASE = {"rattata": .7, "pidgey": .7, "caterpie": .8, "zubat": .6, "ekans": .5, "geodude": .5,
              "machop": .45, "onix": .35, "arcanine": .25, "snorlax": .2, "machamp": .3, "alakazam": .25,
              "gyarados": .2, "tyranitar": .15, "dragonite": .12}
BALLS = {"ball": ("몬스터볼", 10, 1.0), "great": ("슈퍼볼", 30, 1.6), "ultra": ("하이퍼볼", 60, 2.5)}
# 상점 품목 {키: (이름, 가격, 설명)}
SHOP = {
    "ball": ("몬스터볼", 10, "포획률 ×1.0"),
    "great": ("슈퍼볼", 30, "포획률 ×1.6"),
    "ultra": ("하이퍼볼", 60, "포획률 ×2.5"),
    "potion": ("상처약", 20, "체력 +30"),
    "super_potion": ("좋은상처약", 50, "체력 +70"),
    "cure": ("만병통치약", 25, "병 치료"),
    "bento": ("도시락", 15, "배고픔 +60, 친밀도 +5"),
    "candy": ("이상한사탕", 60, "훈련 수치 +3 (무작위)"),
}
CATCH_T = 2.6      # 볼 흔들리는 연출(초). 이 동안 전투가 멈춤
CAUGHT_OUT = 1.8   # 포획 성공 후 마무리(초)
AUTO_FEED_COST = 5
BOND_DRAIN_SEC = 72 * 3600  # 친밀도 100→0 (기본, 3일). 배고픔/병이면 2배 빠름
PET_GAIN = 3             # 펫을 한 번 클릭할 때 친밀도 증가량
AUTO_MEDICINE_COST = 15
AUTO_BALL_STOCK = 5      # 자동 보충: 몬스터볼 목표 개수
AUTO_BALL_RESERVE = 100  # 이 Bits 이상 있을 때만 보충
AUTO_POTION_STOCK = 2    # 자동 돌봄: 상처약 목표 개수(Bits 200 이상일 때 보충)
AUTO_POTION_BELOW = 35   # 체력이 이 값 미만이면 상처약 자동 사용
BUILTIN_TIER = {0: 0, 1: 2, 2: 4, 3: 6}  # 이미지가 없을 때 쓰는 내장 도트(SPRITES 키)


def all_slugs():
    """게임이 쓰는 모든 포켓몬 slug (build_sprites.py 가 사용)."""
    out = {"egg"} | set(BRANCH_FORMS)
    for ch in CHAINS:
        out |= {f for f in ch["forms"] if not f.startswith("@")}
    for pool in FOE_POOL.values():
        out |= set(pool)
    return sorted(out)


TRAIN_KEYS = ["power", "speed", "mind"]
TRAIN_LABEL = {"power": "힘", "speed": "속도", "mind": "지능"}

# 스프라이트: 왼쪽 8칸만 정의, 좌우 대칭으로 펼침. 16행.
# o 윤곽 / b 몸 / l 배 / a 포인트 / e 눈동자 / w 흰자 / m 입
SPRITES = {
    0: [  # 알
        "........", "........", ".....ooo", "....obbb", "...obbbb", "..obbbbb",
        "..obaabb", ".obbaabb", ".obbbbbb", ".obbbaab", ".obbbaab", ".obbbbbb",
        "..obbbbb", "..oobbbb", "....oooo", "........"],
    1: [  # 유아기
        "........", "........", "........", "........", "........", ".....ooo",
        "...oobbb", "..obbbbb", ".obbbbbb", ".obwebbb", ".obbbbbb", ".oblllbb",
        ".oblllbb", "..obbbbb", "...ooooo", "........"],
    2: [  # 유년기
        "........", "......o.", ".....obo", "....obbo", "...obbbb", "..obbbbb",
        "..obwebb", "..obbbbb", "..oblllb", "..oblllb", "...obbbb", "...obbbb",
        "..obobbb", "..oo.ooo", "........", "........"],
    # 눈은 2행(위 ww / 아래 we): 흰자 + 안쪽을 보는 눈동자
    3: [  # 성장기
        "........", ".......o", "......ob", ".....obb", "....obbb", "...obbbb",
        "..obwwbb", "..obwebb", "..obbbbb", ".oobmmbb", ".obblllb", ".obblllb",
        "..oblllb", "..obbbbb", "..obobbb", "..oo.ooo"],
    4: [  # 성숙기: 팔이 생기고 덩치가 커짐
        "......ao", ".....aob", "....oabb", "...obbbb", "..obbbbb", ".obwwbbb",
        ".obwebbb", ".obbbbbb", ".obmmmbb", "oabbbbbb", "oabblllb", ".obblllb",
        ".obblllb", "..obbbbb", "..obobbb", "..ooooo."],
    5: [  # 완전체: 어깨 갑옷 + 계열별 날개(WINGS)
        "......oo", ".....obb", "....obbb", "...obbbb", "...obbbb", "...obwwb",
        "...obweb", "...obbbb", "...obmmb", ".oobbbbb", ".obblllb", ".obblllb",
        "..oblllb", "..obbbbb", "..obobbb", "..oo.ooo"],
    6: [  # 궁극체: 왕관 + 큰 몸 + 큰 날개
        "..a..a.a", "..aoaoao", "...obbbb", "...obbbb", "...obabb", "...obwwb",
        "...obweb", "...obbbb", "...obmmb", "..obabbb", ".obabbll", ".obabbll",
        "..obabll", "..obbbbb", "..obbobb", ".oooo.oo"],
}
# 완전체/궁극체 날개(왼쪽 절반, 2행부터). 계열마다 모양이 달라 실루엣이 갈림
WINGS = [
    ["a.......", "aa......", "aaa.....", "aaaa....", "oaaa....", "oaa.....", ".oa.....", "..o....."],  # 불꽃: 불길 날개
    [".aa.....", "aaaa....", "aaaa....", "ooaa....", ".oaa....", "..oa....", "..oa....", "...o...."],  # 바다: 지느러미
    ["aaa.....", "aaaa....", "aaaa....", "aaaa....", "oaaa....", ".oa.....", "..o.....", "........"],  # 숲: 잎사귀
    ["a.......", "aa......", "aoa.....", "aaoa....", "oaaa....", ".oaa....", "..oa....", "...o...."],  # 어둠: 박쥐
]
EGG_PAL = dict(o="#5b4a3a", b="#fff3d6", l="#fff3d6", a="#ff9eb5", e="#222", w="#fff", m="#c33")
BABY_PAL = dict(o="#a14468", b="#ff9ec2", l="#ffe0ec", a="#fff", e="#222", w="#fff", m="#c33")
CHILD_PAL = dict(o="#8a5a12", b="#f6c445", l="#fff1c2", a="#fff", e="#222", w="#fff", m="#c33")
LINE_PAL = [
    dict(o="#6a1a14", b="#e8574a", l="#ffd59a", a="#ffb62e", e="#222", w="#fff", m="#3a0d0a"),
    dict(o="#143a6a", b="#4a90e8", l="#cfeaff", a="#35d0c8", e="#222", w="#fff", m="#0a1d3a"),
    dict(o="#1d4a1f", b="#4caf50", l="#e1f5c4", a="#f2c14e", e="#222", w="#fff", m="#0d2a10"),
    dict(o="#2b1646", b="#7a4fb0", l="#d9c4ee", a="#e04a8a", e="#ffdd33", w="#222", m="#e04a8a"),
]
_sprite_cache = {}


def palette_for(stage, line):
    if stage == 0:
        return EGG_PAL
    if stage == 1:
        return BABY_PAL
    if stage == 2:
        return CHILD_PAL
    return LINE_PAL[max(line, 0)]


# 계열별 머리 장식(실루엣 차별화). 16칸 전체 폭, 위 3행에 덮어씀. 'c'=장식색(a)
CRESTS = [
    ["...c..c.c..c....".replace("c", "a")[:16], "..cc.cccc.cc....", "...cccccccc....."],  # 불꽃 갈기
    ["................", "......cccc......", ".....cccccc....."],  # 물결 지느러미
    ["......cc........", ".....cccc.......", "......cc........"],  # 새싹 잎
    ["..c..........c..", "..cc........cc..", "...cc......cc..."],  # 어둠 뿔
]


def _darken(hexcol, f):
    h = hexcol.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return "#%02x%02x%02x" % tuple(int(int(h[i:i + 2], 16) * f) for i in (0, 2, 4))


FOE_PAL = dict(o="#1a1a22", b="#5d6270", l="#8b92a3", a="#c0392b", e="#ff3b3b", w="#111", m="#ff3b3b")


def sprite_runs(stage, line, blink, foe=False):
    """[(x, y, w, color)] 가로 런으로 합친 스프라이트. 좌우 대칭 + 장식 + 자동 음영.
    foe=True면 전투 상대용 회색 '바이러스' 팔레트."""
    key = (stage, line, blink, foe)
    if key in _sprite_cache:
        return _sprite_cache[key]
    pal = dict(FOE_PAL if foe else palette_for(stage, line))
    pal["s"] = _darken(pal["b"], 0.78)  # 몸 음영
    pal["d"] = _darken(pal["l"], 0.85)  # 배 음영
    grid = []
    for row in SPRITES[stage]:
        row = (row + "." * 8)[:8]
        grid.append(list(row + row[::-1]))
    if stage >= 3 and line >= 0:  # 계열 장식
        for y, crest in enumerate(CRESTS[line][:3]):
            for x, ch in enumerate(crest[:16]):
                if ch != "." and grid[y][x] == ".":
                    grid[y][x] = "a" if ch != "." else "."
    if stage >= 5 and line >= 0:  # 날개: 몸 뒤쪽(빈 칸)에만 덮음
        top = 2 if stage == 5 else 1
        for i, half in enumerate(WINGS[line]):
            y = top + i
            for x, ch in enumerate(half + half[::-1]):
                if ch != "." and grid[y][x] == ".":
                    grid[y][x] = ch
    if blink:
        grid = [[{"e": "o", "w": "b"}.get(ch, ch) for ch in r] for r in grid]
    # 광원: 왼쪽 위. 아래/오른쪽이 비어 있는 몸 픽셀은 어둡게
    for y in range(16):
        for x in range(16):
            ch = grid[y][x]
            if ch not in "bl":
                continue
            below = grid[y + 1][x] if y < 15 else "."
            right = grid[y][x + 1] if x < 15 else "."
            if below in ".o" or (right in ".o" and x >= 8):
                grid[y][x] = "s" if ch == "b" else "d"
    runs = []
    for y in range(16):
        x = 0
        while x < 16:
            ch = grid[y][x]
            if ch == ".":
                x += 1
                continue
            x2 = x
            while x2 < 16 and grid[y][x2] == ch:
                x2 += 1
            runs.append((x, y, x2 - x, pal[ch]))
            x = x2
    _sprite_cache[key] = runs
    return runs


# ───────────────────────── 게임 로직 ─────────────────────────
def new_state(gen=1, bits=0.0, dex=None, items=None):
    return dict(
        last=time.time(), gen=gen, stage=0, line=-1, chain=-1, slug="egg", stage_time=0.0, total_time=0.0,
        hunger=80.0, happy=80.0, energy=100.0, hp=100.0, weight=5.0,
        sick=False, sick_t=0.0, sick_flag=False, starve_t=0.0, starve_flag=False,
        sleeping=False, dead=False, care_miss=0,
        train=dict(power=0.0, speed=0.0, mind=0.0),
        wins=0, losses=0, bits=float(bits), dex=dict(dex or {}), items=dict(items or {"ball": 3, "great": 0}), explore_t=0.0, battle_t=0.0,
    )


def sanitize_state(s):
    """불러온 저장값을 검사해 깨진 값/모르는 포켓몬을 고친다. 고친 항목 수를 반환."""
    d, fixed = new_state(), 0

    def num(k, lo=None, hi=None, integer=False):
        nonlocal fixed
        v = s.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
            s[k], fixed = d[k], fixed + 1
            return
        if lo is not None and v < lo:
            v, fixed = lo, fixed + 1
        if hi is not None and v > hi:
            v, fixed = hi, fixed + 1
        s[k] = int(v) if integer else float(v)

    for k in ("hunger", "happy", "energy", "hp"):
        num(k, 0, 100)
    for k in ("stage_time", "total_time", "sick_t", "starve_t", "explore_t", "bits", "weight"):
        num(k, 0)
    num("battle_t")
    for k in ("care_miss", "wins", "losses", "gen"):
        num(k, 0, integer=True)
    s["gen"] = max(1, s["gen"])
    num("stage", 0, 3, integer=True)
    for k in ("sick", "sleeping", "dead", "sick_flag", "starve_flag"):
        s[k] = bool(s.get(k, False))
    tr = s.get("train") if isinstance(s.get("train"), dict) else {}
    s["train"] = {k: float(tr[k]) if isinstance(tr.get(k), (int, float)) and not isinstance(tr.get(k), bool) else 0.0
                  for k in TRAIN_KEYS}
    it = s.get("items") if isinstance(s.get("items"), dict) else dict(d["items"])
    s["items"] = {k: int(v) for k, v in it.items() if k in SHOP and isinstance(v, (int, float)) and v >= 0}
    dx = s.get("dex") if isinstance(s.get("dex"), dict) else {}
    s["dex"] = {k: int(v) for k, v in dx.items() if k in KO and k != "egg" and isinstance(v, (int, float)) and v >= 1}
    if s["stage"] == 0:  # 알: 계통은 부화할 때 정해짐
        s["slug"], s["line"], s["chain"] = "egg", -1, -1
        return fixed
    ch = s.get("chain")
    if not isinstance(ch, int) or isinstance(ch, bool) or not 0 <= ch < len(CHAINS):
        ch, fixed = random.randrange(len(CHAINS)), fixed + 1
    forms = CHAINS[ch]["forms"]
    fi = s["stage"] - 1 - (3 - len(forms))
    if fi < 0:  # 이 계통엔 없는 낮은 단계 → 계통의 첫 단계로
        s["stage"], fi, fixed = 4 - len(forms), 0, fixed + 1
    spec = forms[fi]
    allowed = BRANCH_OPTIONS.get(spec, [spec])
    if s.get("slug") not in allowed:
        s["slug"], fixed = allowed[0], fixed + 1
    s["chain"], s["line"] = ch, CHAINS[ch]["color"]
    return fixed


DEFAULT_CFG = dict(roam=True, roam_y=None, layer="top", alpha=1.0, click_through=False, sound=True, auto_battle=True, auto_feed=True, auto_catch=True, mini=False, x=None, y=None)
MINI_W, MINI_H, MINI_FLOOR = 240, 210, 204  # 미니(로밍) 창 크기와 발바닥 높이
ROAM_SPEED = 40       # 바탕화면 로밍 속도(px/초)
FACING_RIGHT = set()  # 원본 스프라이트가 오른쪽을 보는 종 (기본은 왼쪽을 본다고 가정)
AUTO_BATTLE_EVERY = 1200  # 자동 배틀 간격(초)
BATTLE_HP_FLOOR = 15.0  # 전투로 떨어질 수 있는 최저 체력
BATTLE_IN = 1.5   # 상대 등장 연출(초)
BATTLE_OUT = 2.0  # 결과 표시(초). 공격 1회당 1초


class Game:
    def __init__(self):
        self.s = new_state()
        self.active_battle = None  # 연출 중인 전투(저장 안 함)
        self.quiet = False         # True면 메시지를 쌓지 않음(오프라인 따라잡기 중)
        self.cfg = dict(DEFAULT_CFG)
        self.log = []  # (시각, 메시지)
        self.load()

    # --- 저장/불러오기 ---
    def load(self):
        data, used = None, None
        for path in (SAVE, SAVE + ".bak"):  # 본 파일 → 백업 순으로 시도
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict) and isinstance(d.get("s"), dict):
                    data, used = d, path
                    break
                raise ValueError("형식이 다름")
            except (OSError, ValueError, TypeError):
                if path == SAVE:  # 깨진 파일은 덮어써지기 전에 따로 보관
                    try:
                        os.replace(path, f"{SAVE}.corrupt-{int(time.time())}")
                    except OSError:
                        pass
        if data is None:
            self.say("알을 발견했다! 따뜻하게 지켜봐 주자.")
            return
        if used != SAVE:
            self.say("저장 파일이 손상돼 백업에서 복구했어요.")
        cfg = data.get("cfg") if isinstance(data.get("cfg"), dict) else {}
        self.cfg.update({k: v for k, v in cfg.items() if k in DEFAULT_CFG})
        for k in ("x", "y", "roam_y"):  # 좌표는 숫자 또는 None 만 허용
            if self.cfg[k] is not None and (isinstance(self.cfg[k], bool) or not isinstance(self.cfg[k], (int, float))):
                self.cfg[k] = None
        for k in ("roam", "click_through", "sound", "auto_battle", "auto_feed", "auto_catch", "mini"):
            self.cfg[k] = bool(self.cfg[k])
        if "layer" not in cfg and "topmost" in cfg:
            self.cfg["layer"] = "top" if cfg["topmost"] else "normal"
        if self.cfg["layer"] not in ("top", "normal", "bottom"):
            self.cfg["layer"] = "top"
        a = self.cfg["alpha"]
        self.cfg["alpha"] = min(max(float(a), 0.2), 1.0) if isinstance(a, (int, float)) and not isinstance(a, bool) else 1.0
        if "chain" not in data["s"]:  # 진화 계통 구조가 바뀌기 전 저장 → 새 알로 시작
            self.s = new_state(data["s"].get("gen", 1), data["s"].get("bits", 0.0), data["s"].get("dex"), data["s"].get("items"))
            sanitize_state(self.s)
            self.say("진화 계통이 본가 기준으로 바뀌어 새 알로 시작해요.")
            return
        self.s.update(data["s"])
        fixed = sanitize_state(self.s)
        if fixed:
            self.say(f"저장 파일의 일부 값({fixed}개)을 복구했어요.")
        away = time.time() - self.s["last"]
        if away > 15:
            self.catchup_report(away)

    def save(self):
        self.s["last"] = time.time()
        tmp = SAVE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"ver": 2, "s": self.s, "cfg": self.cfg}, f, ensure_ascii=False)
        if os.path.exists(SAVE):  # 직전 저장을 백업으로 보관
            try:
                shutil.copyfile(SAVE, SAVE + ".bak")
            except OSError:
                pass
        os.replace(tmp, SAVE)

    def say(self, msg):
        if self.quiet:
            return
        self.log.append((time.time(), msg))
        del self.log[:-50]

    # --- 정보 ---
    def name(self):
        return KO[self.s["slug"]]

    def stage_label(self):
        s = self.s
        if s["stage"] == 0:
            return "알"
        i = s["stage"] - 1 - (3 - len(CHAINS[s["chain"]]["forms"]))
        return ["기본", "1진화", "2진화"][i]

    def power(self):
        s = self.s
        p = BASE_POWER[s["stage"]] + sum(s["train"].values()) * 0.3 + s["happy"] / 25 + s["gen"] * 1.5 + len(s["dex"]) * 0.4
        return p * (0.7 if s["sick"] else 1.0)

    def needs(self):
        s = self.s
        if s["dead"]:
            return []
        n = []
        if s["sick"]:
            n.append(("sick", "아파요…"))
        if s["stage"] > 0 and s["hunger"] < 25:
            n.append(("hungry", "배고파!"))
        if s["stage"] > 0 and s["happy"] < 25:
            n.append(("bored", "심심해…"))
        return n

    def next_evo(self):
        s = self.s
        need = STAGE_TIME[s["stage"]]
        if need is None:
            return "최종 단계"
        left = max(0, need - s["stage_time"])
        txt = f"{int(left // 3600)}시간 {int(left % 3600 // 60)}분 후"
        nxt = s["stage"] + 1
        if nxt in WIN_NEED and s["wins"] < WIN_NEED[nxt]:
            txt += f" (승리 {s['wins']}/{WIN_NEED[nxt]} 필요)"
        return txt

    # --- 시간 진행 ---
    def catchup_report(self, dt):
        """자리를 비운 시간을 따라잡고, 그 사이 일어난 일을 한 줄로 요약해 알려 줌."""
        s = self.s
        before = (s["slug"], s["wins"], s["losses"], len(s["dex"]), s["stage"])
        self.quiet = True
        try:
            self.catchup(dt)
        finally:
            self.quiet = False
        parts = []
        w, l, n = s["wins"] - before[1], s["losses"] - before[2], len(s["dex"]) - before[3]
        if w or l:
            parts.append(f"{w}승 {l}패")
        if n > 0:
            parts.append(f"새 포켓몬 {n}종 포획")
        extra = f" ({', '.join(parts)})" if parts else ""
        self.say(f"자리를 비운 {int(min(dt, MAX_OFFLINE) // 60)}분 동안 무럭무럭 자랐다.{extra}")
        if s["slug"] != before[0] and not s["dead"]:
            self.say(f"그 사이 {self.name()}(으)로 {'부화' if before[4] == 0 else '진화'}했다!")

    def catchup(self, dt):
        dt = min(dt, MAX_OFFLINE)
        while dt > 0:
            step = min(30.0, dt)
            self.tick(step, offline=True)
            dt -= step

    def tick(self, dt, offline=False):
        s = self.s
        if s["dead"]:
            return
        k = 0.4 if offline else 1.0
        st = s["stage"]
        ab = self.active_battle
        if ab and not ab["settled"]:
            e = self.ab_elapsed(ab)
            if e >= ab["dur"]:
                self.settle_battle()
            else:
                self.auto_catch(ab, e)
        s["total_time"] += dt
        s["stage_time"] += dt
        if self.cfg["auto_catch"] and s["items"].get("ball", 0) < AUTO_BALL_STOCK and s["bits"] >= AUTO_BALL_RESERVE:
            s["bits"] -= BALLS["ball"][1]  # 자동 포획: Bits 여유가 있으면 몬스터볼을 알아서 보충
            s["items"]["ball"] = s["items"].get("ball", 0) + 1
        if self.cfg["auto_feed"] and s["items"].get("potion", 0) < AUTO_POTION_STOCK and s["bits"] >= 2 * AUTO_BALL_RESERVE:
            s["bits"] -= SHOP["potion"][1]  # 자동 돌봄: 상처약도 알아서 보충
            s["items"]["potion"] = s["items"].get("potion", 0) + 1
        if st == 0:
            self.check_evolve()
            return

        mult = 0.5 if s["sleeping"] else 1.0
        s["hunger"] = max(0.0, s["hunger"] - 100 * dt / HUNGER_EMPTY[st] * mult * k)
        if self.cfg["auto_feed"] and s["hunger"] < 30 and s["bits"] >= AUTO_FEED_COST:
            s["bits"] -= AUTO_FEED_COST
            s["hunger"] = min(100.0, s["hunger"] + 30)
            s["weight"] += 0.5
            if not offline:
                self.say(f"[자동 급식] 알아서 밥을 먹었다. (-{AUTO_FEED_COST} Bits)")

        if s["sleeping"]:
            s["energy"] = min(100.0, s["energy"] + 100 * dt / 1200)
            if s["energy"] >= 100:
                s["sleeping"] = False
                self.say("푹 자고 일어났다!")
        else:
            s["energy"] = max(0.0, s["energy"] - 100 * dt / (4 * 3600) * k)
            if s["energy"] <= 5:
                s["sleeping"] = True
                self.say("졸려서 스르르 잠들었다…")

        drain = 100 * dt / BOND_DRAIN_SEC
        if s["hunger"] < 20:
            drain *= 2
        if s["sick"]:
            drain *= 2
        s["happy"] = max(0.0, s["happy"] - drain * k)

        # 질병 / 굶주림
        if not offline:
            if not s["sick"] and random.random() < dt / (12 * 3600):
                s["sick"] = True
                self.say("몸이 안 좋아 보인다…")
        if s["sick"] and self.cfg["auto_feed"] and s["sick_t"] > 120:
            if s["items"].get("cure", 0) > 0:  # 자동 돌봄: 아픈 지 2분이 지나면 알아서 치료(약 > Bits)
                self.use_item("cure", auto=True)
            elif s["bits"] >= AUTO_MEDICINE_COST:
                s["bits"] -= AUTO_MEDICINE_COST
                self.cure_sick(15)
                if not offline:
                    self.say(f"[자동 치료] 약을 먹고 나았다. (-{AUTO_MEDICINE_COST} Bits)")
        if s["sick"]:
            s["sick_t"] += dt
            s["hp"] -= 100 * dt / 3600 * k
            if s["sick_t"] > 600 and not s["sick_flag"] and not offline:
                s["sick_flag"] = True
                s["care_miss"] += 1
        if s["hunger"] <= 0:
            s["starve_t"] += dt
            s["hp"] -= 100 * dt / 7200 * k
            if s["starve_t"] > 600 and not s["starve_flag"] and not offline:
                s["starve_flag"] = True
                s["care_miss"] += 1
        else:
            s["starve_t"] = 0
            s["starve_flag"] = False
        if not s["sick"] and s["hunger"] > 30:
            s["hp"] = min(100.0, s["hp"] + 100 * dt / 900)

        if self.cfg["auto_feed"] and s["hp"] < AUTO_POTION_BELOW:
            for kind in ("potion", "super_potion"):
                if s["items"].get(kind, 0) > 0:
                    self.use_item(kind, auto=True)
                    break
        if offline:
            s["hp"] = max(s["hp"], 15.0)
        if s["hp"] <= 0:
            s["dead"] = True
            self.say(f"{self.name()}(이)가 데이터의 바다로 돌아갔다…")
            return

        # 방치형 요소: 탐험으로 Bits 획득, 패시브 훈련, 자동 배틀
        if not s["sleeping"] and not s["sick"]:
            s["bits"] += (1 + st) * 0.03 * dt * k
            s["train"][random.choice(TRAIN_KEYS)] += dt * 0.0005 * k
            if self.cfg["auto_battle"] and st >= 1:
                s["battle_t"] += dt
                # 20분마다(꺼 둔 동안은 40분마다), 컨디션이 충분히 좋을 때만. 패배하면 쉬었다가 다음 전투
                if s["battle_t"] >= AUTO_BATTLE_EVERY * (2 if offline else 1):
                    if s["hp"] >= 60 and s["hunger"] >= 30 and s["energy"] >= 40:
                        s["battle_t"] = 0
                        self.battle(auto=True, instant=offline)
        self.check_evolve()

    def resolve_form(self, spec):
        """진화 형태 결정. '@...' 는 분기 진화 규칙."""
        if not spec.startswith("@"):
            return spec
        s = self.s
        t = s["train"]
        if spec == "@eevee":
            if s["care_miss"] <= 2 and s["happy"] >= 70:  # 친밀도 진화: 낮=에브이, 밤=블래키
                return "espeon" if 6 <= time.localtime().tm_hour < 20 else "umbreon"
            best = max(TRAIN_KEYS, key=lambda k: t[k] + random.random() * 0.1)
            return {"power": "flareon", "speed": "jolteon", "mind": "vaporeon"}[best]
        if spec == "@ralts":
            return "gallade" if t["power"] > t["mind"] else "gardevoir"
        raise ValueError(spec)

    def check_evolve(self):
        s = self.s
        st = s["stage"]
        need = STAGE_TIME[st]
        if need is None or s["stage_time"] < need:
            return
        nxt = st + 1
        if st == 0:  # 부화: 무작위 진화 계통. 2단 진화 계통은 tier 2부터 시작
            s["chain"] = random.randrange(len(CHAINS))
            ch = CHAINS[s["chain"]]
            nxt = 4 - len(ch["forms"])
            s["line"] = ch["color"]
            s["slug"] = ch["forms"][0]
        else:
            if nxt in WIN_NEED and s["wins"] < WIN_NEED[nxt]:
                return  # 배틀 승리가 더 필요
            ch = CHAINS[s["chain"]]
            s["slug"] = self.resolve_form(ch["forms"][nxt - 1 - (3 - len(ch["forms"]))])
        s["stage"] = nxt
        s["stage_time"] = 0.0
        s["hp"] = 100.0
        s["weight"] += 3
        if st == 0:
            self.say(f"알이 부화했다! 안녕, {self.name()}!")
        else:
            self.say(f"진화! {self.name()}(으)로 진화했다!")

    # --- 행동 ---
    def _ok(self):
        s = self.s
        if s["dead"]:
            self.say("이미 떠났다…")
            return False
        if s["stage"] == 0:
            self.say("아직 알이다. 조금만 기다리자.")
            return False
        return True

    def feed(self, kind="meat"):
        s = self.s
        if not self._ok():
            return
        if s["sleeping"]:
            return self.say("자는 중이다. 깨우고 먹이자.")
        if s["hunger"] >= 100:
            return self.say("배불러서 안 먹는다.")
        if kind == "snack":
            if s["bits"] < 5:
                return self.say("간식을 사려면 5 Bits가 필요하다.")
            s["bits"] -= 5
            s["hunger"] = min(100, s["hunger"] + 10)
            s["happy"] = min(100, s["happy"] + 15)
            s["weight"] += 2
            self.say("간식 냠냠! 기분이 좋아졌다.")
        else:
            s["hunger"] = min(100, s["hunger"] + 30)
            s["weight"] += 1
            self.say("고기를 먹었다. 냠냠!")

    def train(self, key):
        s = self.s
        if not self._ok():
            return
        if s["sleeping"]:
            return self.say("자는 중이다.")
        if s["energy"] < 15 or s["hunger"] < 10:
            return self.say("지쳐서 훈련할 수 없다.")
        s["train"][key] += 1 + random.random()
        s["energy"] -= 10
        s["hunger"] = max(0, s["hunger"] - 5)
        s["happy"] = max(0, s["happy"] - 2)
        s["weight"] = max(1.0, s["weight"] - 0.5)
        self.say(f"{TRAIN_LABEL[key]} 훈련 완료!")

    def toggle_sleep(self):
        s = self.s
        if not self._ok():
            return
        s["sleeping"] = not s["sleeping"]
        self.say("쿨쿨… 잠들었다." if s["sleeping"] else "일어났다!")

    def medicine(self):
        s = self.s
        if not self._ok():
            return
        if not s["sick"]:
            return self.say("아프지 않다.")
        if s["items"].get("cure", 0) > 0:
            return self.use_item("cure")
        if s["bits"] < AUTO_MEDICINE_COST:
            return self.say(f"치료하려면 {AUTO_MEDICINE_COST} Bits(또는 만병통치약)가 필요하다.")
        s["bits"] -= AUTO_MEDICINE_COST
        self.cure_sick(15)
        self.say(f"약을 먹고 나았다! (-{AUTO_MEDICINE_COST} Bits)")

    def cure_sick(self, heal):
        s = self.s
        s["sick"] = False
        s["sick_t"] = 0
        s["sick_flag"] = False
        s["hp"] = min(100.0, s["hp"] + heal)

    def use_item(self, kind, auto=False):
        """가방 아이템 사용. 볼은 전투 중에 던지므로 여기서는 제외."""
        s = self.s
        if kind in BALLS:
            return self.say("볼은 전투 중에 던질 수 있다.")
        if s["dead"] or s["stage"] == 0:
            return self.say("지금은 쓸 수 없다.")
        if s["items"].get(kind, 0) <= 0:
            return self.say(f"{SHOP[kind][0]}이(가) 없다.")
        if kind in ("potion", "super_potion"):
            if s["hp"] >= 100:
                return self.say("체력이 가득 차 있다.")
            s["hp"] = min(100.0, s["hp"] + (30 if kind == "potion" else 70))
        elif kind == "cure":
            if not s["sick"]:
                return self.say("아프지 않다.")
            self.cure_sick(10)
        elif kind == "bento":
            if s["hunger"] >= 100:
                return self.say("배불러서 안 먹는다.")
            s["hunger"] = min(100.0, s["hunger"] + 60)
            s["happy"] = min(100.0, s["happy"] + 5)
            s["weight"] += 1
        elif kind == "candy":
            key = random.choice(TRAIN_KEYS)
            s["train"][key] += 3
            self.say(f"{TRAIN_LABEL[key]} 수치가 올랐다!")
        s["items"][kind] -= 1
        self.say(f"{'[자동] ' if auto else ''}{SHOP[kind][0]}을(를) 썼다.")

    def pet(self):
        s = self.s
        if s["dead"] or s["stage"] == 0:
            return False
        s["happy"] = min(100, s["happy"] + PET_GAIN)
        return True

    def battle(self, auto=False, instant=False):
        s = self.s
        if not self._ok():
            return
        if s["sleeping"] or s["hp"] < 30 or s["energy"] < 15:
            return self.say("컨디션이 안 좋아 싸울 수 없다.")
        ab = self.active_battle
        if ab and not ab["settled"]:
            return self.say("이미 전투 중이다.")
        st = s["stage"]
        slug = random.choice(FOE_POOL[st])
        enemy = BASE_POWER[st] * random.uniform(0.7, 1.4) + 2
        s["energy"] -= 8
        win = self.power() * random.uniform(0.8, 1.2) > enemy
        events = self.battle_events(win)
        # 결과(승패/보상/체력)는 연출이 끝날 때 settle_battle 에서 반영. 그 사이 볼을 던져 잡을 수 있음
        self.active_battle = dict(
            foe=KO[slug], slug=slug, stage=st, line=random.randrange(4), win=win, auto=auto,
            reward=random.randint(3, 6) * st if win else 0, events=events, start=time.time(),
            dur=BATTLE_IN + len(events) + BATTLE_OUT, pause=None, captured=False, settled=False,
            auto_tries=0, fail_t=0.0)
        if instant:  # 앱을 꺼 둔 동안의 전투: 연출 없이 바로 결과 반영
            self.instant_finish()

    def instant_finish(self):
        s, ab = self.s, self.active_battle
        if self.cfg["auto_catch"] and ab["slug"] not in s["dex"]:  # 새 포켓몬이면 볼을 한 번 던짐(상대 체력 50% 가정)
            for kind in ("ball", "great"):
                if s["items"].get(kind, 0) > 0:
                    s["items"][kind] -= 1
                    ab["captured"] = random.random() < min(0.95, max(0.05, CATCH_BASE.get(ab["slug"], 0.4) * BALLS[kind][2]))
                    break
        self.settle_battle()
        self.active_battle = None

    def settle_now(self):
        """종료 직전: 진행 중이던 전투 결과를 잃지 않도록 바로 반영."""
        ab = self.active_battle
        if ab and not ab["settled"]:
            pa = ab["pause"]
            if pa and pa["ok"]:
                ab["captured"] = True
            self.settle_battle()

    def ab_elapsed(self, ab):
        """전투 경과 시간. 볼을 던지면 CATCH_T 동안 시간이 멈추고, 끝나면 이어서(성공이면 마무리) 진행."""
        pa = ab["pause"]
        if pa:
            now = time.time()
            if now < pa["until"]:
                return pa["at"]
            ab["pause"] = None
            ab["start"] = now - pa["at"]
            if pa["ok"]:
                ab["captured"] = True
                ab["pause_kind"] = pa["kind"]
                ab["dur"] = pa["at"] + CAUGHT_OUT
            else:
                ab["fail_t"] = now
                self.say(f"{ab['foe']}이(가) 볼에서 빠져나왔다!")
        return time.time() - ab["start"]

    def battle_state(self, ab, e):
        """경과 시간 e 에서의 체력/돌진/흔들림 연출 값."""
        evs = ab["events"]
        pet_hp = foe_hp = 100.0
        lunge = {"pet": 0.0, "foe": 0.0}
        shake = {"pet": 0.0, "foe": 0.0}
        pop = None
        for i, (who, dmg) in enumerate(evs):
            f = e - BATTLE_IN - i
            if f < 0:
                break
            target = "foe" if who == "pet" else "pet"
            if f < 1:
                lunge[who] = math.sin(math.pi * f)
                if f >= 0.5:
                    shake[target] = math.sin(f * 60) * (1 - f) * 6
                    pop = (target, dmg, f)
            if f >= 0.5:
                if target == "foe":
                    foe_hp -= dmg
                else:
                    pet_hp -= dmg
        if e >= BATTLE_IN + len(evs) and not ab["win"]:
            pet_hp = 0
        return dict(pet_hp=max(0, pet_hp), foe_hp=max(0, foe_hp), lunge=lunge, shake=shake, pop=pop)

    def throw_ball(self, kind, auto=False):
        s, ab = self.s, self.active_battle
        if not ab or ab["settled"] or ab["pause"] or ab["captured"]:
            return False if auto else self.say("지금은 볼을 던질 수 없다.")
        e = self.ab_elapsed(ab)
        if e < BATTLE_IN or e >= BATTLE_IN + len(ab["events"]) - 0.5:
            return False if auto else self.say("지금은 볼을 던질 수 없다.")
        if s["items"].get(kind, 0) <= 0:
            return False if auto else self.say(f"{BALLS[kind][0]}이(가) 없다. 상점에서 살 수 있다.")
        s["items"][kind] -= 1
        frac = self.battle_state(ab, e)["foe_hp"] / 100
        p = min(0.95, max(0.05, CATCH_BASE.get(ab["slug"], 0.4) * (1.5 - frac) * BALLS[kind][2]))
        now = time.time()
        ab["pause"] = dict(at=e, until=now + CATCH_T, t0=now, ok=random.random() < p, kind=kind)
        self.say(f"{BALLS[kind][0]}을(를) 던졌다!")
        return True

    def auto_catch(self, ab, e):
        """자동 포획: 아직 도감에 없는 상대가 체력 50% 이하일 때 볼을 던짐(최대 2번)."""
        s = self.s
        if (not self.cfg["auto_catch"] or ab["pause"] or ab["captured"] or ab["auto_tries"] >= 2
                or e < BATTLE_IN or ab["slug"] in s["dex"]):
            return
        if self.battle_state(ab, e)["foe_hp"] > 50:
            return
        order = ["great", "ball"] if CATCH_BASE.get(ab["slug"], 0.4) < 0.3 else ["ball", "great"]
        for kind in order:
            if s["items"].get(kind, 0) > 0:
                ab["auto_tries"] += 1
                self.throw_ball(kind, auto=True)
                return

    def buy(self, kind, qty=1):
        return self.buy_many({kind: qty})

    def buy_many(self, cart):
        """장바구니 {품목: 수량}을 한 번에 구매. Bits가 모자라면 아무것도 사지 않음."""
        s = self.s
        cart = {k: int(q) for k, q in cart.items() if k in SHOP and int(q) > 0}
        if not cart:
            return self.say("구매할 수량을 골라 주세요.") or False
        total = sum(SHOP[k][1] * q for k, q in cart.items())
        if total > s["bits"]:
            return self.say(f"Bits가 부족하다. (필요 {total}, 보유 {int(s['bits'])})") or False
        s["bits"] -= total
        for k, q in cart.items():
            s["items"][k] = s["items"].get(k, 0) + q
        self.say("구매: " + ", ".join(f"{SHOP[k][0]} ×{q}" for k, q in cart.items()) + f" (-{total} Bits)")
        return True

    def settle_battle(self):
        s, ab = self.s, self.active_battle
        if not ab or ab["settled"]:
            return
        ab["settled"] = True
        foe, tag = ab["foe"], "[자동] " if ab["auto"] else ""
        if ab["captured"] or ab["win"]:
            s["wins"] += 1
            s["happy"] = min(100, s["happy"] + (8 if ab["captured"] else 5))
            s["hp"] = max(BATTLE_HP_FLOOR, s["hp"] - (1 if ab["captured"] else 2))
            s["train"][random.choice(TRAIN_KEYS)] += 0.5
            reward = ab["reward"] // 2 if ab["captured"] else ab["reward"]
            if ab["captured"] and not ab["win"]:
                reward = max(reward, 2 * s["stage"])
            s["bits"] += reward
        if ab["captured"]:
            first = ab["slug"] not in s["dex"]
            s["dex"][ab["slug"]] = s["dex"].get(ab["slug"], 0) + 1
            if first:
                s["bits"] += 20
                self.say(f"{tag}{foe}을(를) 포획했다! 도감 등록 ({len(s['dex'])}종) +20 Bits")
            else:
                self.say(f"{tag}{foe}을(를) 또 포획했다! +{reward} Bits")
        elif ab["win"]:
            self.say(f"{tag}{foe}에게 승리! +{ab['reward']} Bits")
        else:
            s["losses"] += 1
            s["hp"] = max(BATTLE_HP_FLOOR, s["hp"] - 8)  # 전투로는 죽지 않음
            s["happy"] = max(0, s["happy"] - 8)
            s["battle_t"] = -AUTO_BATTLE_EVERY  # 패배 후엔 자동 배틀을 쉼
            self.say(f"{tag}{foe}에게 졌다… 쉬어야겠다.")

    @staticmethod
    def battle_events(win):
        """[(공격자, 데미지%)] 연출용. 승자는 합계 100%로 상대를 쓰러뜨리고, 패자는 30~70%만 입힘."""
        def split(total, n):
            cuts = sorted(random.sample(range(1, total), n - 1)) if n > 1 else []
            return [b - a for a, b in zip([0] + cuts, cuts + [total])]
        winner, loser = ("pet", "foe") if win else ("foe", "pet")
        wl = split(100, random.randint(2, 4))
        ll = split(random.randint(30, 70), random.randint(1, 3))
        last = wl.pop()
        ev, i = [], 0
        while wl or ll:
            side = "pet" if i % 2 == 0 else "foe"
            src = wl if side == winner else ll
            if not src:
                side = loser if side == winner else winner
                src = wl if side == winner else ll
            ev.append((side, src.pop(0)))
            i += 1
        ev.append((winner, last))
        return ev

    def reincarnate(self):
        s = self.s
        self.s = new_state(gen=s["gen"] + 1, bits=s["bits"], dex=s["dex"], items=s["items"])
        self.say(f"{self.s['gen']}세대 알을 받았다!")


# ───────────────────────── UI ─────────────────────────
SHELL = "#2b2f3a"
BTN = "#4a5163"


class App:
    def __init__(self):
        self.g = Game()
        self.root = tk.Tk()
        r = self.root
        r.title("DigiPet")
        r.overrideredirect(True)
        r.configure(bg=KEY)
        try:
            r.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass

        self._hot = False
        self._hot_p = False
        self.hidden = False
        self.face = -1          # 이동 방향(-1 왼쪽 / +1 오른쪽)
        self.rx = None          # 로밍 중인 창의 x (실수)
        self.rdir, self.rwait, self.rwalk = -1, 0.0, 6.0
        self.full_pos = None
        self.tray = None
        self._cmds = deque()    # 트레이 콜백은 Tk를 직접 부르면 안 되므로(GIL 충돌) 명령을 큐에 쌓아 루프에서 처리
        self._tray_key = None
        self._last_rt = time.time()
        self._alpha_cur = None
        self._bottom_t = 0.0
        self.page = "main"
        self.img_cache = {}
        self.hearts = []  # [x, y, life]
        self.px = 160.0
        self.target = 160.0
        self.wait = 0.0
        self.last_needs = set()
        self.last_t = time.time()
        self.last_save = time.time()
        self._drag = None

        self.build_full()
        self.build_mini()
        self.build_menus()

        c = self.g.cfg
        if c["x"] is None:
            c["x"] = r.winfo_screenwidth() - 380
            c["y"] = r.winfo_screenheight() - 560
        self.place()
        self.show_mode(c["mini"])
        r.update_idletasks()
        self.apply_window()
        self.move_into_view()
        r.report_callback_exception = log_exception
        if winutil:
            try:
                self.tray = winutil.Tray("DigiPet", self.tray_items, self._cmds.append)
                self.refresh_tray()
            except Exception:
                log_exception(*sys.exc_info())
        r.protocol("WM_DELETE_WINDOW", self.quit)
        r.after(200, self.loop)
        r.after(50, self.move_loop)

    # --- 구성 ---
    def build_full(self):
        self.full = tk.Frame(self.root, bg=SHELL, padx=8, pady=6)
        bar = tk.Frame(self.full, bg=SHELL)
        bar.pack(fill="x")
        t = tk.Label(bar, text="DigiPet", bg=SHELL, fg="#9fb0d0", font=(FONT, 9, "bold"))
        t.pack(side="left")
        for txt, cmd in (("×", self.quit), ("—", lambda: self.show_mode(True))):
            tk.Button(bar, text=txt, command=cmd, bg=SHELL, fg="#9fb0d0", bd=0, width=3,
                      activebackground=BTN, activeforeground="#fff", font=(FONT, 9)).pack(side="right")
        self.screen = tk.Canvas(self.full, width=320, height=230, highlightthickness=3,
                                highlightbackground="#171a21", bd=0)
        self.screen.pack(pady=4)
        self.info = tk.Label(self.full, bg=SHELL, fg="#c9d4ec", font=(FONT, 9))
        self.info.pack()

        grid = tk.Frame(self.full, bg=SHELL)
        grid.pack(pady=(4, 0))
        self.btns = {}
        specs = [
            ("먹이", lambda: self.popup(self.feed_menu, "먹이")),
            ("훈련", lambda: self.popup(self.train_menu, "훈련")),
            ("배틀", self.battle_btn),
            ("재우기", self.g.toggle_sleep),
            ("치료", self.g.medicine),
            ("가방", self.open_bag),
            ("상점", self.open_shop),
            ("도감", self.toggle_dex),
            ("상태", self.toggle_stats),
            ("설정", lambda: self.popup(self.menu, "설정")),
        ]
        for i, (txt, cmd) in enumerate(specs):
            b = tk.Button(grid, text=txt, command=cmd, width=5, bg=BTN, fg="#fff", bd=0,
                          activebackground="#6a7390", activeforeground="#fff", font=(FONT, 9))
            b.grid(row=i // 5, column=i % 5, padx=2, pady=2)
            self.btns[txt] = b

        self.bind_drag(bar)
        self.bind_drag(t)
        self.bind_drag(self.screen, click=self.on_click)
        self.screen.bind("<Double-Button-1>", lambda e: self.show_mode(True))

    def build_mini(self):
        self.mini = tk.Canvas(self.root, width=MINI_W, height=MINI_H, bg=KEY, highlightthickness=0, bd=0)
        self.bind_drag(self.mini, click=self.on_click)
        self.mini.bind("<Double-Button-1>", lambda e: self.show_mode(False))

    def build_menus(self):
        g = self.g
        self.feed_menu = tk.Menu(self.root, tearoff=0)
        self.feed_menu.add_command(label="고기 (+30)", command=lambda: g.feed("meat"))
        self.feed_menu.add_command(label="간식 (5 Bits, 친밀도↑)", command=lambda: g.feed("snack"))
        self.train_menu = tk.Menu(self.root, tearoff=0)
        for k in TRAIN_KEYS:
            self.train_menu.add_command(label=f"{TRAIN_LABEL[k]} 훈련", command=lambda k=k: g.train(k))
        self.v_feed = tk.BooleanVar(value=g.cfg["auto_feed"])
        self.v_catch = tk.BooleanVar(value=g.cfg["auto_catch"])
        self.v_layer = tk.StringVar(value=g.cfg["layer"])
        self.v_alpha = tk.IntVar(value=round(g.cfg["alpha"] * 100))
        self.v_ct = tk.BooleanVar(value=g.cfg["click_through"])
        self.v_roam = tk.BooleanVar(value=g.cfg["roam"])
        self.v_auto = tk.BooleanVar(value=g.cfg["auto_battle"])
        self.v_sound = tk.BooleanVar(value=g.cfg["sound"])
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="미니/전체 모드 전환 (더블클릭)", command=lambda: self.show_mode(not g.cfg["mini"]))
        m.add_command(label="상점 열기", command=self.open_shop)
        m.add_command(label="상태 보기", command=self.show_stats)
        m.add_command(label="도감 보기", command=self.show_dex)
        win = tk.Menu(m, tearoff=0)
        for val, txt in (("top", "항상 위"), ("normal", "보통"), ("bottom", "항상 아래 (다른 창 뒤, 바탕화면 위)")):
            win.add_radiobutton(label=txt, value=val, variable=self.v_layer, command=self.apply_cfg)
        win.add_separator()
        for pct in (100, 80, 60, 40, 25):
            win.add_radiobutton(label=f"투명도 {pct}%", value=pct, variable=self.v_alpha, command=self.apply_cfg)
        win.add_separator()
        win.add_checkbutton(label="클릭 통과 (해제: Ctrl+Alt+D)", variable=self.v_ct, command=self.apply_cfg)
        win.add_separator()
        win.add_command(label="창 되찾기 / 앞으로 (Ctrl+Alt+P)", command=self.rescue)
        m.add_cascade(label="창 설정 (투명/클릭 통과)", menu=win)
        m.add_checkbutton(label="바탕화면 돌아다니기 (미니 모드)", variable=self.v_roam, command=self.apply_cfg)
        m.add_command(label="펫을 바닥(작업표시줄 위)으로 내리기", command=self.drop_to_ground)
        m.add_checkbutton(label="자동 배틀", variable=self.v_auto, command=self.apply_cfg)
        m.add_checkbutton(label="자동 돌봄: 급식·치료 (Bits 소모)", variable=self.v_feed, command=self.apply_cfg)
        m.add_checkbutton(label="자동 포획 (새 포켓몬만)", variable=self.v_catch, command=self.apply_cfg)
        m.add_checkbutton(label="알림 소리", variable=self.v_sound, command=self.apply_cfg)
        m.add_separator()
        m.add_command(label="몬스터볼 던지기", command=lambda: g.throw_ball("ball"))
        m.add_command(label="슈퍼볼 던지기", command=lambda: g.throw_ball("great"))
        m.add_command(label="하이퍼볼 던지기", command=lambda: g.throw_ball("ultra"))
        m.add_separator()
        m.add_command(label="새 알로 환생", command=self.reincarnate)
        m.add_command(label="저장 후 종료", command=self.quit)
        self.menu = m
        self.root.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

    def battle_btn(self):
        """전투 중에는 볼 선택 메뉴, 아니면 전투 시작."""
        g = self.g
        ab = g.active_battle
        if not (ab and not ab["settled"]):
            return g.battle()
        m = tk.Menu(self.root, tearoff=0)
        for k, (nm, _, _) in BALLS.items():
            m.add_command(label=f"{nm} ({g.s['items'].get(k, 0)}개)", command=lambda k=k: g.throw_ball(k))
        self.popup(m, "배틀")

    def open_shop(self):
        """상점 창: 품목별 수량을 고르고(스핀박스/+10/최대) 한꺼번에 구매."""
        old = getattr(self, "shop_win", None)
        if old is not None and old.winfo_exists():
            old.lift()
            return
        g, root = self.g, self.root
        win = self.shop_win = tk.Toplevel(root)
        win.title("상점")
        win.configure(bg=SHELL, padx=12, pady=10)
        win.resizable(False, False)
        win.transient(root)
        if g.cfg["layer"] == "top":
            win.attributes("-topmost", True)
        fg, dim = "#e8edf8", "#9fb0d0"
        bits_lbl = tk.Label(win, bg=SHELL, fg="#ffd23c", font=(FONT, 11, "bold"))
        bits_lbl.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
        rows = {}
        for i, (key, (nm, price, desc)) in enumerate(SHOP.items(), start=1):
            var = tk.StringVar(value="0")
            tk.Label(win, text=nm, bg=SHELL, fg=fg, font=(FONT, 10, "bold"), width=9, anchor="w").grid(row=i, column=0, sticky="w")
            tk.Label(win, text=desc, bg=SHELL, fg=dim, font=(FONT, 9), width=20, anchor="w").grid(row=i, column=1, sticky="w")
            tk.Label(win, text=f"{price} Bits", bg=SHELL, fg=fg, font=(FONT, 9), width=8, anchor="e").grid(row=i, column=2)
            own = tk.Label(win, bg=SHELL, fg=dim, font=(FONT, 9), width=7, anchor="e")
            own.grid(row=i, column=3)
            sp = tk.Spinbox(win, from_=0, to=999, width=4, textvariable=var, font=(FONT, 10), justify="center")
            sp.grid(row=i, column=4, padx=(8, 2), pady=2)
            btns = tk.Frame(win, bg=SHELL)
            btns.grid(row=i, column=5, sticky="w")
            rows[key] = dict(var=var, own=own)
            for txt, cmd in (("+10", lambda k=key: bump(k, 10)), ("최대", lambda k=key: fill_max(k)), ("0", lambda k=key: rows[k]["var"].set("0"))):
                tk.Button(btns, text=txt, command=cmd, bg=BTN, fg="#fff", bd=0, font=(FONT, 8), width=3,
                          activebackground="#6a7390", activeforeground="#fff").pack(side="left", padx=1)
            var.trace_add("write", lambda *a: refresh())
        n = len(SHOP) + 1
        total_lbl = tk.Label(win, bg=SHELL, fg=fg, font=(FONT, 10, "bold"))
        total_lbl.grid(row=n, column=0, columnspan=4, sticky="w", pady=(8, 0))
        foot = tk.Frame(win, bg=SHELL)
        foot.grid(row=n, column=4, columnspan=2, sticky="e", pady=(8, 0))
        buy_btn = tk.Button(foot, text="구매", command=lambda: do_buy(), bg="#3b82e0", fg="#fff", bd=0, width=7,
                            font=(FONT, 10, "bold"), activebackground="#5b9cf0", activeforeground="#fff")
        buy_btn.pack(side="left", padx=2)
        tk.Button(foot, text="닫기", command=win.destroy, bg=BTN, fg="#fff", bd=0, width=6, font=(FONT, 10),
                  activebackground="#6a7390", activeforeground="#fff").pack(side="left", padx=2)

        def qty(key):
            try:
                return min(999, max(0, int(rows[key]["var"].get())))
            except ValueError:
                return 0

        def total():
            return sum(SHOP[k][1] * qty(k) for k in SHOP)

        def bump(key, n):
            rows[key]["var"].set(str(min(999, qty(key) + n)))

        def fill_max(key):
            others = total() - SHOP[key][1] * qty(key)
            rows[key]["var"].set(str(max(0, min(999, (int(g.s["bits"]) - others) // SHOP[key][1]))))

        def refresh():
            if not win.winfo_exists():
                return
            t, bits = total(), int(g.s["bits"])
            bits_lbl.config(text=f"보유 Bits: {bits}")
            for k, r in rows.items():
                r["own"].config(text=f"보유 {g.s['items'].get(k, 0)}")
            items = sum(qty(k) for k in SHOP)
            total_lbl.config(text=f"합계 {t} Bits ({items}개)" + ("  — Bits 부족!" if t > bits else ""),
                             fg="#ff6b6b" if t > bits else fg)
            buy_btn.config(state="normal" if 0 < t <= bits else "disabled")

        def do_buy():
            if g.buy_many({k: qty(k) for k in SHOP}):
                win.destroy()  # 구매가 끝나면 상점 창을 닫음
            else:
                refresh()

        def tick():  # 열어 둔 동안에도 Bits 증가/보유 수가 갱신되도록
            if win.winfo_exists():
                refresh()
                win.after(1000, tick)

        refresh()  # 글자가 채워진 뒤의 실제 크기로 위치를 계산
        root.update_idletasks()
        win.update_idletasks()
        l, t, rr, b = self.work_area()  # 펫 창 근처에 열되, 화면(작업 영역) 밖으로 나가지 않게
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        # geometry 의 x,y 는 제목줄/테두리를 포함한 바깥 위치 → 크기에 제목줄(약 38px)+테두리(약 18px) 여유를 더함
        x = min(max(l, root.winfo_x() + 20), max(l, rr - w - 18))
        y = min(max(t, root.winfo_y() + 20), max(t, b - h - 48))
        win.geometry(f"+{x}+{y}")
        refresh()
        tick()

    def open_bag(self):
        g = self.g
        m = tk.Menu(self.root, tearoff=0)
        owned = [(k, n) for k, n in g.s["items"].items() if n > 0 and k in SHOP and k not in BALLS]
        for k, n in owned:
            m.add_command(label=f"{SHOP[k][0]} ×{n}  ·  {SHOP[k][2]}", command=lambda k=k: g.use_item(k))
        if not owned:
            m.add_command(label="(사용할 아이템이 없어요 — 상점에서 구매)", state="disabled")
        balls = ", ".join(f"{BALLS[k][0]} {g.s['items'].get(k, 0)}" for k in BALLS)
        m.add_separator()
        m.add_command(label=f"볼: {balls}", state="disabled")
        self.popup(m, "가방")

    def popup(self, menu, name):
        b = self.btns[name]
        menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def apply_cfg(self):
        c = self.g.cfg
        c["layer"] = self.v_layer.get()
        c["alpha"] = self.v_alpha.get() / 100
        c["click_through"] = self.v_ct.get()
        c["roam"] = self.v_roam.get()
        self.rx = None
        c["auto_battle"] = self.v_auto.get()
        c["sound"] = self.v_sound.get()
        c["auto_feed"] = self.v_feed.get()
        c["auto_catch"] = self.v_catch.get()
        self.apply_window()

    # --- 창 투명/클릭 통과/레이어 (Windows) ---
    def hwnd(self):
        return USER32.GetAncestor(self.root.winfo_id(), 2) if USER32 else 0

    def apply_window(self):
        """창 위치(항상 위/보통/아래), 투명도, 클릭 통과를 반영."""
        c = self.g.cfg
        self.root.attributes("-topmost", c["layer"] == "top")
        self._alpha_cur = None
        self.update_alpha(force=True)
        if USER32:
            h = self.hwnd()
            style = USER32.GetWindowLongW(h, -20) | 0x80000  # WS_EX_LAYERED
            style = (style | 0x20) if c["click_through"] else (style & ~0x20)  # WS_EX_TRANSPARENT
            USER32.SetWindowLongW(h, -20, style)
            if c["layer"] == "bottom":
                self.push_to_bottom()

    def push_to_bottom(self):
        # HWND_BOTTOM, SWP_NOMOVE|NOSIZE|NOACTIVATE
        USER32.SetWindowPos(self.hwnd(), 1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def update_alpha(self, force=False):
        a = round(self.g.cfg["alpha"], 2)
        if force or a != self._alpha_cur:
            self._alpha_cur = a
            self.root.attributes("-alpha", a)

    def poll_window(self, now):
        if not USER32:
            return
        down = all(USER32.GetAsyncKeyState(k) & 0x8000 for k in (0x11, 0x12, 0x44))  # Ctrl+Alt+D
        if down and not self._hot:
            c = self.g.cfg
            c["click_through"] = not c["click_through"]
            self.v_ct.set(c["click_through"])
            self.apply_window()
            self.g.say("클릭 통과 켜짐 (Ctrl+Alt+D 로 해제)" if c["click_through"] else "클릭 통과 꺼짐")
        self._hot = down
        down_p = all(USER32.GetAsyncKeyState(k) & 0x8000 for k in (0x11, 0x12, 0x50))  # Ctrl+Alt+P
        if down_p and not self._hot_p:
            self.rescue()
        self._hot_p = down_p
        if self.g.cfg["layer"] == "bottom" and now - self._bottom_t > 1.0:
            self._bottom_t = now
            self.push_to_bottom()

    # --- 창 이동/모드 ---
    def bind_drag(self, w, click=None):
        def press(e):
            self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y(), e.x_root, e.y_root, False)

        def move(e):
            if not self._drag:
                return
            dx, dy, sx, sy, _ = self._drag
            moved = abs(e.x_root - sx) + abs(e.y_root - sy) > 4
            if moved:
                self.root.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")
                self._drag = (dx, dy, sx, sy, True)

        def release(e):
            if not self._drag:
                return
            moved = self._drag[4]
            self._drag = None
            if moved:
                self.g.cfg["x"], self.g.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
                self.note_drag_y()
            elif click:
                click(e)

        w.bind("<ButtonPress-1>", press)
        w.bind("<B1-Motion>", move)
        w.bind("<ButtonRelease-1>", release)

    def place(self):
        c = self.g.cfg
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = min(max(0, int(c["x"])), sw - 100)
        y = min(max(0, int(c["y"])), sh - 100)
        self.root.geometry(f"+{x}+{y}")

    def show_mode(self, mini):
        c, r = self.g.cfg, self.root
        was = c["mini"]
        if mini and not was:  # 전체 → 미니: 전체 창 위치를 기억
            self.full_pos = (r.winfo_x(), r.winfo_y())
        c["mini"] = mini
        if mini:
            self.full.pack_forget()
            self.mini.pack()
        else:
            self.mini.pack_forget()
            self.full.pack()
            if was and self.full_pos:  # 미니 → 전체: 원래 위치로 복귀
                r.geometry(f"+{self.full_pos[0]}+{self.full_pos[1]}")
        self.rx = None
        r.update_idletasks()
        self.move_into_view()

    def work_area(self):
        wa = winutil.work_area(self.hwnd()) if winutil and USER32 else None
        return wa or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def move_into_view(self):
        """창이 화면(작업 영역) 밖에 있으면 안으로 옮김. 미니 창은 투명한 가장자리만큼은 밖으로 나가도 됨."""
        r = self.root
        r.update_idletasks()
        l, t, rr, b = self.work_area()
        # 숨김/최소화 중에는 winfo_x 가 낡았을 수 있어, 예약된 위치를 담은 geometry() 문자열을 기준으로 함
        mt = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", r.geometry())  # Tk는 음수 좌표를 "+-123" 으로 표기
        w, h, cx, cy = (int(mt.group(1)), int(mt.group(2)), int(mt.group(3)), int(mt.group(4))) if mt else (
            r.winfo_width(), r.winfo_height(), r.winfo_x(), r.winfo_y())
        m = 60 if self.g.cfg["mini"] else 0
        x = min(max(cx, l - m), max(l - m, rr - w + m))
        y = min(max(cy, t), max(t, b - h))
        if (x, y) != (cx, cy):
            r.geometry(f"+{x}+{y}")
            r.update()  # 바로 적용(이후 topmost 변경 등이 낡은 위치를 되살리지 않도록)

    def rescue(self):
        """창이 안 보일 때: 보이기 + 클릭 통과 해제 + 화면 안으로 + 맨 앞으로."""
        c, r = self.g.cfg, self.root
        self.hidden = False
        r.deiconify()
        r.update()  # 숨겨 둔 동안 예약된 위치가 먼저 적용되도록
        if c["click_through"]:
            c["click_through"] = False
            self.v_ct.set(False)
        self.apply_window()
        self.move_into_view()
        r.lift()
        r.attributes("-topmost", True)  # 잠깐 맨 위로 띄웠다가 설정대로 복귀
        r.after(2500, lambda: r.attributes("-topmost", c["layer"] == "top"))
        self.g.say("창을 불러왔어요!")

    def drop_to_ground(self):
        self.g.cfg["roam_y"] = None
        self.rx = None

    def note_drag_y(self):
        c = self.g.cfg
        if c["mini"] and c["roam"]:
            ground = self.work_area()[3] - MINI_H
            y = self.root.winfo_y()
            c["roam_y"] = None if abs(y - ground) <= 24 else y

    # --- 시스템 트레이 ---
    def tray_items(self):
        c = self.g.cfg
        return [(1, "보이기" if self.hidden else "숨기기", False), (2, "앞으로 가져오기 (Ctrl+Alt+P)", False), None,
                (3, "미니 모드", c["mini"]), (4, "바탕화면 돌아다니기", c["roam"]),
                (5, "클릭 통과 (해제: Ctrl+Alt+D)", c["click_through"]), None, (6, "저장 후 종료", False)]

    def tray_command(self, cmd):
        c = self.g.cfg
        if cmd == 1:
            self.hidden = not self.hidden
            self.root.withdraw() if self.hidden else self.root.deiconify()
        elif cmd == 2:
            self.rescue()
        elif cmd == 3:
            self.rescue()
            self.show_mode(not c["mini"])
        elif cmd == 4:
            self.v_roam.set(not c["roam"])
            self.apply_cfg()
        elif cmd == 5:
            self.v_ct.set(not c["click_through"])
            self.apply_cfg()
        elif cmd == 6:
            self.quit()

    def refresh_tray(self):
        """진화/사망으로 모습이 바뀌면 트레이 아이콘도 갱신."""
        s = self.g.s
        key = (s["stage"], s["line"], s["dead"])
        if not self.tray or key == self._tray_key:
            return
        self._tray_key = key
        rows = [[(0, 0, 0, 0)] * 16 for _ in range(16)]
        for x, y, w, col in sprite_runs(BUILTIN_TIER[s["stage"]], max(s["line"], 0), False):
            h = col.lstrip("#")
            h = "".join(ch * 2 for ch in h) if len(h) == 3 else h
            rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
            for i in range(w):
                rows[y][x + i] = rgb + (255,)
        self.tray.set_icon(rows)

    def toggle_stats(self):
        self.page = "main" if self.page == "stats" else "stats"

    def toggle_dex(self):
        self.page = "main" if self.page == "dex" else "dex"

    def show_dex(self):
        self.page = "dex"
        self.show_mode(False)

    def show_stats(self):
        self.page = "stats"
        self.show_mode(False)

    def reincarnate(self):
        if messagebox.askyesno("환생", "현재 펫을 보내고 새 알로 시작할까요?\n(Bits와 세대 보너스는 유지돼요)"):
            self.g.reincarnate()

    def on_click(self, e):
        g = self.g
        if g.s["dead"]:  # 실수 클릭으로 바로 환생하지 않도록 확인
            if messagebox.askyesno("작별", f"{g.name()}이(가) 떠났어요.\n새 알을 받을까요?\n(Bits · 도감 · 가방은 유지돼요)"):
                g.reincarnate()
        elif g.pet():
            self.hearts.append([e.x, e.y - 10, 1.0])

    # --- 메인 루프 ---
    def loop(self):
        try:
            now = time.time()
            dt = now - self.last_t
            self.last_t = now
            if dt > 10:  # 절전 등으로 오래 멈췄다면 오프라인 처리
                self.g.catchup_report(dt)
            else:
                self.g.tick(dt * FAST)
            self.walk(dt)
            self.poll_window(now)
            self.refresh_tray()
            self.notify()
            self.render()
            if now - self.last_save > 30:
                self.last_save = now
                self.g.save()
        except Exception:
            log_exception(*sys.exc_info())  # 한 번 실패해도 게임은 계속 돌아가게
        finally:
            self.root.after(200, self.loop)

    def move_loop(self):
        try:
            while self._cmds:
                self.tray_command(self._cmds.popleft())
            now = time.time()
            self.roam_step(min(now - self._last_rt, 0.5))
            self._last_rt = now
        except Exception:
            log_exception(*sys.exc_info())
        finally:
            self.root.after(50, self.move_loop)

    def roam_step(self, dt):
        """미니 모드 + 돌아다니기: 창 자체를 작업표시줄 위를 따라 좌우로 이동."""
        c, s = self.g.cfg, self.g.s
        if not (c["mini"] and c["roam"]) or self.hidden or self._drag:
            self.rx = None
            return
        ab = self.g.active_battle
        busy = s["dead"] or s["stage"] == 0 or s["sleeping"] or (ab and not ab["settled"])
        l, t, r, b = self.work_area()
        cur_x, cur_y = self.root.winfo_x(), self.root.winfo_y()
        if self.rx is None or abs(self.rx - cur_x) > 2:  # 사용자가 옮겼다면 그 자리에서 이어서
            self.rx = float(cur_x)
        lo, hi = l - (MINI_W / 2 - 60), r - (MINI_W / 2 + 60)  # 펫(반폭≈60)이 화면 끝까지 가도록
        ground = b - MINI_H
        ry = c["roam_y"] if c["roam_y"] is not None else ground
        ry = min(max(ry, t), ground)
        self.rx = min(max(self.rx, lo), hi)
        if not busy:
            if self.rwait > 0:
                self.rwait -= dt
            else:
                self.rx += self.rdir * ROAM_SPEED * dt
                self.rwalk -= dt
                if self.rx <= lo:
                    self.rx, self.rdir = lo, 1
                elif self.rx >= hi:
                    self.rx, self.rdir = hi, -1
                if self.rwalk <= 0:  # 잠깐 멈춰 서고, 가끔 방향을 바꿈
                    self.rwait = random.uniform(3, 10)
                    self.rwalk = random.uniform(5, 14)
                    if random.random() < 0.5:
                        self.rdir = -self.rdir
            self.face = self.rdir
        x, y = int(self.rx), int(ry)
        if (x, y) != (cur_x, cur_y):
            self.root.geometry(f"+{x}+{y}")

    def walk(self, dt):
        s, c = self.g.s, self.g.cfg
        if s["dead"] or s["sleeping"] or s["stage"] == 0:
            return
        if c["mini"] and c["roam"]:  # 로밍 중에는 펫을 창 가운데에 두고 창을 움직임
            self.px = self.target = MINI_W / 2
            return
        lo, hi = (70, MINI_W - 70) if c["mini"] else (80, 240)
        self.wait -= dt
        if abs(self.px - self.target) < 3:
            if self.wait <= 0:
                self.target = random.uniform(lo, hi)
                self.wait = random.uniform(2, 8)
        else:
            self.face = 1 if self.target > self.px else -1
            self.px += self.face * 26 * dt

    def notify(self):
        needs = self.g.needs()
        cur = {k for k, _ in needs}
        new = cur - self.last_needs
        self.last_needs = cur
        if not new:
            return
        if self.g.cfg["sound"] and winsound:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except RuntimeError:
                pass
        if self.tray and (self.hidden or self.g.cfg["layer"] == "bottom"):  # 창이 안 보일 땐 풍선 알림
            self.tray.balloon(self.g.name(), " · ".join(t for k, t in needs if k in new))

    # --- 렌더링 ---
    def render(self):
        g, s = self.g, self.g.s
        night = not (6 <= time.localtime().tm_hour < 20)
        if g.cfg["mini"]:
            self.draw_scene(self.mini, MINI_W, MINI_H, MINI_FLOOR, 7, mini=True, night=night)
        else:
            self.draw_scene(self.screen, 320, 230, 196, 8, mini=False, night=night)
            age = int(s["total_time"] // 60)
            self.info.config(
                text=f"{g.name()} · {g.stage_label()} · {age // 60}시간 {age % 60}분 · "
                     f"{g.s['gen']}세대 · Bits {int(s['bits'])} · 볼 {sum(s['items'].get(k, 0) for k in BALLS)}")
            self.btns["재우기"].config(text="깨우기" if s["sleeping"] else "재우기")

    def draw_actor(self, c, x, floor, scale, slug, tier, color, foe=False, blink=False, bob=0, face=None):
        """펫/적 한 마리를 (x, floor) 발바닥 기준으로 그림. 위쪽 y(머리 꼭대기)를 반환.
        foe에는 적 slug를 넘김(이미지가 없으면 회색 도트)."""
        img = self.custom_image(slug, tier, scale, face)
        if img:
            c.create_image(x, floor + 4 + bob // 2, image=img, anchor="s")
            return floor - img.height()
        x0 = x - 8 * scale
        y0 = floor - 15 * scale + bob
        for rx, ry, w, col in sprite_runs(BUILTIN_TIER[tier], max(color, 0), blink, foe):
            c.create_rectangle(x0 + rx * scale, y0 + ry * scale,
                               x0 + (rx + w) * scale, y0 + (ry + 1) * scale, fill=col, outline="")
        return y0

    def battle_view(self):
        """진행 중인 전투의 현재 연출 상태. 끝났으면 None."""
        g = self.g
        ab = g.active_battle
        if not ab:
            return None
        e = g.ab_elapsed(ab)
        if ab["settled"] or e >= ab["dur"]:
            g.settle_battle()
            g.active_battle = None
            return None
        bs = g.battle_state(ab, e)
        over = ab["captured"] or e >= BATTLE_IN + len(ab["events"])
        return dict(ab=ab, e=e, entering=e < BATTLE_IN, over=over, **bs)

    def draw_ball(self, c, x, y, r, kind, tilt=0.0):
        top = "#e0483c" if kind == "ball" else "#3b82e0"
        c.create_arc(x - r, y - r, x + r, y + r, start=0, extent=180, fill=top, outline="#222", width=2)
        c.create_arc(x - r, y - r, x + r, y + r, start=180, extent=180, fill="#f4f4f4", outline="#222", width=2)
        c.create_line(x - r, y, x + r, y, fill="#222", width=2)
        c.create_oval(x - r / 3 + tilt, y - r / 3, x + r / 3 + tilt, y + r / 3, fill="#fff", outline="#222", width=2)

    def draw_battle_ui(self, c, W, mini, bv, scale, night):
        ab = bv["ab"]
        y = 46 if not mini else 10
        fg = "#eee" if night else "#222"
        for x, name, hp, col in ((10, self.g.name(), bv["pet_hp"], "#43b36b"),
                                 (W - 100, ab["foe"], bv["foe_hp"], "#e0483c")):
            c.create_text(x, y, text=name, anchor="w", font=(FONT, 8, "bold"), fill=fg)
            c.create_rectangle(x, y + 8, x + 90, y + 16, fill="#444", outline="#111")
            c.create_rectangle(x, y + 8, x + 90 * hp / 100, y + 16, fill=col, outline="")
        if ab["pause"]:
            msg = "볼이 흔들린다…"
        elif ab["captured"]:
            msg = f"{ab['foe']} 포획 성공!"
        elif time.time() - ab["fail_t"] < 1.3:
            msg = "앗! 빠져나왔다!"
        elif bv["entering"]:
            msg = f"야생의 {ab['foe']}이(가) 나타났다!"
        elif bv["over"]:
            msg = f"승리! +{ab['reward']} Bits" if ab["win"] else "패배…"
        else:
            msg = "⚔ 전투 중!"
        self.draw_bubble(c, W // 2, y + 36, msg)

    def draw_scene(self, c, W, H, floor, scale, mini, night):
        g, s = self.g, self.g.s
        c.delete("all")
        if not mini:
            sky, ground = ("#25304d", "#2f4a3a") if night else ("#dff0ff", "#b9d99a")
            c.create_rectangle(0, 0, W, H, fill=sky, outline="")
            c.create_rectangle(0, floor, W, H, fill=ground, outline="")
            if self.page == "stats":
                return self.draw_stats(c, night)
            if self.page == "dex":
                return self.draw_dex(c, night)
            self.draw_bars(c, night)

        t = time.time()
        bv = None if s["dead"] else self.battle_view()
        top = floor - 15 * scale
        if s["dead"]:
            self.draw_grave(c, self.px, floor)
        elif bv:
            pet_x, foe_x = (W * 0.25, W * 0.76)
            ab = bv["ab"]
            fx = foe_x + (1 - bv["e"] / BATTLE_IN) * 220 if bv["entering"] else foe_x
            px = pet_x + bv["lunge"]["pet"] * 40 + bv["shake"]["pet"]
            fx += -bv["lunge"]["foe"] * 40 + bv["shake"]["foe"]
            pa = ab["pause"]
            foe_alive = not (ab["win"] and bv["over"] and int(t * 8) % 2)
            if foe_alive and not (ab["win"] and bv["e"] > BATTLE_IN + len(ab["events"]) + 1.2) \
                    and not pa and not ab["captured"]:
                self.draw_actor(c, fx, floor, scale, ab["slug"], ab["stage"], ab["line"], foe=True,
                                blink=bv["shake"]["foe"] != 0, face=-1)
            self.draw_actor(c, px, floor, scale, s["slug"], s["stage"], s["line"], blink=bv["shake"]["pet"] != 0,
                            face=1)
            if pa:  # 볼 던지기: 날아가서 상대를 빨아들이고 3번 흔들림
                tp = t - pa["t0"]
                r = 11 if scale >= 8 else 9
                if tp < 0.5:
                    u = tp / 0.5
                    self.draw_ball(c, px + (fx - px) * u, floor - 40 - math.sin(math.pi * u) * 50, r, pa["kind"], u * 6)
                else:
                    wob = math.sin((tp - 0.5) * 9) * 5 if tp < CATCH_T - 0.4 else 0
                    self.draw_ball(c, fx + wob, floor - r + 2, r, pa["kind"], wob)
                    if tp >= CATCH_T - 0.4 and pa["ok"]:
                        c.create_text(fx, floor - 40, text="★", fill="#ffd23c", font=(FONT, 20, "bold"))
            elif ab["captured"]:
                self.draw_ball(c, fx, floor - 11, 11, ab.get("pause_kind", "ball"))
            if bv["pop"] and not pa:
                who, dmg, f = bv["pop"]
                x = fx if who == "foe" else px
                c.create_text(x, top - 20 - f * 25, text=f"-{dmg}", fill="#ff3b3b",
                              font=(FONT, 14, "bold"))
            self.draw_battle_ui(c, W, mini, bv, scale, night)
            top = None
        else:
            blink = s["sleeping"] or int(t * 2) % 9 == 0
            bob = scale if (int(t * 2.5) % 2 and not s["sleeping"]) else 0
            wig = int(t * 6) % 2 * 3 - 1 if s["stage"] == 0 else 0
            y0 = self.draw_actor(c, self.px + wig, floor, scale, s["slug"], s["stage"], s["line"], blink=blink,
                                 bob=bob, face=self.face)
            top = y0
            if s["sick"]:
                c.create_text(self.px + 50, y0 + 20, text="+", fill="#4caf50", font=(FONT, 20, "bold"))

        text = None if bv else self.bubble_text()
        if text:
            self.draw_bubble(c, self.px, (top if top is not None else floor - 15 * scale) - 10, text)

        for h in self.hearts[:]:
            h[1] -= 1.5
            h[2] -= 0.04
            if h[2] <= 0:
                self.hearts.remove(h)
            else:
                c.create_text(h[0], h[1], text=f"♥+{PET_GAIN}", fill="#ff5c8a", font=(FONT, 11, "bold"))

        if not mini and not bv:
            if g.log and time.time() - g.log[-1][0] < 15:
                c.create_text(W // 2, H - 14, text=g.log[-1][1], font=(FONT, 9, "bold"),
                              fill="#fff" if night else "#2d3b1f")
            if s["dead"]:
                c.create_text(W // 2, 40, text="클릭하면 새 알을 받아요", font=(FONT, 10), fill="#c33")

    STAGE_H = [56, 72, 90, 112]  # 단계(tier)별 화면상 목표 높이(scale 8 기준)

    def custom_image(self, slug, tier, scale, face=None):
        """sprites/mons/{slug}.png 를 단계별 목표 높이에 맞춰 정수배 확대. 없으면 None(내장 도트)."""
        native = 1 if slug in FACING_RIGHT else -1
        flip = face is not None and face != native  # 가는 방향을 바라보도록 좌우 반전
        return self.cached_image(f"mons/{slug}", self.STAGE_H[tier] * scale // 8, scale, flip)

    def cached_image(self, name, target_h, scale, flip=False):
        key = (name, target_h, scale, flip)
        if key not in self.img_cache:
            self.img_cache[key] = self.load_image(name, target_h, 16 * scale, flip)
        return self.img_cache[key]

    def load_image(self, name, target_h, max_w, flip=False):
        for ext in (".png", ".gif"):
            path = os.path.join(HERE, "sprites", name + ext)
            if not os.path.exists(path):
                continue
            try:
                img = tk.PhotoImage(file=path)
            except tk.TclError:
                return None
            h, w = max(img.height(), 1), max(img.width(), 1)
            z = max(1, min(round(target_h / h), max_w // w))  # 높이 목표, 단 폭은 칸을 넘지 않게
            if z > 1:
                img = img.zoom(z)
            elif h > target_h * 1.5:
                img = img.subsample(max(1, round(h / target_h)))
            return img.subsample(-1, 1) if flip else img
        return None

    def bubble_text(self):
        s = self.g.s
        if s["dead"]:
            return None
        if s["sleeping"]:
            return "zZz…"
        recent = self.g.log[-1] if self.g.log else None
        if self.g.cfg["mini"] and recent and time.time() - recent[0] < 6:
            return recent[1]
        needs = self.g.needs()
        return needs[0][1] if needs else None

    def draw_bubble(self, c, x, y, text):
        f = (FONT, 9, "bold")
        tid = c.create_text(x, y, text=text, font=f, fill="#222", width=190, justify="center")  # 긴 글은 줄바꿈
        bx = c.bbox(tid)
        c.create_rectangle(bx[0] - 6, bx[1] - 3, bx[2] + 6, bx[3] + 3, fill="#fff", outline="#555")
        c.tag_raise(tid)

    def draw_bars(self, c, night):
        s = self.g.s
        items = [("배고픔", s["hunger"]), ("친밀도", s["happy"]), ("기력", s["energy"]), ("체력", s["hp"])]
        fg = "#eee" if night else "#333"
        for i, (label, v) in enumerate(items):
            x = 8 + i * 78
            c.create_text(x, 11, text=label, anchor="w", font=(FONT, 8), fill=fg)
            c.create_rectangle(x, 22, x + 70, 30, fill="#8896a8" if not night else "#444", outline="")
            col = "#e0483c" if v < 25 else "#43b36b"
            c.create_rectangle(x, 22, x + 70 * v / 100, 30, fill=col, outline="")

    def draw_grave(self, c, x, floor):
        c.create_rectangle(x - 30, floor - 70, x + 30, floor, fill="#8d949e", outline="#4a4f57", width=3)
        c.create_oval(x - 30, floor - 90, x + 30, floor - 50, fill="#8d949e", outline="#4a4f57", width=3)
        c.create_rectangle(x - 27, floor - 62, x + 27, floor - 3, fill="#8d949e", outline="")
        c.create_text(x, floor - 45, text="RIP", font=(FONT, 14, "bold"), fill="#3a3f47")

    def draw_dex(self, c, night):
        """포획 도감: 잡은 포켓몬은 그림+이름+횟수, 못 잡은 포켓몬은 ? 로 표시."""
        dex = self.g.s["dex"]
        species = list(dict.fromkeys(sl for t in sorted(FOE_POOL) for sl in FOE_POOL[t]))
        fg = "#eee" if night else "#2d3b1f"
        total = sum(dex.values())
        c.create_text(12, 12, text=f"포켓몬 도감  {sum(1 for sl in species if sl in dex)}/{len(species)}종",
                      anchor="w", font=(FONT, 10, "bold"), fill=fg)
        c.create_text(308, 12, text=f"총 포획 {total}마리", anchor="e", font=(FONT, 8), fill=fg)
        cw, ch, cols = 64, 66, 5
        for i, sl in enumerate(species):
            x0, y0 = 4 + (i % cols) * cw, 26 + (i // cols) * ch
            got = sl in dex
            c.create_rectangle(x0 + 2, y0, x0 + cw - 2, y0 + ch - 4, fill="#ffffff" if got else "#c9d3dd",
                               outline="#8896a8" if not night else "#556", stipple="" if got else "gray50")
            cx = x0 + cw / 2
            img = self.cached_image(f"mons/{sl}", 36, 4) if got else None
            if img:
                c.create_image(cx, y0 + 40, image=img, anchor="s")
            else:
                c.create_text(cx, y0 + 24, text="?" if not got else "●", font=(FONT, 18, "bold"), fill="#8896a8")
            c.create_text(cx, y0 + 46, text=KO[sl] if got else "???", font=(FONT, 8, "bold"), fill="#222" if got else "#667")
            if got:
                c.create_text(cx, y0 + 57, text=f"×{dex[sl]}", font=(FONT, 8), fill="#c0392b")

    def draw_stats(self, c, night):
        g, s = self.g, self.g.s
        t = s["train"]
        lines = [
            f"{g.name()}  ({g.stage_label()})  {s['gen']}세대",
            f"배고픔 {int(s['hunger'])}   친밀도 {int(s['happy'])}   기력 {int(s['energy'])}   체력 {int(s['hp'])}",
            f"몸무게 {s['weight']:.0f}g   케어미스 {s['care_miss']}",
            f"힘 {t['power']:.0f}  속도 {t['speed']:.0f}  지능 {t['mind']:.0f}   전투력 {g.power():.0f}",
            f"전적 {s['wins']}승 {s['losses']}패   Bits {int(s['bits'])}",
            f"다음 진화: {g.next_evo()}",
            "가방: " + (" · ".join(f"{SHOP[k][0]} {n}" for k, n in s["items"].items() if n > 0 and k in SHOP) or "비어 있음"),
            f"도감 {len(s['dex'])}종 (전투력 +{len(s['dex']) * 0.4:.1f})",
            "포획: " + (", ".join(KO[k] + (f"×{v}" if v > 1 else "") for k, v in list(s["dex"].items())[-6:]) or "아직 없음"),
        ]
        fg = "#eee" if night else "#2d3b1f"
        for i, ln in enumerate(lines):
            c.create_text(14, 18 + i * 25, text=ln, anchor="w", font=(FONT, 9, "bold" if i == 0 else "normal"), fill=fg)

    def quit(self):
        c = self.g.cfg
        c["x"], c["y"] = self.root.winfo_x(), self.root.winfo_y()
        self.g.settle_now()
        self.g.save()
        if self.tray:
            self.tray.remove()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    sys.excepthook = log_exception
    if winutil and not winutil.acquire_single_instance():
        return  # 이미 실행 중: 기존 창을 앞으로 불러오고 종료
    App().run()


if __name__ == "__main__":
    main()
