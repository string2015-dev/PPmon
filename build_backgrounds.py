"""myself_made 폴더의 `*배경.png` 를 게임 화면(320x230) 크기로 잘라 sprites/backgrounds/ 에 복사한다.
exe 에 함께 넣을 사본이다(게임은 먼저 원본 폴더를 읽고, 없거나 PIL 이 없으면 이 사본을 씀)."""
import glob
import os

from PIL import Image

SRC = r"C:\Users\user\Documents\PoketMonPixcel\myself_made"
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites", "backgrounds")
W, H = 320, 230


def cover(im, w=W, h=H):
    s = max(w / im.width, h / im.height)
    im = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


if __name__ == "__main__":
    os.makedirs(DST, exist_ok=True)
    for f in sorted(glob.glob(os.path.join(SRC, "*배경.png"))):
        stem = os.path.basename(f)[:-4].replace("%", "")
        cover(Image.open(f).convert("RGB")).save(os.path.join(DST, stem + ".png"), optimize=True)
        print("saved", stem)
