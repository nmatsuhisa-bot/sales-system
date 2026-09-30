# -*- coding: utf-8 -*-
"""帳票に貼り込む画像（原紙から起こした図）

■ なぜ data URI なのか
  xhtml2pdf には画像パスの解決口（link_callback）を渡していないため、
  相対パスの <img src="..."> はPDF側で読み込めない。data URI なら
  ブラウザ表示・PDF変換のどちらでもそのまま出る。

■ 図の出どころ
  排風機2011年～.xlsx の「BFQ注文確認書」シートに貼ってあった EMF（図形）。
  EMF は MOVETO/LINETO だけの線画のため、_work/emf/emf2png.py で
  座標を読み取ってPNGに起こした。原紙を差し替えるときは同スクリプトを使う。
"""
import base64
import os

_DIR = os.path.dirname(__file__)
_cache = {}


def data_uri(name: str) -> str:
    """assets配下のPNGを data URI にして返す（プロセス内でキャッシュ）"""
    if name not in _cache:
        with open(os.path.join(_DIR, name), "rb") as fh:
            _cache[name] = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
    return _cache[name]
