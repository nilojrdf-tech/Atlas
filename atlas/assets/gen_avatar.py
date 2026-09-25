"""Gera a identidade visual provisória do Atlas: um pequeno robo com tracos
limpos e olhos expressivos, em variacoes de boca para o lip sync.

Arte vetorial procedural (desenhada com Pillow), fundo transparente, mesmo
enquadramento/dimensoes em todos os sprites para nao haver saltos ao trocar
de boca. Rode: python gen_avatar.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 512
OUT_DIR = Path(__file__).parent

# Paleta: corpo azul-petroleo suave com destaque em ciano, sem referencia
# visual ao personagem original do Pynkaro.
BODY_TOP = (58, 84, 130, 255)
BODY_BOTTOM = (38, 58, 96, 255)
PANEL = (86, 214, 214, 255)
EYE_WHITE = (240, 248, 250, 255)
EYE_IRIS = (35, 45, 60, 255)
OUTLINE = (24, 32, 48, 255)
ANTENNA = (86, 214, 214, 255)
MOUTH_COLOR = (24, 32, 48, 255)
CHEEK = (255, 150, 150, 90)


def _vertical_gradient(draw: ImageDraw.ImageDraw, box, top, bottom):
    x0, y0, x1, y1 = box
    height = y1 - y0
    for i in range(height):
        t = i / max(height - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(x0, y0 + i), (x1, y0 + i)], fill=(r, g, b, 255))


def _rounded_rect_mask(size, box, radius):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle(box, radius=radius, fill=255)
    return mask


def _base_head() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # Sombra suave no chao do enquadramento (ajuda o avatar a "assentar").
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((SIZE * 0.20, SIZE * 0.88, SIZE * 0.80, SIZE * 0.98), fill=(0, 0, 0, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(shadow)

    head_box = (SIZE * 0.16, SIZE * 0.10, SIZE * 0.84, SIZE * 0.86)

    # Corpo/cabeca com gradiente, recortado em retangulo arredondado.
    grad = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    _vertical_gradient(gd, (int(head_box[0]), int(head_box[1]), int(head_box[2]), int(head_box[3])),
                        BODY_TOP, BODY_BOTTOM)
    mask = _rounded_rect_mask((SIZE, SIZE), head_box, radius=110)
    img.paste(grad, (0, 0), mask)

    # Contorno.
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(head_box, radius=110, outline=OUTLINE, width=6)

    # Antena.
    cx = SIZE * 0.5
    d.line([(cx, head_box[1]), (cx, head_box[1] - 46)], fill=OUTLINE, width=8)
    d.ellipse((cx - 16, head_box[1] - 70, cx + 16, head_box[1] - 38), fill=ANTENNA, outline=OUTLINE, width=4)

    # Painel/viseira translucida onde ficam os olhos.
    visor_box = (SIZE * 0.24, SIZE * 0.28, SIZE * 0.76, SIZE * 0.56)
    vd_mask = _rounded_rect_mask((SIZE, SIZE), visor_box, radius=70)
    visor = Image.new("RGBA", (SIZE, SIZE), (18, 26, 40, 235))
    img.paste(visor, (0, 0), vd_mask)
    d.rounded_rectangle(visor_box, radius=70, outline=OUTLINE, width=5)

    # Bochechas (charme, sutil).
    d.ellipse((SIZE * 0.18, SIZE * 0.60, SIZE * 0.30, SIZE * 0.68), fill=CHEEK)
    d.ellipse((SIZE * 0.70, SIZE * 0.60, SIZE * 0.82, SIZE * 0.68), fill=CHEEK)

    # Olhos expressivos: grandes, redondos, com brilho.
    eye_y = SIZE * 0.42
    eye_r = SIZE * 0.075
    for ex in (SIZE * 0.365, SIZE * 0.635):
        d.ellipse((ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r), fill=EYE_WHITE, outline=OUTLINE, width=4)
        iris_r = eye_r * 0.52
        d.ellipse((ex - iris_r, eye_y - iris_r, ex + iris_r, eye_y + iris_r), fill=EYE_IRIS)
        gl = iris_r * 0.35
        d.ellipse((ex - iris_r * 0.35 - gl, eye_y - iris_r * 0.45 - gl,
                   ex - iris_r * 0.35 + gl, eye_y - iris_r * 0.45 + gl), fill=(255, 255, 255, 230))

    # Painel de peito com detalhe (marca visual do Atlas: circulo com anel).
    chest_cx, chest_cy = SIZE * 0.5, SIZE * 0.735
    d.ellipse((chest_cx - 26, chest_cy - 26, chest_cx + 26, chest_cy + 26), outline=PANEL, width=5)
    d.ellipse((chest_cx - 8, chest_cy - 8, chest_cx + 8, chest_cy + 8), fill=PANEL)

    return img, visor_box


MOUTH_Y = 0.60  # posicao vertical da boca, relativa ao SIZE


def _draw_mouth(img: Image.Image, kind: str) -> Image.Image:
    img = img.copy()
    d = ImageDraw.Draw(img)
    cx, cy = SIZE * 0.5, SIZE * MOUTH_Y
    w = SIZE * 0.5

    if kind == "closed":
        d.rounded_rectangle((cx - w * 0.16, cy - 5, cx + w * 0.16, cy + 5), radius=5, fill=MOUTH_COLOR)
    elif kind == "mid":
        d.ellipse((cx - w * 0.14, cy - 14, cx + w * 0.14, cy + 14), fill=MOUTH_COLOR)
    elif kind == "open":
        d.ellipse((cx - w * 0.18, cy - 30, cx + w * 0.18, cy + 30), fill=MOUTH_COLOR)
        d.ellipse((cx - w * 0.10, cy - 4, cx + w * 0.10, cy + 20), fill=(214, 90, 90, 255))
    elif kind == "round":
        r = 20
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=MOUTH_COLOR)
    elif kind == "fv":
        d.rounded_rectangle((cx - w * 0.15, cy - 3, cx + w * 0.15, cy + 9), radius=6, fill=MOUTH_COLOR)
        d.rounded_rectangle((cx - w * 0.12, cy - 9, cx + w * 0.12, cy - 3), radius=4, fill=EYE_WHITE)
    return img


def main() -> None:
    base, _ = _base_head()
    variants = {
        "avatar": "closed",
        "avatar_mid": "mid",
        "avatar_open": "open",
        "avatar_round": "round",
        "avatar_fv": "fv",
    }
    for filename, kind in variants.items():
        out = _draw_mouth(base, kind)
        out.save(OUT_DIR / f"{filename}.png")
        print(f"gerado {filename}.png")


if __name__ == "__main__":
    main()
