// ブラウザ内でDXFを走査し、見積生成に必要な情報だけを取り出す。
//
// 実運用の図面は13〜101MBあり、そのままサーバへ送るとリクエスト上限・
// タイムアウトに掛かる（実測: 48MB/59MB とも応答なし）。
// 必要なのは「INSERTのブロック名」と「TEXT/MTEXT/ATTRIBの文字」だけなので
// ここで抽出し、数KBのJSONにしてから送る。
//
// DXFは「グループコード行 → 値行」の繰り返しのテキスト形式。

export interface DxfScanResult {
  block_names: string[];
  texts: string[];
  insunits?: string;
  acadver?: string;
  stats: { bytes: number; blocks: number; texts: number; ms: number };
}

// サーバへ送るテキストの絞り込み（型式・径・容量・風量・制御盤・既設のいずれかを含む行）
const RELEVANT = /(BFR|BFQ|SCA|SCD|ADC|CYP|CYT|CY|PLD|PL|RV|FS|ASM|SD-?\d)|%%[Cc]\d|[φΦ]\d|[kK][wW]|m3\/min|㎥|制御盤|既設/;
const MAX_TEXTS = 4000;

export async function scanDxf(file: File): Promise<DxfScanResult> {
  const t0 = performance.now();
  const buf = await file.arrayBuffer();

  // バイナリDXFは非対応（先頭に固定の識別子が入る）
  const head = new TextDecoder('ascii').decode(new Uint8Array(buf, 0, Math.min(22, buf.byteLength)));
  if (head.startsWith('AutoCAD Binary DXF')) {
    throw new Error('バイナリDXFには対応していません。AutoCADで「AutoCAD 2018 DXF」（ASCII形式）として保存し直してください');
  }

  const text = new TextDecoder('utf-8', { fatal: false }).decode(new Uint8Array(buf));

  const block_names: string[] = [];
  const texts: string[] = [];
  let insunits: string | undefined;
  let acadver: string | undefined;

  let inEntities = false;
  let sectionNext = false;   // 直前が (0, SECTION) で、次の (2, 名前) が区名
  let entity = '';
  let headerVar = '';

  // 行イテレータ（split('\n')で巨大配列を作らないよう indexOf で走査）
  let pos = 0;
  const nextLine = (): string | null => {
    if (pos >= text.length) return null;
    const nl = text.indexOf('\n', pos);
    const end = nl === -1 ? text.length : nl;
    const line = text.slice(pos, end);
    pos = end + 1;
    return line;
  };

  for (;;) {
    const codeLine = nextLine();
    if (codeLine === null) break;
    const valueLine = nextLine();
    if (valueLine === null) break;

    const code = codeLine.trim();
    const value = valueLine.replace(/\r$/, '');

    if (code === '0') {
      const v = value.trim();
      if (v === 'SECTION') { sectionNext = true; entity = ''; continue; }
      if (v === 'ENDSEC') { inEntities = false; entity = ''; continue; }
      entity = v;
      continue;
    }

    if (sectionNext && code === '2') {
      inEntities = value.trim() === 'ENTITIES';
      sectionNext = false;
      continue;
    }

    // HEADER の $INSUNITS / $ACADVER
    if (code === '9') { headerVar = value.trim(); continue; }
    if (headerVar === '$INSUNITS' && code === '70') { insunits = value.trim(); headerVar = ''; continue; }
    if (headerVar === '$ACADVER' && code === '1') { acadver = value.trim(); headerVar = ''; continue; }

    if (!inEntities) continue;

    if (entity === 'INSERT' && code === '2') {
      block_names.push(value.trim());
    } else if ((entity === 'TEXT' || entity === 'MTEXT' || entity === 'ATTRIB') && (code === '1' || code === '3')) {
      if (texts.length < MAX_TEXTS && RELEVANT.test(value)) texts.push(value);
    }
  }

  return {
    block_names, texts, insunits, acadver,
    stats: { bytes: file.size, blocks: block_names.length, texts: texts.length, ms: Math.round(performance.now() - t0) },
  };
}
