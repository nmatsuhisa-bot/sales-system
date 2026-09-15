#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置図PDF → 図面画像（システム取込用）を作る。

  python3 tools/equipment_prepare_drawings.py <PDFのフォルダ or PDF...> [-o 出力先] [--dpi 150]

出力（PDF 1 枚につき 2 ファイル）:
  <名前>.png           背景用。図面に焼き込まれた赤い機械番号（赤枠・赤字）を白で塗りつぶしたもの
  <名前>_original.png  番号入りの元図面（画面の「元図面を表示」で参照する）

赤の判定は「R が高く G・B が低い」画素（純赤系）。CAD の黒線・寸法・青の写真は残る。
PyMuPDF / Pillow / numpy が必要（ローカル作業用。サーバ側では使わない）。
"""
import argparse
import os
import sys

import fitz  # PyMuPDF
import numpy as np
from PIL import Image


def render(pdf_path: str, dpi: int) -> Image.Image:
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def remove_red(img: Image.Image) -> tuple:
    """赤系画素を白にする。戻り値 (画像, 置換画素数)"""
    a = np.asarray(img).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mask = (r > 150) & (g < 120) & (b < 120) & ((r - g) > 80) & ((r - b) > 80)
    # アンチエイリアスの縁（薄い赤〜ピンク）も拾うため 1 画素膨張
    m = mask.copy()
    m[1:, :] |= mask[:-1, :]
    m[:-1, :] |= mask[1:, :]
    m[:, 1:] |= mask[:, :-1]
    m[:, :-1] |= mask[:, 1:]
    out = a.copy()
    out[m] = 255
    return Image.fromarray(out.astype(np.uint8)), int(mask.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", default="_work/equipment/drawings")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    pdfs = []
    for p in args.inputs:
        if os.path.isdir(p):
            pdfs += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.lower().endswith(".pdf")]
        else:
            pdfs.append(p)
    os.makedirs(args.out, exist_ok=True)
    for pdf in pdfs:
        name = os.path.splitext(os.path.basename(pdf))[0].replace("　", "_").replace(" ", "_")
        img = render(pdf, args.dpi)
        clean, n = remove_red(img)
        img.save(os.path.join(args.out, f"{name}_original.png"), optimize=True)
        clean.save(os.path.join(args.out, f"{name}.png"), optimize=True)
        print(f"{name}: {img.width}x{img.height}px  赤画素 {n:,} を除去")


if __name__ == "__main__":
    sys.exit(main())
