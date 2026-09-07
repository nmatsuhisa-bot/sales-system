import { useEffect, useState } from 'react';
import { arrangementApi } from '../api';
import { Plus, Trash2, Save, Printer, X } from 'lucide-react';

// 明細行の列定義（手配書タイプごと）。key は帳票PDF側の items_json と揃える
const CRANE_COLS = [
  { key: 'machine', label: '機械名', w: '110px' },
  { key: 'spec', label: '重量・仕様', w: '110px' },
  { key: 'start_date', label: '使用開始日', w: '100px' },
  { key: 'start_time', label: '開始時刻', w: '80px' },
  { key: 'end_date', label: '使用終了日', w: '100px' },
  { key: 'end_time', label: '終了時刻', w: '80px' },
  { key: 'delivery', label: '納品方法', w: '90px' },
  { key: 'return_method', label: '返却方法', w: '90px' },
  { key: 'note', label: '備考', w: '' },
];
const SHIPPING_COLS = [
  { key: 'truck_type', label: '車種', w: '90px' },
  { key: 'cargo', label: '積込内容', w: '' },
  { key: 'load_date', label: '積込日', w: '100px' },
  { key: 'arrive_date', label: '到着日', w: '100px' },
  { key: 'arrive_time', label: '到着時刻', w: '80px' },
  { key: 'load1_place', label: '積込①', w: '80px' },
  { key: 'load1_time', label: '①時間', w: '70px' },
  { key: 'load2_place', label: '積込②', w: '80px' },
  { key: 'load2_time', label: '②時間', w: '70px' },
  { key: 'load3_place', label: '積込③', w: '80px' },
  { key: 'load3_time', label: '③時間', w: '70px' },
  { key: 'note', label: '備考', w: '' },
];
const HOTEL_COLS = [
  { key: 'hotel', label: 'ホテル名', w: '140px' },
  { key: 'tel', label: 'TEL', w: '100px' },
  { key: 'checkin', label: 'IN', w: '90px' },
  { key: 'checkout', label: 'OUT', w: '90px' },
  { key: 'nights', label: '泊', w: '40px' },
  { key: 'persons', label: '人数', w: '50px' },
  { key: 'price', label: '値段/泊', w: '70px' },
  { key: 'guests', label: '宿泊者', w: '' },
  { key: 'note', label: '備考', w: '' },
];

// 排風機は明細行ではなく、仕様項目（spec_json / instruction_json）を持つ
const FAN_SPEC = [
  { key: 'frequency', label: '周波数(Hz)' },
  { key: 'voltage', label: '動力(V)' },
  { key: 'control_voltage', label: '制御(V)' },
  { key: 'motor_kw', label: 'ﾓｰﾀ出力(kW)' },
  { key: 'motor_pole', label: '極数(P)' },
  { key: 'motor_type', label: 'ﾓｰﾀ仕様（屋内/屋外）' },
  { key: 'motor_flange', label: '取付（ﾌﾗﾝｼﾞ/脚）' },
  { key: 'motor_maker', label: 'ﾒｰｶ' },
  { key: 'motor_note', label: 'ﾓｰﾀ備考' },
  { key: 'spec_place', label: '仕様（屋内/屋外）' },
  { key: 'intake_dia', label: '吸気口 φ' },
  { key: 'intake_flange', label: '吸気口ﾌﾗﾝｼﾞ' },
  { key: 'exhaust_dia', label: '排気口 φ' },
  { key: 'exhaust_flange', label: '排気口ﾌﾗﾝｼﾞ' },
  { key: 'switch_type', label: 'ｽｲｯﾁ' },
  { key: 'control_panel', label: '制御盤' },
  { key: 'paint_color', label: '指定色' },
  { key: 'color_no', label: '色番号' },
];
const FAN_INSTRUCTION = [
  { key: 'order_customer', label: '御注文主' },
  { key: 'usage_spec', label: '用途・仕様' },
  { key: 'bearing_fan', label: '軸受（羽根側）' },
  { key: 'bearing_pulley', label: '軸受（ﾌﾟｰﾘ側）' },
  { key: 'motor_pulley', label: 'ﾓｰﾀ側ﾌﾟｰﾘ' },
  { key: 'fan_pulley', label: 'ﾌｧﾝ側ﾌﾟｰﾘ' },
  { key: 'belt', label: 'Vﾍﾞﾙﾄ' },
  { key: 'rpm', label: '回転数(rpm)' },
  { key: 'cover', label: 'ｶﾊﾞｰ' },
  { key: 'inspection_port', label: '点検口' },
  { key: 'frame', label: '架台' },
  { key: 'paint', label: '塗装色' },
  { key: 'pressure', label: '想定圧力(mmaq)' },
  { key: 'airflow', label: '想定風量(㎥/min)' },
  { key: 'current', label: '想定電流(A)' },
];

