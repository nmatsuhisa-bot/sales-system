#!/bin/bash
# DWG図面を、CADから見積作成で使えるDXFに変換する
#
# 「CADから見積作成」はDXF（ASCII形式）しか読めない。手元にDWGしか無い場合は
# このスクリプトで変換してからアップロードする。
#
# 使い方:
#   tools/dwg2dxf.sh <DWGのあるフォルダ> [出力先フォルダ]
#   例) tools/dwg2dxf.sh ~/Downloads/OneDrive_1_2026-7-18 ~/Downloads/DXF
#
# 前提: LibreDWG（brew install libredwg）。導入済みなら dwg2dxf コマンドがある。
#
# 注意: LibreDWGはAutoCAD 2018形式(R2018)の読み取りが完全ではない。
#       実績として釧路ウッドプロダクツ製材棟(101MB)は変換できなかった。
#       変換できない図面は、井上電設にAutoCADの DXFOUT で
#       「AutoCAD 2018 DXF」として書き出してもらうのが確実。

set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

SRC="${1:-}"
OUT="${2:-$PWD/dxf}"

if [ -z "$SRC" ] || [ ! -d "$SRC" ]; then
  echo "使い方: $0 <DWGのあるフォルダ> [出力先フォルダ]" >&2
  exit 1
fi

if ! command -v dwg2dxf >/dev/null 2>&1; then
  echo "dwg2dxf が見つかりません。先に導入してください:" >&2
  echo "  brew install libredwg" >&2
  exit 1
fi

mkdir -p "$OUT"
ok=0; ng=0

shopt -s nullglob
for f in "$SRC"/*.dwg "$SRC"/*.DWG; do
  base="$(basename "$f")"
  dst="$OUT/${base%.*}.dxf"
  printf '%-52s ' "${base:0:50}"
  if dwg2dxf -o "$dst" "$f" >/dev/null 2>&1 && [ -s "$dst" ]; then
    printf '成功 (%s)\n' "$(du -h "$dst" | cut -f1)"
    ok=$((ok+1))
  else
    printf '失敗 — DXFでの書き出しを依頼してください\n'
    rm -f "$dst"
    ng=$((ng+1))
  fi
done

echo
echo "変換完了: 成功 ${ok}件 / 失敗 ${ng}件"
echo "出力先: $OUT"
