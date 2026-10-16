"""PokéSprite(gen8) 폴더에서 게임에 필요한 포켓몬 스프라이트를 뽑아 sprites/mons/ 에 저장.
- 필요한 목록은 species.py(1세대 151종 + 추가 종)에서 자동으로 가져옴
- 일반: sprites/mons/{slug}.png, 이로치(색이 다른 개체): sprites/mons/shiny/{slug}.png
- 투명 여백을 잘라내(bbox crop) 발바닥 기준 정렬이 되게 함
사용: python build_sprites.py [PokéSprite 폴더 경로]
"""
import os
import sys

from PIL import Image

import species

SRC_ROOT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\user\Documents\PoketMonPixcel"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites", "mons")
# 원본이 반대 방향을 보고 있어서 좌우 반전이 필요한 것
FLIP = set()


def src_path(slug, shiny):
    if slug == "egg":
        return os.path.join(SRC_ROOT, "pokemon-gen8", "egg.png")
    return os.path.join(SRC_ROOT, "pokemon-gen8", "shiny" if shiny else "regular", slug + ".png")


def convert(slug, shiny, dst):
    p = src_path(slug, shiny)
    if not os.path.exists(p):
        return False
    im = Image.open(p).convert("RGBA")
    box = im.getchannel("A").getbbox()
    if box:
        im = im.crop(box)
    if slug in FLIP:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    im.save(dst)
    return True


def main():
    os.makedirs(os.path.join(OUT, "shiny"), exist_ok=True)
    n = miss = 0
    for slug in species.all_slugs():
        if convert(slug, False, os.path.join(OUT, slug + ".png")):
            n += 1
        else:
            miss += 1
            print("missing:", slug)
        if slug != "egg":
            if convert(slug, True, os.path.join(OUT, "shiny", slug + ".png")):
                n += 1
            else:
                print("missing shiny:", slug)
    print(f"{n}개 스프라이트 생성 (누락 {miss}) -> {OUT}")


if __name__ == "__main__":
    main()
