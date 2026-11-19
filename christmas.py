#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
圣诞快乐 · 交互动画（单文件，零外部素材）

运行：python christmas.py
依赖：pygame（首次运行自动安装；音乐由程序内部合成，不需要任何 mp3/图片文件）

交互：
    鼠标点击 / 拖动  -> 放烟花
    空格             -> 音乐开关        ↑ / ↓  -> 音量
    C                -> 切换彩灯配色     F      -> 随机烟花
    R                -> 重新播放开场     S      -> 保存截图
    H                -> 显示/隐藏提示     ESC    -> 退出
"""

import os
import sys
import math
import random
import wave
import struct
import tempfile
import time

# ---------------------------------------------------------------- 依赖引导
try:
    import pygame
except ImportError:
    print("首次运行，正在自动安装 pygame（约 10 秒）…")
    import subprocess
    ok = False
    for extra in (["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"], []):
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "pygame",
                 "--disable-pip-version-check", "--quiet"] + extra)
            ok = True
            break
        except Exception:
            continue
    if not ok:
        print("自动安装失败，请手动执行:  pip install pygame")
        input("按回车退出…")
        sys.exit(1)
    import pygame

VW, VH = 1200, 800
if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- 小工具
def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(c1, c2, t):
    return (int(lerp(c1[0], c2[0], t)),
            int(lerp(c1[1], c2[1], t)),
            int(lerp(c1[2], c2[2], t)))


def smooth(x):
    x = 0.0 if x < 0 else (1.0 if x > 1 else x)
    return x * x * (3 - 2 * x)


_glow_cache = {}


def glow(radius, color, power=2.4):
    key = (radius, color, power)
    if key in _glow_cache:
        return _glow_cache[key]
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        a = int(240 * (1.0 - r / radius) ** power)
        pygame.draw.circle(surf, (color[0], color[1], color[2], a), (radius, radius), r)
    _glow_cache[key] = surf
    return surf


def blur(surf, factor=8):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // factor), max(1, h // factor)))
    return pygame.transform.smoothscale(small, (w, h))


def load_font(size, bold=False):
    paths = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
             r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\Deng.ttf",
             r"C:\Windows\Fonts\simsun.ttc"]
    for p in paths:
        if os.path.exists(p):
            try:
                return pygame.font.Font(p, size)
            except Exception:
                pass
    return pygame.font.SysFont("microsoftyahei,simhei,arial", size, bold=bold)


# ---------------------------------------------------------------- 音乐合成
def _freq(name):
    table = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    midi = 12 * (int(name[1:]) + 1) + table[name[0]]
    return 440.0 * 2 ** ((midi - 69) / 12.0)


A_PHRASE = [("E4", 1), ("D4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1), ("E4", 2)]
B_PHRASE = [("D4", 1), ("D4", 1), ("E4", 1), ("D4", 1), ("C4", 2), (None, 2)]


def build_music(path, tempo=0.42, sr=22050):
    """纯数学合成《Jingle Bells》铃铛旋律 + 低音铺底 + 回声，写成 wav 循环播放。"""
    seq = (A_PHRASE + B_PHRASE + A_PHRASE + B_PHRASE) * 2
    total_beats = sum(b for _, b in seq)
    n = int(total_beats * tempo * sr) + sr
    buf = [0.0] * n

    def bell(t, f, decay=5.4):
        env = math.exp(-decay * t) * min(1.0, t / 0.008)
        return (0.55 * math.sin(2 * math.pi * f * t)
                + 0.26 * math.sin(2 * math.pi * 2 * f * t + 0.4)
                + 0.13 * math.sin(2 * math.pi * 3.01 * f * t + 1.1)
                + 0.07 * math.sin(2 * math.pi * 4.9 * f * t))

    beat = 0
    for note, beats in seq:
        dur = beats * tempo
        if note:
            f = _freq(note)
            i0 = int(beat * tempo * sr)
            cnt = min(int(dur * sr * 1.6), n - i0)
            for i in range(cnt):
                buf[i0 + i] += bell(i / sr, f) * 0.34
        beat += beats

    pad1, pad2 = _freq("C3"), _freq("G3")
    for i in range(n):
        t = i / sr
        e = 0.045 * (0.6 + 0.4 * math.sin(2 * math.pi * 0.08 * t))
        buf[i] += e * math.sin(2 * math.pi * pad1 * t) + 0.55 * e * math.sin(2 * math.pi * pad2 * t + 0.7)

    d = int(0.085 * sr)
    for i in range(n - 1, d, -1):
        buf[i] += 0.23 * buf[i - d]

    peak = max(1e-6, max(abs(v) for v in buf))
    scale = 0.92 / peak
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, v * scale)) * 32000)) for v in buf))
    return path


def build_chime(path, f=1174.0, sr=22050):
    n = int(0.45 * sr)
    data = bytearray()
    for i in range(n):
        t = i / sr
        env = math.exp(-7.5 * t) * min(1.0, t / 0.006)
        v = env * (0.7 * math.sin(2 * math.pi * f * t) + 0.3 * math.sin(2 * math.pi * 2.01 * f * t))
        data += struct.pack("<h", int(max(-1.0, min(1.0, v)) * 30000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(data))
    return path


# ---------------------------------------------------------------- 常量
TREE_W, TREE_H = 640, 700
TCX = 320
FOL_TOP, FOL_BOT = 70, 645
LAYERS = 8
TREE_X = 600 - TREE_W // 2
TREE_Y = 700 - TREE_H

PALETTES = [
    [(255, 92, 92), (255, 205, 92), (128, 240, 150), (104, 186, 255), (255, 128, 220)],
    [(242, 248, 255), (176, 214, 255), (130, 178, 255)],
    [(255, 176, 64), (255, 108, 56), (255, 226, 140)],
]

BG = None
TREEBASE = None
GIFTS = None
HOUSE = None
SNOWMAN = None
AURORA = None
LIGHTS = []
TXT_MAIN = TXT_GLOW = TXT_SUB = TXT_HINT_TOP = None
FONT_HUD = None
FLAKE_SPR = {}
HUD_SURF = None
HUD_ON = None
HUD_OFF = None
_toast_cache = {}

STATE = dict(
    flakes=[], sparks=[], t=0.0, palette=0, music_on=True, help_on=True,
    toast="", toast_t=0.0, volume=0.75, shots=0, shooting=None, next_shoot=6.0,
    k=1.0, ox=0, oy=0,
)


# ---------------------------------------------------------------- 圣诞树
def layer_geom(i):
    span = FOL_BOT - FOL_TOP
    y_bot = FOL_TOP + span * (i + 1) / LAYERS
    y_top = FOL_TOP + span * (i / LAYERS) - span * 0.085
    halfw = 26 + 268 * ((i + 1) / LAYERS) ** 1.3
    return y_top, y_bot, halfw


def tier_path(y_top, y_bot, halfw, teeth=8, depth=13):
    """带枝杈锯齿的树冠层轮廓：下垂的枝尖会让树看起来像真的冷杉。"""
    pts = [(TCX, y_top)]
    for s in (1, 2, 3):
        f = s / 3.0
        pts.append((TCX + halfw * (0.38 + 0.56 * f), lerp(y_top, y_bot, 0.82 * f)))
    pts.append((TCX + halfw, y_bot))
    for t in range(teeth, 0, -1):
        fx = t / teeth
        pts.append((TCX + halfw * 0.94 * fx, y_bot + (depth if t % 2 else -2)))
    pts.append((TCX - halfw, y_bot))
    for s in (3, 2, 1):
        f = s / 3.0
        pts.append((TCX - halfw * (0.38 + 0.56 * f), lerp(y_top, y_bot, 0.82 * f)))
    return pts


def build_tree():
    global LIGHTS
    img = pygame.Surface((TREE_W, TREE_H), pygame.SRCALPHA)
    random.seed(20241225)

    pygame.draw.polygon(img, (72, 52, 40),
                        [(TCX - 34, FOL_BOT - 30), (TCX + 34, FOL_BOT - 30),
                         (TCX + 26, TREE_H - 4), (TCX - 26, TREE_H - 4)])
    pygame.draw.polygon(img, (96, 70, 52),
                        [(TCX - 34, FOL_BOT - 30), (TCX - 8, FOL_BOT - 30),
                         (TCX - 4, TREE_H - 4), (TCX - 26, TREE_H - 4)])

    for i in range(LAYERS):
        y_top, y_bot, halfw = layer_geom(i)
        base_col = lerp3((14, 64, 50), (40, 128, 86), i / (LAYERS - 1))
        pts = tier_path(y_top, y_bot, halfw)
        pygame.draw.polygon(img, base_col, pts)
        # 右侧月光高光
        lit = lerp3(base_col, (70, 160, 110), 0.5)
        pygame.draw.polygon(img, lit, [(TCX + halfw * 0.72, y_top + (y_bot - y_top) * 0.35),
                                       (TCX + halfw, y_bot), (TCX + halfw * 0.86, y_bot + 10),
                                       (TCX, y_top + (y_bot - y_top) * 0.28)])
        # 针叶纹理
        for _ in range(150):
            fy = random.random()
            y = lerp(y_bot, y_top, fy)
            w = halfw * (1 - fy)
            x = TCX + random.uniform(-w * 0.94, w * 0.94)
            c = lerp3(base_col, (150, 220, 160), random.random() * 0.32)
            pygame.draw.line(img, c, (x, y), (x + random.uniform(-5, 5), y + random.uniform(5, 11)), 1)

    # 树顶雪帽
    pygame.draw.ellipse(img, (238, 246, 255, 235), (TCX - 18, FOL_TOP - 14, 36, 22))

    # 彩灯
    LIGHTS = []
    for i in range(LAYERS):
        y_top, y_bot, halfw = layer_geom(i)
        cnt = max(5, int(halfw / 22))
        for k in range(cnt):
            f = (k + 0.5) / cnt
            x = lerp(-halfw * 0.93, halfw * 0.93, f)
            y = y_bot - random.uniform(2, 14)
            LIGHTS.append((TCX + x, y))
        for _ in range(max(2, int(halfw / 46))):
            fy = random.uniform(0.2, 0.8)
            y = lerp(y_top, y_bot, fy)
            w = halfw * (1 - fy) * 0.72
            LIGHTS.append((TCX + random.uniform(-w, w), y))
    LIGHTS.append((TCX, FOL_TOP + 2))
    return img


def draw_tree(t, reveal):
    surf = TREEBASE.copy()
    pal = PALETTES[STATE["palette"]]
    last = len(LIGHTS) - 1

    for i, (lx, ly) in enumerate(LIGHTS):
        if i == last:
            gate = smooth((reveal - 0.76) / 0.24)
            if gate <= 0:
                continue
            pulse = 0.78 + 0.22 * math.sin(t * 2.6)
            g = glow(56, (255, 222, 140), 2.0)
            g.set_alpha(int(165 * gate * pulse))
            surf.blit(g, (lx - 56, ly - 56))

            # 旋转光芒（一帧只建一个临时面）
            maxlen = 46
            rays = pygame.Surface((maxlen * 2, maxlen * 2), pygame.SRCALPHA)
            for k in range(12):
                ang = t * 0.35 + k * (math.pi / 6)
                ln = 24 + 18 * abs(math.sin(t * 1.8 + k))
                a = int(80 * gate * (0.35 + 0.65 * abs(math.sin(t * 1.8 + k))))
                pygame.draw.line(rays, (255, 238, 180, a), (maxlen, maxlen),
                                 (maxlen + math.cos(ang) * ln, maxlen + math.sin(ang) * ln), 2)
            surf.blit(rays, (lx - maxlen, ly - maxlen))

            star = []
            for k in range(10):
                ang = -math.pi / 2 + k * math.pi / 5
                rr = 27 if k % 2 == 0 else 11
                star.append((lx + math.cos(ang) * rr, ly + math.sin(ang) * rr))
            pygame.draw.polygon(surf, (255, 236, 168), star)
            pygame.draw.polygon(surf, (255, 251, 226),
                                [(lx + (px - lx) * 0.52, ly + (py - ly) * 0.52) for px, py in star])
            continue

        gate = smooth((reveal - 0.05 - 0.72 * i / last) / 0.22)
        if gate <= 0:
            continue
        col = pal[(i // 3 + int(t * 0.9)) % len(pal)]
        pulse = 0.55 + 0.45 * math.sin(t * 3.1 + i * 0.75)
        g = glow(13, col, 2.0)
        g.set_alpha(int(185 * gate * pulse))
        surf.blit(g, (lx - 13, ly - 13))
        pygame.draw.circle(surf, (min(255, col[0] + 70), min(255, col[1] + 70), min(255, col[2] + 70),
                                  int(235 * gate)), (int(lx), int(ly)), 3)

    if reveal < 0.999:
        k = 0.82 + 0.18 * reveal
        surf = pygame.transform.smoothscale(
            surf, (max(1, int(TREE_W * k)), max(1, int(TREE_H * k))))
    return surf


# ---------------------------------------------------------------- 场景元件
def build_gifts():
    s = pygame.Surface((600, 200), pygame.SRCALPHA)
    boxes = [(24, 66, 118, 104, (176, 46, 62), (242, 226, 200)),
             (160, 90, 92, 80, (44, 96, 148), (255, 224, 140)),
             (268, 56, 128, 114, (58, 128, 90), (250, 206, 128)),
             (424, 96, 84, 74, (150, 76, 150), (255, 236, 210))]
    d = 15
    for x, y, w, h, col, rib in boxes:
        # 影子
        sha = pygame.Surface((w + 54, 38), pygame.SRCALPHA)
        pygame.draw.ellipse(sha, (26, 44, 74, 72), sha.get_rect())
        s.blit(sha, (x - 27, y + h - 14))
        top = lerp3(col, (255, 255, 255), 0.26)
        side = lerp3(col, (0, 0, 0), 0.42)
        # 顶面 / 右侧面 / 正面
        pygame.draw.polygon(s, top, [(x, y), (x + d, y - d), (x + w + d, y - d), (x + w, y)])
        pygame.draw.polygon(s, side, [(x + w, y), (x + w + d, y - d), (x + w + d, y - d + h), (x + w, y + h)])
        pygame.draw.polygon(s, col, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
        # 高光
        pygame.draw.polygon(s, lerp3(col, (255, 255, 255), 0.12),
                            [(x, y), (x + 12, y), (x + 12, y + h), (x, y + h)])
        # 丝带
        pygame.draw.rect(s, rib, (x + w // 2 - 8, y, 16, h))
        pygame.draw.rect(s, rib, (x, y + h // 2 - 8, w, 16))
        pygame.draw.polygon(s, rib, [(x + w // 2 - 8, y), (x + w // 2 - 8 + d, y - d), (x + w // 2 + 8 + d, y - d), (x + w // 2 + 8, y)])
        # 蝴蝶结
        pygame.draw.ellipse(s, rib, (x + w // 2 - 27, y - 34, 26, 18))
        pygame.draw.ellipse(s, rib, (x + w // 2 + 2, y - 34, 26, 18))
        pygame.draw.circle(s, lerp3(rib, (0, 0, 0), 0.28), (x + w // 2, y - 21), 5)
    return s


def build_house():
    s = pygame.Surface((280, 270), pygame.SRCALPHA)
    x, y, w, h = 26, 100, 200, 130
    pygame.draw.rect(s, (58, 44, 44), (x, y, w, h))
    pygame.draw.rect(s, (72, 54, 52), (x, y, 10, h))
    for i in range(6):
        pygame.draw.line(s, (46, 34, 34), (x, y + 20 + i * 20), (x + w, y + 20 + i * 20))
    pygame.draw.polygon(s, (44, 34, 40), [(x - 26, y + 6), (x + w + 26, y + 6), (x + w // 2, y - 46)])
    pygame.draw.polygon(s, (236, 243, 255), [(x - 26, y + 6), (x + w + 26, y + 6), (x + w + 12, y - 2), (x + 12, y - 2)])
    pygame.draw.polygon(s, (244, 249, 255), [(x + 12, y - 4), (x + w - 12, y - 4), (x + w // 2, y - 44)])
    for wx in (x + 26, x + 120):
        s.blit(glow(38, (255, 198, 118), 1.7), (wx + 22 - 38, y + 40 + 22 - 38))
        pygame.draw.rect(s, (255, 209, 134), (wx, y + 40, 44, 42), border_radius=3)
        pygame.draw.rect(s, (188, 138, 78), (wx, y + 40, 44, 42), 2, border_radius=3)
        pygame.draw.line(s, (150, 110, 64), (wx + 22, y + 40), (wx + 22, y + 82), 3)
        pygame.draw.line(s, (150, 110, 64), (wx, y + 61), (wx + 44, y + 61), 3)
    pygame.draw.rect(s, (36, 26, 28), (x + 74, y + 66, 52, h - 66), border_radius=4)
    pygame.draw.circle(s, (232, 202, 122), (x + 116, y + 112), 4)
    pygame.draw.rect(s, (52, 40, 42), (x + 152, y - 68, 26, 52))
    pygame.draw.rect(s, (240, 246, 255), (x + 147, y - 72, 36, 9))
    return s


def build_snowman():
    s = pygame.Surface((160, 240), pygame.SRCALPHA)
    cx = 80
    pygame.draw.circle(s, (196, 210, 232), (cx - 12, 196), 30)
    pygame.draw.circle(s, (226, 236, 250), (cx, 186), 44)
    pygame.draw.circle(s, (232, 241, 252), (cx, 128), 32)
    pygame.draw.circle(s, (236, 244, 254), (cx, 84), 24)
    pygame.draw.circle(s, (34, 34, 44), (cx - 8, 78), 3)
    pygame.draw.circle(s, (34, 34, 44), (cx + 8, 78), 3)
    for k in range(4):
        pygame.draw.circle(s, (34, 34, 44), (cx - 9 + k * 6, 92 + (1 if k in (0, 3) else 0)), 2)
    pygame.draw.polygon(s, (240, 140, 60), [(cx - 2, 82), (cx + 2, 82), (cx + 22, 89), (cx + 2, 91)])
    for yy in (118, 136, 154):
        pygame.draw.circle(s, (40, 44, 56), (cx, yy), 3)
    pygame.draw.rect(s, (196, 54, 60), (cx - 25, 100, 50, 12), border_radius=4)
    pygame.draw.rect(s, (196, 54, 60), (cx + 12, 104, 10, 36), border_radius=3)
    pygame.draw.rect(s, (38, 30, 44), (cx - 18, 58, 36, 20))
    pygame.draw.rect(s, (28, 22, 34), (cx - 25, 74, 50, 8), border_radius=3)
    pygame.draw.line(s, (96, 74, 50), (cx - 28, 132), (cx - 58, 108), 4)
    pygame.draw.line(s, (96, 74, 50), (cx - 58, 108), (cx - 66, 96), 3)
    pygame.draw.line(s, (96, 74, 50), (cx + 28, 132), (cx + 58, 108), 4)
    pygame.draw.line(s, (96, 74, 50), (cx + 58, 108), (cx + 66, 96), 3)
    pygame.draw.ellipse(s, (214, 228, 246), (cx - 62, 214, 124, 16))
    return s


def build_background():
    bg = pygame.Surface((VW, VH)).convert()
    for y in range(VH):
        f = y / (VH - 1)
        if f < 0.6:
            t = f / 0.6
            c = (int(lerp(6, 16, t)), int(lerp(12, 30, t)), int(lerp(30, 58, t)))
        else:
            t = (f - 0.6) / 0.4
            c = (int(lerp(16, 24, t)), int(lerp(30, 42, t)), int(lerp(58, 72, t)))
        pygame.draw.line(bg, c, (0, y), (VW, y))

    random.seed(99)
    for _ in range(340):
        x = random.randint(0, VW)
        y = random.randint(0, 600)
        r = 1 if random.random() < 0.85 else 2
        a = random.randint(90, 235)
        col = (int(lerp(200, 255, random.random())), int(lerp(215, 255, random.random())),
               int(lerp(235, 255, random.random())), a)
        pygame.draw.circle(bg, col, (x, y), r)
        if r == 2:
            pygame.draw.line(bg, (255, 255, 255, 80), (x - 5, y), (x + 5, y))
            pygame.draw.line(bg, (255, 255, 255, 80), (x, y - 5), (x, y + 5))

    # 月亮
    mx, my = VW - 190, 150
    bg.blit(glow(150, (150, 185, 235), 2.6), (mx - 150, my - 150))
    pygame.draw.circle(bg, (246, 248, 255), (mx, my), 46)
    pygame.draw.circle(bg, (233, 238, 252), (mx + 8, my - 6), 40)
    for dx, dy, r in ((-12, 8, 9), (6, 16, 7), (-4, -14, 6), (14, -4, 5)):
        pygame.draw.circle(bg, (226, 232, 248), (mx + dx, my + dy), r)

    # 远山
    pts = [(-40, 660)]
    for x in range(-40, VW + 60, 30):
        y = 606 + 26 * math.sin(x * 0.0055) + 14 * math.sin(x * 0.014 + 1.4)
        pts.append((x, y))
    pts += [(VW + 60, 700)]
    pygame.draw.polygon(bg, (20, 36, 56), pts)

    # 远处松树剪影
    def pine(cx, base, h, w, col):
        tiers = 4
        for i in range(tiers):
            f = i / tiers
            yy = base - h * f
            ww = w * (1 - f * 0.72)
            pygame.draw.polygon(bg, col, [(cx - ww / 2, yy), (cx + ww / 2, yy),
                                          (cx, yy - h / tiers * 1.8)])
        pygame.draw.rect(bg, (18, 28, 38), (cx - 5, base - 6, 10, 30))

    for cx, base, h, w in ((40, 668, 130, 60), (110, 662, 92, 42), (180, 670, 66, 30),
                           (1150, 664, 120, 56), (1080, 658, 84, 40), (1000, 668, 56, 26),
                           (880, 662, 44, 22), (330, 666, 40, 20)):
        pine(cx, base, h, w, (16, 30, 44))

    # 雪地
    ground = [(-20, VH + 20), (-20, 650)]
    for x in range(-20, VW + 40, 24):
        y = 646 + 12 * math.sin(x * 0.006 + 0.6) + 6 * math.sin(x * 0.017 + 2.1)
        ground.append((x, y))
    ground += [(VW + 40, VH + 20)]
    pygame.draw.polygon(bg, (190, 206, 232), ground)
    # 雪面高光 & 阴影
    for i in range(26):
        x = random.randint(-20, VW)
        y = random.randint(660, VH)
        pygame.draw.ellipse(bg, (206, 220, 242, 255),
                            (x, y, random.randint(60, 170), random.randint(10, 26)))
    for i in range(14):
        x = random.randint(-20, VW)
        y = random.randint(690, VH + 10)
        pygame.draw.ellipse(bg, (168, 186, 216),
                            (x, y, random.randint(80, 200), random.randint(14, 30)))

    bg.blit(HOUSE, (VW - 300, 700 - 250))
    bg.blit(SNOWMAN, (118, 700 - 236))
    return bg


# ---------------------------------------------------------------- 动态元素
def init_flakes():
    fl = []
    for _ in range(230):
        fl.append([random.uniform(0, VW), random.uniform(-VH, VH),
                   random.choice((1, 1, 2, 2, 2, 3, 3, 4)),
                   random.uniform(22, 78), random.uniform(0, 6.28), random.uniform(6, 22), 1.0])
    STATE["flakes"] = fl


def build_flake_sprites():
    for r in (1, 2, 3, 4):
        s = pygame.Surface((r * 6, r * 6), pygame.SRCALPHA)
        for rr in range(r * 3, 0, -1):
            a = int(235 * (1 - rr / (r * 3 + 1)) ** 1.6)
            pygame.draw.circle(s, (238, 246, 255, a), (r * 3, r * 3), rr)
        FLAKE_SPR[r] = s


def update_flakes(dt, t, mouse):
    mx, my = mouse
    for f in STATE["flakes"]:
        x, y, r, spd, ph, drift, _ = f
        y += spd * dt
        x += math.sin(t * 0.6 + ph) * drift * dt * 2 + 6 * dt
        d = math.hypot(x - mx, y - my)
        if d < 96:
            k = (96 - d) / 96 * 55 * dt
            x += (x - mx) / (d + 1) * k
            y += (y - my) / (d + 1) * k
        if y > VH + 12:
            y = -12
            x = random.uniform(0, VW)
        if x < -12:
            x = VW + 10
        elif x > VW + 12:
            x = -10
        f[0], f[1] = x, y


def draw_flakes(surf):
    for x, y, r, spd, ph, drift, _ in STATE["flakes"]:
        spr = FLAKE_SPR.get(r)
        if spr is None:
            continue
        surf.blit(spr, (x - r * 3, y - r * 3))


def spawn_firework(x, y, color=None, count=78, power=1.0):
    pal = PALETTES[STATE["palette"]]
    base = color or random.choice(pal)
    for _ in range(count):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(60, 260) * power
        c = base if random.random() < 0.75 else random.choice(pal + [(255, 255, 255)])
        STATE["sparks"].append([x, y, math.cos(ang) * spd, math.sin(ang) * spd,
                                random.uniform(0.9, 1.9), c, random.choice((2, 2, 3))])


def update_sparks(dt):
    alive = []
    for s in STATE["sparks"]:
        s[0] += s[2] * dt
        s[1] += s[3] * dt
        s[3] += 90 * dt          # 重力
        s[2] *= (1 - 1.2 * dt)
        s[3] *= (1 - 1.2 * dt)
        s[4] -= dt
        if s[4] > 0:
            alive.append(s)
    STATE["sparks"] = alive


def draw_sparks(surf):
    for x, y, vx, vy, life, col, r in STATE["sparks"]:
        a = int(235 * min(1.0, life / 0.8))
        g = glow(r * 7, col, 2.0)
        g.set_alpha(a)
        surf.blit(g, (x - r * 7, y - r * 7))
        pygame.draw.line(surf, (col[0], col[1], col[2], int(a * 0.55)),
                         (x, y), (x - vx * 0.028, y - vy * 0.028), 2)
        pygame.draw.circle(surf, (255, 255, 255, a), (int(x), int(y)), max(1, r - 1))


def draw_shooting(surf, t):
    s = STATE["shooting"]
    if s is None:
        return
    x, y, vx, vy, life = s
    for k in range(9):
        px = x - vx * k * 0.026
        py = y - vy * k * 0.026
        a = int(200 * (1 - k / 9) * min(1.0, life / 0.4))
        pygame.draw.line(surf, (255, 255, 255, a), (px, py), (px + vx * 0.012, py + vy * 0.012), 2)


def draw_intro_text(surf, t):
    a = 255 * smooth((t - 0.25) / 1.7) * (1 - smooth((t - 4.15) / 1.05))
    if a <= 2:
        return
    zoom = 1.0 + 0.015 * math.sin(t * 1.7)
    gw, gh = TXT_GLOW.get_size()
    gl = pygame.transform.smoothscale(TXT_GLOW, (int(gw * zoom), int(gh * zoom)))
    gl.set_alpha(int(a * 0.6))
    surf.blit(gl, (VW // 2 - gl.get_width() // 2, 300 - gl.get_height() // 2))

    mw, mh = TXT_MAIN.get_size()
    main = pygame.transform.smoothscale(TXT_MAIN, (int(mw * zoom), int(mh * zoom)))
    main.set_alpha(int(a))
    surf.blit(main, (VW // 2 - main.get_width() // 2, 300 - main.get_height() // 2))

    sa = int(a * 0.92)
    TXT_SUB.set_alpha(sa)
    surf.blit(TXT_SUB, (VW // 2 - TXT_SUB.get_width() // 2, 382))

    ha = int(a * smooth((t - 2.4) / 1.0) * 0.95)
    if ha > 0:
        TXT_HINT_TOP.set_alpha(ha)
        surf.blit(TXT_HINT_TOP, (VW // 2 - TXT_HINT_TOP.get_width() // 2, 432))


def draw_hud(surf, t):
    if not STATE["help_on"]:
        return
    fade = smooth((t - 5.6) / 1.5)
    if fade <= 0:
        return
    a = (170 + 60 * math.sin(t * 1.2)) * fade
    bar = HUD_SURF
    bar.set_alpha(int(a))
    surf.blit(bar, (0, VH - 44))
    mark = HUD_ON if STATE["music_on"] else HUD_OFF
    mark.set_alpha(int(a))
    surf.blit(mark, (26, VH - 38))
    if STATE["toast_t"] > 0 and STATE["toast"]:
        surf_txt = toast_surface(STATE["toast"])
        surf_txt.set_alpha(int(255 * min(1.0, STATE["toast_t"] / 0.6)))
        surf.blit(surf_txt, (VW // 2 - surf_txt.get_width() // 2, 120))


def toast_surface(text):
    if text not in _toast_cache:
        f = load_font(28)
        txt = f.render(text, True, (255, 244, 214))
        pad = 26
        s = pygame.Surface((txt.get_width() + pad * 2, txt.get_height() + pad), pygame.SRCALPHA)
        pygame.draw.rect(s, (20, 26, 44, 190), s.get_rect(), border_radius=14)
        pygame.draw.rect(s, (255, 214, 130, 110), s.get_rect(), 1, border_radius=14)
        s.blit(txt, (pad, pad // 2))
        _toast_cache[text] = s
    return _toast_cache[text]


# ---------------------------------------------------------------- 资源初始化
def init_assets(screen):
    global BG, TREEBASE, GIFTS, HOUSE, SNOWMAN, AURORA
    global TXT_MAIN, TXT_GLOW, TXT_SUB, TXT_HINT_TOP, FONT_HUD, HUD_SURF, HUD_ON, HUD_OFF

    f_big = load_font(108, bold=True)
    TXT_MAIN = f_big.render("圣诞快乐", True, (255, 246, 220))
    TXT_GLOW = blur(f_big.render("圣诞快乐", True, (255, 186, 92)), 6)
    TXT_SUB = load_font(30).render("M E R R Y   C H R I S T M A S", True, (215, 232, 255))
    TXT_HINT_TOP = load_font(22).render("点击任意位置 / 按任意键 继续", True, (180, 200, 230))

    HOUSE = build_house()
    SNOWMAN = build_snowman()
    GIFTS = build_gifts()
    TREEBASE = build_tree()
    BG = build_background()
    build_flake_sprites()
    init_flakes()

    FONT_HUD = load_font(19)
    hints = "鼠标点击 烟花    空格 音乐    上/下键 音量    C 彩灯    F 烟花    R 重播    S 截图    H 隐藏    ESC 退出"
    txt = FONT_HUD.render(hints, True, (206, 220, 244))
    HUD_SURF = pygame.Surface((VW, 44), pygame.SRCALPHA)
    HUD_SURF.fill((8, 12, 24, 165))
    HUD_SURF.blit(txt, (VW - txt.get_width() - 26, 12))
    HUD_ON = FONT_HUD.render("音乐 · 开", True, (255, 226, 150))
    HUD_OFF = FONT_HUD.render("音乐 · 关", True, (150, 160, 180))


# ---------------------------------------------------------------- 绘制一帧
def draw_frame(screen, t):
    screen.blit(BG, (0, 0))
    draw_shooting(screen, t)

    reveal = smooth((t - 4.5) / 2.1)

    # 树下暖光洒在雪地上
    if reveal > 0.01:
        gl = glow(200, (255, 214, 150), 2.6)
        g2 = pygame.transform.smoothscale(gl, (560, 160))
        g2.set_alpha(int(42 * reveal))
        screen.blit(g2, (600 - 280, 690 - 60))

    # 圣诞树
    if reveal > 0.005:
        tree = draw_tree(t, reveal)
        screen.blit(tree, (TREE_X + (TREE_W - tree.get_width()) // 2,
                           TREE_Y + TREE_H - tree.get_height()))

    # 礼物（在树的前面）
    ga = smooth((reveal - 0.42) / 0.55)
    if ga > 0.02:
        g = GIFTS
        g.set_alpha(int(255 * ga))
        screen.blit(g, (600 - 300, 545))

    draw_flakes(screen)
    draw_sparks(screen)

    dark = 1 - smooth((t - 4.25) / 2.0)
    if dark > 0.01:
        ov = pygame.Surface((VW, VH), pygame.SRCALPHA)
        ov.fill((3, 7, 20, int(222 * dark)))
        screen.blit(ov, (0, 0))
    draw_intro_text(screen, t)
    draw_hud(screen, t)


# ---------------------------------------------------------------- 交互
def trigger_firework(x, y, sound=True, count=76, power=1.0):
    spawn_firework(x, y, count=count, power=power)
    if sound and CHIME:
        CHIME.play()


def set_toast(text, sec=1.8):
    STATE["toast"] = text
    STATE["toast_t"] = sec


def screenshot(screen):
    STATE["shots"] += 1
    path = os.path.join(SCRIPT_DIR, "圣诞截图_%s.png" % time.strftime("%H%M%S"))
    pygame.image.save(screen, path)
    set_toast("截图已保存：" + os.path.basename(path), 2.4)


CHIME = None
MUSIC_PATH = None
MUSIC_OK = False


def setup_audio():
    global CHIME, MUSIC_PATH, MUSIC_OK
    try:
        pygame.mixer.init()
    except Exception:
        MUSIC_OK = False
        return
    try:
        tmp = tempfile.gettempdir()
        MUSIC_PATH = build_music(os.path.join(tmp, "xmas_music.wav"))
        audio = build_chime(os.path.join(tmp, "xmas_chime.wav"))
        pygame.mixer.music.load(MUSIC_PATH)
        pygame.mixer.music.set_volume(STATE["volume"])
        pygame.mixer.music.play(-1)
        CHIME = pygame.mixer.Sound(audio)
        CHIME.set_volume(0.5)
        MUSIC_OK = True
    except Exception:
        MUSIC_OK = False


def present(screen, virt):
    """把 1200x800 的画布等比缩放到窗口里，窗口任意大小都不变形。"""
    sw, sh = screen.get_size()
    k = min(sw / VW, sh / VH)
    w, h = int(VW * k), int(VH * k)
    ox, oy = (sw - w) // 2, (sh - h) // 2
    STATE["k"], STATE["ox"], STATE["oy"] = k, ox, oy
    if (sw, sh) == (VW, VH):
        screen.blit(virt, (0, 0))
        return
    screen.fill((0, 0, 0))
    screen.blit(pygame.transform.smoothscale(virt, (w, h)), (ox, oy))


def to_virtual(pos):
    k = STATE["k"] if STATE["k"] else 1.0
    return (int((pos[0] - STATE["ox"]) / k), int((pos[1] - STATE["oy"]) / k))


# ---------------------------------------------------------------- 主循环
def main():
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption("圣诞快乐 · Merry Christmas")

    info = pygame.display.Info()
    win_w = max(720, min(VW, info.current_w - 40))
    win_h = max(480, min(VH, info.current_h - 80))
    screen = pygame.display.set_mode((win_w, win_h), pygame.DOUBLEBUF | pygame.RESIZABLE)
    virt = pygame.Surface((VW, VH)).convert()

    # 先把画面显示出来，再做耗时的音乐合成
    txt = load_font(26).render("正在准备音乐与场景…", True, (220, 232, 250))
    screen.fill((6, 10, 22))
    screen.blit(txt, (win_w // 2 - txt.get_width() // 2, win_h // 2))
    pygame.display.flip()

    init_assets(virt)
    setup_audio()

    clock = pygame.time.Clock()
    running = True

    while running:
        dt = min(0.05, clock.tick(60) / 1000.0)
        STATE["t"] += dt
        t = STATE["t"]
        mouse = to_virtual(pygame.mouse.get_pos())

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                k = e.key
                if k == pygame.K_ESCAPE:
                    running = False
                elif k == pygame.K_SPACE:
                    if MUSIC_OK:
                        if STATE["music_on"]:
                            pygame.mixer.music.pause()
                        else:
                            pygame.mixer.music.unpause()
                        STATE["music_on"] = not STATE["music_on"]
                        set_toast("音乐已" + ("关闭" if not STATE["music_on"] else "打开"))
                    else:
                        set_toast("没有检测到音频设备")
                elif k == pygame.K_UP:
                    STATE["volume"] = min(1.0, STATE["volume"] + 0.1)
                    if MUSIC_OK:
                        pygame.mixer.music.set_volume(STATE["volume"])
                    set_toast("音量 %d%%" % int(STATE["volume"] * 100))
                elif k == pygame.K_DOWN:
                    STATE["volume"] = max(0.0, STATE["volume"] - 0.1)
                    if MUSIC_OK:
                        pygame.mixer.music.set_volume(STATE["volume"])
                    set_toast("音量 %d%%" % int(STATE["volume"] * 100))
                elif k == pygame.K_c:
                    STATE["palette"] = (STATE["palette"] + 1) % len(PALETTES)
                    set_toast("彩灯配色 %d/%d" % (STATE["palette"] + 1, len(PALETTES)))
                elif k == pygame.K_f:
                    trigger_firework(random.randint(200, VW - 200), random.randint(150, 430))
                elif k == pygame.K_r:
                    STATE["t"] = 0.0
                    STATE["sparks"].clear()
                elif k == pygame.K_s:
                    screenshot(virt)
                elif k == pygame.K_h:
                    STATE["help_on"] = not STATE["help_on"]
                else:
                    if t < 4.2:
                        STATE["t"] = 4.2
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if t < 4.2:
                    STATE["t"] = 4.2
                else:
                    trigger_firework(*to_virtual(e.pos))

        # 鼠标拖拽持续放烟花
        if pygame.mouse.get_pressed()[0] and t > 4.4 and random.random() < 0.55:
            trigger_firework(mouse[0], mouse[1], sound=False, count=26, power=0.55)

        update_flakes(dt, t, mouse)
        update_sparks(dt)

        # 随机流星
        if STATE["shooting"] is None and t > STATE["next_shoot"]:
            STATE["shooting"] = [random.randint(120, VW - 200), random.randint(60, 200),
                                 random.uniform(340, 520), random.uniform(120, 190), 1.4]
            STATE["next_shoot"] = t + random.uniform(9, 17)
        if STATE["shooting"]:
            s = STATE["shooting"]
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[4] -= dt
            if s[4] <= 0 or s[0] > VW + 40 or s[1] > VH:
                STATE["shooting"] = None

        if STATE["toast_t"] > 0:
            STATE["toast_t"] -= dt

        draw_frame(virt, t)
        present(screen, virt)
        pygame.display.flip()

    pygame.quit()


# ---------------------------------------------------------------- 截图自检模式
def snapshot_mode():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    screen = pygame.display.set_mode((VW, VH))
    init_assets(screen)
    out = []
    for tt, fw in ((1.6, None), (3.4, None), (5.2, (820, 220)), (6.4, None), (8.5, (300, 250))):
        STATE["t"] = tt
        STATE["sparks"].clear()
        if fw:
            spawn_firework(fw[0], fw[1])
        for _ in range(18):
            update_sparks(0.02)
        draw_frame(screen, tt)
        p = os.path.join(tempfile.gettempdir(), "xmas_snap_%s.png" % tt)
        pygame.image.save(screen, p)
        out.append(p)
    print("\n".join(out))
    pygame.quit()


if __name__ == "__main__":
    if "--snapshot" in sys.argv:
        snapshot_mode()
    else:
        main()