const CONFIG: Record<string, any> = {
  crane: {
    title: 'クレーン・作業車等 依頼書', cols: CRANE_COLS,
    header: [
      { key: 'site_name', label: '現場名' },
      { key: 'site_address', label: '現場住所' },
      { key: 'site_tel', label: '現場TEL' },
      { key: 'site_dept', label: '現場部署' },
      { key: 'site_contact', label: '現場ご担当' },
      { key: 'order_no', label: '注番' },
      { key: 'vendor_name', label: '依頼業者' },
      { key: 'vendor_branch', label: '営業所' },
      { key: 'vendor_contact', label: '業者ご担当' },
      { key: 'vendor_tel', label: '業者TEL' },
      { key: 'vendor_fax', label: '業者FAX' },
      { key: 'issue_date', label: '作成日', type: 'date' },
      { key: 'staff_name', label: '担当' },
      { key: 'creator_name', label: '作成' },
    ],
    get: arrangementApi.getCrane, save: arrangementApi.saveCrane, pdf: arrangementApi.cranePdf,
    vendorCategory: 'クレーン・作業車',
    vendorFill: (v: any) => ({ vendor_name: v.name, vendor_branch: v.branch || '', vendor_contact: v.contact_person || '', vendor_tel: v.phone || '', vendor_fax: v.fax || '' }),
  },
  shipping: {
    title: 'トラック手配 送り状', cols: SHIPPING_COLS,
    header: [
      { key: 'dest_name', label: '送り先' },
      { key: 'dest_address', label: '送り先住所' },
      { key: 'dest_tel', label: '送り先TEL' },
      { key: 'dest_dept', label: '送り先部署' },
      { key: 'dest_contact', label: '送り先ご担当' },
      { key: 'order_no', label: '注番' },
      { key: 'carrier_name', label: '運送業者' },
      { key: 'carrier_contact', label: '運送ご担当' },
      { key: 'carrier_tel', label: '運送TEL' },
      { key: 'carrier_fax', label: '運送FAX' },
      { key: 'issue_date', label: '作成日', type: 'date' },
      { key: 'staff_name', label: '担当' },
      { key: 'creator_name', label: '作成' },
    ],
    get: arrangementApi.getShipping, save: arrangementApi.saveShipping, pdf: arrangementApi.shippingPdf,
    vendorCategory: '運送（トラック）',
    vendorFill: (v: any) => ({ carrier_name: v.name, carrier_contact: v.contact_person || '', carrier_tel: v.phone || '', carrier_fax: v.fax || '' }),
  },
  fan: {
    title: '排風機 注文確認書 / ファン作業指示書', cols: null,
    header: [
      { key: 'order_no', label: '受注No.' },
      { key: 'form_type', label: '様式（PL/BFQ/FS）' },
      { key: 'vendor_name', label: '発注先' },
      { key: 'vendor_contact', label: '発注先ご担当' },
      { key: 'user_name', label: 'ユーザー名' },
      { key: 'user_plant', label: 'ユーザー工場' },
      { key: 'user_address', label: 'ユーザー住所' },
      { key: 'user_tel', label: 'ユーザーTEL' },
      { key: 'user_contact', label: 'ユーザーご担当' },
      { key: 'ship_to_name', label: '出荷先' },
      { key: 'ship_to_plant', label: '出荷先工場' },
      { key: 'ship_to_address', label: '出荷先住所' },
      { key: 'ship_to_tel', label: '出荷先TEL' },
      { key: 'ship_to_contact', label: '出荷先ご担当' },
      { key: 'ship_date', label: '出荷日', type: 'date' },
      { key: 'transport_method', label: '運送方法（引取/ﾊﾟﾚｯﾄ/工事）' },
      { key: 'product_name', label: '名称' },
      { key: 'model', label: '型式' },
      { key: 'drive_type', label: '駆動方式' },
      { key: 'serial_no', label: '製造No.' },
      { key: 'sales_person_name', label: '営業担当' },
      { key: 'creator_name', label: '作成' },
    ],
    sections: [
      { field: 'spec_json', title: '仕様（注文確認書）', items: FAN_SPEC },
      { field: 'instruction_json', title: '作業指示（ファン作業指示書）', items: FAN_INSTRUCTION },
    ],
    get: arrangementApi.getFan, save: arrangementApi.saveFan, pdf: arrangementApi.fanPdf,
    extraPdf: { label: 'ファン作業指示書', url: arrangementApi.fanInstructionPdf },
    vendorCategory: '排風機',
    vendorFill: (v: any) => ({ vendor_name: v.name, vendor_contact: v.contact_person || '' }),
  },
  hotel: {
    title: '宿泊予約票', cols: HOTEL_COLS,
    header: [
      { key: 'site_name', label: '現場' },
      { key: 'site_address', label: '現場住所' },
    ],
    get: arrangementApi.getHotel, save: arrangementApi.saveHotel, pdf: arrangementApi.hotelPdf,
  },
};

