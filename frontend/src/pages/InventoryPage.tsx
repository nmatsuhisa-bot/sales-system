// ============================================
// 在庫管理ページ（部材ベース：在庫 = 入荷 − 利用）
// ============================================
import { useEffect, useState } from 'react';
import { inventoryApi, procurementApi } from '../api';
import { Boxes, Plus, Search, History, X, Check } from 'lucide-react';

const MOVE_TYPES = ['入荷', '利用', '引当', '調整'];
const MOVE_COLORS: Record<string, string> = {
  '入荷': 'text-green-600', '利用': 'text-red-500', '引当': 'text-orange-500', '調整': 'text-gray-500',
};

export default function InventoryPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [lowOnly, setLowOnly] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [historyFor, setHistoryFor] = useState<any>(null);

  const load = () => inventoryApi.listMaterialStock(search || undefined, lowOnly).then(r => setRows(r.data || [])).catch(() => {});
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [search, lowOnly]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2"><Boxes size={22} />在庫管理（部材）</h1>
          <p className="text-sm text-gray-500 mt-1">在庫数 = 入荷累計 − 利用累計。仕入の在庫引当・発注入荷が反映されます。</p>
        </div>
        <button onClick={() => setAddOpen(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} />入出庫を登録
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-3 mb-4 flex items-center gap-3 flex-wrap">
        <Search size={15} className="text-gray-400" />
        <input placeholder="部材名・コードで検索" value={search} onChange={e => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] outline-none text-sm" />
        <label className="flex items-center gap-1.5 text-sm text-gray-600">
          <input type="checkbox" checked={lowOnly} onChange={e => setLowOnly(e.target.checked)} />在庫0以下のみ
        </label>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['部材コード', '部材名', '単位', '入荷累計', '利用累計', '在庫数', ''].map(h =>
                <th key={h} className="px-4 py-3 text-left font-medium text-gray-600">{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {rows.map(r => (
              <tr key={r.material_id} className="hover:bg-blue-50">
                <td className="px-4 py-2.5 font-mono text-xs text-amber-700">{r.material_code}</td>
                <td className="px-4 py-2.5 text-gray-800">{r.material_name}</td>
                <td className="px-4 py-2.5 text-gray-500">{r.unit || '—'}</td>
                <td className="px-4 py-2.5 text-right text-green-600">{r.received.toLocaleString()}</td>
                <td className="px-4 py-2.5 text-right text-red-500">{r.used.toLocaleString()}</td>
                <td className={`px-4 py-2.5 text-right font-bold ${r.is_low ? 'text-red-600' : 'text-gray-800'}`}>{r.stock.toLocaleString()}</td>
                <td className="px-4 py-2.5 text-center">
                  <button onClick={() => setHistoryFor(r)} className="text-gray-400 hover:text-blue-600" title="履歴"><History size={15} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <div className="text-center py-10 text-gray-400">在庫の動いた部材がありません（入出庫を登録してください）</div>}
      </div>

      {addOpen && <AddMovementModal onClose={() => setAddOpen(false)} onSaved={() => { setAddOpen(false); load(); }} />}
      {historyFor && <HistoryModal row={historyFor} onClose={() => setHistoryFor(null)} />}
    </div>
  );
}

// ---- 入出庫登録モーダル ----
function AddMovementModal({ onClose, onSaved }: any) {
  const [matQuery, setMatQuery] = useState('');
  const [matResults, setMatResults] = useState<any[]>([]);
  const [mat, setMat] = useState<any>(null);
  const [form, setForm] = useState<any>({ movement_type: '入荷', quantity: 1, movement_date: new Date().toISOString().slice(0, 10), notes: '' });

  const searchMat = (q: string) => {
    setMatQuery(q); setMat(null);
    if (!q.trim()) { setMatResults([]); return; }
    procurementApi.listMaterials(q).then(r => setMatResults(r.data.slice(0, 15))).catch(() => {});
  };
  const save = async () => {
    if (!mat) { alert('部材を選択してください'); return; }
    await inventoryApi.addMaterialMovement({ material_id: mat.id, ...form, quantity: Number(form.quantity) });
    onSaved();
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-800">入出庫を登録</h2>
          <button onClick={onClose} className="text-gray-400"><X size={18} /></button>
        </div>
        <div className="space-y-3">
          <div className="relative">
            <label className="block text-xs text-gray-500 mb-1">部材 *</label>
            <input value={matQuery} onChange={e => searchMat(e.target.value)} placeholder="部材名・コードで検索"
              className="w-full border rounded-lg px-3 py-2 text-sm" />
            {matResults.length > 0 && !mat && (
              <div className="absolute z-10 mt-1 w-full bg-white border rounded-lg shadow max-h-48 overflow-y-auto">
                {matResults.map(m => (
                  <button key={m.id} onClick={() => { setMat(m); setMatQuery(`${m.material_code} ${m.material_name}`); setMatResults([]); }}
                    className="block w-full text-left px-3 py-1.5 text-xs hover:bg-blue-50">
                    <span className="font-mono text-amber-700">{m.material_code}</span> {m.material_name}
                  </button>
                ))}
              </div>
            )}
            {mat && <p className="mt-1 text-xs text-green-700">✓ {mat.material_name}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">区分</label>
              <select value={form.movement_type} onChange={e => setForm({ ...form, movement_type: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm">
                {MOVE_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">数量{form.movement_type === '調整' ? '（±可）' : ''}</label>
              <input type="number" value={form.quantity} onChange={e => setForm({ ...form, quantity: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm text-right" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">日付</label>
            <input type="date" value={form.movement_date} onChange={e => setForm({ ...form, movement_date: e.target.value })}
              className="w-full border rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">備考</label>
            <input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
              className="w-full border rounded-lg px-3 py-2 text-sm" />
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-5">
          <button onClick={onClose} className="px-4 py-2 border rounded-lg text-sm">キャンセル</button>
          <button onClick={save} className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm"><Check size={15} />登録</button>
        </div>
      </div>
    </div>
  );
}

// ---- 履歴モーダル ----
function HistoryModal({ row, onClose }: any) {
  const [hist, setHist] = useState<any[]>([]);
  useEffect(() => { inventoryApi.materialHistory(row.material_id).then(r => setHist(r.data)).catch(() => {}); }, [row]);
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-bold text-gray-800">{row.material_name}</h2>
            <p className="text-xs text-gray-500">現在庫: <strong>{row.stock.toLocaleString()}</strong> {row.unit}</p>
          </div>
          <button onClick={onClose} className="text-gray-400"><X size={18} /></button>
        </div>
        <div className="overflow-y-auto flex-1">
          <table className="w-full text-xs">
            <thead className="bg-gray-50"><tr>
              {['日付', '区分', '数量', '案件', '備考'].map(h => <th key={h} className="px-2 py-1.5 text-left text-gray-500">{h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-gray-50">
              {hist.map(m => (
                <tr key={m.id}>
                  <td className="px-2 py-1.5">{m.movement_date || '—'}</td>
                  <td className={`px-2 py-1.5 font-medium ${MOVE_COLORS[m.movement_type] || ''}`}>{m.movement_type}</td>
                  <td className={`px-2 py-1.5 text-right ${m.quantity < 0 ? 'text-red-500' : 'text-green-600'}`}>{m.quantity > 0 ? '+' : ''}{m.quantity.toLocaleString()}</td>
                  <td className="px-2 py-1.5 font-mono">{m.child_no || '—'}</td>
                  <td className="px-2 py-1.5 text-gray-500">{m.notes || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {hist.length === 0 && <div className="text-center py-8 text-gray-400 text-sm">履歴なし</div>}
        </div>
      </div>
    </div>
  );
}
