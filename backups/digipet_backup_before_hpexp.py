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
STAGE_TIME = [60, 5 * 3600, 24 * 3600, None]  # 다음 단계까지(초): 알 1분 / 기본→1진화 5시간 / 1진화→2진화 24시간
HUNGER_EMPTY = [None, 3600, 5400, 7200]  # 배부름 100→0 걸리는 초
BASE_POWER = [0, 6, 16, 32]
EXP_NEED = {2: 60, 3: 200}  # 해당 단계로 진화하는 데 필요한 경험치(시간 조건과 함께 충족해야 함)

# 종·타입·상성·진화 계통·희귀도는 species.py (1세대 151종 + 기존 계통에 쓰던 추가 종)
try:  # 배경 이미지 리사이즈용 (없으면 미리 줄여 둔 사본(sprites/backgrounds)을 씀)
    from PIL import Image, ImageTk
except Exception:  # noqa: BLE001
    Image = ImageTk = None
from species import (KO, TYPES, TYPE_KO, TYPE_COLOR, SKILL_KO, CHAINS, BRANCH_OPTIONS, FOE_POOL, FOE_WEIGHT,  # noqa: E402
                     FOE_POWER, CATCH_BASE, DEX_ORDER, RARITY_KO, RARITY_STARS, RARITY_PCT, SHINY_CHANCE, LEGENDARY,
                     SPECIES, type_mult, best_type, all_slugs)
# ── 타입별 배경: BG_DIR 의 `*배경.png` (예: 숲배경.png, 불%배경.png)를 읽어 주 타입에 맞게 고름 ──
BG_DIR = r"C:\Users\user\Documents\PoketMonPixcel\myself_made"
# 타입 → 가까운 배경 이름(앞쪽이 우선). 파일명이 타입 이름이면(불%배경 등) 그게 가장 우선, 아무것도 없으면 있는 배경 중 하나
BG_PREF = {
    "water": ["해변", "고산", "들판"], "ice": ["해변", "고산", "들판"],
    "grass": ["숲", "들판"], "bug": ["숲", "들판"], "poison": ["숲", "들판"], "ghost": ["숲", "고산"], "dark": ["숲", "고산"],
    "normal": ["들판", "숲"], "electric": ["들판", "고산"], "fighting": ["들판", "고산"], "psychic": ["들판", "숲"],
    "fairy": ["들판", "숲"], "ground": ["들판", "고산"],
    "rock": ["고산", "들판"], "steel": ["고산", "들판"], "fire": ["고산", "들판"], "flying": ["고산", "들판"],
    "dragon": ["고산", "들판"],
}
BG_W, BG_H = 320, 230
EVOLVE_DELAY = 15  # 프로그램을 켠 뒤 이 시간(초)이 지나야 부화/진화 (꺼 둔 동안 조건을 채워도 켠 뒤 15초 후에 진행)
TICKET_PRICE = 1500
DEX_POWER = 0.15   # 도감 1종당 전투력
LOW_BOND = 15      # 친밀도가 이 값 미만이면 전투 불이익(전투력·경험치 -25%). 새 알의 시작 친밀도도 15
# 강적: 일정 확률로 등장하는 매우 강한 상대. 강화(전투력)를 올려야 이길 수 있고, 자동 전투는 승산이 낮으면 도망침
ELITE_CHANCE = {1: 0.14, 2: 0.2, 3: 0.25}   # 단계별 강적 등장 확률(전설 포켓몬은 항상 강적)
ELITE_MULT = {1: (1.9, 2.5), 2: (2.0, 2.7), 3: (2.2, 3.0)}  # 강적의 강도 배율
ELITE_FLEE_BELOW = 0.8  # 자동 전투에서 (내 전투력 / 상대 전투력)이 이 값 미만이면 도망
# 돌: 전투 승리/포획 시 일정 확률로 줍는 아이템 (상점에는 없음)
STONES = {
    "fire_stone": ("불의 돌", "이브이를 부스터로 진화시킴 (불꽃 타입 적이 떨어뜨림)"),
    "water_stone": ("물의 돌", "이브이를 샤미드로 진화시킴 (물 타입 적이 떨어뜨림)"),
    "thunder_stone": ("번개의 돌", "이브이를 쥬피썬더로 진화시킴 (전기 타입 적이 떨어뜨림)"),
    "everstone": ("변함없는 돌", "진화를 막음. 알로 돌아가기 전까지 유지, 상태 화면에서 해제"),
}
STONE_CAP = {"fire_stone": 3, "water_stone": 3, "thunder_stone": 3, "everstone": 2}  # 종류별 최대 보유 수
TYPE_STONE = {"fire": "fire_stone", "water": "water_stone", "electric": "thunder_stone"}
STONE_ONLY = {"raichu": "thunder_stone"}   # 이 형태로는 해당 돌을 써야만 진화 (피카츄 → 라이츄)
STONE_FORM = {"fire_stone": "flareon", "water_stone": "vaporeon", "thunder_stone": "jolteon"}
STONE_DROP, STONE_DROP_ELITE = 0.12, 0.35   # 타입이 맞는 적에게서 진화의 돌
EVER_DROP, EVER_DROP_ELITE = 0.05, 0.20     # 변함없는 돌(모든 적)


def item_label(k):
    return SHOP[k][0] if k in SHOP else STONES[k][0]
SKILL_PP = 5       # 전투 한 판당 스킬 사용 횟수
# 볼 종류 {키: (이름, 가격, 포획률 배율)}
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
    "energy1": ("활력의 가루", 25, "기력 +40"),
    "energy2": ("원기의 덩어리", 60, "기력 +100 (완전 회복)"),
    "ticket": ("계통 선택권", TICKET_PRICE, "알의 계통 선택 (전설 제외)"),
}
CATCH_T = 2.4      # 볼 던지기 연출(초)
CAUGHT_OUT = 1.8   # 포획 성공 후 마무리(초)
ANIM = 0.9         # 공격 한 번의 연출(초)
AUTO_DELAY = 0.7   # 자동 진행 시 내 차례를 기다리는 시간(초)
MANUAL_TIMEOUT = 12  # 직접 조작 중 이 시간(초) 입력이 없으면 자동 진행으로 복귀
AUTO_FEED_COST = 5
# 영구 강화 {키: (이름, 레벨당 효과 설명, 최대 레벨, 기본 가격, 가격 증가율)} - 환생해도 유지
UPGRADES = {
    "power": ("근력 단련", "전투력 +1.5 / Lv", 20, 80, 1.35),
    "exp": ("수련장", "전투 경험치 +8% / Lv", 15, 120, 1.4),
    "catch": ("포획 연구", "포획률 +6% / Lv", 10, 100, 1.4),
    "tempo": ("전투 훈련소", "자동 배틀 간격 -72초 / Lv", 10, 150, 1.5),
    "income": ("탐험 장비", "자동 Bits 수익 +8% / Lv", 15, 100, 1.4),
    "rest": ("포근한 침대", "수면 회복 속도 +15% / Lv", 5, 90, 1.5),
    "luck": ("행운의 부적", "알 부화: 희귀 등급 +15% / 이로치 +10% / Lv", 10, 200, 1.5),
}


def bg_name_of(path):
    base = os.path.basename(path)[:-4].replace("%", "")
    return base[:-2] if base.endswith("배경") else base


def scan_backgrounds():
    """{이름: [후보 파일들]}. 원본 폴더(PIL 필요)가 우선, 그다음 exe/폴더에 넣어 둔 사본."""
    import glob
    found = {}
    for folder, pil in ((BG_DIR, True), (os.path.join(HERE, "sprites", "backgrounds"), False)):
        for f in sorted(glob.glob(os.path.join(folder, "*배경.png"))):
            if pil and Image is None:
                continue
            found.setdefault(bg_name_of(f), []).append((f, pil))
    return found


def bg_for_type(typ, names):
    """주 타입에 가장 가까운 배경 이름. 배경이 하나라도 있으면 반드시 하나를 돌려줌."""
    ko = TYPE_KO.get(typ, "")
    for n in names:  # 파일명이 타입 이름이면 최우선 (불 → 불꽃)
        if n and ko.startswith(n):
            return n
    for n in BG_PREF.get(typ, ()):
        if n in names:
            return n
    return sorted(names)[0]


def loss_penalty(res, stage):
    """패배/도망 페널티 (경험치, 성장 시간(초 = 걸음), 친밀도). 도망은 패배의 절반."""
    if res == "fled":
        return 3 + 2 * stage, 450, FLEE_BOND_LOSS
    return 6 + 4 * stage, 900, LOSE_BOND_LOSS


def selectable_chain(i):
    """계통 선택권으로 고를 수 없는 계통: 전설/환상의 포켓몬."""
    ch = CHAINS[i]
    return ch["rar"] != "L" and not any(f in LEGENDARY for f in ch["forms"])


def s_happy_low(s):
    return s["happy"] < LOW_BOND


def upgrade_cost(key, lv):
    base, grow = UPGRADES[key][3], UPGRADES[key][4]
    return int(round(base * grow ** lv))


def upgrade_effect(key, lv):
    return {"power": f"+{1.5 * lv:.1f}", "exp": f"+{8 * lv}%", "catch": f"+{6 * lv}%",
            "tempo": f"{max(480, 1200 - 72 * lv) // 60}분 간격", "income": f"+{8 * lv}%", "rest": f"+{15 * lv}%",
            "luck": f"희귀 +{15 * lv}% · 이로치 +{10 * lv}%"}[key]