export default function ArrangementModal({ type, orderId, childNo, onClose }: any) {
  const cfg = CONFIG[type];
  const [data, setData] = useState<any>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    cfg.get(orderId).then((r: any) => setData(r.data)).catch(() => setData({ items_json: [] }));
  }, [orderId]);

  if (!data) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl p-8 text-gray-400">読み込み中...</div>
      </div>
    );
  }

  const items = data.items_json || [];

  const setHeader = (key: string, v: string) => setData((d: any) => ({ ...d, [key]: v }));
  // spec_json / instruction_json の中の1項目を更新する
  const setNested = (field: string, key: string, v: string) =>
    setData((d: any) => ({ ...d, [field]: { ...(d[field] || {}), [key]: v } }));
  const addRow = () => setData((d: any) => ({ ...d, items_json: [...(d.items_json || []), {}] }));
  const updateRow = (idx: number, key: string, v: string) =>
    setData((d: any) => ({
      ...d,
      items_json: d.items_json.map((it: any, i: number) => i === idx ? { ...it, [key]: v } : it),
    }));
  const deleteRow = (idx: number) =>
    setData((d: any) => ({ ...d, items_json: d.items_json.filter((_: any, i: number) => i !== idx) }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await cfg.save(orderId, data);
      alert('保存しました');
    } catch (e: any) {
      alert(e.response?.data?.detail || '保存に失敗しました');
    } finally {
      setSaving(false);
    }
  };

  // 保存してから帳票を開く（自動補完しただけの未保存状態でも出力できるようにする）
  const handlePdf = async (urlFn?: any, fmt: string = 'pdf') => {
    await cfg.save(orderId, data).catch(() => {});
    window.open((urlFn || cfg.pdf)(orderId, fmt), '_blank');
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-5xl max-h-[92vh] flex flex-col">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-800">{cfg.title}</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              子ID: <strong className="text-blue-700">{childNo}</strong>
              {data._autofilled && (
                <span className="ml-2 inline-block bg-amber-50 border border-amber-300 text-amber-700 px-2 py-0.5 rounded text-[11px]">
                  案件・見積から自動補完しました（未保存）。内容を確認・加筆してください
                </span>
              )}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={20} /></button>
        </div>

        <div className="overflow-y-auto flex-1 p-4">
          {/* 業者マスタから選択 */}
          {cfg.vendorCategory && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <label className="block text-xs font-semibold text-blue-700 mb-1.5">業者マスタから選択（住所・連絡先を自動補完）</label>
              <VendorPicker category={cfg.vendorCategory}
                onSelect={(v: any) => setData((d: any) => ({ ...d, ...cfg.vendorFill(v) }))} />
            </div>
          )}

          {/* ヘッダー項目 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            {cfg.header.map((h: any) => (
              <div key={h.key}>
                <label className="block text-xs text-gray-500 mb-1">{h.label}</label>
                <input type={h.type || 'text'} value={data[h.key] || ''}
                  onChange={e => setHeader(h.key, e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
              </div>
            ))}
          </div>

          {/* 仕様セクション（排風機のように明細行を持たない帳票） */}
          {cfg.sections && cfg.sections.map((sec: any) => (
            <div key={sec.field} className="mb-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">{sec.title}</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {sec.items.map((it: any) => (
                  <div key={it.key}>
                    <label className="block text-xs text-gray-500 mb-1">{it.label}</label>
                    <input value={(data[sec.field] || {})[it.key] || ''}
                      onChange={e => setNested(sec.field, it.key, e.target.value)}
                      className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* 明細行テーブル */}
          {cfg.cols && (<>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-700">明細（{items.length}件）</h3>
            <button onClick={addRow}
              className="flex items-center gap-1 bg-blue-50 border border-blue-300 text-blue-700 px-3 py-1 rounded-lg text-xs font-medium hover:bg-blue-100">
              <Plus size={12} /> 行を追加
            </button>
          </div>
          <div className="overflow-x-auto border border-gray-100 rounded-lg">
            <table className="w-full text-xs">
              <thead className="bg-gray-50">
                <tr>
                  {cfg.cols.map((c: any) => (
                    <th key={c.key} className="px-2 py-2 text-left font-medium text-gray-500" style={c.w ? { width: c.w } : {}}>{c.label}</th>
                  ))}
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {items.map((it: any, idx: number) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    {cfg.cols.map((c: any) => (
                      <td key={c.key} className="px-1 py-1">
                        <input value={it[c.key] || ''} onChange={e => updateRow(idx, c.key, e.target.value)}
                          className="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-400 focus:outline-none" />
                      </td>
                    ))}
                    <td className="px-1 py-1 text-center">
                      <button onClick={() => deleteRow(idx)} className="text-red-300 hover:text-red-500"><Trash2 size={12} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {items.length === 0 && <div className="text-center py-8 text-gray-400 text-sm">「行を追加」で明細を追加してください</div>}
          </div>
          </>)}

          {/* 備考 */}
          <div className="mt-4">
            <label className="block text-xs text-gray-500 mb-1">備考（全体）</label>
            <textarea value={data.notes || ''} rows={2} onChange={e => setHeader('notes', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" />
          </div>
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-gray-100">
          <button onClick={onClose} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">閉じる</button>
          {cfg.extraPdf && (
            <button onClick={() => handlePdf(cfg.extraPdf.url)}
              className="flex items-center gap-1 bg-teal-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-teal-700">
              <Printer size={14} /> {cfg.extraPdf.label}
            </button>
          )}
          <button onClick={() => handlePdf(cfg.pdf, 'html')}
            className="flex items-center gap-1 border border-gray-300 text-gray-700 px-4 py-2 rounded-lg text-sm hover:bg-gray-50">
            <Printer size={14} /> 印刷プレビュー
          </button>
          <button onClick={() => handlePdf()}
            className="flex items-center gap-1 bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700">
            <Printer size={14} /> 保存してPDF
          </button>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-1 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-60">
            <Save size={14} /> {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}

// 業者マスタ検索セレクタ
function VendorPicker({ category, onSelect }: { category: string; onSelect: (v: any) => void }) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<any>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      arrangementApi.listVendors(category, q || undefined)
        .then((r: any) => { setResults(r.data); setOpen(true); })
        .catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [q, category]);

  return (
    <div className="relative">
      <input value={q} onChange={e => { setQ(e.target.value); setPicked(null); }}
        onFocus={() => results.length && setOpen(true)}
        placeholder="業者名・営業所・担当で検索"
        className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-400 focus:outline-none" />
      {open && results.length > 0 && !picked && (
        <div className="absolute z-30 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {results.map(v => (
            <button key={v.id} onClick={() => { onSelect(v); setPicked(v); setQ(v.name); setOpen(false); }}
              className="block w-full text-left px-3 py-1.5 text-xs hover:bg-blue-50 border-b border-gray-50 last:border-0">
              <span className="font-medium text-gray-800">{v.name}</span>
              {v.branch && <span className="text-gray-500"> / {v.branch}</span>}
              <span className="text-gray-400 ml-2">担当:{v.contact_person || '—'} TEL:{v.phone || '—'}</span>
            </button>
          ))}
        </div>
      )}
      {picked && (
        <p className="mt-1 text-xs text-green-700">✓ {picked.name}{picked.branch ? ` / ${picked.branch}` : ''} を反映しました</p>
      )}
    </div>
  );
}
