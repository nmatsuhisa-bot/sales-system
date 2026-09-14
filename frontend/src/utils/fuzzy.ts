// マスタの曖昧検索
// 全角/半角・大文字/小文字・カタカナ/ひらがな・空白や記号・法人格（株式会社/(株) など）の違いを無視して照合する。
// 空白区切りの語はすべて含む必要がある（例:「宮川 工機」）。

const CORP_RE = /株式会社|有限会社|合同会社|\(株\)|\(有\)|\(同\)/g;
const SEP_RE = /[\s・･\-‐－ー_/／.,，、。()（）\[\]［］「」『』]/g;

export function normalizeForSearch(s: unknown): string {
  if (s == null) return '';
  let t = String(s).normalize('NFKC').toLowerCase();
  t = t.replace(CORP_RE, '');
  // カタカナ → ひらがな（「ミヤカワ」と「みやかわ」を同一視）
  t = t.replace(/[ァ-ヶ]/g, c => String.fromCharCode(c.charCodeAt(0) - 0x60));
  return t.replace(SEP_RE, '');
}

function isSubsequence(needle: string, hay: string): boolean {
  let i = 0;
  for (let j = 0; j < hay.length && i < needle.length; j++) {
    if (hay[j] === needle[i]) i++;
  }
  return i === needle.length;
}

/** 一致しなければ -1。値が小さいほど上位（前方一致 < 部分一致 < 飛び飛び一致） */
export function fuzzyScore(query: string, text: string): number {
  const tokens = String(query || '').split(/[\s　]+/).map(normalizeForSearch).filter(Boolean);
  if (!tokens.length) return 0;
  const hay = normalizeForSearch(text);
  let score = 0;
  for (const tk of tokens) {
    const pos = hay.indexOf(tk);
    if (pos === 0) score += 0;
    else if (pos > 0) score += 10 + Math.min(pos, 50);
    else if (tk.length >= 2 && isSubsequence(tk, hay)) score += 200;
    else return -1;
  }
  return score;
}

/** 候補を絞り込み、一致度順（同点は元の並び順）に並べる */
export function fuzzyFilter<T>(items: T[], query: string, textOf: (item: T) => string): T[] {
  if (!String(query || '').trim()) return items;
  return items
    .map((item, idx) => ({ item, idx, s: fuzzyScore(query, textOf(item)) }))
    .filter(x => x.s >= 0)
    .sort((a, b) => a.s - b.s || a.idx - b.idx)
    .map(x => x.item);
}