BOND_DRAIN_PER_MIN = 0.7        # 친밀도 감소 (켜 둔 동안, 전체/미니 모드 공통): 분당 0.7
BOND_DRAIN_SEC = 100 * 60 / BOND_DRAIN_PER_MIN   # 100→0 걸리는 시간(초) ≈ 2시간 23분
# 켜 둔 동안 감소 배율: (배고픔 20 미만, 병) → 배고픔만 2배 / 병만 4배 / 둘 다 6배
BOND_DRAIN_MULT = {(False, False): 1, (True, False): 2, (False, True): 4, (True, True): 6}
TRAIN_BOND_LOSS = 4             # 훈련 1회
LOSE_BOND_LOSS, FLEE_BOND_LOSS = 16, 3   # 전투 패배 / 도망
ENERGY_ITEM_BOND_LOSS = 3       # 기력 회복 아이템을 쓸 때
OFFLINE_BOND_SEC = 72 * 3600    # 친밀도 100→0 (프로그램을 꺼 둔 동안 72시간)
SNACK_BOND, BENTO_BOND = 8, 4       # 간식 / 도시락으로 오르는 친밀도
WIN_BOND, CAPTURE_BOND = 2, 0       # 전투 승리 / 포획으로 오르는 친밀도
PET_GAIN = 1             # 펫을 한 번 클릭할 때 친밀도 증가량
AUTO_MEDICINE_COST = 15
CATCH_AT = 15      # 도감에 없는 상대의 체력(%)이 이 값 이하가 되면 몬스터볼을 1회 던짐
CATCH_KEEP = 8     # 볼을 던지기 전까지 자동 공격이 상대 체력을 이 값(%) 아래로 깎지 않음
AUTO_BALL_STOCK = 5      # 자동 보충: 몬스터볼 목표 개수
AUTO_BALL_RESERVE = 100  # 이 Bits 이상 있을 때만 보충
AUTO_POTION_STOCK = 2    # 자동 돌봄: 상처약 목표 개수(Bits 200 이상일 때 보충)
AUTO_ENERGY_STOCK = 2    # 자동 돌봄: 활력의 가루 목표 개수(Bits 200 이상일 때 보충)
AUTO_ENERGY_BELOW = 25   # 기력이 이 값 미만이면 기력 아이템 자동 사용
AUTO_POTION_BELOW = 35   # 체력이 이 값 미만이면 상처약 자동 사용
BUILTIN_TIER = {0: 0, 1: 2, 2: 4, 3: 6}  # 이미지가 없을 때 쓰는 내장 도트(SPRITES 키)


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
def new_state(gen=1, bits=0.0, dex=None, items=None, upg=None, new_dex=None):
    return dict(
        last=time.time(), gen=gen, stage=0, line=-1, chain=-1, slug="egg", stage_time=0.0, total_time=0.0,
        hunger=80.0, happy=15.0, energy=100.0, hp=100.0, weight=5.0,
        sick=False, sick_t=0.0, sick_flag=False, starve_t=0.0, starve_flag=False,
        sleeping=False, dead=False, care_miss=0,
        train=dict(power=0.0, speed=0.0, mind=0.0),
        wins=0, losses=0, exp=0.0, shiny=False, rarity="C", raised={}, egg_decided=False, evo_declined="", stone=None, everstone=False, bits=float(bits), dex=dict(dex or {}), items=dict(items or {"ball": 3, "great": 0}), upg=dict(upg or {}), new_dex=list(new_dex or []), explore_t=0.0, battle_t=0.0,
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
    for k in ("stage_time", "total_time", "sick_t", "starve_t", "explore_t", "bits", "weight", "exp"):
        num(k, 0)
    num("battle_t")
    for k in ("care_miss", "wins", "losses", "gen"):
        num(k, 0, integer=True)
    s["gen"] = max(1, s["gen"])
    s["shiny"] = bool(s.get("shiny", False))
    rs = s.get("raised") if isinstance(s.get("raised"), dict) else {}
    s["raised"] = {k: 1 for k in rs if k in KO and k != "egg"}
    num("stage", 0, 3, integer=True)
    for k in ("sick", "sleeping", "dead", "sick_flag", "starve_flag"):
        s[k] = bool(s.get(k, False))
    tr = s.get("train") if isinstance(s.get("train"), dict) else {}
    s["train"] = {k: float(tr[k]) if isinstance(tr.get(k), (int, float)) and not isinstance(tr.get(k), bool) else 0.0
                  for k in TRAIN_KEYS}
    it = s.get("items") if isinstance(s.get("items"), dict) else dict(d["items"])
    s["items"] = {k: int(v) for k, v in it.items()
                  if (k in SHOP or k in STONES) and isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0}
    for k, cap in STONE_CAP.items():
        if k in s["items"]:
            s["items"][k] = min(cap, s["items"][k])
    s["egg_decided"] = bool(s.get("egg_decided", False))
    if s.get("evo_declined") not in ("", "day", "night"):
        s["evo_declined"] = ""
    s["everstone"] = bool(s.get("everstone", False))
    if s.get("stone") not in (None, "fire_stone", "water_stone", "thunder_stone"):
        s["stone"] = None
    up = s.get("upg") if isinstance(s.get("upg"), dict) else {}
    s["upg"] = {k: min(UPGRADES[k][2], max(0, int(v))) for k, v in up.items()
                if k in UPGRADES and isinstance(v, (int, float)) and not isinstance(v, bool)}
    dx = s.get("dex") if isinstance(s.get("dex"), dict) else {}
    s["dex"] = {k: int(v) for k, v in dx.items() if k in KO and k != "egg" and isinstance(v, (int, float)) and v >= 1}
    nd = s.get("new_dex") if isinstance(s.get("new_dex"), list) else []
    s["new_dex"] = [k for k in dict.fromkeys(nd) if isinstance(k, str) and k in s["dex"]]  # 아직 확인 안 한 새 포켓몬
    for k in s["raised"]:  # 키워 본 포켓몬은 도감에도 등록
        s["dex"].setdefault(k, 1)
    if s["stage"] == 0:  # 알: 계통은 부화할 때 정해짐
        s["slug"], s["line"], s["chain"] = "egg", -1, -1
        s["shiny"], s["rarity"] = False, "C"
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
    if s.get("rarity") not in RARITY_KO:
        s["rarity"] = CHAINS[ch]["rar"]
    return fixed


DEFAULT_CFG = dict(battle_window=True, auto_battle_window=False, roam=True, roam_y=None, layer="top", alpha=1.0, click_through=False, sound=True, auto_battle=True, auto_feed=True, auto_catch=True, mini=False, x=None, y=None)
MINI_W, MINI_H, MINI_FLOOR = 320, 230, 224  # 미니(로밍) 창 크기(전체 모드 화면과 같은 320x230)와 발바닥 높이(창 맨 아래 근처)
ROAM_SPEED = 40       # 바탕화면 로밍 속도(px/초)
FACING_RIGHT = set()  # 원본 스프라이트가 오른쪽을 보는 종 (기본은 왼쪽을 본다고 가정)
AUTO_BATTLE_EVERY = 1200  # 자동 배틀 간격(초)
BATTLE_HP_FLOOR = 15.0  # 전투로 떨어질 수 있는 최저 체력
BATTLE_IN = 1.2   # 상대 등장 연출(초)
BATTLE_OUT = 2.0  # 결과 표시(초)


class Game:
    def __init__(self):
        self.s = new_state()
        self.active_battle = None  # 연출 중인 전투(저장 안 함)
        self.quiet = False         # True면 메시지를 쌓지 않음(오프라인 따라잡기 중)
        self.clock = time.time     # 전투 시계(테스트에서 가짜 시계로 교체 가능)
        self.cfg = dict(DEFAULT_CFG)
        self.log = []  # (시각, 메시지)
        self.evo_pending = None    # (진화할 형태, "day"/"night"): 이브이 진화 여부를 사용자에게 물어봐야 함
        self.evo_ok = None         # 사용자가 진화를 승인한 시간대
        self.up_t = 0.0            # 프로그램이 켜져 있던 시간(초). EVOLVE_DELAY 가 지나야 부화/진화
        self.fx = []               # 아이템 사용 연출 대기열 [(아이템, 시각)]
        self.fx_on = True
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
        for k in ("battle_window", "auto_battle_window", "roam", "click_through", "sound", "auto_battle", "auto_feed", "auto_catch", "mini"):
            self.cfg[k] = bool(self.cfg[k])
        self.cfg.update(roam=True, auto_battle=True, auto_feed=True, auto_catch=True, battle_window=True,
                        auto_battle_window=False)  # 설정 메뉴에서 숨긴 항목: 항상 기본값
        if "layer" not in cfg and "topmost" in cfg:
            self.cfg["layer"] = "top" if cfg["topmost"] else "normal"
        if self.cfg["layer"] not in ("top", "normal", "bottom"):
            self.cfg["layer"] = "top"
        a = self.cfg["alpha"]
        self.cfg["alpha"] = min(max(float(a), 0.2), 1.0) if isinstance(a, (int, float)) and not isinstance(a, bool) else 1.0
        if "chain" not in data["s"]:  # 진화 계통 구조가 바뀌기 전 저장 → 새 알로 시작
            self.s = new_state(data["s"].get("gen", 1), data["s"].get("bits", 0.0), data["s"].get("dex"), data["s"].get("items"), data["s"].get("upg"))
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

    def display_name(self):
        return ("✨" if self.s.get("shiny") else "") + KO[self.s["slug"]]

    def stage_label(self):
        s = self.s
        if s["stage"] == 0:
            return "알"
        i = s["stage"] - 1 - (3 - len(CHAINS[s["chain"]]["forms"]))
        return ["기본", "1진화", "2진화"][i]

    def upg(self, key):
        return self.s["upg"].get(key, 0)

    def power(self):
        s = self.s
        p = (BASE_POWER[s["stage"]] + sum(s["train"].values()) * 0.3 + s["happy"] / 25 + s["gen"] * 1.5
             + len(s["dex"]) * DEX_POWER + self.upg("power") * 1.5 + (3 if s.get("shiny") else 0))
        return p * (0.7 if s["sick"] else 1.0) * (0.75 if s["happy"] < LOW_BOND else 1.0)

    def needs(self):
        s = self.s
        if s["dead"]:
            return []
        n = []
        if s["sick"]:
            n.append(("sick", "아파요…"))
        if s["stage"] > 0 and s["hunger"] < 25:
            n.append(("hungry", "배고파!"))
        if s["stage"] > 0 and s["happy"] < LOW_BOND:
            n.append(("bored", "심심해… (전투 불이익)"))
        return n

    def next_evo(self):
        s = self.s
        need = STAGE_TIME[s["stage"]]
        if need is None:
            return "최종 단계"
        left = max(0, need - s["stage_time"])
        nxt = s["stage"] + 1
        parts = [f"{int(left // 3600)}시간 {int(left % 3600 // 60)}분 남음" if left > 0 else "시간 ✔"]
        if nxt in EXP_NEED:
            have = int(s["exp"])
            parts.append(f"EXP {have}/{EXP_NEED[nxt]}" + (" ✔" if have >= EXP_NEED[nxt] else ""))
        if s["everstone"]:
            parts.append("변함없는 돌: 정지")
        elif self.needs_stone():
            parts.append("진화의 돌 필요")
        return " · ".join(parts)

    def needs_stone(self):
        """피카츄(라이츄로), 또는 이브이가 돌 없이 진화할 수 없는 상태(돌봄 실수 3회 이상)면 True."""
        s = self.s
        if s["stage"] == 0 or s["stage"] >= 3 or s["chain"] < 0:
            return False
        if s["slug"] == "pikachu":  # 라이츄는 번개의 돌로만 진화
            return s["stone"] is None
        if "@eevee" not in CHAINS[s["chain"]]["forms"]:
            return False
        return s["stone"] is None and not s["care_miss"] <= 2

    # --- 시간 진행 ---
    def catchup_report(self, dt):
        """자리를 비운 시간을 따라잡고, 그 사이 일어난 일을 한 줄로 요약해 알려 줌."""
        s = self.s
        before = (s["slug"], s["wins"], s["losses"], len(s["dex"]), s["stage"])
        stones0 = sum(s["items"].get(k, 0) for k in STONES)
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
        gained = sum(s["items"].get(k, 0) for k in STONES) - stones0
        if gained > 0:
            parts.append(f"돌 {gained}개 획득")
        extra = f" ({', '.join(parts)})" if parts else ""
        self.say(f"자리를 비운 {int(min(dt, MAX_OFFLINE) // 60)}분 동안 무럭무럭 자랐다.{extra}")
        if s["slug"] != before[0] and not s["dead"]:
            self.say(f"그 사이 {self.name()}(으)로 {'부화' if before[4] == 0 else '진화'}했다!")

    def catchup(self, dt):
        full, dt = dt, min(dt, MAX_OFFLINE)
        s = self.s
        if full > dt and not s["dead"] and s["stage"] > 0:  # 시뮬레이션 상한(8시간)을 넘긴 시간도 친밀도는 72시간 기준으로 반영
            s["happy"] = max(0.0, s["happy"] - 100 * (full - dt) / OFFLINE_BOND_SEC)
        self.fx_on = False  # 자리를 비운 동안 쓴 아이템은 연출하지 않음
        try:
            while dt > 0:
                step = min(30.0, dt)
                self.tick(step, offline=True)
                dt -= step
        finally:
            self.fx_on = True

    def tick(self, dt, offline=False):
        s = self.s
        if s["dead"]:
            return
        k = 0.4 if offline else 1.0
        st = s["stage"]
        self.update_battle(self.clock())
        s["total_time"] += dt
        s["stage_time"] += dt
        if not offline:
            self.up_t += dt
        if self.cfg["auto_catch"] and s["items"].get("ball", 0) < AUTO_BALL_STOCK and s["bits"] >= AUTO_BALL_RESERVE:
            s["bits"] -= BALLS["ball"][1]  # 자동 포획: Bits 여유가 있으면 몬스터볼을 알아서 보충
            s["items"]["ball"] = s["items"].get("ball", 0) + 1
        if self.cfg["auto_feed"] and s["items"].get("potion", 0) < AUTO_POTION_STOCK and s["bits"] >= 2 * AUTO_BALL_RESERVE:
            s["bits"] -= SHOP["potion"][1]  # 자동 돌봄: 상처약도 알아서 보충
            s["items"]["potion"] = s["items"].get("potion", 0) + 1
        if self.cfg["auto_feed"] and s["items"].get("energy1", 0) < AUTO_ENERGY_STOCK and s["bits"] >= 2 * AUTO_BALL_RESERVE:
            s["bits"] -= SHOP["energy1"][1]  # 활력의 가루도 알아서 보충
            s["items"]["energy1"] = s["items"].get("energy1", 0) + 1
        if st == 0:
            if not offline:  # 부화/진화는 프로그램이 켜져 있을 때만 (꺼 둔 동안 조건을 채웠으면 켠 뒤 진행)
                self.check_evolve()
            return

        mult = 0.5 if s["sleeping"] else 1.0
        s["hunger"] = max(0.0, s["hunger"] - 100 * dt / HUNGER_EMPTY[st] * mult * k)
        if self.cfg["auto_feed"] and s["hunger"] < 30 and s["bits"] >= AUTO_FEED_COST:
            s["bits"] -= AUTO_FEED_COST
            s["hunger"] = min(100.0, s["hunger"] + 30)
            s["weight"] += 0.5
            if not offline:
                self.say(f"밥을 먹었다. (-{AUTO_FEED_COST} Bits)")

        if s["sleeping"]:
            s["energy"] = min(100.0, s["energy"] + 100 * dt / 1200 * (1 + 0.15 * self.upg("rest")))
            if s["energy"] >= 100:
                s["sleeping"] = False
                self.say("푹 자고 일어났다!")
        else:
            s["energy"] = max(0.0, s["energy"] - 100 * dt / (4 * 3600) * k)
            if s["energy"] <= 5:
                s["sleeping"] = True
                self.say("졸려서 스르르 잠들었다…")

        if self.cfg["auto_feed"] and not s["sleeping"] and s["energy"] < AUTO_ENERGY_BELOW:
            for kind in ("energy1", "energy2"):  # 자동 돌봄: 기력이 바닥나기 전에 아이템 사용
                if s["items"].get(kind, 0) > 0:
                    self.use_item(kind, auto=True)
                    break

        if offline:  # 꺼 둔 동안: 72시간에 100→0 (배고픔/병 가중 없음)
            drain = 100 * dt / OFFLINE_BOND_SEC
        else:
            drain = 100 * dt / BOND_DRAIN_SEC * BOND_DRAIN_MULT[(s["hunger"] < 20, bool(s["sick"]))]
        s["happy"] = max(0.0, s["happy"] - drain)

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
                    self.say(f"약을 먹고 나았다. (-{AUTO_MEDICINE_COST} Bits)")
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
            s["bits"] += (1 + st) * 0.03 * dt * k * (1 + 0.08 * self.upg("income"))
            s["train"][random.choice(TRAIN_KEYS)] += dt * 0.0005 * k
            if self.cfg["auto_battle"] and st >= 1:
                s["battle_t"] += dt
                # 20분마다(꺼 둔 동안은 40분마다), 컨디션이 충분히 좋을 때만. 패배하면 쉬었다가 다음 전투
                if s["battle_t"] >= max(480, AUTO_BATTLE_EVERY - 72 * self.upg("tempo")) * (2 if offline else 1):
                    if s["hp"] >= 60 and s["hunger"] >= 30 and s["energy"] >= 40:
                        s["battle_t"] = 0
                        self.battle(auto=True, instant=offline)
        if not offline:
            self.check_evolve()

    @staticmethod
    def day_period():
        return "day" if 6 <= time.localtime().tm_hour < 20 else "night"

    def approve_evolve(self):
        """이브이 진화를 승인함 → 바로 진화."""
        if self.evo_pending:
            self.evo_ok = self.evo_pending[1]
            self.evo_pending = None
            self.s["evo_declined"] = ""
            self.check_evolve()

    def decline_evolve(self):
        """이브이로 유지하기로 함. 낮/밤이 바뀐 뒤에도 조건이 유지되면 다시 물어봄."""
        if self.evo_pending:
            self.s["evo_declined"] = self.evo_pending[1]
            self.evo_pending = None
            self.say(f"{self.name()}(으)로 유지하기로 했다. (낮/밤이 바뀌면 다시 물어볼게요)")

    def resolve_form(self, spec):
        """진화 형태 결정. '@...' 는 분기 진화 규칙. None 이면 조건(진화의 돌)이 아직 안 맞아 진화 대기."""
        if not spec.startswith("@"):
            return spec
        s = self.s
        t = s["train"]
        if spec == "@eevee":
            if s.get("stone") in STONE_FORM:  # 진화의 돌: 불 → 부스터 / 물 → 샤미드 / 번개 → 쥬피썬더
                slug = STONE_FORM[s["stone"]]
                s["stone"] = None
                return slug
            if s["care_miss"] <= 2:  # 낮=에스피, 밤=블래키: 자동으로 진화하지 않고 사용자가 진화/유지를 고름
                period = self.day_period()
                if self.evo_ok == period:
                    self.evo_ok = None
                    return "espeon" if period == "day" else "umbreon"
                if s["evo_declined"] != period:  # 이 시간대에 '유지'를 고르지 않았으면 물어봄 (낮↔밤이 바뀌면 다시 물어봄)
                    self.evo_pending = ("espeon" if period == "day" else "umbreon", period)
            return None
        if spec == "@ralts":
            return "gallade" if t["power"] > t["mind"] else "gardevoir"
        raise ValueError(spec)

    def egg_waiting(self):
        """알인데 계통 선택권이 있고 아직 사용 여부를 정하지 않았으면 True (이 동안은 부화하지 않음)."""
        s = self.s
        return (s["stage"] == 0 and not s["dead"] and s["items"].get("ticket", 0) > 0
                and not s.get("egg_decided") and s.get("next_chain") is None)

    def decline_ticket(self):
        """선택권을 쓰지 않기로 함 → 알이 바로 부화."""
        self.s["egg_decided"] = True

    def use_stone(self, kind):
        s = self.s
        if s["dead"] or s["stage"] == 0:
            return self.say("알일 때는 쓸 수 없다.")
        if s["items"].get(kind, 0) <= 0:
            return self.say(f"{item_label(kind)}이(가) 없다.")
        if kind == "everstone":
            if s["everstone"]:
                return self.say("이미 변함없는 돌을 지니고 있다.")
            if s["stage"] >= 3:
                return self.say("이미 최종 단계라 필요 없다.")
            s["items"][kind] -= 1
            s["everstone"] = True
            self._fx(kind)
            return self.say("변함없는 돌을 지녔다! 다시 알로 돌아가기 전까지 진화하지 않는다. (상태 화면에서 해제)")
        pika = s["slug"] == "pikachu" and kind == "thunder_stone"
        if s["stage"] >= 3 or not (pika or "@eevee" in CHAINS[s["chain"]]["forms"]):
            return self.say("이 포켓몬에게는 효과가 없다.")
        if s["stone"]:
            return self.say("이미 진화의 돌을 쓰는 중이다.")
        s["items"][kind] -= 1
        s["stone"] = kind
        self._fx(kind)
        self.say(f"{item_label(kind)}을(를) 사용했다! 진화 조건이 차면 {KO['raichu'] if pika else KO[STONE_FORM[kind]]}(으)로 진화한다.")

    def release_everstone(self):
        s = self.s
        if not s["everstone"]:
            return self.say("변함없는 돌을 지니고 있지 않다.")
        s["everstone"] = False
        self.say("변함없는 돌을 해제했다. 진화 조건이 차면 진화한다. (돌은 사라짐)")

    def roll_drops(self, ab):
        """전투 승리/포획 시 돌 줍기: 타입이 맞는 적에게서 진화의 돌, 모든 적에게서 변함없는 돌(강적은 확률 ↑)."""
        s, elite = self.s, ab.get("elite", False)
        drops = [TYPE_STONE[t] for t in ab["foe_types"]
                 if t in TYPE_STONE and random.random() < (STONE_DROP_ELITE if elite else STONE_DROP)]
        if random.random() < (EVER_DROP_ELITE if elite else EVER_DROP):
            drops.append("everstone")
        for key in drops:
            have, cap = s["items"].get(key, 0), STONE_CAP[key]
            if have >= cap:
                self.say(f"{item_label(key)}을(를) 발견했지만 더 가질 수 없다. ({cap}/{cap})")
            else:
                s["items"][key] = have + 1
                self.say(f"✨ {item_label(key)}을(를) 주웠다! ({have + 1}/{cap})")

    def roll_hatch(self):
        """부화 확률: 등급(일반 60 / 희귀 28 / 매우 희귀 10.5 / 전설 1.5 %)을 먼저 뽑고 그 안에서 균등 추첨.
        행운의 부적은 희귀 이상의 비중과 이로치 확률(기본 1/40)을 높임. 계통 선택권이 있으면 그 계통."""
        s = self.s
        pick = s.pop("next_chain", None)
        luck = self.upg("luck")
        if isinstance(pick, int) and 0 <= pick < len(CHAINS):
            idx = pick
        else:
            w = {k: RARITY_PCT[k] * (1 if k == "C" else 1 + 0.15 * luck) for k in "CURL"}
            cat = random.choices(list(w), weights=list(w.values()))[0]
            idx = random.choice([i for i, ch in enumerate(CHAINS) if ch["rar"] == cat])
        return idx, random.random() < SHINY_CHANCE * (1 + 0.1 * luck)

    def check_evolve(self):
        s = self.s
        st = s["stage"]
        self.evo_pending = None
        if s["dead"] or self.up_t < EVOLVE_DELAY:
            return  # 켠 직후에는 잠깐 기다렸다가 진행 (꺼 둔 동안은 진행하지 않음)
        nxt = st + 1
        if st == 0:
            if self.egg_waiting():
                return  # 계통 선택권 사용 여부를 정하기 전에는 부화하지 않음. 선택권이 없으면 바로 부화
        else:
            need = STAGE_TIME[st]
            if need is None or s["stage_time"] < need:
                return
            if s["exp"] < EXP_NEED.get(nxt, 0):
                return  # 시간은 찼지만 경험치(전투/훈련)가 더 필요
            if s["everstone"]:
                return  # 변함없는 돌: 해제하기 전까지 진화하지 않음
        if st == 0:  # 부화: 등급별 확률로 계통 결정. 2단 진화 계통은 tier 2, 진화 없는 종은 tier 3부터 시작
            idx, shiny = self.roll_hatch()
            s["chain"] = idx
            ch = CHAINS[idx]
            nxt = 4 - len(ch["forms"])
            s["line"] = ch["color"]
            s["slug"] = ch["forms"][0]
            s["shiny"], s["rarity"] = shiny, ch["rar"]
        else:
            ch = CHAINS[s["chain"]]
            slug = self.resolve_form(ch["forms"][nxt - 1 - (3 - len(ch["forms"]))])
            if slug is None:
                return  # 진화의 돌(또는 사용자의 선택)이 필요해서 대기
            if slug in STONE_ONLY:  # 피카츄 → 라이츄: 번개의 돌이 있어야 진화
                if s["stone"] != STONE_ONLY[slug]:
                    return
                s["stone"] = None
            s["exp"] = max(0.0, s["exp"] - EXP_NEED.get(nxt, 0))  # 초과분은 다음 단계로 이월
            s["slug"] = slug
        s["stage"] = nxt
        s["stage_time"] = 0.0
        s["evo_declined"] = ""
        s["hp"] = 100.0
        s["weight"] += 3
        s["raised"][s["slug"]] = 1  # 도감: 키워 본 포켓몬
        if s["slug"] not in s["dex"]:  # 키워서 얻은 포켓몬도 도감에 등록
            s["dex"][s["slug"]] = 1
            s["new_dex"].append(s["slug"])
            self.say(f"도감 등록! {self.name()} ({len(s['dex'])}종)")
        if st == 0:
            self.say(f"알이 부화했다! {RARITY_STARS[s['rarity']]} {self.display_name()}!"
                     + (" ✨이로치다!" if s["shiny"] else "") + (" 전설의 포켓몬이다!" if s["rarity"] == "L" else ""))
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
            s["happy"] = min(100, s["happy"] + SNACK_BOND)
            s["weight"] += 2
            self._fx("snack")
            self.say("간식 냠냠! 기분이 좋아졌다.")
        else:
            s["hunger"] = min(100, s["hunger"] + 30)
            s["weight"] += 1
            self._fx("meat")
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
        s["exp"] += 2
        s["energy"] -= 10
        s["hunger"] = max(0, s["hunger"] - 5)
        s["happy"] = max(0, s["happy"] - TRAIN_BOND_LOSS)
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
        if kind in STONES:
            return self.use_stone(kind)
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
            s["happy"] = min(100.0, s["happy"] + BENTO_BOND)
            s["weight"] += 1
        elif kind == "ticket":
            return self.say("알일 때 가방에서 쓰면 계통을 고를 수 있다.")
        elif kind in ("energy1", "energy2"):
            if s["energy"] >= 100:
                return self.say("기력이 가득 차 있다.")
            s["energy"] = min(100.0, s["energy"] + (40 if kind == "energy1" else 100))
            s["happy"] = max(0.0, s["happy"] - ENERGY_ITEM_BOND_LOSS)   # 억지로 기운을 내서 친밀도가 조금 줄어듦
            if s["sleeping"] and s["energy"] > 20:
                s["sleeping"] = False  # 기력이 돌아오면 잠에서 깸
        elif kind == "candy":
            key = random.choice(TRAIN_KEYS)
            s["train"][key] += 3
            self.say(f"{TRAIN_LABEL[key]} 수치가 올랐다!")
        s["items"][kind] -= 1
        self._fx(kind)
        self.say(f"{SHOP[kind][0]}을(를) 썼다.")

    def _fx(self, kind):
        if self.fx_on:
            self.fx.append((kind, time.time()))
            del self.fx[:-3]

    def pet(self):
        s = self.s
        if s["dead"] or s["stage"] == 0:
            return False
        s["happy"] = min(100, s["happy"] + PET_GAIN)
        return True

    # ── 턴제 전투: 자동으로 진행되지만, 전투 창에서 명령을 누르면 직접 조작(수동)할 수 있음 ──
    def battle_running(self):
        ab = self.active_battle
        return bool(ab and not ab["settled"])

    def battle(self, auto=False, instant=False, foe=None, user=False):
        """foe 를 주면 그 포켓몬과(현재 단계 상대 목록 안에서), 없으면 무작위 상대와 싸움."""
        s = self.s
        if not self._ok():
            return
        if s["sleeping"]:
            return self.say("자는 중이라 싸울 수 없다. 깨우거나 기력 아이템을 쓰자.")
        if s["hp"] < 30:
            return self.say("체력이 부족해서 싸울 수 없다. (상처약으로 회복)")
        if s["energy"] < 15:
            return self.say("기력이 부족해서 싸울 수 없다. (활력의 가루 / 재우기)")
        if self.battle_running():
            return self.say("이미 전투 중이다.")
        st = s["stage"]
        pool = FOE_POOL[st]
        slug = foe if foe in pool else random.choices(pool, weights=[FOE_WEIGHT[x] for x in pool])[0]
        elite = slug in LEGENDARY or random.random() < ELITE_CHANCE[st]  # 강적: 강화 없이는 이기기 어려움
        emult = random.uniform(*ELITE_MULT[st]) if elite else 1.0
        now = self.clock()
        s["energy"] -= 8
        self.active_battle = dict(
            foe=("강적 " if elite else "") + KO[slug], slug=slug, stage=st, elite=elite, line=random.randrange(4), auto=auto,
            user=user, ball_thrown=False,
            manual=False,                        # 모든 전투는 기본이 자동 (버튼을 누르면 그때부터 직접 조작)
            P=max(1.0, self.power()), E=(BASE_POWER[st] * random.uniform(0.7, 1.4) + 2) * FOE_POWER.get(slug, 1.0) * emult,
            pet_hp=100.0, foe_hp=100.0, guard=False, pp=SKILL_PP, pet_types=TYPES.get(s["slug"], ("normal",)),
            foe_types=TYPES.get(slug, ("normal",)), events=[], pending=None, last_input=now,
            auto_tries=0, captured=False, result=None, settled=False, start=now,
            phase="intro", t_next=now + BATTLE_IN, t_choose=now, t_outro=0.0, fail_t=0.0,
            reward=int(random.randint(3, 6) * st * (2.5 if elite else 1)))
        if instant:  # 앱을 꺼 둔 동안의 전투: 연출 없이 바로 결과 반영
            self._finish_instant()
        else:
            self.update_battle(now)

    def _ratio(self, ab):
        return min(3.0, max(0.35, ab["P"] / ab["E"]))

    @staticmethod
    def _eff(mult):
        """타입 상성 배율을 피해 계수로: 무효는 아주 약하게, 4배/0.25배는 3배/0.3배로 제한."""
        return 0.15 if mult == 0 else min(3.0, max(0.3, mult))

    def skill_type(self, ab):
        return best_type(ab["pet_types"], ab["foe_types"])

    def skill_mult(self, ab):
        return type_mult(self.skill_type(ab), ab["foe_types"])

    def _event(self, ab, t0, who, kind, dur, **kw):
        ev = dict(t0=t0, dur=dur, who=who, kind=kind, tgt="foe" if who == "pet" else "pet", dmg=0, ok=None,
                  ball=None, type=None, mult=None)
        ev.update(kw)
        ab["events"].append(ev)
        del ab["events"][:-30]
        return ev

    def perform_pet(self, ab, act, t0):
        """내 차례의 행동. 쓸 수 없는 행동이면 False(차례 유지).
        공격: 타입과 무관한 기본 공격(안정적). 스킬: 내 타입 기술(상성 적용·PP 소모·명중 90%)."""
        s, r = self.s, self._ratio(ab)
        dmg, kind, typ, mult = 0, "attack", None, None
        if act == "attack":
            dmg = self.catch_cap(ab, int(round(20 * r ** 0.7 * random.uniform(0.75, 1.25))))
        elif act == "skill":
            if ab["pp"] <= 0:
                return False
            ab["pp"] -= 1
            typ = self.skill_type(ab)
            mult = type_mult(typ, ab["foe_types"])
            if random.random() < 0.9:
                dmg = self.catch_cap(ab, int(round(30 * r ** 0.7 * self._eff(mult) * random.uniform(0.75, 1.25))))
                kind = "skill"
            else:
                kind = "miss"
        elif act == "guard":   # 다음 공격 피해 60% 감소 + 체력 약간 회복
            ab["guard"] = True
            heal = min(8, 100 - ab["pet_hp"])
            ab["pet_hp"] += heal
            self._event(ab, t0, "pet", "guard", 0.7, tgt="pet", dmg=-int(heal))
            ab["phase"], ab["t_next"] = "pet_anim", t0 + 0.7
            return True
        elif act.startswith("ball:"):
            kind_b = act[5:]
            if kind_b not in BALLS or s["items"].get(kind_b, 0) <= 0:
                return False
            s["items"][kind_b] -= 1
            ab["ball_thrown"] = True
            frac = ab["foe_hp"] / 100
            p = min(0.95, max(0.05, CATCH_BASE.get(ab["slug"], 0.4) * (1.5 - frac) * BALLS[kind_b][2]
                              * (1 + 0.06 * self.upg("catch")) * (0.5 if ab["elite"] else 1.0)))
            ok = random.random() < p
            self._event(ab, t0, "pet", "ball", CATCH_T, ball=kind_b, ok=ok)
            if ok:
                ab["captured"], ab["result"] = True, "captured"
            else:
                ab["fail_t"] = t0 + CATCH_T
            ab["phase"], ab["t_next"] = "pet_anim", t0 + CATCH_T
            return True
        elif act == "potion":
            item = next((k for k in ("potion", "super_potion") if s["items"].get(k, 0) > 0), None)
            if not item:
                return False
            s["items"][item] -= 1
            heal = min(40 if item == "potion" else 70, 100 - ab["pet_hp"])
            ab["pet_hp"] += heal
            self._event(ab, t0, "pet", "heal", 0.8, tgt="pet", dmg=-int(heal))
            ab["phase"], ab["t_next"] = "pet_anim", t0 + 0.8
            return True
        elif act == "flee":
            ok = random.random() < 0.7
            self._event(ab, t0, "pet", "flee", ANIM, ok=ok)
            if ok:
                ab["result"] = "fled"
            ab["phase"], ab["t_next"] = "pet_anim", t0 + ANIM
            return True
        else:
            return False
        dur = ANIM + (0.5 if act == "skill" else 0)  # 스킬은 이펙트를 보여 주려고 조금 더 길게
        self._event(ab, t0, "pet", kind, dur, dmg=dmg, type=typ, mult=mult)
        ab["foe_hp"] = max(0.0, ab["foe_hp"] - dmg)
        if ab["foe_hp"] <= 0:
            ab["result"] = "win"
        ab["phase"], ab["t_next"] = "pet_anim", t0 + dur
        return True

    def ball_for_catch(self):
        """포획용 볼: 몬스터볼 우선(없으면 슈퍼볼 → 하이퍼볼). 하나도 없으면 None."""
        return next((k for k in ("ball", "great", "ultra") if self.s["items"].get(k, 0) > 0), None)

    def catch_plan(self, ab):
        """자동 진행에서 이 전투는 '새 포켓몬을 볼로 잡는' 계획인가 (도감에 없음 · 아직 안 던짐 · 볼 보유)."""
        return (not ab["manual"] and not ab["ball_thrown"] and ab["slug"] not in self.s["dex"]
                and self.ball_for_catch() is not None)

    def ball_safe(self, ab):
        """볼을 던져 빗나가도 이어지는 상대 공격 한 번에 쓰러지지 않을 만큼 체력이 남았는가."""
        r = self._ratio(ab)
        mult = type_mult(best_type(ab["foe_types"], ab["pet_types"]), ab["pet_types"])
        worst = 16 * (1 / r) ** 0.7 * self._eff(mult) * 1.25
        return ab["pet_hp"] > worst + 1

    def catch_cap(self, ab, dmg):
        """볼을 던질 수 있는 상황이면 자동 공격이 상대를 CATCH_KEEP% 아래로 깎지 않게 함(잡기 전에 쓰러뜨리지 않도록).
        볼이 위험하면(내 체력이 낮아 패배할 수 있으면) 제한 없이 공격해서 끝냄."""
        if self.catch_plan(ab) and self.ball_safe(ab):
            return min(dmg, max(0, int(ab["foe_hp"] - CATCH_KEEP)))
        return dmg

    def perform_foe(self, ab, t0):
        """상대의 공격: 상대 타입 중 내게 가장 효과적인 타입으로 공격(상성 적용)."""
        r = self._ratio(ab)
        typ = best_type(ab["foe_types"], ab["pet_types"])
        mult = type_mult(typ, ab["pet_types"])
        dur = ANIM + 0.4
        if random.random() < 0.1:
            self._event(ab, t0, "foe", "miss", ANIM, type=typ, mult=mult)
            dur = ANIM
        else:
            dmg = 16 * (1 / r) ** 0.7 * self._eff(mult) * random.uniform(0.75, 1.25)
            kind = "attack"
            if ab["guard"]:
                dmg, kind = dmg * 0.4, "blocked"
            dmg = int(round(dmg))
            ab["pet_hp"] = max(0.0, ab["pet_hp"] - dmg)
            self._event(ab, t0, "foe", kind, dur, dmg=dmg, type=typ, mult=mult)
            if ab["pet_hp"] <= 0:
                ab["result"] = "lose"
        ab["guard"] = False
        ab["phase"], ab["t_next"] = "foe_anim", t0 + dur

    def auto_action(self, ab):
        """자동 진행 때의 행동: 새 포켓몬이 약해지면 포획, 체력이 위험하면 포션, 상성이 나쁘지 않으면 스킬, 아니면 공격."""
        s = self.s
        if ab["elite"] and ab["P"] / ab["E"] < ELITE_FLEE_BELOW:  # 승산이 낮은 강적에게서는 도망
            return "flee"
        if self.catch_plan(ab) and ab["foe_hp"] <= CATCH_AT and self.ball_safe(ab):
            return "ball:" + self.ball_for_catch()  # 새 포켓몬: 체력 15% 이하에서 몬스터볼 1회 (위험하면 대신 공격)
        if self.cfg["auto_feed"] and ab["pet_hp"] < 30 and (s["items"].get("potion", 0) or s["items"].get("super_potion", 0)):
            return "potion"
        if ab["pp"] > 0 and self.skill_mult(ab) >= 1.0:
            return "skill"
        return "attack"

    def update_battle(self, now):
        """전투 시계를 now 까지 진행(연출 단계: 등장 → 내 차례 → 공격 → 상대 차례 → … → 결과)."""
        ab = self.active_battle
        for _ in range(16):  # 오래 멈췄다 와도 한 번에 따라잡되 무한 루프는 방지
            if not ab or ab["settled"]:
                return
            ph = ab["phase"]
            if ph == "intro":
                if now < ab["t_next"]:
                    return
                ab["phase"], ab["t_choose"] = "choose", ab["t_next"]
            elif ph == "choose":
                act, t0 = None, now
                if ab["pending"]:
                    act, ab["pending"] = ab["pending"], None
                elif ab["manual"]:
                    if now - ab["last_input"] <= MANUAL_TIMEOUT:
                        return
                    ab["manual"], ab["t_choose"] = False, now  # 입력이 없으면 자동 진행으로 복귀
                    self.say("입력이 없어 자동 진행으로 돌아간다.")
                    return
                elif now >= ab["t_choose"] + AUTO_DELAY:
                    act, t0 = self.auto_action(ab), ab["t_choose"] + AUTO_DELAY
                else:
                    return
                if not self.perform_pet(ab, act, t0):
                    return
            elif ph == "pet_anim":
                if now < ab["t_next"]:
                    return
                if ab["result"]:
                    ab["phase"], ab["t_outro"] = "outro", ab["t_next"]
                    ab["t_next"] += CAUGHT_OUT if ab["result"] == "captured" else BATTLE_OUT
                else:
                    self.perform_foe(ab, ab["t_next"])
            elif ph == "foe_anim":
                if now < ab["t_next"]:
                    return
                if ab["result"]:
                    ab["phase"], ab["t_outro"] = "outro", ab["t_next"]
                    ab["t_next"] += BATTLE_OUT
                else:
                    ab["phase"], ab["t_choose"] = "choose", ab["t_next"]
            elif ph == "outro":
                if now < ab["t_next"]:
                    return
                self.settle_battle()
                self.active_battle = None  # 결과 반영이 끝났으니 정리(전투 창은 이걸 보고 닫힘)
                return

    def battle_command(self, act):
        """전투 창의 명령. 누르면 직접 조작 모드가 되고, act='auto'면 자동 진행으로 되돌림."""
        ab = self.active_battle
        if not ab or ab["settled"]:
            return self.say("전투 중이 아니다.")
        now = self.clock()
        ab["last_input"] = now
        if act == "auto":
            ab["manual"], ab["pending"] = False, None
            return True
        if ab["phase"] == "outro" or ab["result"]:
            return False
        if act.startswith("ball:") and self.s["items"].get(act[5:], 0) <= 0:
            return self.say(f"{BALLS[act[5:]][0]}이(가) 없다. 상점에서 살 수 있다.")
        if act == "skill" and ab["pp"] <= 0:
            return self.say("스킬 PP가 없다. 기본 공격을 쓰자.")
        if act == "potion" and not (self.s["items"].get("potion", 0) or self.s["items"].get("super_potion", 0)):
            return self.say("상처약이 없다.")
        ab["manual"], ab["pending"] = True, act
        self.update_battle(now)
        return True

    def throw_ball(self, kind):
        return self.battle_command("ball:" + kind)

    def _finish_instant(self):
        """남은 전투를 연출 없이 자동으로 끝까지 진행해 결과 반영 (오프라인/종료 시)."""
        ab = self.active_battle
        ab["manual"], ab["pending"] = False, None
        for _ in range(80):
            if ab["result"]:
                break
            act = self.auto_action(ab)
            if not self.perform_pet(ab, act, 0.0):
                self.perform_pet(ab, "attack", 0.0)
            if ab["result"]:
                break
            self.perform_foe(ab, 0.0)
        if not ab["result"]:
            ab["result"] = "win" if ab["foe_hp"] <= ab["pet_hp"] else "lose"
        self.settle_battle()
        self.active_battle = None

    def settle_now(self):
        """종료 직전: 진행 중이던 전투 결과를 잃지 않도록 바로 반영."""
        if self.battle_running():
            self._finish_instant()

    def exp_gain(self, ab):
        """전투로 얻는 경험치: 상대가 강할수록 많이, 포획은 1.5배(새 포켓몬 +5), 패배는 소량, 도망은 없음."""
        res = ab["result"]
        bonus = (1 + 0.08 * self.upg("exp")) * (2 if ab.get("elite") else 1) * (0.75 if s_happy_low(self.s) else 1)
        base = (8 + 4 * ab["stage"]) * min(1.5, max(0.7, ab["E"] / ab["P"])) * bonus
        if res == "win":
            return int(round(base))
        if res == "captured":
            return int(round(base * 1.5)) + (5 if ab["slug"] not in self.s["dex"] else 0)
        return 0

    def pick_chain(self, idx):
        """계통 선택권 1장을 써서 다음에 부화할 계통을 정함(알일 때만)."""
        s = self.s
        if s["stage"] != 0 or s["dead"] or s["items"].get("ticket", 0) <= 0 or not 0 <= idx < len(CHAINS):
            self.say("지금은 계통을 고를 수 없다.")
            return False
        if not selectable_chain(idx):
            self.say("전설/환상의 포켓몬은 선택할 수 없다.")
            return False
        s["items"]["ticket"] -= 1
        s["next_chain"] = idx
        first = next(f for f in CHAINS[idx]["forms"] if not f.startswith("@"))
        self.say(f"{KO[first]} 계통으로 키우기로 했다!")
        return True

    def buy_upgrade(self, key, levels=1):
        """강화를 levels 만큼(살 수 있는 만큼) 올림. 올린 레벨 수를 반환."""
        s = self.s
        done = 0
        while done < levels and self.upg(key) < UPGRADES[key][2]:
            cost = upgrade_cost(key, self.upg(key))
            if s["bits"] < cost:
                break
            s["bits"] -= cost
            s["upg"][key] = self.upg(key) + 1
            done += 1
        name = UPGRADES[key][0]
        if done:
            self.say(f"{name} 강화! Lv {self.upg(key)} ({upgrade_effect(key, self.upg(key))})")
        elif self.upg(key) >= UPGRADES[key][2]:
            self.say(f"{name}은(는) 이미 최대 레벨이다.")
        else:
            self.say(f"Bits가 부족하다. ({name} 강화 {upgrade_cost(key, self.upg(key))} Bits)")
        return done

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

    def apply_loss(self, res, stage):
        """패배/도망 페널티: 경험치·성장 시간(걸음)·친밀도 감소. 줄어든 만큼을 문장으로 반환."""
        s = self.s
        e, t, h = loss_penalty(res, stage)
        e2, t2, h2 = min(e, int(s["exp"])), min(t, int(s["stage_time"])), min(h, int(s["happy"]))
        s["exp"] -= e2
        s["stage_time"] -= t2
        s["happy"] -= h2
        return f" (EXP -{e2}, 성장 -{t2 // 60}분, 친밀도 -{h2})"

    def settle_battle(self):
        s, ab = self.s, self.active_battle
        if not ab or ab["settled"]:
            return
        ab["settled"] = True
        res, foe, tag = ab["result"], ab["foe"], ""   # 자동/수동 같은 내부 표시는 메시지에 붙이지 않음
        gain = self.exp_gain(ab)
        s["exp"] += gain
        exp_txt = f", +{gain} EXP" if gain else ""
        if res in ("win", "captured"):
            s["wins"] += 1
            s["happy"] = min(100, s["happy"] + (CAPTURE_BOND if res == "captured" else WIN_BOND))
            s["hp"] = max(BATTLE_HP_FLOOR, s["hp"] - (1 if res == "captured" else 2))
            s["train"][random.choice(TRAIN_KEYS)] += 0.5
            reward = ab["reward"] // 2 if res == "captured" else ab["reward"]
            s["bits"] += reward
        if res == "captured":
            first = ab["slug"] not in s["dex"]
            s["dex"][ab["slug"]] = s["dex"].get(ab["slug"], 0) + 1
            if first:
                s["new_dex"].append(ab["slug"])  # 도감을 열어 확인하기 전까지 ✨ 표시
            if first:
                s["bits"] += 20
                self.say(f"{tag}{foe}을(를) 포획했다! 도감 등록 ({len(s['dex'])}종) +20 Bits{exp_txt}")
            else:
                self.say(f"{tag}{foe}을(를) 또 포획했다! +{reward} Bits{exp_txt}")
        elif res == "win":
            self.say(f"{tag}{foe}에게 승리! +{ab['reward']} Bits{exp_txt}")
        elif res == "fled":
            s["losses"] += 1  # 도망도 패배로 집계
            pen = self.apply_loss(res, ab["stage"])
            self.say((f"{tag}{foe}에게서 도망쳤다!" if ab.get("elite") else f"{tag}도망쳤다!") + pen)
        else:
            s["losses"] += 1
            s["hp"] = max(BATTLE_HP_FLOOR, s["hp"] - 8)  # 전투로는 죽지 않음
            s["battle_t"] = -AUTO_BATTLE_EVERY  # 패배 후엔 자동 배틀을 쉼
            pen = self.apply_loss(res, ab["stage"])
            self.say(f"{tag}{foe}에게 졌다… 쉬어야겠다.{pen}")
        if res in ("win", "captured"):
            self.roll_drops(ab)

    def reset_all(self):
        """전체 초기화: 진행 데이터를 모두 지우고 1세대 새 알로 처음부터 (창 위치 등 설정은 유지).
        실수에 대비해 직전 저장을 save.json.reset-backup 으로 한 부 남김(다음 초기화 때 덮어씀)."""
        try:
            if os.path.exists(SAVE):
                shutil.copyfile(SAVE, SAVE + ".reset-backup")
            for f in (SAVE, SAVE + ".bak"):
                if os.path.exists(f):
                    os.remove(f)
        except OSError:
            pass
        self.s = new_state()
        self.active_battle = None
        self.evo_pending = self.evo_ok = None
        self.up_t = 0.0
        self.fx.clear()
        self.log.clear()
        self.say("모든 데이터를 초기화했다. 새 알을 받았다!")
        self.save()

    def reincarnate(self):
        s = self.s
        # 훈련 수치(힘/속도/지능)·경험치·돌 등은 새로 시작(리셋). Bits·도감·가방·강화(영구)는 유지
        self.s = new_state(gen=s["gen"] + 1, bits=s["bits"], dex=s["dex"], items=s["items"], upg=s["upg"],
                           new_dex=s.get("new_dex"))
        self.say(f"{self.s['gen']}세대 알을 받았다!")


# ───────────────────────── UI ─────────────────────────
SHELL = "#2b2f3a"
SCR = "#10141a"   # 도감 틀의 검은 화면 바탕색 (build_frame.py 의 SCREEN 과 같은 색)
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
        self.dex_page = 0
        self._egg_prompted = False
        self._evo_asking = False
        self._closing = False   # 종료 중이면 예약된 반복 작업(loop/move_loop)이 더는 돌지 않게 함
        self.img_cache = {}
        self.hearts = []  # [x, y, life]
        self.bg_files = scan_backgrounds()
        self.bg_name, self.bg_img, self.bg_bad = None, None, set()
        self.drop = None  # 아이템 사용 연출 {kind, x, y, phase, t0, ...}
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
    def load_frame(self):
        """도감 기기 틀(sprites/ui/dex_frame.png, build_frame.py 로 생성). 없거나 읽기 실패면 None → 기존 모양."""
        try:
            with open(os.path.join(HERE, "sprites", "ui", "dex_frame.json"), encoding="utf-8") as f:
                meta = json.load(f)
            img = tk.PhotoImage(file=os.path.join(HERE, "sprites", "ui", "dex_frame.png"), master=self.root)
            sx0, sy0, sx1, sy1 = meta["screen"]
            if img.width() != meta["size"][0] or sx1 - sx0 < 336 or sy1 - sy0 < 340:
                return None
            return img, (sx0, sy0, sx1 - sx0, sy1 - sy0)
        except Exception:  # noqa: BLE001
            return None

    def build_full(self):
        frame = self.load_frame()
        if frame:  # 도감 기기 모양 틀: 검은 화면 자리에 게임 화면(배경·펫·버튼)이 들어감
            self.frame_img, (fx, fy, fw, fh) = frame
            self.full = tk.Frame(self.root, bg=KEY)
            self.dev = tk.Canvas(self.full, width=self.frame_img.width(), height=self.frame_img.height(), bg=KEY,
                                 highlightthickness=0, bd=0)
            self.dev.pack()
            self.dev.create_image(0, 0, image=self.frame_img, anchor="nw")
            box = tk.Frame(self.dev, bg=SCR, width=fw, height=fh)
            box.pack_propagate(False)
            self.dev.create_window(fx, fy, window=box, anchor="nw")
            self.bind_drag(self.dev)  # 틀(빨간 몸체)을 잡고 끌어 옮김
            bg0, pad = SCR, 0
        else:
            self.dev = None
            self.full = box = tk.Frame(self.root, bg=SHELL, padx=8, pady=6)
            bg0 = SHELL
        bar = self.bar_w = tk.Frame(box, bg=bg0)
        bar.pack(fill="x", padx=pad)
        t = tk.Label(bar, text="DigiPet", bg=bg0, fg="#9fb0d0", font=(FONT, 9, "bold"))
        t.pack(side="left", padx=(6, 0))
        for txt, cmd in (("×", self.quit), ("—", lambda: self.show_mode(True))):
            tk.Button(bar, text=txt, command=cmd, bg=bg0, fg="#9fb0d0", bd=0, width=3,
                      activebackground=BTN, activeforeground="#fff", font=(FONT, 9)).pack(side="right")
        self.screen = tk.Canvas(box, width=320, height=230, highlightthickness=3,
                                highlightbackground="#171a21", bd=0)
        self.screen.pack(pady=2 if self.dev else 4)
        self.info = tk.Label(box, bg=bg0, fg="#c9d4ec", font=(FONT, 9))
        self.info.pack()

        grid = self.grid = tk.Frame(box, bg=bg0)
        self.grid_pad = (2, 0) if self.dev else (4, 0)
        grid.pack(pady=self.grid_pad)
        # 전투 화면 때 아래 버튼 줄이 이 명령 버튼으로 바뀜 (평소엔 숨김)
        self.bgrid = tk.Frame(box, bg=bg0)
        self.sb_btns = {}
        r1 = tk.Frame(self.bgrid, bg=bg0)
        r1.pack(pady=2)
        for key, text, w in (("attack", "공격", 5), ("skill", "스킬", 6), ("guard", "방어", 4),
                             ("potion", "포션", 5), ("flee", "도망", 4), ("auto", "자동", 4)):
            b = tk.Button(r1, text=text, command=lambda k=key: self.g.battle_command(k), width=w,
                          bg="#3b82e0" if key == "attack" else BTN, fg="#fff", bd=0, font=(FONT, 9),
                          activebackground="#6a7390", activeforeground="#fff", disabledforeground="#6b7385")
            b.pack(side="left", padx=2)
            self.sb_btns[key] = b
        r2 = tk.Frame(self.bgrid, bg=bg0)
        r2.pack(pady=2)
        for kind in BALLS:
            b = tk.Button(r2, text=BALLS[kind][0], command=lambda k=kind: self.g.battle_command("ball:" + k), width=11,
                          bg=BTN, fg="#fff", bd=0, font=(FONT, 9), activebackground="#6a7390", activeforeground="#fff",
                          disabledforeground="#6b7385")
            b.pack(side="left", padx=2)
            self.sb_btns["ball:" + kind] = b
        self._bui = False
        self._last_bt = 0.0
        self.box, self.box_bg = box, bg0
        self.shop_open, self.shop_frame = False, None
        self._dex_prev, self._dex_t0 = None, 0.0
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
        self.screen.bind("<MouseWheel>", self.on_wheel)
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
        self.v_bw = tk.BooleanVar(value=g.cfg["battle_window"])
        self.v_abw = tk.BooleanVar(value=g.cfg["auto_battle_window"])
        self.v_auto = tk.BooleanVar(value=g.cfg["auto_battle"])
        self.v_sound = tk.BooleanVar(value=g.cfg["sound"])
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="미니/전체 모드 전환 (더블클릭)", command=lambda: self.show_mode(not g.cfg["mini"]))
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
        m.add_command(label="펫을 바닥(작업표시줄 위)으로 내리기", command=self.drop_to_ground)
        m.add_checkbutton(label="알림 소리", variable=self.v_sound, command=self.apply_cfg)
        m.add_separator()
        m.add_command(label="몬스터볼 던지기", command=lambda: g.throw_ball("ball"))
        m.add_command(label="슈퍼볼 던지기", command=lambda: g.throw_ball("great"))
        m.add_command(label="하이퍼볼 던지기", command=lambda: g.throw_ball("ultra"))
        m.add_separator()
        m.add_command(label="새 알로 환생", command=self.reincarnate)
        m.add_command(label="전체 초기화 (모든 데이터 삭제)", command=self.reset_game)
        m.add_command(label="저장 후 종료", command=self.quit)
        self.menu = m
        self.root.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

    def battle_btn(self):
        self.start_battle_ui()

    def start_battle_ui(self):
        """배틀 버튼/트레이: 전투를 시작함 (자동 전투가 기본). 전체 모드는 도감 틀 화면이 전투 화면으로 바뀌고,
        미니 모드는 예전처럼 전투 창을 엶."""
        g = self.g
        if g.battle_running():
            if g.cfg["mini"]:
                g.active_battle.pop("bw_closed", None)
                self.open_battle_window()
            return
        g.battle(user=True)
        if g.battle_running() and g.cfg["mini"] and g.cfg["battle_window"]:
            self.open_battle_window()

    def open_shop(self):
        """상점: 팝업 창 대신 도감 틀의 게임 화면이 상점 화면으로 바뀜. [아이템] 탭(수량을 골라 한꺼번에 구매) /
        [강화] 탭(영구 강화). 구매가 끝나거나 [닫기]를 누르면 게임 화면으로 돌아옴."""
        g = self.g
        if self.shop_open:
            return self.close_shop()
        if g.cfg["mini"]:
            self.show_mode(False)
        if g.battle_running():
            return g.say("전투 중에는 상점을 열 수 없다.")
        for w in (self.bar_w, self.screen, self.info, self.grid, self.bgrid):
            w.pack_forget()   # 상점 화면은 위 제목줄까지 비우고 틀 화면 전체를 씀
        bgc, fg, dim = self.box_bg, "#e8edf8", "#9fb0d0"
        page = self.shop_frame = tk.Frame(self.box, bg=bgc)
        page.pack(fill="both", expand=True, padx=4)
        self.shop_open = True

        head = tk.Frame(page, bg=bgc)
        head.pack(fill="x", pady=(0, 1))
        bits_lbl = tk.Label(head, bg=bgc, fg="#ffd23c", font=(FONT, 10, "bold"))
        bits_lbl.pack(side="left")
        tabs = tk.Frame(head, bg=bgc)
        tabs.pack(side="right")
        body = tk.Frame(page, bg=bgc)
        body.pack(fill="both", expand=True)
        items_f = tk.Frame(body, bg=bgc)
        upg_f = tk.Frame(body, bg=bgc)
        items_f.place(x=0, y=0, relwidth=1, relheight=1)
        upg_f.place(x=0, y=0, relwidth=1, relheight=1)
        desc = tk.Label(page, bg=bgc, fg=dim, font=(FONT, 8), anchor="w", justify="left", wraplength=330,
                        text="항목에 마우스를 올리면 설명이 나와요.")
        desc.pack(fill="x", pady=(1, 0))
        tab_btns = {}

        def show_tab(name):
            (items_f if name == "items" else upg_f).tkraise()
            for k, bt in tab_btns.items():
                bt.config(bg="#3b82e0" if k == name else BTN)

        def mkb(parent, text, cmd, width, bg=BTN, bold=False, font=9):
            return tk.Button(parent, text=text, command=cmd, bg=bg, fg="#fff", bd=0, width=width,
                             font=(FONT, font, "bold" if bold else "normal"), activebackground="#6a7390",
                             activeforeground="#fff", disabledforeground="#6b7385", pady=0)

        for key, text in (("items", "아이템"), ("upg", "강화")):
            bt = mkb(tabs, text, lambda k=key: show_tab(k), 6, bold=True)
            bt.pack(side="left", padx=1)
            tab_btns[key] = bt
        mkb(tabs, "닫기", self.close_shop, 5).pack(side="left", padx=(6, 0))

        def hover(widgets, text):
            for w in widgets:
                w.bind("<Enter>", lambda e, t=text: desc.config(text=t))

        # ── 아이템 탭 ──
        rows = {}
        for i, (key, (nm, price, dsc)) in enumerate(SHOP.items()):
            var = tk.StringVar(value="0")
            ws = []
            ic = self.cached_image(f"items/{key}", 16, 2)
            ws.append(tk.Label(items_f, image=ic, bg=bgc) if ic else tk.Label(items_f, text=" ", bg=bgc))
            ws.append(tk.Label(items_f, text=nm, bg=bgc, fg=fg, font=(FONT, 9, "bold"), width=10, anchor="w"))
            ws.append(tk.Label(items_f, text=f"{price}", bg=bgc, fg="#ffd23c", font=(FONT, 9), width=5, anchor="e"))
            own = tk.Label(items_f, bg=bgc, fg=dim, font=(FONT, 8), width=6, anchor="e")
            ws.append(own)
            sp = tk.Spinbox(items_f, from_=0, to=999, width=3, textvariable=var, font=(FONT, 8), justify="center", bd=1)
            mx = mkb(items_f, "최대", lambda k=key: fill_max(k), 3, font=8)
            for c_, w in enumerate(ws):
                w.grid(row=i, column=c_, sticky="w", pady=0)
            sp.grid(row=i, column=4, padx=(6, 2))
            mx.grid(row=i, column=5)
            hover(ws + [sp, mx], f"{nm} — {dsc}")
            rows[key] = dict(var=var, own=own)
            var.trace_add("write", lambda *a: refresh())
        n = len(SHOP)
        foot = tk.Frame(items_f, bg=bgc)
        foot.grid(row=n, column=0, columnspan=6, sticky="ew", pady=(2, 0))
        total_lbl = tk.Label(foot, bg=bgc, fg=fg, font=(FONT, 9, "bold"))
        total_lbl.pack(side="left")
        buy_btn = mkb(foot, "구매", lambda: do_buy(), 7, "#3b82e0", True, 10)
        buy_btn.pack(side="right")

        # ── 강화 탭 ──
        tk.Label(upg_f, text="강화는 영구적이며 환생해도 유지돼요.", bg=bgc, fg=dim, font=(FONT, 8)).grid(
            row=0, column=0, columnspan=5, sticky="w", pady=(0, 3))
        urows = {}
        for i, (key, (nm, dsc, mx_, base, grow)) in enumerate(UPGRADES.items(), start=1):
            l1 = tk.Label(upg_f, text=nm, bg=bgc, fg=fg, font=(FONT, 9, "bold"), width=11, anchor="w")
            lv = tk.Label(upg_f, bg=bgc, fg=fg, font=(FONT, 9), width=8, anchor="e")
            cost = tk.Label(upg_f, bg=bgc, fg=fg, font=(FONT, 9), width=9, anchor="e")
            b1 = mkb(upg_f, "강화", lambda k=key: do_upgrade(k, 1), 5, "#3b82e0", True)
            b2 = mkb(upg_f, "최대", lambda k=key: do_upgrade(k, 99), 4)
            for c_, w in enumerate((l1, lv, cost)):
                w.grid(row=i, column=c_, sticky="w", pady=2)
            b1.grid(row=i, column=3, padx=(6, 2))
            b2.grid(row=i, column=4)
            urows[key] = dict(lv=lv, cost=cost, b1=b1, b2=b2, ws=[l1, lv, cost, b1, b2])

        def qty(key):
            try:
                return min(999, max(0, int(rows[key]["var"].get())))
            except ValueError:
                return 0

        def total():
            return sum(SHOP[k][1] * qty(k) for k in SHOP)

        def fill_max(key):
            others = total() - SHOP[key][1] * qty(key)
            rows[key]["var"].set(str(max(0, min(999, (int(g.s["bits"]) - others) // SHOP[key][1]))))

        def refresh():
            if not page.winfo_exists():
                return
            t, bits = total(), int(g.s["bits"])
            bits_lbl.config(text=f"Bits {bits}")
            for k, r in rows.items():
                r["own"].config(text=f"보유 {g.s['items'].get(k, 0)}")
            count = sum(qty(k) for k in SHOP)
            total_lbl.config(text=f"합계 {t} ({count}개)" + (" · 부족!" if t > bits else ""),
                             fg="#ff6b6b" if t > bits else fg)
            buy_btn.config(state="normal" if 0 < t <= bits else "disabled")
            for k, r in urows.items():
                lv_now, mx_ = g.upg(k), UPGRADES[k][2]
                r["lv"].config(text=f"Lv {lv_now}/{mx_}")
                hover(r["ws"], f"{UPGRADES[k][0]} — {UPGRADES[k][1]} → 현재 {upgrade_effect(k, lv_now)}")
                if lv_now >= mx_:
                    r["cost"].config(text="MAX", fg="#ffd23c")
                    r["b1"].config(state="disabled")
                    r["b2"].config(state="disabled")
                else:
                    c1 = upgrade_cost(k, lv_now)
                    r["cost"].config(text=f"{c1} Bits", fg=fg if bits >= c1 else "#ff6b6b")
                    r["b1"].config(state="normal" if bits >= c1 else "disabled")
                    r["b2"].config(state="normal" if bits >= c1 else "disabled")

        def do_buy():
            if g.buy_many({k: qty(k) for k in SHOP}):
                self.close_shop()  # 아이템 구매가 끝나면 게임 화면으로 돌아감
            else:
                refresh()

        def do_upgrade(key, n):  # 강화는 여러 번 연달아 올리는 일이 많아 상점에 머무름
            g.buy_upgrade(key, n)
            refresh()

        def tick():  # 열어 둔 동안에도 Bits 증가/보유 수가 갱신되도록
            if self.shop_open and page.winfo_exists():
                refresh()
                page.after(1000, tick)

        show_tab("items")
        refresh()
        tick()

    def close_shop(self):
        if not self.shop_open:
            return
        self.shop_open = False
        if self.shop_frame is not None:
            self.shop_frame.destroy()
            self.shop_frame = None
        self.bar_w.pack(fill="x")
        self.screen.pack(pady=2 if self.dev else 4)
        self.info.pack()
        (self.bgrid if self._bui else self.grid).pack(pady=self.grid_pad)

    def choose_chain(self):
        """계통 선택권 사용: 알일 때 다음에 부화할 진화 계통을 직접 고름 (등급 높은 순 목록)."""
        g = self.g
        if g.s["stage"] != 0 or g.s["dead"]:
            return g.say("계통 선택권은 알일 때만 쓸 수 있다.")
        if g.s["items"].get("ticket", 0) <= 0:
            return g.say("계통 선택권이 없다. 상점에서 살 수 있다.")
        old = getattr(self, "chain_win", None)
        if old is not None and old.winfo_exists():
            old.lift()
            return
        win = self.chain_win = tk.Toplevel(self.root)
        win.title("계통 선택")
        win.configure(bg=SHELL, padx=12, pady=10)
        win.resizable(False, False)
        win.transient(self.root)
        if g.cfg["layer"] == "top":
            win.attributes("-topmost", True)
        tk.Label(win, text="어떤 포켓몬으로 키울까요?  (선택권 1장 소모)", bg=SHELL, fg="#e8edf8",
                 font=(FONT, 10, "bold")).pack(pady=(0, 6))
        order = {"L": 0, "R": 1, "U": 2, "C": 3}
        idxs = sorted((i for i in range(len(CHAINS)) if selectable_chain(i)), key=lambda i: (order[CHAINS[i]["rar"]], i))
        box = tk.Frame(win, bg=SHELL)
        box.pack()
        lb = tk.Listbox(box, width=46, height=16, font=(FONT, 10), activestyle="none", bg="#1f232c", fg="#e8edf8",
                        selectbackground="#3b82e0", selectforeground="#fff", bd=0, highlightthickness=0)
        sb = tk.Scrollbar(box, command=lb.yview)
        lb.config(yscrollcommand=sb.set)
        lb.pack(side="left")
        sb.pack(side="left", fill="y")
        for i in idxs:
            ch = CHAINS[i]
            forms = [f for f in ch["forms"] if not f.startswith("@")]
            first = KO[forms[0]]
            if "@eevee" in ch["forms"]:
                tail = "분기 진화"
            elif "@ralts" in ch["forms"]:
                tail = "가디안/엘레이드"
            else:
                tail = KO[forms[-1]] if len(forms) > 1 else "(진화 없음)"
            types = "/".join(TYPE_KO[t] for t in TYPES[forms[0]])
            lb.insert("end", f"{RARITY_STARS[ch['rar']]:<4} {first} → {tail}   [{types}]")

        def pick():
            sel = lb.curselection()
            if sel and g.pick_chain(idxs[sel[0]]):
                win.destroy()

        lb.bind("<Double-Button-1>", lambda e: pick())
        foot = tk.Frame(win, bg=SHELL)
        foot.pack(pady=(8, 0))
        tk.Button(foot, text="이 계통으로 키우기", command=pick, bg="#3b82e0", fg="#fff", bd=0, font=(FONT, 10, "bold"),
                  activebackground="#5b9cf0", activeforeground="#fff", width=16).pack(side="left", padx=3)
        tk.Button(foot, text="무작위로 (선택권 아끼기)", command=lambda: (g.decline_ticket(), win.destroy()), bg=BTN, fg="#e8edf8", bd=0, font=(FONT, 10),
                  activebackground="#6a7390", activeforeground="#fff").pack(side="left", padx=3)
        win.update_idletasks()
        l, t, rr, b = self.work_area()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{min(max(l, self.root.winfo_x() + 20), max(l, rr - w - 18))}+"
                     f"{min(max(t, self.root.winfo_y() + 20), max(t, b - h - 48))}")

    def after_new_egg(self):
        """환생 직후: 계통 선택권이 있으면 (메인 루프가) 사용 여부를 물어봄. 없으면 알이 바로 부화."""
        self._egg_prompted = False

    def ask_evolve(self):
        g = self.g
        try:
            pend = g.evo_pending
            if not pend or g.battle_running():
                return
            form, period = pend
            who = g.name()
            if messagebox.askyesno("진화", f"진화할 수 있어요! ({'낮' if period == 'day' else '밤'}의 모습)\n{who} → {KO[form]}\n"
                                         f"진화할까요?\n\n[아니오]를 누르면 {who}(으)로 유지해요.\n"
                                         "낮/밤이 바뀌어도 조건이 계속되면 다시 물어봐요."):
                g.approve_evolve()
            else:
                g.decline_evolve()
        finally:
            self._evo_asking = False

    def ask_ticket(self):
        """알 + 계통 선택권 보유: 사용 여부를 확인할 때까지 부화하지 않음."""
        g = self.g
        if not g.egg_waiting():
            return
        n = g.s["items"].get("ticket", 0)
        if messagebox.askyesno("알", f"계통 선택권이 {n}장 있어요.\n사용해서 키울 포켓몬을 고를까요?\n\n"
                                     "[아니오]를 누르면 선택권은 아끼고 알이 바로 부화해요."):
            self.choose_chain()
        else:
            g.decline_ticket()

    def open_bag(self):
        g = self.g
        m = tk.Menu(self.root, tearoff=0)
        owned = [(k, n) for k, n in g.s["items"].items() if n > 0 and (k in SHOP or k in STONES) and k not in BALLS]
        for k, n in owned:
            m.add_command(label=f"{item_label(k)} ×{n}  ·  {SHOP[k][2] if k in SHOP else STONES[k][1]}",
                          command=(self.choose_chain if k == "ticket" else (lambda k=k: g.use_item(k))))
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
        c["battle_window"] = self.v_bw.get()
        c["auto_battle_window"] = self.v_abw.get()
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
                (7, "배틀 시작", False), (3, "미니 모드", c["mini"]),
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
        elif cmd == 7:
            self.start_battle_ui()
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

    def reset_game(self):
        """설정 → 전체 초기화: 두 번 확인한 뒤 모든 진행 데이터를 지우고 처음부터 시작."""
        if not messagebox.askyesno("전체 초기화", "모든 데이터를 지우고 처음부터 시작할까요?\n\n"
                                   "지워지는 것: 펫, Bits, 도감, 가방, 영구 강화, 세대, 전적\n"
                                   "(창 위치·투명도 같은 설정은 유지돼요)", icon="warning", default="no"):
            return
        if not messagebox.askyesno("전체 초기화 - 마지막 확인", "정말 초기화할까요? 되돌릴 수 없어요.\n"
                                   "(직전 저장은 save.json.reset-backup 으로 한 부 남겨요)", icon="warning", default="no"):
            return
        self.close_shop()
        if self.bw_alive():
            self.bw.destroy()
        self.page, self.drop, self.hearts = "main", None, []
        self.g.reset_all()
        self.after_new_egg()

    def reincarnate(self):
        if messagebox.askyesno("환생", "현재 펫을 보내고 새 알로 시작할까요?\n(Bits · 도감 · 가방 · 강화는 유지돼요)"):
            self.g.reincarnate()
            self.after_new_egg()

    def on_wheel(self, e):
        if self.page == "dex":
            pages = (len(DEX_ORDER) + 14) // 15
            self.dex_page = (self.dex_page + (-1 if e.delta > 0 else 1)) % pages

    def on_click(self, e):
        g = self.g
        if self.dex_nav(e):
            return
        if self.page == "stats" and g.s["everstone"] and 100 <= e.x <= 250 and 206 <= e.y <= 228:
            return g.release_everstone()  # 상태 화면의 [변함없는 돌 해제] 버튼
        if g.egg_waiting():
            return self.ask_ticket()
        if g.s["dead"]:  # 실수 클릭으로 바로 환생하지 않도록 확인
            if messagebox.askyesno("작별", f"{g.name()}이(가) 떠났어요.\n새 알을 받을까요?\n(Bits · 도감 · 가방 · 강화는 유지돼요)"):
                g.reincarnate()
                self.after_new_egg()
        elif g.pet():
            self.hearts.append([e.x, e.y - 10, 1.0])

    # --- 메인 루프 ---
    def _again(self, ms, fn):
        if self._closing:
            return
        try:
            self.root.after(ms, fn)
        except tk.TclError:  # 창이 이미 닫힌 경우
            pass

    def loop(self):
        if self._closing:
            return
        try:
            now = time.time()
            dt = now - self.last_t
            self.last_t = now
            if dt > 10:  # 절전 등으로 오래 멈췄다면 오프라인 처리
                self.g.catchup_report(dt)
            else:
                self.g.tick(dt * FAST)
            if self.g.egg_waiting():  # 선택권 사용 여부를 정할 때까지 부화를 멈추고 한 번 물어봄
                if not self._egg_prompted:
                    self._egg_prompted = True
                    self.root.after(300, self.ask_ticket)
            else:
                self._egg_prompted = False
            if self.g.evo_pending and not self._evo_asking and not self.g.battle_running():
                self._evo_asking = True  # 이브이: 낮/밤 진화 여부를 사용자에게 물어봄
                self.root.after(300, self.ask_evolve)
            ab = self.g.active_battle
            # 직접 시작한 배틀만 전투 창을 자동으로 엶. 자동 배틀은 백그라운드에서 조용히 진행(설정으로 켤 수 있음,
            # 진행 중인 자동 배틀을 보고 싶으면 `배틀` 버튼을 누르면 창이 열리고 거기서 직접 조작도 가능)
            if (ab and not ab["settled"] and self.g.cfg["mini"] and self.g.cfg["battle_window"] and not ab.get("bw_closed")
                    and (ab.get("user") or self.g.cfg["auto_battle_window"]) and not self.bw_alive()):
                self.open_battle_window()  # 미니 모드에서만 별도 전투 창 (전체 모드는 화면 전환)
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
            self._again(200, self.loop)

    def move_loop(self):
        if self._closing:
            return
        try:
            while self._cmds:
                self.tray_command(self._cmds.popleft())
            now = time.time()
            dt = min(now - self._last_rt, 0.5)
            self.roam_step(dt)
            self.drop_step(dt)
            if not self.g.cfg["mini"] and self.g.battle_running() and now - self._last_bt >= 0.09:
                self._last_bt = now  # 전투 화면은 부드러운 연출을 위해 약 10fps 로 다시 그림
                self.render()
            self._last_rt = now
        except Exception:
            log_exception(*sys.exc_info())
        finally:
            self._again(50, self.move_loop)

    def roam_step(self, dt):
        """미니 모드 + 돌아다니기: 창 자체를 작업표시줄 위를 따라 좌우로 이동."""
        c, s = self.g.cfg, self.g.s
        if not (c["mini"] and c["roam"]) or self.hidden or self._drag:
            self.rx = None
            return
        ab = self.g.active_battle
        busy = s["dead"] or s["stage"] == 0 or s["sleeping"] or (ab and not ab["settled"]) or self.drop
        l, t, r, b = self.work_area()
        cur_x, cur_y = self.root.winfo_x(), self.root.winfo_y()
        if self.rx is None or abs(self.rx - cur_x) > 2:  # 사용자가 옮겼다면 그 자리에서 이어서
            self.rx = float(cur_x)
        lo, hi = l - (MINI_W / 2 - 64), r - (MINI_W / 2 + 64)  # 펫(반폭≈64)이 화면 끝까지 가도록
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
        if s["dead"] or s["sleeping"] or s["stage"] == 0 or self.drop:
            return
        if c["mini"] and c["roam"]:  # 로밍 중에는 펫을 창 가운데에 두고 창을 움직임 (연출 뒤엔 제자리로 돌아옴)
            self.target = MINI_W / 2
            if abs(self.px - self.target) > 3:
                self.face = 1 if self.target > self.px else -1
                self.px += self.face * min(60 * dt, abs(self.target - self.px))
            else:
                self.px = self.target
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

    # ── 아이템 사용 연출: 위에서 떨어지고, 펫이 달려가 먹고(쓰고) 폴짝 ──
    DROP_FALL, DROP_EAT, DROP_WAIT = 0.8, 0.9, 2.5

    # ── 타입별 배경 ──
    def load_bg(self, name):
        for path, pil in self.bg_files.get(name, ()):
            try:
                if pil:
                    with Image.open(path) as im:
                        im = im.convert("RGB")
                        sc = max(BG_W / im.width, BG_H / im.height)
                        im = im.resize((max(BG_W, round(im.width * sc)), max(BG_H, round(im.height * sc))), Image.LANCZOS)
                        x, y = (im.width - BG_W) // 2, (im.height - BG_H) // 2
                        return ImageTk.PhotoImage(im.crop((x, y, x + BG_W, y + BG_H)), master=self.root)
                return tk.PhotoImage(file=path, master=self.root)
            except Exception:  # noqa: BLE001  (깨진 파일 등 → 다음 후보)
                continue
        return None

    def current_bg(self):
        """지금 포켓몬의 주 타입에 맞는 배경 이미지. 타입이 바뀌면 이전 배경은 해제하고 새로 읽음. 없으면 None(기본 배경)."""
        names = [n for n in self.bg_files if n not in self.bg_bad]
        if not names:
            self.bg_name, self.bg_img = None, None
            return None
        typ = (TYPES.get(self.g.s["slug"]) or ("normal",))[0]
        name = bg_for_type(typ, names)
        if name != self.bg_name or self.bg_img is None:
            self.bg_img = None  # 이전 배경 해제
            img = self.load_bg(name)
            if img is None:  # 이 배경이 읽히지 않으면 제외하고 다른 배경으로, 모두 실패하면 기본 배경
                self.bg_bad.add(name)
                return self.current_bg()
            self.bg_name, self.bg_img = name, img
        return self.bg_img

    def drop_floor(self):
        return MINI_FLOOR if self.g.cfg["mini"] else 196

    def start_drop(self):
        g, s = self.g, self.g.s
        while g.fx and not self.drop:
            kind, t = g.fx.pop(0)
            if time.time() - t > 3 or self.hidden or s["dead"] or s["stage"] == 0:
                continue
            c = g.cfg
            lo, hi = (70, MINI_W - 70) if c["mini"] else (80, 240)
            x = self.px + random.choice((-1, 1)) * random.uniform(45, 75)
            if not lo <= x <= hi:
                x = self.px + (60 if self.px - 60 < lo else -60)
            x = min(max(x, lo), hi)
            img = self.cached_image(f"items/{kind}", 28, 4)
            self.drop = dict(kind=kind, x=x, y=-40.0, phase="fall", t0=time.time(), land=None, eat=None, img=img)

    def drop_step(self, dt):
        if not self.drop:
            self.start_drop()
        d = self.drop
        if not d:
            return
        s, now = self.g.s, time.time()
        floor = self.drop_floor()
        if self.hidden or s["dead"]:
            self.drop = None
            return
        if d["phase"] in ("fall", "wait") and not s["sleeping"] and abs(self.px - d["x"]) > 4:
            self.face = 1 if d["x"] > self.px else -1   # 떨어지는 동안 아이템 쪽으로 달려감
            self.px += self.face * min(95 * dt, abs(self.px - d["x"]))
        if d["phase"] == "fall":
            u = (now - d["t0"]) / self.DROP_FALL
            if u >= 1:
                d["y"], d["phase"], d["land"] = floor, "wait", now
            else:
                d["y"] = -40 + (floor + 40) * u * u
        elif d["phase"] == "wait":
            hop = max(0.0, 1 - (now - d["land"]) / 0.3)   # 땅에 닿고 살짝 튕김
            d["y"] = floor - 10 * hop * abs(math.sin((now - d["land"]) * 14))
            if abs(self.px - d["x"]) <= 8 or now - d["land"] > self.DROP_WAIT:
                d["phase"], d["eat"], d["y"] = "eat", now, floor
        elif d["phase"] == "eat" and now - d["eat"] > self.DROP_EAT:
            self.drop = None
        self.render()

    def draw_drop(self, c, scale):
        d = self.drop
        if not d:
            return
        x, y = d["x"], d["y"]
        if d["phase"] == "eat":
            u = (time.time() - d["eat"]) / self.DROP_EAT
            if u < 0.5 and d["img"] and int(u * 16) % 2 == 0:   # 깜빡이며 사라짐
                c.create_image(x, y, image=d["img"], anchor="s")
            if u >= 0.5:  # 다 쓰고 반짝
                for k in range(3):
                    a = u * 6 + k * 2.1
                    c.create_text(self.px + 26 * math.cos(a), self.drop_floor() - 50 - 40 * (u - 0.5) + 10 * k, text="✦",
                                  fill="#ffd84d", font=(FONT, 12, "bold"))
            return
        if d["img"]:
            c.create_image(x, y, image=d["img"], anchor="s")
        else:
            c.create_oval(x - 8, y - 16, x + 8, y, fill="#ffd84d", outline="#a07a00")

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
        night = False  # 낮/밤은 배경색으로 구분하지 않음 (해·달 아이콘)
        self.dex_seen_tick()
        if self.shop_open:
            if g.battle_running() or g.cfg["mini"]:
                self.close_shop()
            else:
                return
        if g.cfg["mini"]:
            self.draw_scene(self.mini, MINI_W, MINI_H, MINI_FLOOR, 8, mini=True, night=night)
        elif g.battle_running():
            if self.bw_alive():
                self.bw.destroy()  # 전체 모드에서는 전투 창 대신 화면 전환
            self.render_battle_screen(g.active_battle)
        else:
            self.set_battle_ui(False)
            self.draw_scene(self.screen, 320, 230, 196, 8, mini=False, night=night)
            age = int(s["total_time"] // 60)
            self.info.config(
                text=f"{g.display_name()} · {g.stage_label()} · {age // 60}시간 {age % 60}분 · "
                     f"{g.s['gen']}세대 · Bits {int(s['bits'])} · 볼 {sum(s['items'].get(k, 0) for k in BALLS)}")
            self.btns["재우기"].config(text="깨우기" if s["sleeping"] else "재우기")

    def draw_actor(self, c, x, floor, scale, slug, tier, color, foe=False, blink=False, bob=0, face=None, shiny=False):
        """펫/적 한 마리를 (x, floor) 발바닥 기준으로 그림. 위쪽 y(머리 꼭대기)를 반환.
        foe에는 적 slug를 넘김(이미지가 없으면 회색 도트)."""
        img = self.custom_image(slug, tier, scale, face, shiny)
        if img:
            c.create_image(x, floor + 4 + bob // 2, image=img, anchor="s")
            return floor - img.height()
        x0 = x - 8 * scale
        y0 = floor - 15 * scale + bob
        for rx, ry, w, col in sprite_runs(BUILTIN_TIER[tier], max(color, 0), blink, foe):
            c.create_rectangle(x0 + rx * scale, y0 + ry * scale,
                               x0 + (rx + w) * scale, y0 + (ry + 1) * scale, fill=col, outline="")
        return y0

    # ── 전투 창: 자동 전투를 작은 창으로 보여 주고, 명령 버튼을 누르면 직접 조작(수동) ──
    BW_W, BW_H, BW_FLOOR, BW_SCALE = 340, 190, 168, 6

    def bw_alive(self):
        w = getattr(self, "bw", None)
        return w is not None and bool(w.winfo_exists())

    def open_battle_window(self):
        ab = self.g.active_battle
        if not ab or ab["settled"] or self.bw_alive():
            return
        g, root = self.g, self.root
        win = self.bw = tk.Toplevel(root)
        win.overrideredirect(True)
        win.configure(bg=SHELL, highlightthickness=2, highlightbackground="#171a21")
        win.attributes("-topmost", True)
        fg, dim = "#e8edf8", "#9fb0d0"

        bar = tk.Frame(win, bg=SHELL)
        bar.pack(fill="x")
        title = tk.Label(bar, text="⚔ 전투  (버튼을 누르면 직접 조작)", bg=SHELL, fg=dim, font=(FONT, 9, "bold"))
        title.pack(side="left", padx=6)

        def close():
            ab2 = g.active_battle
            if ab2:
                ab2["bw_closed"] = True  # 이 전투에서는 다시 열지 않음(전투는 계속 자동 진행)
            win.destroy()

        tk.Button(bar, text="✕", command=close, bg=SHELL, fg=dim, bd=0, width=3, font=(FONT, 9),
                  activebackground=BTN, activeforeground="#fff").pack(side="right")
        drag = {}

        def press(e):
            drag["o"] = (e.x_root - win.winfo_x(), e.y_root - win.winfo_y())

        def move(e):
            if "o" in drag:
                win.geometry(f"+{e.x_root - drag['o'][0]}+{e.y_root - drag['o'][1]}")

        for w in (bar, title):
            w.bind("<ButtonPress-1>", press)
            w.bind("<B1-Motion>", move)

        self.bw_canvas = tk.Canvas(win, width=self.BW_W, height=self.BW_H, highlightthickness=0, bd=0)
        self.bw_canvas.pack()
        self.bw_status = tk.Label(win, bg=SHELL, fg=fg, font=(FONT, 9, "bold"))
        self.bw_status.pack(pady=(4, 0))
        self.bw_hint = tk.Label(win, bg=SHELL, fg=dim, font=(FONT, 8))
        self.bw_hint.pack(pady=(0, 2))

        def mk(parent, text, cmd, width, bg=BTN):
            return tk.Button(parent, text=text, command=cmd, width=width, bg=bg, fg="#fff", bd=0, font=(FONT, 9),
                             activebackground="#6a7390", activeforeground="#fff", disabledforeground="#6b7385")

        row1 = tk.Frame(win, bg=SHELL)
        row1.pack(pady=1)
        self.bw_btns = {}
        for key, text, w in (("attack", "공격", 6), ("skill", "스킬", 8), ("guard", "방어", 5),
                             ("potion", "포션", 6), ("flee", "도망", 5), ("auto", "자동", 5)):
            b = mk(row1, text, lambda k=key: g.battle_command(k), w, "#3b82e0" if key == "attack" else BTN)
            if key != "auto":  # [자동] 버튼은 사용자에게 보이지 않음 (입력이 12초 없으면 자동으로 돌아감)
                b.pack(side="left", padx=2)
            self.bw_btns[key] = b
        row2 = tk.Frame(win, bg=SHELL)
        row2.pack(pady=(1, 6))
        for kind in BALLS:
            b = mk(row2, BALLS[kind][0], lambda k=kind: g.battle_command("ball:" + k), 11)
            b.pack(side="left", padx=2)
            self.bw_btns["ball:" + kind] = b

        # 포커스를 빼앗지 않는 창(WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW): 작업 중인 창이 끊기지 않게
        win.update_idletasks()
        if USER32:
            h = USER32.GetAncestor(win.winfo_id(), 2)
            USER32.SetWindowLongW(h, -20, USER32.GetWindowLongW(h, -20) | 0x08000000 | 0x80)
        # 펫 창 위(없으면 아래)에 띄우되 화면 밖으로 나가지 않게
        l, t, rr, b = self.work_area()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x = min(max(l, root.winfo_x() + root.winfo_width() // 2 - w // 2), max(l, rr - w))
        y = root.winfo_y() - h - 8
        if y < t:
            y = root.winfo_y() + root.winfo_height() + 8
        y = min(max(t, y), max(t, b - h))
        win.geometry(f"+{x}+{y}")
        self.bw_render()

    # ── 스킬 이펙트: 타입별로 날아가는 구간(앞 절반) + 맞는 구간(뒤 절반) ──
    def draw_skill_fx(self, c, typ, f, sx, sy, tx, ty, seed, strong=True):
        """f: 0~1 진행도, (sx,sy)=시전자 위치, (tx,ty)=대상 위치. strong=False 면 기본 공격용 작은 효과."""
        rnd = random.Random(seed)
        col = TYPE_COLOR.get(typ, "#ffffff")
        fly = min(1.0, f / 0.5)
        hit = max(0.0, (f - 0.5) / 0.5)

        def at(u, arc=0.0):
            return sx + (tx - sx) * u, sy + (ty - sy) * u - math.sin(math.pi * u) * arc

        def burst(n, rmax, color, width=3, inner=0.3):
            for k in range(n):
                a = 2 * math.pi * k / n + rnd.random() * 0.3
                r0, r1 = rmax * hit * inner, rmax * hit
                c.create_line(tx + math.cos(a) * r0, ty + math.sin(a) * r0, tx + math.cos(a) * r1, ty + math.sin(a) * r1,
                              fill=color, width=width)

        def dot(x, y, r, color, outline=""):
            c.create_oval(x - r, y - r, x + r, y + r, fill=color, outline=outline)

        if not strong or typ in (None, "normal"):
            if hit > 0:
                burst(8, 34, "#ffffff", 3)
                burst(8, 22, "#ffe36b", 2, 0.1)
            return
        if typ == "fire":
            if fly < 1 and f < 0.5:
                for i in range(5):
                    x, y = at(max(0.0, fly - i * 0.08), 14)
                    dot(x, y, 9 - i, ("#ffd23c", "#ffb02e", "#f08030", "#e0482a", "#a02818")[i])
            for k in range(7):
                if hit > 0:
                    bx = tx + (k - 3) * 11
                    h = 46 * hit * (1 - 0.35 * hit) * (0.7 + 0.3 * rnd.random())
                    c.create_polygon(bx - 8, ty + 18, bx, ty + 18 - h, bx + 8, ty + 18, fill="#f08030" if k % 2 else "#ffb02e", outline="")
        elif typ == "water":
            if f < 0.5:
                for i in range(7):
                    x, y = at(max(0.0, fly - i * 0.07), 18)
                    dot(x, y, 6 - i * 0.4, "#6890f0" if i % 2 else "#a8c8ff")
            for k in range(10):
                if hit > 0:
                    a = math.pi * (k / 9)
                    dot(tx + math.cos(a) * hit * 42, ty - math.sin(a) * hit * 34 + hit * 12, 5 * (1 - hit * 0.5), "#8fb4ff")
        elif typ == "electric":
            if f < 0.8:
                rj = random.Random(seed + int(f * 18))
                pts = [(sx, sy)]
                for i in range(1, 8):
                    u = i / 8
                    x, y = at(u)
                    pts.append((x + rj.uniform(-14, 14), y + rj.uniform(-14, 14)))
                pts.append((tx, ty))
                flat = [v for p in pts for v in p]
                c.create_line(*flat, fill="#f8d030", width=5)
                c.create_line(*flat, fill="#ffffff", width=2)
            if hit > 0:
                burst(10, 40, "#f8d030", 3, 0.2)
        elif typ == "grass":
            if f < 0.5:
                for i in range(6):
                    x, y = at(max(0.0, fly - i * 0.07), 16)
                    c.create_oval(x - 9, y - 4 - i % 2 * 2, x + 9, y + 4, fill="#78c850" if i % 2 else "#a8e070", outline="#3c7a28")
            for k in range(8):
                if hit > 0:
                    a = 2 * math.pi * k / 8
                    x, y = tx + math.cos(a) * hit * 38, ty + math.sin(a) * hit * 30
                    c.create_oval(x - 8, y - 3, x + 8, y + 3, fill="#78c850", outline="#3c7a28")
        elif typ == "ice":
            if f < 0.5:
                for i in range(4):
                    x, y = at(max(0.0, fly - i * 0.1), 8)
                    c.create_polygon(x, y - 10, x + 7, y, x, y + 10, x - 7, y, fill="#98d8d8", outline="#ffffff")
            if hit > 0:
                burst(8, 40, "#d8f8ff", 3)
                for k in range(6):
                    a = 2 * math.pi * k / 6 + 0.4
                    x, y = tx + math.cos(a) * hit * 26, ty + math.sin(a) * hit * 26
                    c.create_polygon(x, y - 8, x + 5, y, x, y + 8, x - 5, y, fill="#98d8d8", outline="#ffffff")
        elif typ == "fighting":
            if f < 0.5:
                x, y = at(fly)
                c.create_line(x - 26, y, x, y, fill="#c03028", width=6)
            if hit > 0:
                burst(10, 46, "#c03028", 5, 0.1)
                burst(10, 30, "#ffffff", 2, 0.1)
                c.create_text(tx, ty - 30 * hit, text="!!", fill="#ffffff", font=(FONT, 18, "bold"))
        elif typ == "poison":
            if f < 0.5:
                for i in range(4):
                    x, y = at(max(0.0, fly - i * 0.1), 12)
                    dot(x, y, 8 - i, "#a040a0", "#d890e0")
            for k in range(8):
                if hit > 0:
                    dot(tx + (k - 3.5) * 9, ty + 16 - hit * (24 + 14 * rnd.random()) , 4 + rnd.random() * 4, "#b060c0", "#e0a8f0")
        elif typ == "ground":
            if f < 0.5:
                c.create_line(sx, ty + 28, sx + (tx - sx) * fly, ty + 28 + math.sin(fly * 40) * 3, fill="#a8884a", width=5)
            for k in range(6):
                if hit > 0:
                    h = 40 * min(1.0, hit * 1.6) * (0.6 + 0.4 * rnd.random()) * (1 - max(0, hit - 0.7) * 2)
                    bx = tx + (k - 2.5) * 12
                    c.create_polygon(bx - 7, ty + 28, bx, ty + 28 - h, bx + 7, ty + 28, fill="#c8a860", outline="#7a5a28")
        elif typ == "flying":
            if f < 0.6:
                for i in range(3):
                    x, y = at(max(0.0, fly - i * 0.12), 20)
                    c.create_arc(x - 16, y - 12, x + 16, y + 12, start=200, extent=140, style="arc", outline="#e8e0ff", width=4)
            if hit > 0:
                for k in range(3):
                    c.create_arc(tx - 36, ty - 30 + k * 10, tx + 36, ty + 30 + k * 10, start=30 + k * 40, extent=90, style="arc", outline="#ffffff", width=3)
        elif typ == "psychic":
            x, y = at(fly)
            if f < 0.5:
                dot(x, y, 8 + 3 * math.sin(f * 40), "#f85888", "#ffffff")
            for k in range(3):
                if hit > 0:
                    r = (hit + k * 0.25) % 1.0 * 48
                    c.create_oval(tx - r, ty - r, tx + r, ty + r, outline="#f85888" if k % 2 else "#c8a0ff", width=3)
        elif typ == "bug":
            for k in range(14):
                u = min(1.0, fly + rnd.uniform(-0.15, 0.0)) if f < 0.5 else 1.0
                x, y = at(u, 6)
                if f >= 0.5:
                    a = rnd.random() * 6.28 + f * 12
                    x, y = tx + math.cos(a) * 26 * hit, ty + math.sin(a) * 22 * hit
                dot(x + rnd.uniform(-10, 10), y + rnd.uniform(-10, 10), 3, "#a8b820" if k % 2 else "#e8f060")
        elif typ == "rock":
            drop = (1 - min(1.0, f / 0.6))
            for k in range(4):
                x = tx + (k - 1.5) * 18
                y = ty - 14 - 130 * drop * (0.7 + 0.1 * k)
                c.create_polygon(x - 10, y + 8, x - 6, y - 8, x + 8, y - 6, x + 11, y + 6, fill="#b8a038", outline="#6a5a18")
            if hit > 0:
                burst(8, 34, "#b8a038", 3)
        elif typ == "ghost":
            if f < 0.5:
                for i in range(3):
                    x, y = at(max(0.0, fly - i * 0.12), 10)
                    dot(x, y, 9 - i * 2, "#705898", "#2b1646")
                    if i == 0:
                        dot(x - 3, y - 1, 2, "#ffffff")
                        dot(x + 3, y - 1, 2, "#ffffff")
            for k in range(3):
                if hit > 0:
                    r = (hit * 44) * (0.5 + 0.25 * k)
                    c.create_oval(tx - r, ty - r * 0.8, tx + r, ty + r * 0.8, outline="#705898", width=3)
        elif typ == "dragon":
            if f < 0.6:
                for i in range(6):
                    x, y = at(max(0.0, fly - i * 0.07), 10)
                    dot(x, y, 12 - i, ("#7038f8", "#5b8def", "#a060ff", "#e0482a", "#ffb02e", "#ffd23c")[i])
            if hit > 0:
                for k in range(3):
                    r = hit * (30 + 14 * k)
                    c.create_oval(tx - r, ty - r, tx + r, ty + r, outline=("#7038f8", "#a060ff", "#e0482a")[k], width=4)
        elif typ == "dark":
            if hit > 0 or f > 0.35:
                p = max(hit, 0.2)
                c.create_arc(tx - 40, ty - 40, tx + 40, ty + 40, start=30, extent=int(110 * p), style="arc", outline="#1b1018", width=8)
                c.create_arc(tx - 40, ty - 40, tx + 40, ty + 40, start=30, extent=int(110 * p), style="arc", outline="#a050d0", width=3)
                c.create_arc(tx - 40, ty - 40, tx + 40, ty + 40, start=210, extent=int(110 * p), style="arc", outline="#1b1018", width=8)
                c.create_arc(tx - 40, ty - 40, tx + 40, ty + 40, start=210, extent=int(110 * p), style="arc", outline="#a050d0", width=3)
            if f < 0.5:
                x, y = at(fly, 10)
                dot(x, y, 8, "#403048", "#a050d0")
        elif typ == "steel":
            if hit > 0 or f > 0.3:
                p = max(hit, 0.3)
                for k in range(3):
                    c.create_line(tx - 40 + k * 8, ty - 36 + k * 6, tx - 40 + k * 8 + 84 * p, ty - 36 + k * 6 + 72 * p, fill="#e8e8f8", width=4)
                    c.create_line(tx - 40 + k * 8, ty - 36 + k * 6, tx - 40 + k * 8 + 84 * p, ty - 36 + k * 6 + 72 * p, fill="#8890a8", width=1)
            if hit > 0:
                burst(6, 30, "#ffe36b", 2, 0.3)
        elif typ == "fairy":
            if f < 0.5:
                for i in range(5):
                    x, y = at(max(0.0, fly - i * 0.09), 14)
                    c.create_text(x, y, text="✦", fill="#ffb0d0", font=(FONT, 14 - i))
            for k in range(8):
                if hit > 0:
                    a = 2 * math.pi * k / 8 + hit * 3
                    x, y = tx + math.cos(a) * hit * 40, ty + math.sin(a) * hit * 34 - hit * 10
                    c.create_text(x, y, text="♥" if k % 2 else "✦", fill="#ee99ac" if k % 2 else "#ffffff", font=(FONT, 13))
        else:
            if hit > 0:
                burst(8, 34, col, 3)

    def draw_type_chips(self, c, x, y, types):
        for t in types:
            w = 12 + 9 * len(TYPE_KO[t])
            c.create_rectangle(x, y, x + w, y + 12, fill=TYPE_COLOR[t], outline="")
            c.create_text(x + w / 2, y + 6, text=TYPE_KO[t], fill="#ffffff", font=(FONT, 7, "bold"))
            x += w + 3

    def battle_message(self, ab, now):
        res = ab["result"]
        if ab["phase"] == "intro":
            return f"야생의 {ab['foe']}이(가) 나타났다!"
        if ab["phase"] == "outro" or ab["settled"]:
            if res == "win":
                return f"승리! +{ab['reward']} Bits"
            return {"captured": f"{ab['foe']} 포획 성공!", "fled": "무사히 도망쳤다!"}.get(res, "패배…")
        ev = ab["events"][-1] if ab["events"] else None
        if ev and ev["kind"] == "ball" and now < ev["t0"] + ev["dur"]:
            return "볼이 흔들린다…"
        if now - ab["fail_t"] < 1.3 and ab["fail_t"]:
            return "앗! 빠져나왔다!"
        if ev and ev["kind"] == "flee" and ev["ok"] is False and now < ev["t0"] + ev["dur"] + 0.8:
            return "도망칠 수 없었다!"
        if ev and ev["mult"] is not None and ev["t0"] + ev["dur"] * 0.45 <= now < ev["t0"] + ev["dur"] + 0.9:
            who = ab["foe"] if ev["who"] == "foe" else self.g.name()
            name = SKILL_KO.get(ev["type"], "공격")
            if ev["kind"] == "miss":
                return f"{who}의 {name}! 빗나갔다…"
            m = ev["mult"]
            tail = ("효과가 굉장했다!" if m >= 2 else "효과가 별로인 듯하다…" if 0 < m < 1 else
                    "효과가 없는 듯하다…" if m == 0 else "")
            return f"{who}의 {name}! {tail}".strip()
        return "무엇을 할까?" if ab["manual"] else "자동 전투 중…"

    def battle_visual(self, ab, now):
        """현재 시각의 연출 값(돌진/흔들림/체력 표시/볼/숨김/스킬 이펙트)."""
        v = dict(pet_dx=0.0, foe_dx=0.0, pet_off=0.0, foe_off=0.0, pet_hp=ab["pet_hp"], foe_hp=ab["foe_hp"],
                 pop=None, ball=None, foe_visible=True, pet_blink=False, foe_blink=False, shield=False, fx=None)
        if ab["phase"] == "intro":
            v["foe_off"] = max(0.0, 1 - (now - ab["start"]) / BATTLE_IN) * 220
        ev = ab["events"][-1] if ab["events"] else None
        if ev:
            f = (now - ev["t0"]) / ev["dur"]
            kind, who, tgt = ev["kind"], ev["who"], ev["tgt"]
            if 0 <= f < 1:
                if kind in ("attack", "skill", "blocked", "miss"):
                    v[who + "_dx"] = math.sin(math.pi * min(1.0, f * 1.6)) * (22 if ev["type"] else 40) * (1 if who == "pet" else -1)
                    v["fx"] = (ev["type"], f, who, ev["t0"], kind in ("skill", "attack", "blocked") and ev["type"] is not None, kind)
                    if f >= 0.5:
                        if kind == "miss":
                            v["pop"] = (tgt, "MISS", f, "#8a93a6")
                        else:
                            v[tgt + "_blink"] = True
                            v[tgt + "_dx"] += math.sin(f * 60) * (1 - f) * 6
                            col = "#3b82e0" if kind == "blocked" else ("#ff3b3b" if (ev["mult"] or 1) >= 1 else "#9aa3b5")
                            txt = f"-{ev['dmg']}" + ("!" if (ev["mult"] or 1) >= 2 else "")
                            v["pop"] = (tgt, txt, f, col)
                    elif ev["dmg"]:  # 맞기 전에는 체력이 아직 그대로
                        v[tgt + "_hp"] = min(100.0, v[tgt + "_hp"] + ev["dmg"])
                elif kind in ("guard", "heal"):
                    v["shield"] = kind == "guard"
                    heal = -ev["dmg"]
                    if f < 0.5:
                        v["pet_hp"] = max(0.0, v["pet_hp"] - heal)
                    v["pop"] = ("pet", f"+{heal}" if heal else "GUARD", f, "#2fb86a")
                elif kind == "ball":
                    v["ball"], v["foe_visible"] = (ev, now - ev["t0"]), False
                elif kind == "flee":
                    v["pet_off"] = -f * 220 if ev["ok"] else math.sin(f * 40) * 6
        if ab["captured"] and not v["ball"]:
            v["foe_visible"] = False
        if ab["phase"] == "outro":
            e = now - ab["t_outro"]
            if ab["result"] == "win":
                v["foe_blink"] = True
                v["foe_visible"] = e < 1.0
            elif ab["result"] == "lose":
                v["pet_blink"] = True
            elif ab["result"] == "fled":
                v["pet_off"] = -min(e, 1.0) * 260
        return v

    def draw_battle_scene(self, c, ab, now, W=None, H=None, floor=None, scale=None, bg=None):
        W, H, floor, scale = W or self.BW_W, H or self.BW_H, floor or self.BW_FLOOR, scale or self.BW_SCALE
        c.delete("all")
        if bg:  # 전체 모드 전투 화면: 현재 포켓몬의 타입 배경 위에 그림
            c.create_image(0, 0, image=bg, anchor="nw")
            c.create_rectangle(0, 0, W, 44, fill="#0b1018", outline="")
        else:
            c.create_rectangle(0, 0, W, H, fill="#dff0ff", outline="")
            c.create_rectangle(0, floor, W, H, fill="#b9d99a", outline="")
        s, v = self.g.s, self.battle_visual(ab, now)
        px = W * 0.27 + v["pet_dx"] + v["pet_off"]
        fx = W * 0.74 + v["foe_off"] + v["foe_dx"]
        if v["foe_visible"] and not (v["foe_blink"] and int(now * 10) % 2):
            self.draw_actor(c, fx, floor, scale, ab["slug"], ab["stage"], ab["line"], foe=True, face=-1)
        if not (v["pet_blink"] and int(now * 10) % 2):
            self.draw_actor(c, px, floor, scale, s["slug"], s["stage"], s["line"], face=1, shiny=s["shiny"])
        if v["shield"]:
            c.create_oval(px - 62, floor - 100, px + 62, floor + 6, outline="#3b82e0", width=3)
        if v["fx"]:  # 스킬 이펙트(타입별)
            typ, f, who, t0, strong, kind = v["fx"]
            ox, oy = (px, floor - 50) if who == "pet" else (fx, floor - 50)
            tx_, ty_ = (fx, floor - 50) if who == "pet" else (px, floor - 50)
            self.draw_skill_fx(c, typ, f, ox, oy, tx_, ty_, int(t0 * 1000) % 100000, strong=strong and kind != "miss")
            if typ and f < 0.45 and kind != "miss":
                c.create_text(ox, floor - 118, text=SKILL_KO.get(typ, ""), fill=TYPE_COLOR.get(typ, "#fff"),
                              font=(FONT, 11, "bold"))
        if v["ball"]:  # 볼: 날아가서 상대를 빨아들이고 흔들린 뒤 결과
            ev, tp = v["ball"]
            r = 10
            if tp < 0.5:
                u = tp / 0.5
                self.draw_ball(c, px + (fx - px) * u, floor - 40 - math.sin(math.pi * u) * 50, r, ev["ball"], u * 6)
            else:
                wob = math.sin((tp - 0.5) * 9) * 5 if tp < CATCH_T - 0.4 else 0
                self.draw_ball(c, fx + wob, floor - r + 2, r, ev["ball"], wob)
                if tp >= CATCH_T - 0.4 and ev["ok"]:
                    c.create_text(fx, floor - 40, text="★", fill="#ffd23c", font=(FONT, 20, "bold"))
        elif ab["captured"]:
            last = next((e for e in reversed(ab["events"]) if e["kind"] == "ball"), None)
            self.draw_ball(c, fx, floor - 8, 10, last["ball"] if last else "ball")
        if v["pop"]:
            tgt, text, f, col = v["pop"]
            x = fx if tgt == "foe" else px
            c.create_text(x, floor - 96 - f * 22, text=text, fill=col, font=(FONT, 14, "bold"))
        fg = "#fff" if bg else "#222"
        for x, name, hp, col, types in ((10, self.g.display_name(), v["pet_hp"], "#43b36b", ab["pet_types"]),
                                        (W - 110, ab["foe"], v["foe_hp"], "#e0483c", ab["foe_types"])):
            c.create_text(x, 12, text=name, anchor="w", font=(FONT, 8, "bold"), fill="#ff5a5a" if name.startswith("강적") else fg)
            c.create_rectangle(x, 20, x + 100, 28, fill="#444", outline="#111")
            c.create_rectangle(x, 20, x + 100 * max(0, hp) / 100, 28, fill=col, outline="")
            self.draw_type_chips(c, x, 31, types)
        self.draw_bubble(c, W // 2, 62, self.battle_message(ab, now))

    def battle_ui_update(self, ab, now, btns):
        """전투 명령 버튼의 문구/활성 상태를 갱신하고 (상태 문장, 상성 힌트)를 돌려줌."""
        g = self.g
        can = ab["phase"] != "outro" and not ab["result"]
        for key, b in btns.items():
            if key.startswith("ball:"):
                k = key[5:]
                n = g.s["items"].get(k, 0)
                b.config(text=f"{BALLS[k][0]}({n})", state="normal" if can and n > 0 else "disabled")
            elif key == "potion":
                n = g.s["items"].get("potion", 0) + g.s["items"].get("super_potion", 0)
                b.config(text=f"포션({n})", state="normal" if can and n > 0 else "disabled")
            elif key == "skill":
                b.config(text=f"스킬({ab['pp']})", state="normal" if can and ab["pp"] > 0 else "disabled")
            elif key == "auto":
                b.config(state="normal" if ab["manual"] else "disabled")
            else:
                b.config(state="normal" if can else "disabled")
        if ab["manual"] and ab["phase"] == "choose" and not ab["pending"]:
            left = max(0, int(MANUAL_TIMEOUT - (now - ab["last_input"])) + 1)
            txt = f"내 차례! 명령을 고르세요 ({left}초 뒤 자동)"
        elif ab["pending"]:
            txt = "다음 차례에 실행합니다…"
        elif ab["manual"]:
            txt = "직접 조작 중"
        else:
            txt = "자동 전투 중 — 버튼을 누르면 직접 조작"
        st_t, st_m = g.skill_type(ab), g.skill_mult(ab)
        word = "굉장함" if st_m >= 2 else "별로" if 0 < st_m < 1 else "효과 없음" if st_m == 0 else "보통"
        return txt, f"스킬: {SKILL_KO[st_t]} [{TYPE_KO[st_t]}] → 상성 ×{st_m:g} ({word}) · 공격은 상성 없음"

    def set_battle_ui(self, on):
        """아래 버튼 줄을 평소 버튼 ↔ 전투 명령 버튼으로 바꿈."""
        if on == self._bui:
            return
        self._bui = on
        if on:
            self.grid.pack_forget()
            self.bgrid.pack(pady=self.grid_pad)
        else:
            self.bgrid.pack_forget()
            self.grid.pack(pady=self.grid_pad)

    def render_battle_screen(self, ab):
        """전체 모드: 도감 틀의 게임 화면이 전투 화면으로 바뀜 (자동 전투든 직접 시작한 전투든)."""
        self.set_battle_ui(True)
        now = self.g.clock()
        self.draw_battle_scene(self.screen, ab, now, 320, 230, 200, 6, bg=self.current_bg())
        txt, hint = self.battle_ui_update(ab, now, self.sb_btns)
        self.info.config(text=txt)

    def bw_render(self):
        win = getattr(self, "bw", None)
        if win is None or not win.winfo_exists():
            return
        try:
            g, ab, now = self.g, self.g.active_battle, self.g.clock()
            if not ab or ab["settled"]:
                win.destroy()
                return
            self.draw_battle_scene(self.bw_canvas, ab, now)
            txt, hint = self.battle_ui_update(ab, now, self.bw_btns)
            self.bw_status.config(text=txt)
            self.bw_hint.config(text=hint)
        except Exception:
            log_exception(*sys.exc_info())
        finally:
            if win.winfo_exists():
                win.after(100, self.bw_render)

    def draw_ball(self, c, x, y, r, kind, tilt=0.0):
        top = "#e0483c" if kind == "ball" else "#3b82e0"
        c.create_arc(x - r, y - r, x + r, y + r, start=0, extent=180, fill=top, outline="#222", width=2)
        c.create_arc(x - r, y - r, x + r, y + r, start=180, extent=180, fill="#f4f4f4", outline="#222", width=2)
        c.create_line(x - r, y, x + r, y, fill="#222", width=2)
        c.create_oval(x - r / 3 + tilt, y - r / 3, x + r / 3 + tilt, y + r / 3, fill="#fff", outline="#222", width=2)

    @staticmethod
    def is_night():
        return not (6 <= time.localtime().tm_hour < 20)

    def sky_icon(self, night):
        """낮=해, 밤=달 도트 아이콘(투명 배경, 28x28). 한 번 만들어 재사용."""
        key = ("sky", night)
        if key not in self.img_cache:
            n = 14
            img = tk.PhotoImage(width=n, height=n)
            cx = cy = (n - 1) / 2
            for y in range(n):
                for x in range(n):
                    dx, dy = x - cx, y - cy
                    r = math.hypot(dx, dy)
                    col = None
                    if night:  # 초승달: 큰 원에서 오른쪽 위로 어긋난 원을 뺀 모양
                        if r <= 6.3:
                            if math.hypot(dx - 3.2, dy + 2.4) > 5.2:
                                col = "#fff3b0" if r < 5.4 else "#c9b458"
                    else:
                        if r <= 3.6:
                            col = "#ffd23c" if r < 2.8 else "#d99a00"
                        elif 4.6 <= r <= 6.6 and (abs(dx) < 0.8 or abs(dy) < 0.8 or abs(abs(dx) - abs(dy)) < 0.8):
                            col = "#ffb020"   # 햇살(8방향)
                    if col:
                        img.put(col, (x, y))
            self.img_cache[key] = img   # 14x14 (예전 크기의 절반)
        return self.img_cache[key]

    def draw_scene(self, c, W, H, floor, scale, mini, night):
        g, s = self.g, self.g.s
        c.delete("all")
        if not mini:
            bg = self.current_bg() if self.page == "main" else None
            band = 60 if self.exp_shown() else 36   # 상태바 띠 높이 (경험치 줄이 없으면 짧게)
            if bg:
                c.create_image(0, 0, image=bg, anchor="nw")
            else:
                c.create_rectangle(0, 0, W, H, fill="#dff0ff", outline="")   # 낮/밤은 배경색이 아니라 해·달 아이콘으로 구분
                c.create_rectangle(0, floor, W, H, fill="#b9d99a", outline="")
            if self.page == "stats":
                return self.draw_stats(c, night)
            if self.page == "dex":
                return self.draw_dex(c, night)
            c.create_rectangle(0, 0, W, band, fill="#0b1018", outline="")   # 상태바: 어두운 색 100%
            self.draw_bars(c, True)
            night_now = self.is_night()   # 오른쪽 위 해/달 (배경과 겹쳐도 보이도록 둥근 판을 깔음)
            iy = band + 14
            c.create_oval(W - 27, iy - 11, W - 5, iy + 11, fill="#1d2740" if night_now else "#5aa8e8", outline="#ffffff", width=1)
            c.create_image(W - 16, iy, image=self.sky_icon(night_now), anchor="center")

        t = time.time()
        top = floor - 15 * scale
        if s["dead"]:
            self.draw_grave(c, self.px, floor)
        else:
            blink = s["sleeping"] or int(t * 2) % 9 == 0
            bob = scale if (int(t * 2.5) % 2 and not s["sleeping"]) else 0
            if self.drop and self.drop["phase"] == "eat":  # 아이템을 쓰며 폴짝폴짝
                bob = -int(abs(math.sin((t - self.drop["eat"]) * 11)) * scale * 2)
            wig = int(t * 6) % 2 * 3 - 1 if s["stage"] == 0 else 0
            y0 = self.draw_actor(c, self.px + wig, floor, scale, s["slug"], s["stage"], s["line"], blink=blink,
                                 bob=bob, face=self.face, shiny=s.get("shiny", False))
            top = y0
            if s["sick"]:
                c.create_text(self.px + 50, y0 + 20, text="+", fill="#4caf50", font=(FONT, 20, "bold"))

        self.draw_drop(c, scale)
        text = self.bubble_text()
        if text:
            self.draw_bubble(c, self.px, (top if top is not None else floor - 15 * scale) - 10, text)

        for h in self.hearts[:]:
            h[1] -= 1.5
            h[2] -= 0.04
            if h[2] <= 0:
                self.hearts.remove(h)
            else:
                c.create_text(h[0], h[1], text="♥", fill="#ff5c8a", font=(FONT, 11, "bold"))

        if not mini:
            if g.log and time.time() - g.log[-1][0] < 15:   # 메시지가 나올 때만 아래 줄(어두운 색 100%)을 깔음
                c.create_rectangle(0, H - 26, W, H, fill="#0b1018", outline="")
                c.create_text(W // 2, H - 13, text=g.log[-1][1], font=(FONT, 9, "bold"), fill="#fff")
            if s["dead"]:
                c.create_text(W // 2, band + 30, text="클릭하면 새 알을 받아요", font=(FONT, 10, "bold"), fill="#ff8a8a")

    STAGE_H = [56, 72, 90, 112]  # 단계(tier)별 화면상 목표 높이(scale 8 기준)

    def custom_image(self, slug, tier, scale, face=None, shiny=False):
        """sprites/mons/{slug}.png 를 단계별 목표 높이에 맞춰 정수배 확대. 없으면 None(내장 도트)."""
        native = 1 if slug in FACING_RIGHT else -1
        flip = face is not None and face != native  # 가는 방향을 바라보도록 좌우 반전
        h = self.STAGE_H[tier] * scale // 8
        img = self.cached_image(f"mons/shiny/{slug}", h, scale, flip) if shiny else None
        return img or self.cached_image(f"mons/{slug}", h, scale, flip)

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
        if self.g.egg_waiting():
            return "알을 눌러 계통 선택권 사용 여부를 정해요"
        if self.g.battle_running():
            return "⚔ 전투 중!"
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

    def exp_shown(self):
        """경험치 글자/막대는 진화할 다음 단계가 있을 때만 보임 (최종 단계·알이면 숨김)."""
        s = self.g.s
        return s["stage"] > 0 and EXP_NEED.get(s["stage"] + 1) is not None

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
        if self.exp_shown():  # 경험치: 진화 조건(시간과 함께). 최종 단계에서는 숨김
            need = EXP_NEED.get(s["stage"] + 1)
            frac = min(1.0, s["exp"] / need)
            label = f"경험치 {int(s['exp'])}/{need}"
            c.create_text(8, 41, text=label, anchor="w", font=(FONT, 8), fill=fg)
            c.create_rectangle(8, 48, 308, 54, fill="#8896a8" if not night else "#444", outline="")
            c.create_rectangle(8, 48, 8 + 300 * frac, 54, fill="#e0a82e" if frac >= 1 else "#5b8def", outline="")

    def draw_grave(self, c, x, floor):
        c.create_rectangle(x - 30, floor - 70, x + 30, floor, fill="#8d949e", outline="#4a4f57", width=3)
        c.create_oval(x - 30, floor - 90, x + 30, floor - 50, fill="#8d949e", outline="#4a4f57", width=3)
        c.create_rectangle(x - 27, floor - 62, x + 27, floor - 3, fill="#8d949e", outline="")
        c.create_text(x, floor - 45, text="RIP", font=(FONT, 14, "bold"), fill="#3a3f47")

    def dex_seen_tick(self):
        """도감을 열었다가 닫으면(어느 쪽을 봤든) 새 포켓몬 ✨ 표시를 모두 지움."""
        g = self.g
        cur = self.dex_page if (self.page == "dex" and not g.cfg["mini"] and not g.battle_running()
                                and not self.shop_open) else None
        if cur != self._dex_prev:
            if self._dex_prev is not None and cur is None:
                g.s["new_dex"] = []  # 도감을 열었다가 닫으면 새 포켓몬 ✨ 표시를 모두 지움
            self._dex_prev, self._dex_t0 = cur, time.time()
        if "도감" in self.btns:
            self.btns["도감"].config(text="도감✨" if g.s["new_dex"] else "도감")

    def draw_dex(self, c, night):
        """도감 151종(15칸씩 페이지): 포획한 포켓몬은 그림+이름+횟수, 키워 본 포켓몬은 '육성', 아직이면 ???."""
        s = self.g.s
        dex, raised = s["dex"], s.get("raised", {})
        fg = "#eee" if night else "#2d3b1f"
        per = 15
        pages = (len(DEX_ORDER) + per - 1) // per
        self.dex_page = max(0, min(self.dex_page, pages - 1))
        caught = sum(1 for sl in DEX_ORDER if sl in dex)
        grown = sum(1 for sl in DEX_ORDER if sl in raised and sl not in dex)
        c.create_text(12, 12, text=f"포켓몬 도감 {caught}/{len(DEX_ORDER)} · 육성 {grown}", anchor="w",
                      font=(FONT, 10, "bold"), fill=fg)
        c.create_text(308, 12, text=f"포획 {sum(dex.values())}마리", anchor="e", font=(FONT, 8), fill=fg)
        cw, ch, cols = 64, 58, 5
        for i, sl in enumerate(DEX_ORDER[self.dex_page * per:(self.dex_page + 1) * per]):
            x0, y0 = 4 + (i % cols) * cw, 24 + (i // cols) * ch
            got = sl in dex or sl in raised
            c.create_rectangle(x0 + 2, y0, x0 + cw - 2, y0 + ch - 4, fill="#ffffff" if got else "#c9d3dd",
                               outline="#8896a8" if not night else "#556", stipple="" if got else "gray50")
            cx = x0 + cw / 2
            num = DEX_ORDER.index(sl) + 1
            c.create_text(x0 + 6, y0 + 7, text=f"#{num:03d}", anchor="w", font=(FONT, 6), fill="#667")
            img = self.cached_image(f"mons/{sl}", 30, 4) if got else None
            if img:
                c.create_image(cx, y0 + 38, image=img, anchor="s")
            else:
                c.create_text(cx, y0 + 24, text="?", font=(FONT, 16, "bold"), fill="#8896a8")
            c.create_text(cx, y0 + 43, text=KO[sl] if got else "???", font=(FONT, 8, "bold"), fill="#222" if got else "#667")
            if sl in s.get("new_dex", ()):  # 아직 확인 안 한 새 포켓몬: 반짝이는 표시
                c.create_text(x0 + cw - 12, y0 + 9, text="✨" if int(time.time() * 2) % 2 else "✦",
                              font=("Segoe UI Emoji", 11), fill="#ffb400")
            if sl in dex:
                c.create_text(cx, y0 + 52, text=f"×{dex[sl]}", font=(FONT, 7), fill="#c0392b")
            elif got:
                c.create_text(cx, y0 + 52, text="육성", font=(FONT, 7), fill="#2e8b57")
        c.create_text(70, 217, text="◀", font=(FONT, 13, "bold"), fill=fg)
        c.create_text(160, 217, text=f"{self.dex_page + 1} / {pages}  (휠로도 넘김)", font=(FONT, 8), fill=fg)
        c.create_text(250, 217, text="▶", font=(FONT, 13, "bold"), fill=fg)

    def dex_nav(self, e):
        """도감 화면에서 아래쪽 ◀ ▶ 영역을 누르면 페이지 이동. 처리했으면 True."""
        if self.page != "dex" or e.y < 200:
            return False
        step = -1 if e.x < 120 else (1 if e.x > 200 else 0)
        pages = (len(DEX_ORDER) + 14) // 15
        self.dex_page = (self.dex_page + step) % pages
        return True

    def draw_stats(self, c, night):
        g, s = self.g, self.g.s
        t = s["train"]
        types = " / ".join(TYPE_KO[x] for x in TYPES.get(s["slug"], ()))
        rar = s.get("rarity", "C")
        lines = [
            f"{g.display_name()}  ({g.stage_label()})  {s['gen']}세대",
            f"타입 {types or '-'}   등급 {RARITY_STARS[rar]} {RARITY_KO[rar]}" + ("   ✨이로치(전투력 +3)" if s.get("shiny") else ""),
            f"배고픔 {int(s['hunger'])}   친밀도 {int(s['happy'])}   기력 {int(s['energy'])}   체력 {int(s['hp'])}",
            f"힘 {t['power']:.0f}  속도 {t['speed']:.0f}  지능 {t['mind']:.0f}   전투력 {g.power():.0f}   케어미스 {s['care_miss']}",
            f"전적 {s['wins']}승 {s['losses']}패   Bits {int(s['bits'])}",
            f"다음 진화: {g.next_evo()}",
            "가방: " + (" · ".join(f"{item_label(k)} {n}" for k, n in s["items"].items() if n > 0 and (k in SHOP or k in STONES))
                      or "비어 있음"),
            f"도감 {sum(1 for k in s['dex'] if k in DEX_ORDER)}/{len(DEX_ORDER)}종 (전투력 +{len(s['dex']) * DEX_POWER:.1f})",
            ("진화: 변함없는 돌 사용 중 (진화 정지)" if s["everstone"] else
             (f"진화: {item_label(s['stone'])} 사용 → 조건이 차면 {KO[STONE_FORM[s['stone']]]}" if s["stone"] else
              (("진화: 번개의 돌 필요" if s["slug"] == "pikachu" else "진화: 진화의 돌 필요 (불/물/번개의 돌)") if g.needs_stone() else "진화: 정상"))),
        ]
        if s["happy"] < LOW_BOND:
            lines[1] += "  ⚠ 친밀도 낮음: 전투 -25%"
        fg = "#eee" if night else "#2d3b1f"
        for i, ln in enumerate(lines):
            c.create_text(14, 16 + i * 22, text=ln, anchor="w", font=(FONT, 9, "bold" if i == 0 else "normal"), fill=fg)
        if s["everstone"]:  # 변함없는 돌 해제 버튼 (on_click 에서 이 영역을 처리)
            c.create_rectangle(100, 206, 250, 226, fill="#3b82e0", outline="#1d4fa0")
            c.create_text(175, 216, text="변함없는 돌 해제 (진화 재개)", fill="#ffffff", font=(FONT, 8, "bold"))

    def quit(self):
        self._closing = True
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
