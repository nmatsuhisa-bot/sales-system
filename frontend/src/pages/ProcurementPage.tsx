import { useEffect, useState, Fragment } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { procurementApi } from '../api';
import OrderSearchInput from '../components/common/OrderSearchInput';
import { Plus, Trash2, Check, X, Boxes, FileText, ChevronDown, ChevronRight, GitBranch } from 'lucide-react';

const STATUS_COLORS: Record<string, string> = {
  '作成中': 'bg-yellow-100 text-yellow-700',
  '未発注': 'bg-yellow-100 text-yellow-700',
  '発注済': 'bg-blue-100 text-blue-700',
  '一部入荷': 'bg-orange-100 text-orange-700',
  '入荷済': 'bg-green-100 text-green-700',
  'キャンセル': 'bg-gray-100 text-gray-500',
};
const PO_STATUS = ['作成中', '発注済', '一部入荷', '入荷済', 'キャンセル'];

export default function ProcurementPage() {
  const location = useLocation();
  const initialOrder = (location.state as any)?.childOrder || null;

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">仕入（発注）管理</h1>
        <Link to="/bom-master" className="flex items-center gap-1 text-xs text-indigo-600 hover:underline">
          <GitBranch size={13} />部材マスタ・ユニット構成の管理は「製品BOMマスタ」へ
        </Link>
      </div>
      <PurchaseOrdersTab initialOrder={initialOrder} />
    </div>
  );
}

