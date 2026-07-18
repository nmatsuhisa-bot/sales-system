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
  // 受注票＋見積書の同時印刷（会議2026-07-17: 二度手間を省く）
  const handlePdfWithQuotation = (id: string) => {
    window.open(`${API_BASE}/estimate-quotations/order-ticket/${id}/pdf?with_quotation=1`, '_blank');
  };
  // 元となる見積書のプレビュー
  const handleQuotationPdf = (quotationId: string) => {
    window.open(`${API_BASE}/estimate-quotations/${quotationId}/pdf`, '_blank');
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
          <input placeholder="受注番号・注文主・子IDで検索" value={search}
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

      <div className="bg-white rounded-xl shadow-sm overflow-auto max-h-[70vh]">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100 sticky top-0 z-10">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注番号(COID)</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">種別</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">注文主</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">納入先</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">担当者</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注日</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">出荷予定日</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">顧客納期</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">売上計上日</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">金額（税抜）</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">注文書</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">納期</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">前受金</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(t => (
              <tr key={t.id} className={`hover:bg-blue-50 ${!t.is_active ? 'opacity-50' : ''}`}>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className="flex items-center gap-1 font-mono font-bold text-blue-700"><ShoppingCart size={14} /> {t.child_no || t.ticket_no}
                  {!t.is_active && <span className="ml-1 text-xs text-gray-400">（過去）</span>}</span>
                  <span className="block text-[10px] text-gray-400">票No. {t.ticket_no}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${TYPE_COLORS[t.ticket_type] || 'bg-gray-100'}`}>
                    {TYPE_LABELS[t.ticket_type] || t.ticket_type}
                  </span>
                </td>
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
                  <button onClick={() => setEditTicket(t)} className="text-blue-600 hover:text-blue-800 mr-2" title="受注項目を編集">
                    <Pencil size={15} />
                  </button>
                  <button onClick={() => handlePdf(t.id)} className="text-green-600 hover:text-green-800 mr-2" title="受注票PDF">
                    <FileText size={16} />
                  </button>
                  <button onClick={() => handlePdfWithQuotation(t.id)}
                    className="text-[10px] bg-green-50 border border-green-300 text-green-700 px-1.5 py-0.5 rounded hover:bg-green-100"
                    title="受注票と見積書を同時に印刷">
                    +見積書
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

// 有無（Boolean|null）↔ セレクト文字列の相互変換
const ynToStr = (v: boolean | null | undefined) => (v === true ? 'true' : v === false ? 'false' : '');
const strToYn = (s: string) => (s === '' ? null : s === 'true');

// ========== 受注項目 編集モーダル（注文書/図面/契約書有無・納期・前受金・出荷方法・部品手配） ==========
function OrderTicketEditModal({ ticket, onClose, onSaved }: { ticket: any; onClose: () => void; onSaved: () => void }) {
  const [ticketType, setTicketType] = useState<string>(ticket.ticket_type || 'tanban');
  const [orderSheet, setOrderSheet] = useState<string>(ynToStr(ticket.has_order_sheet));
  const [drawing, setDrawing] = useState<string>(ynToStr(ticket.has_drawing));
  const [contract, setContract] = useState<string>(ynToStr(ticket.has_contract));
  const [partsInput, setPartsInput] = useState<string>(ticket.parts_input_status || '');
  const [partsOrder, setPartsOrder] = useState<string>(ticket.parts_order_status || '');
  const [stockMinus, setStockMinus] = useState<string>(ticket.stock_minus_status || '');
  const [deliveryDate, setDeliveryDate] = useState<string>(ticket.delivery_date || '');
  const [advPays, setAdvPays] = useState<{ date: string; amount: string }[]>(() => {
    const base = (ticket.advance_payments || []).map((a: any) => ({ date: a.date || '', amount: a.amount != null ? String(a.amount) : '' }));
    while (base.length < 3) base.push({ date: '', amount: '' });
    return base.slice(0, 3);
  });
  const [shipMethod, setShipMethod] = useState<string>(ticket.shipping_method || '');
  const [orderDate, setOrderDate] = useState<string>(ticket.order_date || '');
  const [saving, setSaving] = useState(false);
  const setAdv = (i: number, patch: any) => setAdvPays(rows => rows.map((r, j) => j === i ? { ...r, ...patch } : r));

  // 関連書類（注文書・契約書等のPDFアップロード。会議2026-07-17）
  const [files, setFiles] = useState<any[]>([]);
  const [fileKind, setFileKind] = useState('注文書');
  const [uploading, setUploading] = useState(false);
  const loadFiles = () => {
    estimateApi.listTicketFiles(ticket.id).then(r => setFiles(r.data || [])).catch(() => {});
  };
  useEffect(() => { loadFiles(); }, [ticket.id]);
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    if (f.size > 10 * 1024 * 1024) { alert('ファイルサイズは10MBまでです'); return; }
    setUploading(true);
    try {
      const b64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
        reader.onerror = reject;
        reader.readAsDataURL(f);
      });
      await estimateApi.uploadTicketFile(ticket.id, {
        file_kind: fileKind, filename: f.name,
        content_type: f.type || 'application/pdf', content_base64: b64,
      });
      loadFiles();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'アップロードに失敗しました');
    } finally { setUploading(false); }
  };
  const handleDeleteFile = async (fileId: string, name: string) => {
    if (!confirm(`「${name}」を削除しますか？`)) return;
    try { await estimateApi.deleteTicketFile(fileId); loadFiles(); }
    catch (err: any) { alert(err.response?.data?.detail || '削除に失敗しました'); }
  };

  const save = async () => {
    setSaving(true);
    try {
      await estimateApi.updateOrderTicket(ticket.id, {
        ticket_type: ticketType,
        has_order_sheet: strToYn(orderSheet),
        has_drawing: strToYn(drawing),
        has_contract: strToYn(contract),
        delivery_date: deliveryDate || null,
        advance_payments: advPays.map(a => ({ date: a.date || null, amount: a.amount ? Number(a.amount) : null })).filter(a => a.date || a.amount),
        shipping_method: shipMethod || null,
        parts_input_status: partsInput || null,
        parts_order_status: partsOrder || null,
        stock_minus_status: stockMinus || null,
        order_date: orderDate || null,
      });
      onSaved();
    } catch (e: any) {
      alert(e.response?.data?.detail || '保存に失敗しました');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-5 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-gray-800">受注項目の編集</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="text-xs text-gray-500 mb-2">
          {ticket.ticket_no}　{ticket.child_no || ''}　{ticket.customer_name || ''}
        </div>
        {/* 元見積の参照（内容を確認しながら受注情報を更新できるように。会議2026-07-17） */}
        {ticket.quotation_id && (
          <div className="flex items-center gap-2 mb-4 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
            <FileText size={14} className="text-blue-500" />
            <span className="text-xs text-gray-600">元見積: {ticket.quotation_no || ticket.quotation_id}</span>
            <button onClick={() => window.open(`${API_BASE}/estimate-quotations/${ticket.quotation_id}/pdf`, '_blank')}
              className="ml-auto text-xs text-blue-600 hover:underline">見積書を開く</button>
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-sm text-gray-600 mb-1">種別（工番/単番）
              <span className="text-[10px] text-gray-400 ml-1">発行時に税抜300万円で自動判定・手動変更可</span>
            </label>
            <select value={ticketType} onChange={e => setTicketType(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm">
              <option value="koban">工番（税抜300万円以上）</option>
              <option value="tanban">単番（税抜300万円未満）</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">書類の有無</label>
            <div className="grid grid-cols-3 gap-2">
              {([
                ['注文書', orderSheet, setOrderSheet],
                ['図面', drawing, setDrawing],
                ['契約書', contract, setContract],
              ] as const).map(([label, val, set]) => (
                <div key={label}>
                  <span className="block text-xs text-gray-400 mb-0.5">{label}</span>
                  <select value={val} onChange={e => (set as any)(e.target.value)}
                    className="w-full border rounded px-2 py-2 text-sm">
                    <option value="">未確認</option>
                    <option value="true">有</option>
                    <option value="false">無</option>
                  </select>
                </div>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">納期</label>
            <input type="date" value={deliveryDate} onChange={e => setDeliveryDate(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">前受金（最大3回・分割入金）</label>
            <div className="space-y-1.5">
              {advPays.map((a, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-4">{i + 1}.</span>
                  <input type="date" value={a.date} onChange={e => setAdv(i, { date: e.target.value })}
                    className="border rounded px-2 py-1.5 text-sm flex-1" />
                  <input type="number" value={a.amount} onChange={e => setAdv(i, { amount: e.target.value })}
                    placeholder="金額(円)" className="border rounded px-2 py-1.5 text-sm w-28 text-right" />
                </div>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">出荷方法</label>
            <select value={shipMethod} onChange={e => setShipMethod(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm">
              <option value="">未定</option>
              <option value="トラック出荷">トラック出荷</option>
              <option value="宅配出荷">宅配出荷</option>
              <option value="井上納品">井上納品</option>
              <option value="引取">引取</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">部品手配・在庫マイナス</label>
            <div className="grid grid-cols-3 gap-2">
              {([
                ['部品入力', partsInput, setPartsInput],
                ['注文', partsOrder, setPartsOrder],
                ['在庫マイナス', stockMinus, setStockMinus],
              ] as const).map(([label, val, set]) => (
                <div key={label}>
                  <span className="block text-xs text-gray-400 mb-0.5">{label}</span>
                  <select value={val} onChange={e => (set as any)(e.target.value)}
                    className="w-full border rounded px-2 py-2 text-sm">
                    <option value="">未入力</option>
                    <option value="未">未</option>
                    <option value="済">済</option>
                  </select>
                </div>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">受注日</label>
            <input type="date" value={orderDate} onChange={e => setOrderDate(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">関連書類（注文書・契約書等のPDF保管）</label>
            <div className="flex items-center gap-2 mb-2">
              <select value={fileKind} onChange={e => setFileKind(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm">
                <option value="注文書">注文書</option>
                <option value="契約書">契約書</option>
                <option value="図面">図面</option>
                <option value="その他">その他</option>
              </select>
              <label className={`text-sm px-3 py-1.5 rounded border cursor-pointer ${uploading ? 'bg-gray-100 text-gray-400' : 'bg-blue-50 border-blue-300 text-blue-700 hover:bg-blue-100'}`}>
                {uploading ? 'アップロード中...' : '＋ PDFをアップロード'}
                <input type="file" accept="application/pdf,.pdf" className="hidden" onChange={handleUpload} disabled={uploading} />
              </label>
              <span className="text-[10px] text-gray-400">1件10MBまで</span>
            </div>
            {files.length > 0 ? (
              <ul className="space-y-1">
                {files.map(f => (
                  <li key={f.id} className="flex items-center gap-2 text-xs bg-gray-50 rounded px-2 py-1.5">
                    <span className="px-1.5 py-0.5 rounded bg-gray-200 text-gray-600 text-[10px]">{f.file_kind || 'その他'}</span>
                    <a href={`${API_BASE}/estimate-quotations/order-ticket-file/${f.id}`} target="_blank" rel="noreferrer"
                      className="text-blue-600 hover:underline flex-1 truncate">{f.filename}</a>
                    <span className="text-gray-400">{(f.file_size / 1024 / 1024).toFixed(1)}MB</span>
                    <button onClick={() => handleDeleteFile(f.id, f.filename)} className="text-red-300 hover:text-red-500">
                      <X size={13} />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-gray-400">アップロード済みの書類はありません</p>
            )}
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
