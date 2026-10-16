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
import sys
import time
import tkinter as tk
from tkinter import messagebox

try:
    import winsound
except ImportError:  # 비윈도우
    winsound = None

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE = os.path.join(HERE, "save.json")
FAST = 60 if "--fast" in sys.argv else 1
KEY = "#ff00ff"  # 투명 처리 색
FONT = "Malgun Gothic"
MAX_OFFLINE = 8 * 3600

# ───────────────────────── 데이터 ─────────────────────────
STAGES = ["알", "유아기", "유년기", "성장기", "성숙기", "완전체", "궁극체"]
STAGE_TIME = [60, 600, 3600, 3 * 3600, 8 * 3600, 24 * 3600, None]  # 다음 단계까지(초)
HUNGER_EMPTY = [None, 1800, 3600, 5400, 7200, 9000, 10800]  # 배부름 100→0 걸리는 초
BASE_POWER = [0, 2, 5, 10, 20, 35, 60]
WIN_NEED = {4: 3, 5: 8, 6: 15}  # 해당 단계로 진화하기 위한 승리 횟수
BASE_NAMES = ["알", "토게피", "이브이"]
LINE_NAMES = [
    ["파이리", "리자드", "리자몽", "칠색조"],
    ["꼬부기", "어니부기", "거북왕", "가이오가"],
    ["이상해씨", "이상해풀", "이상해꽃", "비리디온"],
    ["고오스", "고우스트", "팬텀", "기라티나"],
]
LINE_LABEL = ["불꽃", "물", "풀", "고스트"]
# 전투 상대: 펫 단계별 풀 (slug는 build_sprites.py 의 FOES 와 동일)
FOE_NAMES = {
    "rattata": "꼬렛", "pidgey": "구구", "caterpie": "캐터피", "zubat": "주뱃", "geodude": "꼬마돌",
    "machop": "완력", "ekans": "아보", "onix": "롱스톤", "arcanine": "윈디", "alakazam": "후딘",
    "gyarados": "갸라도스", "snorlax": "잠만보", "dragonite": "망나뇽", "tyranitar": "마기라스",
    "machamp": "괴력몬", "mewtwo": "뮤츠",
}
FOE_POOL = {
    2: ["rattata", "pidgey", "caterpie"],
    3: ["zubat", "geodude", "machop", "ekans"],
    4: ["onix", "arcanine", "alakazam", "gyarados"],
    5: ["snorlax", "dragonite", "tyranitar", "machamp"],
    6: ["dragonite", "tyranitar", "machamp", "mewtwo"],
}
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
def new_state(gen=1, bits=0.0):
    return dict(
        last=time.time(), gen=gen, stage=0, line=-1, stage_time=0.0, total_time=0.0,
        hunger=80.0, happy=80.0, energy=100.0, hp=100.0, weight=5.0,
        sick=False, sick_t=0.0, sick_flag=False, starve_t=0.0, starve_flag=False,
        sleeping=False, dead=False, care_miss=0,
        train=dict(power=0.0, speed=0.0, mind=0.0),
        wins=0, losses=0, bits=float(bits), explore_t=0.0, battle_t=0.0,
    )


DEFAULT_CFG = dict(topmost=True, sound=True, auto_battle=True, mini=False, x=None, y=None)
BATTLE_IN = 1.5   # 상대 등장 연출(초)
BATTLE_OUT = 2.0  # 결과 표시(초). 공격 1회당 1초


