#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置図（番号入りの元図面 PNG）から機械番号の位置を抽出し、初期配置 CSV の材料を作る。

  python3 tools/equipment_extract_positions.py <図面フォルダ> [-o 出力フォルダ] [--machines 機械一覧.csv]

図面フォルダの `*_original.png`（tools/equipment_prepare_drawings.py の出力）を対象にする。
1. 赤枠（赤い文字）の連結成分を検出し、枠ごとに切り出して OCR（tesseract、英数字とハイフンのみ）
2. 図面全体を OCR して、黒字の番号（溶接棚の枠など）も拾う（赤枠と重なるものは除く）
出力:
  positions_raw.csv     drawing, label, source(red/black), x, y（画像に対する 0〜1）, px, py, conf, in_list
  <図面名>_sheet.png     赤枠の切り出しと OCR 結果を並べた確認用シート（目で照合する）
tesseract / Pillow / numpy が必要（ローカル作業用）。
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

CODE_RE = re.compile(r"^(S1|S2|SK|SKW|SW|SA|SR|F|FW|FA|B|BW|K|KW|KA|H)-?(\d{1,3})([a-z]?)$")


def norm(label: str):
    s = label.strip().upper().replace("—", "-").replace("_", "-").replace(" ", "")
    s = s.replace("O", "0") if re.match(r"^[A-Z]+-?[0-9O]+$", s) and "-" in s else s
    m = CODE_RE.match(s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}{m.group(3)}"
    return None


def ocr(img: Image.Image, psm: int = 7) -> tuple:
    """(text, conf) tesseract で英数字のみ。tsv から単語を結合して返す"""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "c.png")
        img.save(p)
        r = subprocess.run(["tesseract", p, "-", "--psm", str(psm), "-c", "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-?", "tsv"],
                           capture_output=True, text=True)
    words, confs = [], []
    for line in r.stdout.splitlines()[1:]:
        c = line.split("\t")
        if len(c) >= 12 and c[11].strip():
            words.append(c[11].strip()); confs.append(float(c[10]))
    return "".join(words), (min(confs) if confs else 0.0)