// ========== 発注書（発注番号ヘッダー）タブ ==========
function PurchaseOrdersTab({ initialOrder }: { initialOrder?: any }) {
  const [pos, setPos] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [expanded, setExpanded] = useState<Record<string, any>>({});
  // 見積内訳から発注書作成パネル
  const [showImport, setShowImport] = useState(false);
  const [importOrder, setImportOrder] = useState<any>(null);
  const [bdRows, setBdRows] = useState<any[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [importDue, setImportDue] = useState('');
  const [autoMsg, setAutoMsg] = useState('');
  const [importMsg, setImportMsg] = useState('');

  const load = () => procurementApi.listPurchaseOrders(statusFilter || undefined).then(r => setPos(r.data)).catch(() => {});
  useEffect(() => { load(); }, [statusFilter]);

  // 案件管理からの遷移で自動オープン
  useEffect(() => {
    if (initialOrder) { setShowImport(true); onSelectImportOrder(initialOrder); }
    // eslint-disable-next-line
  }, []);

  const onSelectImportOrder = (o: any) => {
    setImportOrder(o); setImportMsg(''); setSelected({}); setBdRows([]); setAutoMsg('読込中...');
    procurementApi.poBreakdowns(o.id).then(r => {
      const rows = r.data.rows || [];
      setBdRows(rows);
      // 既存発注書がない内訳を初期選択
      const initSel: Record<string, boolean> = {};
      rows.forEach((row: any) => { if (!row.existing_po_no) initSel[row.breakdown_no] = true; });
      setSelected(initSel);
      setAutoMsg(rows.length
        ? `採用見積 ${r.data.quotation_no || ''} の内訳 ${rows.length}件（発注番号 = 子ID-内訳番号）`
        : (r.data.message || '受注採用見積に内訳がありません'));
    }).catch(() => setAutoMsg('取得に失敗しました'));
  };
  const toggleSel = (bno: string) => setSelected(s => ({ ...s, [bno]: !s[bno] }));

  const createPOs = async () => {
    if (!importOrder) { alert('案件子IDを選択してください'); return; }
    const chosen = bdRows.filter(r => selected[r.breakdown_no] && !r.existing_po_no);
    if (!chosen.length) { alert('作成する内訳を選択してください'); return; }
    try {
      const r = await procurementApi.createPOsFromBreakdowns({
        project_order_id: importOrder.id,
        due_date: importDue || null,
        breakdowns: chosen.map(r => ({ breakdown_no: r.breakdown_no })),
      });
      setImportMsg(`✓ ${r.data.message}`);
      onSelectImportOrder(importOrder);  // 内訳一覧を再読込（既存発注書欄を更新）
      load();
    } catch (e: any) { setImportMsg(`❌ ${e.response?.data?.detail || 'エラー'}`); }
  };

  const setPoStatus = async (id: string, status: string) => { await procurementApi.updatePoStatus(id, status); load(); };
  const delPo = async (id: string) => { if (confirm('この発注書を削除しますか？')) { await procurementApi.deletePurchaseOrder(id); load(); } };
  const receivePo = async (id: string) => {
    if (!confirm('この発注書を入荷登録します（在庫引当の明細を除き、各明細を在庫に加算）。よろしいですか？')) return;
    try { const r = await procurementApi.receivePoStock(id); alert(r.data.message); load(); }
    catch (e: any) { alert(e.response?.data?.detail || 'エラー'); }
  };
  const toggleExpand = (po: any) => {
    setExpanded(e => { const n = { ...e }; if (n[po.id]) delete n[po.id]; else n[po.id] = true; return n; });
  };
  const createBlankPo = async () => {
    const r = await procurementApi.createPurchaseOrder({});
    load();
    setExpanded(e => ({ ...e, [r.data.id]: true }));
  };
  const selectedCount = bdRows.filter(r => selected[r.breakdown_no] && !r.existing_po_no).length;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="border rounded px-2 py-1 text-sm">
          <option value="">全ステータス</option>
          {PO_STATUS.map(s => <option key={s}>{s}</option>)}
        </select>
        <span className="text-xs text-gray-500">{pos.length}件</span>
        <button onClick={createBlankPo}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-white border border-blue-300 text-blue-600 text-sm rounded hover:bg-blue-50">
          <Plus size={14} />発注書を新規作成
        </button>
        <button onClick={() => setShowImport(v => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700">
          <Boxes size={14} />見積内訳から発注書作成
        </button>
      </div>

      {showImport && (
        <div className="mb-4 p-3 border border-indigo-200 rounded-lg bg-indigo-50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-indigo-700">採用見積の内訳（明細行）ごとに発注書を発番 — 発注番号 = 子ID-内訳番号（例: 2026-0010_A-1-1）</span>
            <button onClick={() => { setShowImport(false); setImportMsg(''); setAutoMsg(''); setBdRows([]); }} className="text-gray-400"><X size={14} /></button>
          </div>
          <div className="flex flex-wrap gap-2 items-end mb-2">
            <div className="min-w-[280px]">
              <label className="block text-xs text-gray-500 mb-0.5">案件ID / 子ID</label>
              <OrderSearchInput onSelect={onSelectImportOrder} placeholder="案件ID または 子ID で検索" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">納期（一括）</label>
              <input type="date" value={importDue} onChange={e => setImportDue(e.target.value)} className="border rounded px-2 py-1 text-sm" />
            </div>
            {autoMsg && <span className="text-xs text-indigo-600 pb-1.5">{autoMsg}</span>}
          </div>
          <div className="bg-white border rounded">
            <table className="w-full text-xs">
              <thead><tr className="bg-gray-50 text-gray-600">
                {['選択', '内訳番号', '大分類', '品名', '数量', '既存発注書'].map(h => <th key={h} className="px-2 py-1.5 text-left font-medium border-b">{h}</th>)}
              </tr></thead>
              <tbody>
                {bdRows.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-4 text-gray-400">案件子IDを選ぶと採用見積の内訳（明細行）が表示されます</td></tr>
                ) : bdRows.map(r => (
                  <tr key={r.breakdown_no} className={`border-b last:border-0 ${r.existing_po_no ? 'bg-gray-50 text-gray-400' : ''}`}>
                    <td className="px-2 py-1.5"><input type="checkbox" checked={!!selected[r.breakdown_no]} disabled={!!r.existing_po_no} onChange={() => toggleSel(r.breakdown_no)} /></td>
                    <td className="px-2 py-1.5 font-mono text-indigo-700">{r.breakdown_no}</td>
                    <td className="px-2 py-1.5">{r.section}</td>
                    <td className="px-2 py-1.5">{r.item_name}</td>
                    <td className="px-2 py-1.5 text-right">{r.quantity}</td>
                    <td className="px-2 py-1.5">{r.existing_po_no ? <span className="font-mono text-green-700">{r.existing_po_no}</span> : <span className="text-gray-300">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <button onClick={createPOs} disabled={!selectedCount}
              className="flex items-center gap-1 px-4 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50">
              <Check size={14} />選択した内訳の発注書を作成（{selectedCount}件）
            </button>
            <span className="text-xs text-gray-400">※内訳ごとに1発注書。ユニット紐付けがあれば部材を自動展開</span>
            {importMsg && <span className={`text-xs ${importMsg.startsWith('✓') ? 'text-green-700' : 'text-red-500'}`}>{importMsg}</span>}
          </div>
        </div>
      )}

      <table className="w-full text-sm border-collapse">
        <thead><tr className="bg-gray-50">
          {['', '発注番号', '内訳', '案件子ID', '発注先', '注文日', '明細', '金額', 'ステータス', ''].map(h =>
            <th key={h} className="border border-gray-200 px-2 py-2 text-left text-xs font-medium text-gray-600">{h}</th>)}
        </tr></thead>
        <tbody>
          {pos.length === 0 ? <tr><td colSpan={10} className="text-center py-8 text-gray-400">発注書なし</td></tr>
            : pos.map(po => (
              <Fragment key={po.id}>
                <tr className="hover:bg-gray-50">
                  <td className="border px-1 py-1 text-center">
                    <button onClick={() => toggleExpand(po)} className="text-gray-400">{expanded[po.id] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</button>
                  </td>
                  <td className="border px-2 py-1.5 font-mono font-bold text-indigo-700">{po.po_no}</td>
                  <td className="border px-2 py-1.5 text-xs" title={po.breakdown_name || ''}>{po.breakdown_no || '—'}</td>
                  <td className="border px-2 py-1.5 font-mono text-xs">{po.child_no || '—'}</td>
                  <td className="border px-2 py-1.5">{po.supplier_name || '（未指定）'}</td>
                  <td className="border px-2 py-1.5 text-xs">{po.order_date || '—'}</td>
                  <td className="border px-2 py-1.5 text-center">{po.line_count}</td>
                  <td className="border px-2 py-1.5 text-right">¥{Number(po.total_amount).toLocaleString()}</td>
                  <td className="border px-2 py-1.5">
                    <select value={po.status} onChange={e => setPoStatus(po.id, e.target.value)}
                      className={`text-xs rounded px-1.5 py-0.5 border-0 ${STATUS_COLORS[po.status] || 'bg-gray-100'}`}>
                      {PO_STATUS.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="border px-1 py-1.5 whitespace-nowrap">
                    {po.status === '作成中' && (
                      <button onClick={() => setPoStatus(po.id, '発注済')}
                        className="px-2 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 mr-1">発注確定</button>
                    )}
                    {(po.status === '発注済' || po.status === '一部入荷') && (
                      <button onClick={() => receivePo(po.id)}
                        className="px-2 py-1 bg-teal-600 text-white text-xs rounded hover:bg-teal-700 mr-1">入荷登録</button>
                    )}
                    <a href={procurementApi.poPdfUrl(po.id)} target="_blank" rel="noreferrer"
                      className="inline-flex items-center gap-1 px-2 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 mr-1"><FileText size={12} />発注書</a>
                    <button onClick={() => delPo(po.id)} className="text-red-400"><Trash2 size={13} /></button>
                  </td>
                </tr>
                {expanded[po.id] && (
                  <tr>
                    <td></td>
                    <td colSpan={9} className="border border-gray-200 bg-gray-50 px-3 py-3">
                      <PoDetail poId={po.id} onChange={load} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
        </tbody>
      </table>
    </div>
  );
}

// ========== 発注書 明細編集（ヘッダー＋明細を編集可能に） ==========
function PoDetail({ poId, onChange }: { poId: string; onChange: () => void }) {
  const [po, setPo] = useState<any>(null);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [hdr, setHdr] = useState<any>({});
  const [hdrDirty, setHdrDirty] = useState(false);
  // 明細追加用
  const [matQuery, setMatQuery] = useState('');
  const [matResults, setMatResults] = useState<any[]>([]);
  const [newLine, setNewLine] = useState<any>({ order_qty: 1 });

  const reload = () => procurementApi.getPurchaseOrder(poId).then(r => {
    setPo(r.data);
    setHdr({
      supplier_id: r.data.supplier_id || '', order_date: r.data.order_date || '',
      delivery_place: r.data.delivery_place || '', seiban: r.data.seiban || '', title: r.data.title || '',
    });
    setHdrDirty(false);
  });
  useEffect(() => { reload(); procurementApi.listSuppliers().then(r => setSuppliers(r.data)).catch(() => {}); }, [poId]);

  const saveHdr = async () => {
    await procurementApi.updatePurchaseOrder(poId, { ...hdr, supplier_id: hdr.supplier_id || null });
    setHdrDirty(false); reload(); onChange();
  };
  const searchMat = (q: string) => {
    setMatQuery(q); setNewLine((n: any) => ({ ...n, material_id: undefined, material_name: undefined }));
    if (!q.trim()) { setMatResults([]); return; }
    procurementApi.listMaterials(q).then(r => setMatResults(r.data.slice(0, 15))).catch(() => {});
  };
  const pickMat = (m: any) => {
    setNewLine((n: any) => ({ ...n, material_id: m.id, material_name: m.material_name, unit: m.unit }));
    setMatQuery(`${m.material_code} ${m.material_name}`); setMatResults([]);
  };
  const addLine = async () => {
    if (!newLine.material_id) { alert('部材を選択してください'); return; }
    await procurementApi.createMaterialOrder({
      purchase_order_id: poId, material_id: newLine.material_id,
      order_qty: Number(newLine.order_qty) || 1,
      unit_price: newLine.unit_price ? Number(newLine.unit_price) : null,
      due_date: newLine.due_date || null,
    });
    setNewLine({ order_qty: 1 }); setMatQuery(''); setMatResults([]); reload(); onChange();
  };
  const saveLine = async (l: any) => {
    await procurementApi.updateMaterialOrder(l.id, {
      order_qty: Number(l.order_qty) || 0, unit_price: l.unit_price === '' || l.unit_price == null ? null : Number(l.unit_price), due_date: l.due_date || null,
    });
    reload(); onChange();
  };
  const delLine = async (id: string) => { await procurementApi.deleteMaterialOrder(id); reload(); onChange(); };
  const allocate = async (l: any) => {
    if (!confirm(`「${l.material_name}」を在庫から引き当てます（数量 ${l.order_qty}）。よろしいですか？`)) return;
    try { await procurementApi.allocateFromStock(l.id); reload(); onChange(); }
    catch (e: any) { alert(e.response?.data?.detail || 'エラー'); }
  };
  const receiveLine = async (l: any) => {
    const input = window.prompt(`「${l.material_name}」の入荷数量を入力（在庫に加算）`, String(l.order_qty ?? ''));
    if (input == null) return;
    const qty = Number(input);
    if (!qty || qty <= 0) { alert('数量を正しく入力してください'); return; }
    try { await procurementApi.receiveLine(l.id, qty); reload(); onChange(); }
    catch (e: any) { alert(e.response?.data?.detail || 'エラー'); }
  };
  const updLineLocal = (id: string, patch: any) =>
    setPo((p: any) => ({ ...p, lines: p.lines.map((l: any) => l.id === id ? { ...l, ...patch } : l) }));

  if (!po) return <div className="text-xs text-gray-400 py-2">読込中...</div>;
  const editable = po.status === '作成中';
  const total = (po.lines || []).reduce((s: number, l: any) => s + (Number(l.order_qty) || 0) * (Number(l.unit_price) || 0), 0);

  return (
    <div>
      {!editable && (
        <div className="mb-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
          ステータスが「{po.status}」のため編集できません。編集するにはステータスを「作成中」に戻してください。
        </div>
      )}
      {/* ヘッダー編集 */}
      <div className="flex flex-wrap gap-2 items-end mb-3">
        <div>
          <label className="block text-[10px] text-gray-500">発注先</label>
          <select disabled={!editable} value={hdr.supplier_id} onChange={e => { setHdr({ ...hdr, supplier_id: e.target.value }); setHdrDirty(true); }} className="border rounded px-2 py-1 text-xs min-w-[160px] disabled:bg-gray-100">
            <option value="">（未指定）</option>
            {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div><label className="block text-[10px] text-gray-500">注文日</label>
          <input disabled={!editable} type="date" value={hdr.order_date} onChange={e => { setHdr({ ...hdr, order_date: e.target.value }); setHdrDirty(true); }} className="border rounded px-2 py-1 text-xs disabled:bg-gray-100" /></div>
        <div><label className="block text-[10px] text-gray-500">納入場所</label>
          <input disabled={!editable} value={hdr.delivery_place} onChange={e => { setHdr({ ...hdr, delivery_place: e.target.value }); setHdrDirty(true); }} className="border rounded px-2 py-1 text-xs w-36 disabled:bg-gray-100" /></div>
        <div><label className="block text-[10px] text-gray-500">製番</label>
          <input disabled={!editable} value={hdr.seiban} onChange={e => { setHdr({ ...hdr, seiban: e.target.value }); setHdrDirty(true); }} className="border rounded px-2 py-1 text-xs w-28 disabled:bg-gray-100" /></div>
        <div className="flex-1 min-w-[160px]"><label className="block text-[10px] text-gray-500">件名</label>
          <input disabled={!editable} value={hdr.title} onChange={e => { setHdr({ ...hdr, title: e.target.value }); setHdrDirty(true); }} className="border rounded px-2 py-1 text-xs w-full disabled:bg-gray-100" /></div>
        {editable && hdrDirty && <button onClick={saveHdr} className="px-3 py-1 bg-blue-600 text-white text-xs rounded">ヘッダー保存</button>}
      </div>

      {/* 明細編集 */}
      <table className="w-full text-xs">
        <thead><tr className="text-gray-500 bg-white">
          {['部材コード', '部材名', '数量', '単位', '単価', '金額', '納期', ''].map(h => <th key={h} className="text-left px-2 py-1">{h}</th>)}
        </tr></thead>
        <tbody>
          {(po.lines || []).map((l: any) => (
            <tr key={l.id} className="border-t border-gray-200 bg-white">
              <td className="px-2 py-1 font-mono text-amber-700">{l.material_code}</td>
              <td className="px-2 py-1">{l.material_name}</td>
              <td className="px-1 py-1"><input disabled={!editable} type="number" value={l.order_qty ?? ''} onChange={e => updLineLocal(l.id, { order_qty: e.target.value })} onBlur={() => editable && saveLine(l)} className="border rounded px-1 w-16 text-right disabled:bg-gray-50 disabled:border-transparent" /></td>
              <td className="px-2 py-1">{l.unit}</td>
              <td className="px-1 py-1"><input disabled={!editable} type="number" value={l.unit_price ?? ''} onChange={e => updLineLocal(l.id, { unit_price: e.target.value })} onBlur={() => editable && saveLine(l)} className="border rounded px-1 w-24 text-right disabled:bg-gray-50 disabled:border-transparent" /></td>
              <td className="px-2 py-1 text-right">¥{Number((Number(l.order_qty) || 0) * (Number(l.unit_price) || 0)).toLocaleString()}</td>
              <td className="px-1 py-1"><input disabled={!editable} type="date" value={l.due_date || ''} onChange={e => updLineLocal(l.id, { due_date: e.target.value })} onBlur={() => editable && saveLine(l)} className="border rounded px-1 text-xs disabled:bg-gray-50 disabled:border-transparent" /></td>
              <td className="px-1 py-1 whitespace-nowrap">
                {l.status === '在庫引当'
                  ? <span className="text-xs text-orange-600 font-medium">在庫引当</span>
                  : l.status === '入荷済'
                  ? <span className="text-xs text-teal-600 font-medium">入荷済</span>
                  : <>
                      <button onClick={() => receiveLine(l)} className="text-teal-600 hover:text-teal-800 mr-1.5 text-[11px]" title="入荷を在庫に登録">入荷</button>
                      {editable && <button onClick={() => allocate(l)} className="text-orange-500 hover:text-orange-700 mr-1.5 text-[11px]" title="在庫から引当">在庫引当</button>}
                      {editable && <button onClick={() => delLine(l.id)} className="text-red-400"><Trash2 size={12} /></button>}
                    </>}
              </td>
            </tr>
          ))}
          {(po.lines || []).length === 0 && <tr><td colSpan={8} className="px-2 py-2 text-gray-400">明細なし。下で追加してください。</td></tr>}
        </tbody>
        <tfoot><tr className="border-t-2 border-gray-300"><td colSpan={5} className="px-2 py-1 text-right font-medium">合計</td><td className="px-2 py-1 text-right font-bold">¥{total.toLocaleString()}</td><td colSpan={2}></td></tr></tfoot>
      </table>

      {/* 明細追加 */}
      {editable && (
      <div className="mt-2 flex flex-wrap items-end gap-2 bg-white border rounded p-2">
        <div className="relative">
          <label className="block text-[10px] text-gray-500">部材を検索して追加</label>
          <input value={matQuery} onChange={e => searchMat(e.target.value)} placeholder="部材名・コード" className="border rounded px-2 py-1 text-xs w-56" />
          {matResults.length > 0 && (
            <div className="absolute z-20 bg-white border rounded shadow mt-0.5 w-72 max-h-48 overflow-y-auto">
              {matResults.map(m => (
                <button key={m.id} onClick={() => pickMat(m)} className="block w-full text-left px-2 py-1 text-xs hover:bg-blue-50">
                  <span className="font-mono text-amber-700">{m.material_code}</span> {m.material_name}
                </button>
              ))}
            </div>
          )}
        </div>
        <div><label className="block text-[10px] text-gray-500">数量</label>
          <input type="number" value={newLine.order_qty} onChange={e => setNewLine({ ...newLine, order_qty: e.target.value })} className="border rounded px-2 py-1 text-xs w-16 text-right" /></div>
        <div><label className="block text-[10px] text-gray-500">単価</label>
          <input type="number" value={newLine.unit_price || ''} onChange={e => setNewLine({ ...newLine, unit_price: e.target.value })} className="border rounded px-2 py-1 text-xs w-24 text-right" /></div>
        <div><label className="block text-[10px] text-gray-500">納期</label>
          <input type="date" value={newLine.due_date || ''} onChange={e => setNewLine({ ...newLine, due_date: e.target.value })} className="border rounded px-2 py-1 text-xs" /></div>
        <button onClick={addLine} className="flex items-center gap-1 px-3 py-1 bg-indigo-600 text-white text-xs rounded hover:bg-indigo-700"><Plus size={12} />明細追加</button>
      </div>
      )}
    </div>
  );
}
