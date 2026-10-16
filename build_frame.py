"""myself_made/포켓몬_도감.png (도감 기기 틀)을 게임 창 크기로 줄여 sprites/ui/ 에 저장한다.
 - 기기 바깥의 베이지색 배경은 투명 처리용 색(KEY)으로 바꾸고,
 - 검은 화면 영역은 깨끗한 검정으로 칠해(원래 그려진 HUD/실루엣 제거) 그 자리에 게임 화면이 들어가게 하며,
 - 화면 영역 좌표를 dex_frame.json 으로 함께 저장한다."""
import json
import os
from collections import deque

from PIL import Image

SRC = r"C:\Users\user\Documents\PoketMonPixcel\myself_made\포켓몬_도감.png"
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites", "ui")
KEY = (255, 0, 255)       # digipet.py 의 투명 처리 색 "#ff00ff"
SCREEN = (16, 20, 26)     # 화면 바탕(검정에 가까운 남색) = digipet.py 의 SCR
SCREEN_W = 342            # 화면 영역의 목표 가로(px). 세로는 비율대로


def dark(p):
    """화면 안쪽(어둡거나 초록 HUD)이면 True, 빨간 기기 몸체가 나오면 False."""
    return not (p[0] > 130 and p[1] < 90 and p[2] < 90)


def find_screen(im):
    """중앙 가로/세로 선을 따라 어두운 영역의 끝을 찾아 화면 사각형(x0, y0, x1, y1)을 구함."""
    w, h = im.size
    px = im.load()
    cx, cy = w // 2, h // 2
    x0 = cx
    while x0 > 0 and dark(px[x0 - 1, cy]):
        x0 -= 1
    x1 = cx
    while x1 < w - 1 and dark(px[x1 + 1, cy]):
        x1 += 1
    y0 = cy
    while y0 > 0 and dark(px[cx, y0 - 1]):
        y0 -= 1
    y1 = cy
    while y1 < h - 1 and dark(px[cx, y1 + 1]):
        y1 += 1
    return x0, y0, x1 + 1, y1 + 1


def outside_mask(im, tol=46):
    """모서리에서 시작해 바깥 배경색(베이지/회갈색 바탕)과 비슷한 픽셀을 채워 나감."""
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    ref = [px[0, 0][:3], px[w - 1, 0][:3], px[0, h - 1][:3], px[w - 1, h - 1][:3]]

    def near(p):
        return any(sum(abs(a - b) for a, b in zip(p[:3], r)) < tol * 3 // 2 + 30 for r in ref) and not (p[0] > p[1] + 60)

    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        if not (0 <= x < w and 0 <= y < h) or seen[y * w + x]:
            continue
        if not near(px[x, y]):
            continue
        seen[y * w + x] = 1
        dq.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return seen


if __name__ == "__main__":
    im = Image.open(SRC).convert("RGB")
    sx0, sy0, sx1, sy1 = find_screen(im)
    print("screen rect (src):", sx0, sy0, sx1, sy1)
    # 화면 영역을 깨끗한 바탕색으로 (HUD 글자·실루엣 제거)
    px = im.load()
    for y in range(sy0, sy1):
        for x in range(sx0, sx1):
            px[x, y] = SCREEN
    w, h = im.size
    out = outside_mask(im)
    for y in range(h):
        for x in range(w):
            if out[y * w + x]:
                px[x, y] = KEY
    # 기기 영역만 남기기
    rows = [y for y in range(h) if sum(1 for x in range(0, w, 4) if not out[y * w + x]) > w // 4 * 0.4]
    cols = [x for x in range(w) if sum(1 for y in range(0, h, 4) if not out[y * w + x]) > h // 4 * 0.1]
    bx0, by0, bx1, by1 = min(cols), min(rows), max(cols) + 1, max(rows) + 1
    for y in range(h):  # 기기 밖에 남은 잡티는 모두 투명색으로
        for x in range(w):
            if not (bx0 <= x < bx1 and by0 <= y < by1):
                px[x, y] = KEY
    print("device bbox:", bx0, by0, bx1, by1)
    sc = SCREEN_W / (sx1 - sx0)
    crop = im.crop((bx0, by0, bx1, by1))
    size = (round(crop.width * sc), round(crop.height * sc))
    small = crop.resize(size, Image.LANCZOS)
    # 줄이면서 번진 KEY 가장자리(분홍 섞인 픽셀)는 투명색으로 통일
    sp = small.load()
    for y in range(small.height):
        for x in range(small.width):
            r, g, b = sp[x, y]
            if r > 200 and b > 170 and g < 110 and abs(r - b) < 70:
                sp[x, y] = KEY
    rect = [round((sx0 - bx0) * sc), round((sy0 - by0) * sc), round((sx1 - bx0) * sc), round((sy1 - by0) * sc)]
    os.makedirs(DST, exist_ok=True)
    small.save(os.path.join(DST, "dex_frame.png"), optimize=True)
    json.dump({"size": list(small.size), "screen": rect}, open(os.path.join(DST, "dex_frame.json"), "w"))
    print("frame size:", small.size, "screen rect:", rect)
