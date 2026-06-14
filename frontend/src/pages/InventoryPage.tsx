// ============================================
// 在庫管理ページ
// ============================================
import { useEffect, useState } from 'react';
import { inventoryApi } from '../api';
import { AlertCircle, Boxes, Plus } from 'lucide-react';

export default function InventoryPage() {
  const [items, setItems] = useState<any[]>([]);
  const [modal, setModal] = useState<any>(null);
  const [form, setForm] = useState({ movement_type: 'in', quantity: 1, notes: '' });

  const load = () => inventoryApi.list().then(r => setItems(r.data || []));
  useEffect(() => { load(); }, []);

  const handleMovement = async () => {
    if (!modal) return;
    try {
      await inventoryApi.addMovement({ product_id: modal.product_id, ...form, quantity: Number(form.quantity) });
      setModal(null);
      load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラー');
    }
  };

  const lowStockItems = items.filter(i => i.is_low_stock);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">在庫管理</h1>
          <p className="text-sm text-gray-500 mt-1">全 {items.length} 品目</p>
        </div>
      </div>

      {lowStockItems.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4 flex items-start gap-3">
          <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-medium text-red-700 mb-1">在庫不足アラート ({lowStockItems.length}品目)</div>
            <div className="text-xs text-red-600">{lowStockItems.map(i => i.name).join('、')}</div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">商品コード</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">商品名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">タイプ</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">在庫数</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">最低在庫数</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">入出庫</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(i => (
              <tr key={i.product_id} className={`hover:bg-blue-50 ${i.is_low_stock ? 'bg-red-50' : ''}`}>
                <td className="px-4 py-3 font-medium text-blue-600">{i.product_code}</td>
                <td className="px-4 py-3 text-gray-800">
                  <div className="flex items-center gap-2">
                    <Boxes size={14} className="text-gray-400" />
                    {i.name}
                    {i.is_low_stock && <AlertCircle size={14} className="text-red-500" />}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">{i.product_type || '—'}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={`font-bold text-lg ${i.is_low_stock ? 'text-red-600' : 'text-gray-800'}`}>
                    {i.stock_quantity}
                  </span>
                  <span className="text-gray-400 ml-1 text-xs">{i.unit}</span>
                </td>
                <td className="px-4 py-3 text-right text-gray-500">{i.min_stock_quantity} {i.unit}</td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => { setModal(i); setForm({ movement_type: 'in', quantity: 1, notes: '' }); }}
                    className="flex items-center gap-1 text-xs bg-green-600 text-white px-2 py-1 rounded hover:bg-green-700 mx-auto">
                    <Plus size={12} /> 入出庫
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="text-center py-12 text-gray-400">在庫データがありません</div>}
      </div>

      {modal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h2 className="text-lg font-bold text-gray-800 mb-1">入出庫登録</h2>
            <p className="text-sm text-gray-500 mb-4">{modal.name}</p>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">種別</label>
                <select value={form.movement_type} onChange={e => setForm(f => ({ ...f, movement_type: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="in">入庫</option>
                  <option value="out">出庫</option>
                  <option value="adjust">在庫調整（絶対値）</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">数量</label>
                <input type="number" step="0.01" value={form.quantity}
                  onChange={e => setForm(f => ({ ...f, quantity: Number(e.target.value) }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">メモ</label>
                <input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
              </div>
              <div className="text-xs text-gray-500">
                現在の在庫: <strong>{modal.stock_quantity} {modal.unit}</strong>
                {form.movement_type === 'in' && ` → ${modal.stock_quantity + Number(form.quantity)} ${modal.unit}`}
                {form.movement_type === 'out' && ` → ${modal.stock_quantity - Number(form.quantity)} ${modal.unit}`}
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setModal(null)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">キャンセル</button>
              <button onClick={handleMovement} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700">登録</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
