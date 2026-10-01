# -*- coding: utf-8 -*-
"""帳票の編集画面に埋め込むJSが壊れていないか確かめる。

一度、閉じ括弧が1つ余ったまま本番へ出てしまい、編集画面のスクリプトが丸ごと
動かなくなった（保存・業者検索・担当者の反映が全部無言で効かなくなる）。
HTMLは200で返るため、画面を開くだけの確認では気づけない。
"""
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.form_edit import EDIT_JS  # noqa: E402

STUB_CFG = '{vendors:[],staff:[],staff_map:{},vendor_map:{}}'


@pytest.mark.skipif(shutil.which("node") is None, reason="node が無い環境では確かめられない")
def test_edit_js_parses():
    js = EDIT_JS.replace("__CFG__", STUB_CFG)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(js)
        path = fh.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        assert r.returncode == 0, "編集画面のJSに構文エラーがあります\n" + r.stderr
    finally:
        os.unlink(path)


def test_edit_js_defines_expected_entry_points():
    """画面のHTMLから呼ぶ関数が消えていないか（名前を変えたら帳票側も直す）"""
    for name in ("efSave", "efPdf", "efOp", "efVFilter", "efVKey", "efVClose",
                 "efVendor", "efStaff", "efDelRow"):
        assert "window.%s" % name in EDIT_JS, "%s が定義されていません" % name