def red_boxes(img: Image.Image):
    a = np.asarray(img).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mask = (r > 150) & (g < 120) & (b < 120) & ((r - g) > 80) & ((r - b) > 80)
    # 連結成分（4近傍、膨張して枠と文字をつなげる）
    m = mask.copy()
    for _ in range(3):
        d = m.copy()
        d[1:, :] |= m[:-1, :]; d[:-1, :] |= m[1:, :]; d[:, 1:] |= m[:, :-1]; d[:, :-1] |= m[:, 1:]
        m = d
    h, w = m.shape
    labels = np.zeros((h, w), dtype=np.int32)
    boxes = []
    cur = 0
    ys, xs = np.nonzero(m)
    order = list(zip(ys.tolist(), xs.tolist()))
    visited = np.zeros((h, w), dtype=bool)
    for y0, x0 in order:
        if visited[y0, x0]:
            continue
        cur += 1
        stack = [(y0, x0)]; visited[y0, x0] = True
        miny = maxy = y0; minx = maxx = x0; n = 0
        while stack:
            y, x = stack.pop(); n += 1
            miny = min(miny, y); maxy = max(maxy, y); minx = min(minx, x); maxx = max(maxx, x)
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True; stack.append((ny, nx))
        bw, bh = maxx - minx + 1, maxy - miny + 1
        if 25 <= bw <= 220 and 12 <= bh <= 60 and n >= 60:
            boxes.append((minx, miny, maxx, maxy))
    # 近接する枠をまとめる（枠線と文字が分かれた場合）
    boxes.sort()
    merged = []
    for bx in boxes:
        for i, mb in enumerate(merged):
            if bx[0] <= mb[2] + 6 and bx[2] >= mb[0] - 6 and bx[1] <= mb[3] + 6 and bx[3] >= mb[1] - 6:
                merged[i] = (min(mb[0], bx[0]), min(mb[1], bx[1]), max(mb[2], bx[2]), max(mb[3], bx[3])); break
        else:
            merged.append(bx)
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--machines", default="_work/equipment/machine_list.csv")
    args = ap.parse_args()
    out = args.out or args.folder
    codes = set()
    if os.path.exists(args.machines):
        for enc in ("utf-8-sig", "cp932"):
            try:
                with open(args.machines, encoding=enc, newline="") as f:
                    codes = {norm(r.get("管理番号", "")) for r in csv.DictReader(f)} - {None}
                break
            except UnicodeDecodeError:
                continue
    rows = []
    for fn in sorted(os.listdir(args.folder)):
        if not fn.endswith("_original.png"):
            continue
        name = fn[: -len("_original.png")]
        img = Image.open(os.path.join(args.folder, fn)).convert("RGB")
        W, H = img.size
        boxes = red_boxes(img)
        crops = []
        for (x0, y0, x1, y1) in boxes:
            crop = img.crop((max(0, x0 - 4), max(0, y0 - 4), min(W, x1 + 5), min(H, y1 + 5)))
            # 赤を黒にして白黒化、3倍に拡大
            a = np.asarray(crop).astype(np.int16)
            red = (a[..., 0] > 150) & (a[..., 1] < 120) & (a[..., 2] < 120)
            bw = np.where(red, 0, 255).astype(np.uint8)
            c2 = Image.fromarray(bw).resize((bw.shape[1] * 3, bw.shape[0] * 3), Image.LANCZOS)
            text, conf = ocr(c2)
            label = norm(text) or text
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            rows.append({"drawing": name, "label": label, "raw": text, "source": "red", "x": round(cx / W, 6), "y": round(cy / H, 6),
                         "px": int(cx), "py": int(cy), "conf": round(conf, 1), "in_list": label in codes})
            crops.append((crop, label, conf))
        # 確認用シート
        cols = 6; cw, ch = 260, 70
        sheet = Image.new("RGB", (cols * cw, ((len(crops) + cols - 1) // cols) * ch + 10), "white")
        dr = ImageDraw.Draw(sheet)
        for i, (crop, label, conf) in enumerate(crops):
            x = (i % cols) * cw; y = (i // cols) * ch + 5
            c = crop.copy(); c.thumbnail((150, 40))
            sheet.paste(c, (x + 5, y))
            dr.text((x + 160, y + 5), f"#{i}", fill="black")
            dr.text((x + 160, y + 22), f"{label} ({conf:.0f})", fill="blue" if label in codes else "red")
        sheet.save(os.path.join(out, f"{name}_sheet.png"))
        # 黒字の番号（図面全体を OCR）
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "page.png")
            img.save(p)
            r = subprocess.run(["tesseract", p, "-", "--psm", "11", "-c", "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-", "tsv"],
                               capture_output=True, text=True)
        n_black = 0
        for line in r.stdout.splitlines()[1:]:
            c = line.split("\t")
            if len(c) < 12 or not c[11].strip():
                continue
            label = norm(c[11])
            if not label or label not in codes:
                continue
            left, top, w, h = int(c[6]), int(c[7]), int(c[8]), int(c[9])
            cx, cy = left + w / 2, top + h / 2
            if any(x0 - 10 <= cx <= x1 + 10 and y0 - 10 <= cy <= y1 + 10 for (x0, y0, x1, y1) in boxes):
                continue
            rows.append({"drawing": name, "label": label, "raw": c[11], "source": "black", "x": round(cx / W, 6), "y": round(cy / H, 6),
                         "px": int(cx), "py": int(cy), "conf": float(c[10]), "in_list": True})
            n_black += 1
        print(f"{name}: 赤枠 {len(boxes)}（一覧と一致 {sum(1 for r_ in rows if r_['drawing'] == name and r_['source'] == 'red' and r_['in_list'])}）, 黒字 {n_black}")
    with open(os.path.join(out, "positions_raw.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["drawing", "label", "raw", "source", "x", "y", "px", "py", "conf", "in_list"])
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} 件 → {os.path.join(out, 'positions_raw.csv')}")


if __name__ == "__main__":
    sys.exit(main())