class Game:
    def __init__(self):
        self.s = new_state()
        self.active_battle = None  # 연출 중인 전투(저장 안 함)
        self.cfg = dict(DEFAULT_CFG)
        self.log = []  # (시각, 메시지)
        self.load()

    # --- 저장/불러오기 ---
    def load(self):
        try:
            with open(SAVE, encoding="utf-8") as f:
                data = json.load(f)
            self.s.update(data["s"])
            self.cfg.update(data.get("cfg", {}))
        except (OSError, ValueError, KeyError):
            self.say("알을 발견했다! 따뜻하게 지켜봐 주자.")
            return
        away = time.time() - self.s["last"]
        if away > 15:
            before = self.s["stage"]
            self.catchup(away)
            self.say(f"자리를 비운 {int(min(away, MAX_OFFLINE) // 60)}분 동안 무럭무럭 자랐다.")
            if self.s["stage"] != before:
                self.say(f"그 사이 {self.name()}(으)로 진화했다!")

    def save(self):
        self.s["last"] = time.time()
        tmp = SAVE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"s": self.s, "cfg": self.cfg}, f, ensure_ascii=False)
        os.replace(tmp, SAVE)

    def say(self, msg):
        self.log.append((time.time(), msg))
        del self.log[:-50]

    # --- 정보 ---
    def name(self):
        s = self.s
        if s["stage"] < 3:
            return BASE_NAMES[s["stage"]]
        return LINE_NAMES[s["line"]][s["stage"] - 3]

    def power(self):
        s = self.s
        p = BASE_POWER[s["stage"]] + sum(s["train"].values()) * 0.3 + s["happy"] / 25 + s["gen"] * 1.5
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
        s["total_time"] += dt
        s["stage_time"] += dt
        if st == 0:
            self.check_evolve()
            return

        mult = 0.5 if s["sleeping"] else 1.0
        s["hunger"] = max(0.0, s["hunger"] - 100 * dt / HUNGER_EMPTY[st] * mult * k)

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

        drain = 100 * dt / 7200
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
            s["hp"] = min(100.0, s["hp"] + 100 * dt / 1800)

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
            if self.cfg["auto_battle"] and not offline and st >= 2:
                s["battle_t"] += dt
                if s["battle_t"] >= 300:
                    s["battle_t"] = 0
                    if s["hp"] > 40 and s["hunger"] > 20 and s["energy"] > 20:
                        self.battle(auto=True)
        self.check_evolve()

    def check_evolve(self):
        s = self.s
        st = s["stage"]
        need = STAGE_TIME[st]
        if need is None or s["stage_time"] < need:
            return
        nxt = st + 1
        if nxt in WIN_NEED and s["wins"] < WIN_NEED[nxt]:
            return  # 배틀 승리가 더 필요
        if nxt == 3:
            if s["care_miss"] >= 4:
                s["line"] = 3
            else:
                t = s["train"]
                best = max(TRAIN_KEYS, key=lambda k: t[k] + random.random() * 0.1)
                s["line"] = TRAIN_KEYS.index(best)
        s["stage"] = nxt
        s["stage_time"] = 0.0
        s["hp"] = 100.0
        s["weight"] += 3
        if nxt == 1:
            self.say(f"알이 부화했다! 안녕, {self.name()}!")
        else:
            extra = f" ({LINE_LABEL[s['line']]} 계열)" if nxt == 3 else ""
            self.say(f"진화! {self.name()}(으)로 진화했다!{extra}")

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
        s["sick"] = False
        s["sick_t"] = 0
        s["sick_flag"] = False
        s["hp"] = min(100, s["hp"] + 15)
        self.say("약을 먹고 나았다!")

    def pet(self):
        s = self.s
        if s["dead"] or s["stage"] == 0:
            return False
        s["happy"] = min(100, s["happy"] + 1.5)
        return True

    def battle(self, auto=False):
        s = self.s
        if not self._ok():
            return
        if s["stage"] < 2:
            return self.say("아직 너무 어려서 싸울 수 없다.")
        if s["sleeping"] or s["hp"] < 20 or s["energy"] < 15:
            return self.say("컨디션이 안 좋아 싸울 수 없다.")
        ab = self.active_battle
        if ab and time.time() < ab["start"] + ab["dur"]:
            return self.say("이미 전투 중이다.")
        st = s["stage"]
        slug = random.choice(FOE_POOL[st])
        foe = FOE_NAMES[slug]
        enemy = BASE_POWER[st] * random.uniform(0.7, 1.5) + 2
        s["energy"] -= 8
        tag = "[자동] " if auto else ""
        win = self.power() * random.uniform(0.8, 1.2) > enemy
        reward = 0
        if win:
            reward = random.randint(3, 6) * st
            s["bits"] += reward
            s["wins"] += 1
            s["happy"] = min(100, s["happy"] + 5)
            s["hp"] -= 3
            s["train"][random.choice(TRAIN_KEYS)] += 0.5
            msg = f"{tag}{foe}에게 승리! +{reward} Bits"
        else:
            s["losses"] += 1
            s["hp"] -= 12
            s["happy"] = max(0, s["happy"] - 8)
            msg = f"{tag}{foe}에게 졌다… 쉬어야겠다."
        self.say(msg)
        events = self.battle_events(win)
        self.active_battle = dict(foe=foe, slug=slug, stage=st, line=random.randrange(4), win=win, reward=reward,
                                  events=events, start=time.time(), dur=BATTLE_IN + len(events) + BATTLE_OUT)

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
        self.s = new_state(gen=s["gen"] + 1, bits=s["bits"])
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
        r.attributes("-topmost", self.g.cfg["topmost"])

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
        r.protocol("WM_DELETE_WINDOW", self.quit)
        r.after(200, self.loop)

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
            ("배틀", self.g.battle),
            ("재우기", self.g.toggle_sleep),
            ("치료", self.g.medicine),
            ("상태", self.toggle_stats),
            ("설정", lambda: self.popup(self.menu, "설정")),
        ]
        for i, (txt, cmd) in enumerate(specs):
            b = tk.Button(grid, text=txt, command=cmd, width=6, bg=BTN, fg="#fff", bd=0,
                          activebackground="#6a7390", activeforeground="#fff", font=(FONT, 9))
            b.grid(row=i // 4, column=i % 4, padx=2, pady=2)
            self.btns[txt] = b

        self.bind_drag(bar)
        self.bind_drag(t)
        self.bind_drag(self.screen, click=self.on_click)
        self.screen.bind("<Double-Button-1>", lambda e: self.show_mode(True))

    def build_mini(self):
        self.mini = tk.Canvas(self.root, width=240, height=210, bg=KEY, highlightthickness=0, bd=0)
        self.bind_drag(self.mini, click=self.on_click)
        self.mini.bind("<Double-Button-1>", lambda e: self.show_mode(False))

    def build_menus(self):
        g = self.g
        self.feed_menu = tk.Menu(self.root, tearoff=0)
        self.feed_menu.add_command(label="고기 (+30)", command=lambda: g.feed("meat"))
        self.feed_menu.add_command(label="간식 (5 Bits, 행복↑)", command=lambda: g.feed("snack"))
        self.train_menu = tk.Menu(self.root, tearoff=0)
        for k in TRAIN_KEYS:
            self.train_menu.add_command(label=f"{TRAIN_LABEL[k]} 훈련", command=lambda k=k: g.train(k))
        self.v_top = tk.BooleanVar(value=g.cfg["topmost"])
        self.v_auto = tk.BooleanVar(value=g.cfg["auto_battle"])
        self.v_sound = tk.BooleanVar(value=g.cfg["sound"])
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="미니/전체 모드 전환 (더블클릭)", command=lambda: self.show_mode(not g.cfg["mini"]))
        m.add_command(label="상태 보기", command=self.show_stats)
        m.add_checkbutton(label="항상 위", variable=self.v_top, command=self.apply_cfg)
        m.add_checkbutton(label="자동 배틀", variable=self.v_auto, command=self.apply_cfg)
        m.add_checkbutton(label="알림 소리", variable=self.v_sound, command=self.apply_cfg)
        m.add_separator()
        m.add_command(label="새 알로 환생", command=self.reincarnate)
        m.add_command(label="저장 후 종료", command=self.quit)
        self.menu = m
        self.root.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

    def popup(self, menu, name):
        b = self.btns[name]
        menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def apply_cfg(self):
        c = self.g.cfg
        c["topmost"] = self.v_top.get()
        c["auto_battle"] = self.v_auto.get()
        c["sound"] = self.v_sound.get()
        self.root.attributes("-topmost", c["topmost"])

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
        self.g.cfg["mini"] = mini
        if mini:
            self.full.pack_forget()
            self.mini.pack()
        else:
            self.mini.pack_forget()
            self.full.pack()

    def toggle_stats(self):
        self.page = "main" if self.page == "stats" else "stats"

    def show_stats(self):
        self.page = "stats"
        self.show_mode(False)

    def reincarnate(self):
        if messagebox.askyesno("환생", "현재 펫을 보내고 새 알로 시작할까요?\n(Bits와 세대 보너스는 유지돼요)"):
            self.g.reincarnate()

    def on_click(self, e):
        g = self.g
        if g.s["dead"]:
            g.reincarnate()
        elif g.pet():
            self.hearts.append([e.x, e.y - 10, 1.0])

    # --- 메인 루프 ---
    def loop(self):
        now = time.time()
        dt = now - self.last_t
        self.last_t = now
        if dt > 10:  # 절전 등으로 오래 멈췄다면 오프라인 처리
            self.g.catchup(dt)
            self.g.say("깜빡 졸다 일어났다.")
        else:
            self.g.tick(dt * FAST)
        self.walk(dt)
        self.notify()
        self.render()
        if now - self.last_save > 30:
            self.last_save = now
            self.g.save()
        self.root.after(200, self.loop)

    def walk(self, dt):
        s = self.g.s
        if s["dead"] or s["sleeping"] or s["stage"] == 0:
            return
        self.wait -= dt
        if abs(self.px - self.target) < 3:
            if self.wait <= 0:
                self.target = random.uniform(80, 240)
                self.wait = random.uniform(2, 8)
        else:
            self.px += (1 if self.target > self.px else -1) * 26 * dt

    def notify(self):
        cur = {k for k, _ in self.g.needs()}
        new = cur - self.last_needs
        self.last_needs = cur
        if new and self.g.cfg["sound"] and winsound:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except RuntimeError:
                pass

    # --- 렌더링 ---
    def render(self):
        g, s = self.g, self.g.s
        night = not (6 <= time.localtime().tm_hour < 20)
        if g.cfg["mini"]:
            self.draw_scene(self.mini, 240, 210, 190, 7, mini=True, night=night)
        else:
            self.draw_scene(self.screen, 320, 230, 196, 8, mini=False, night=night)
            age = int(s["total_time"] // 60)
            self.info.config(
                text=f"{g.name()} · {STAGES[s['stage']]} · {age // 60}시간 {age % 60}분 · "
                     f"{g.s['gen']}세대 · Bits {int(s['bits'])}")
            self.btns["재우기"].config(text="깨우기" if s["sleeping"] else "재우기")

    def draw_actor(self, c, x, floor, scale, stage, line, foe=None, blink=False, bob=0, sleeping=False, frame=0):
        """펫/적 한 마리를 (x, floor) 발바닥 기준으로 그림. 위쪽 y(머리 꼭대기)를 반환.
        foe에는 적 slug를 넘김(이미지가 없으면 회색 도트)."""
        img = self.custom_foe(foe, stage, scale) if foe else self.custom_image(stage, line, frame, sleeping, scale)
        if img:
            c.create_image(x, floor + 4 + bob // 2, image=img, anchor="s")
            return floor - img.height()
        x0 = x - 8 * scale
        y0 = floor - 15 * scale + bob
        for rx, ry, w, col in sprite_runs(stage, max(line, 0), blink, bool(foe)):
            c.create_rectangle(x0 + rx * scale, y0 + ry * scale,
                               x0 + (rx + w) * scale, y0 + (ry + 1) * scale, fill=col, outline="")
        return y0

    def battle_view(self):
        """진행 중인 전투의 현재 연출 상태. 끝났으면 None."""
        ab = self.g.active_battle
        if not ab:
            return None
        e = time.time() - ab["start"]
        if e >= ab["dur"]:
            self.g.active_battle = None
            return None
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
        end_ev = BATTLE_IN + len(evs)
        if e >= end_ev and not ab["win"]:
            pet_hp = 0
        return dict(ab=ab, e=e, pet_hp=max(0, pet_hp), foe_hp=max(0, foe_hp), lunge=lunge, shake=shake,
                    pop=pop, entering=e < BATTLE_IN, over=e >= end_ev)

    def draw_battle_ui(self, c, W, mini, bv, scale, night):
        ab = bv["ab"]
        y = 46 if not mini else 10
        fg = "#eee" if night else "#222"
        for x, name, hp, col in ((10, self.g.name(), bv["pet_hp"], "#43b36b"),
                                 (W - 100, ab["foe"], bv["foe_hp"], "#e0483c")):
            c.create_text(x, y, text=name, anchor="w", font=(FONT, 8, "bold"), fill=fg)
            c.create_rectangle(x, y + 8, x + 90, y + 16, fill="#444", outline="#111")
            c.create_rectangle(x, y + 8, x + 90 * hp / 100, y + 16, fill=col, outline="")
        if bv["entering"]:
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
            foe_alive = not (ab["win"] and bv["over"] and int(t * 8) % 2)
            if foe_alive and not (ab["win"] and bv["e"] > BATTLE_IN + len(ab["events"]) + 1.2):
                self.draw_actor(c, fx, floor, scale, ab["stage"], ab["line"], foe=ab["slug"], blink=bv["shake"]["foe"] != 0)
            self.draw_actor(c, px, floor, scale, s["stage"], s["line"], blink=bv["shake"]["pet"] != 0,
                            frame=int(t * 4) % 2)
            if bv["pop"]:
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
            y0 = self.draw_actor(c, self.px + wig, floor, scale, s["stage"], s["line"], blink=blink,
                                 bob=bob, sleeping=s["sleeping"], frame=int(t * 2.5) % 2)
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
                c.create_text(h[0], h[1], text="♥", fill="#ff5c8a", font=(FONT, 12))

        if not mini and not bv:
            if g.log and time.time() - g.log[-1][0] < 15:
                c.create_text(W // 2, H - 14, text=g.log[-1][1], font=(FONT, 9, "bold"),
                              fill="#fff" if night else "#2d3b1f")
            if s["dead"]:
                c.create_text(W // 2, 40, text="클릭하면 새 알을 받아요", font=(FONT, 10), fill="#c33")

    STAGE_H = [56, 64, 72, 84, 96, 108, 120]  # 단계별 화면상 목표 높이(scale 8 기준)

    def custom_image(self, stage, line, frame, sleeping, scale):
        """sprites/ 폴더의 PNG/GIF를 찾아 정수배 확대해 반환. 없으면 None(내장 도트 사용).
        탐색 순서: stage{N}_line{L} -> stage{N}, 각각 _sleep / _2(2프레임) 변형 지원."""
        bases = [f"stage{stage}"]
        if line >= 0 and stage >= 3:
            bases.insert(0, f"stage{stage}_line{line}")
        suffixes = (["_sleep"] if sleeping else []) + (["_2"] if frame else []) + [""]
        for base in bases:
            for suf in suffixes:
                img = self.cached_image(base + suf, self.STAGE_H[stage] * scale // 8, scale)
                if img:
                    return img
        return None

    def custom_foe(self, slug, stage, scale):
        return self.cached_image(f"foes/{slug}", self.STAGE_H[min(stage, 6)] * scale // 8, scale)

    def cached_image(self, name, target_h, scale):
        key = (name, target_h, scale)
        if key not in self.img_cache:
            self.img_cache[key] = self.load_image(name, target_h, 16 * scale)
        return self.img_cache[key]

    def load_image(self, name, target_h, max_w):
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
            return img
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
        tid = c.create_text(x, y, text=text, font=f, fill="#222")
        bx = c.bbox(tid)
        c.create_rectangle(bx[0] - 6, bx[1] - 3, bx[2] + 6, bx[3] + 3, fill="#fff", outline="#555")
        c.tag_raise(tid)

    def draw_bars(self, c, night):
        s = self.g.s
        items = [("배고픔", s["hunger"]), ("행복", s["happy"]), ("기력", s["energy"]), ("체력", s["hp"])]
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

    def draw_stats(self, c, night):
        g, s = self.g, self.g.s
        t = s["train"]
        lines = [
            f"{g.name()}  ({STAGES[s['stage']]}"
            + (f" / {LINE_LABEL[s['line']]}" if s["line"] >= 0 else "") + f")  {s['gen']}세대",
            f"배고픔 {int(s['hunger'])}   행복 {int(s['happy'])}   기력 {int(s['energy'])}   체력 {int(s['hp'])}",
            f"몸무게 {s['weight']:.0f}g   케어미스 {s['care_miss']}",
            f"힘 {t['power']:.0f}  속도 {t['speed']:.0f}  지능 {t['mind']:.0f}   전투력 {g.power():.0f}",
            f"전적 {s['wins']}승 {s['losses']}패   Bits {int(s['bits'])}",
            f"다음 진화: {g.next_evo()}",
        ]
        fg = "#eee" if night else "#2d3b1f"
        for i, ln in enumerate(lines):
            c.create_text(14, 24 + i * 30, text=ln, anchor="w", font=(FONT, 9, "bold" if i == 0 else "normal"), fill=fg)

    def quit(self):
        c = self.g.cfg
        c["x"], c["y"] = self.root.winfo_x(), self.root.winfo_y()
        self.g.save()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
