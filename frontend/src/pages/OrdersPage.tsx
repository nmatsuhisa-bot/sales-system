import { useEffect, useState } from 'react';
import { estimateApi, API_BASE } from '../api';
import { Search, FileText, ShoppingCart, Pencil, X, Check } from 'lucide-react';

const TYPE_LABELS: Record<string, string> = { koban: '工番', tanban: '単番' };
const TYPE_COLORS: Record<string, string> = {
  koban: 'bg-purple-100 text-purple-700',
  tanban: 'bg-orange-100 text-orange-700',
};

// 注文書有無の表示
function orderSheetLabel(v: boolean | null | undefined) {
  if (v === true) return '有';
  if (v === false) return '無';
  return '—';
}

export default function OrdersPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [editTicket, setEditTicket] = useState<any>(null);

  const load = () => {
    estimateApi.listOrderTickets({
      search: search || undefined,
      ticket_type: typeFilter || undefined,
      status_filter: statusFilter,
    })
      .then(r => { setItems(r.data.items || []); setTotal(r.data.total || 0); })
      .catch(() => {});
  };

  useEffect(() => { load(); }, [search, typeFilter, statusFilter]);

  const handlePdf = (id: string) => {
    window.open(`${API_BASE}/estimate-quotations/order-ticket/${id}/pdf`, '_blank');
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">受注管理</h1>
          <p className="text-sm text-gray-500 mt-1">全 {total} 件</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-4 mb-4 flex gap-3">
        <div className="flex items-center gap-2 flex-1 border border-gray-200 rounded-lg px-3 py-2">
          <Search size={16} className="text-gray-400" />
          <input placeholder="受注番号・顧客名・子IDで検索" value={search}
            onChange={e => setSearch(e.target.value)} className="flex-1 outline-none text-sm" />
        </div>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="">全種別</option>
          <option value="koban">工番</option>
          <option value="tanban">単番</option>
        </select>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="active">最新のみ</option>
          <option value="inactive">過去（非表示）</option>
          <option value="">全件</option>
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注番号</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">種別</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">子ID</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">顧客名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">納入先</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">担当者</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注日</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">出荷予定日</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">顧客納期</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">売上計上日</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">金額（税込）</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">注文書</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">納期</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">前受金</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(t => (
              <tr key={t.id} className={`hover:bg-blue-50 ${!t.is_active ? 'opacity-50' : ''}`}>
                <td className="px-4 py-3 font-medium text-blue-600 whitespace-nowrap">
                  <span className="flex items-center gap-1"><ShoppingCart size={14} /> {t.ticket_no}
                  {!t.is_active && <span className="ml-1 text-xs text-gray-400">（過去）</span>}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${TYPE_COLORS[t.ticket_type] || 'bg-gray-100'}`}>
                    {TYPE_LABELS[t.ticket_type] || t.ticket_type}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600">{t.child_no || '—'}</td>
                <td className="px-4 py-3 text-gray-700">{t.customer_name || '—'}</td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{t.delivery_name || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{t.sales_person_name || '—'}</td>
                <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{t.order_date || '—'}</td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{t.expected_shipment_date || '—'}</td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{t.customer_delivery_date || '—'}</td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{t.sales_date || '—'}</td>
                <td className="px-4 py-3 text-right font-medium text-gray-800 whitespace-nowrap">
                  ¥{(t.total_amount || 0).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={t.has_order_sheet === true ? 'text-green-700 font-medium' : t.has_order_sheet === false ? 'text-gray-400' : 'text-gray-300'}>
                    {orderSheetLabel(t.has_order_sheet)}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{t.delivery_date || '—'}</td>
                <td className="px-4 py-3 text-right text-gray-700 whitespace-nowrap">
                  {t.advance_payment ? `¥${Number(t.advance_payment).toLocaleString()}` : '—'}
                </td>
                <td className="px-4 py-3 text-center whitespace-nowrap">
                  <button onClick={() => setEditTicket(t)} className="text-blue-600 hover:text-blue-800 mr-3" title="受注項目を編集">
                    <Pencil size={15} />
                  </button>
                  <button onClick={() => handlePdf(t.id)} className="text-green-600 hover:text-green-800" title="受注票PDF">
                    <FileText size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            受注票がありません<br />
            <span className="text-xs mt-1 block">見積管理から「受注票」ボタンで発行してください</span>
          </div>
        )}
      </div>

      {editTicket && (
        <OrderTicketEditModal
          ticket={editTicket}
          onClose={() => setEditTicket(null)}
          onSaved={() => { setEditTicket(null); load(); }}
        />
      )}
    </div>
  );
}

// ========== 受注項目 編集モーダル（注文書有無・納期・前受金・受注日） ==========
function OrderTicketEditModal({ ticket, onClose, onSaved }: { ticket: any; onClose: () => void; onSaved: () => void }) {
  const [ticketType, setTicketType] = useState<string>(ticket.ticket_type || 'tanban');
  const [orderSheet, setOrderSheet] = useState<string>(
    ticket.has_order_sheet === true ? 'true' : ticket.has_order_sheet === false ? 'false' : ''
  );
  const [deliveryDate, setDeliveryDate] = useState<string>(ticket.delivery_date || '');
  const [advance, setAdvance] = useState<string>(ticket.advance_payment != null ? String(ticket.advance_payment) : '');
  const [orderDate, setOrderDate] = useState<string>(ticket.order_date || '');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await estimateApi.updateOrderTicket(ticket.id, {
        ticket_type: ticketType,
        has_order_sheet: orderSheet === '' ? null : orderSheet === 'true',
        delivery_date: deliveryDate || null,
        advance_payment: advance === '' ? null : Number(advance),
        order_date: orderDate || null,
      });
      onSaved();
    } catch (e: any) {
      alert(e.response?.data?.detail || '保存に失敗しました');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-gray-800">受注項目の編集</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="text-xs text-gray-500 mb-4">
          {ticket.ticket_no}　{ticket.child_no || ''}　{ticket.customer_name || ''}
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-sm text-gray-600 mb-1">種別（工番/単番）
              <span className="text-[10px] text-gray-400 ml-1">発行時に300万円で自動判定・手動変更可</span>
            </label>
            <select value={ticketType} onChange={e => setTicketType(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm">
              <option value="koban">工番（300万円以上）</option>
              <option value="tanban">単番（300万円未満）</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">注文書</label>
            <select value={orderSheet} onChange={e => setOrderSheet(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm">
              <option value="">未確認</option>
              <option value="true">有</option>
              <option value="false">無</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">納期</label>
            <input type="date" value={deliveryDate} onChange={e => setDeliveryDate(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">前受金（円・空欄=なし）</label>
            <input type="number" value={advance} onChange={e => setAdvance(e.target.value)}
              placeholder="0" className="w-full border rounded px-3 py-2 text-sm text-right" />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">受注日</label>
            <input type="date" value={orderDate} onChange={e => setOrderDate(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm" />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-4 py-2 border rounded text-sm hover:bg-gray-50">キャンセル</button>
          <button onClick={save} disabled={saving}
            className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
            <Check size={15} />{saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}
