import { useEffect, useState, Fragment } from 'react';
import { useLocation } from 'react-router-dom';
import { procurementApi } from '../api';
import OrderSearchInput from '../components/common/OrderSearchInput';
import { Plus, Trash2, Edit2, Check, X, Search, Boxes, FileText, ChevronDown, ChevronRight } from 'lucide-react';

const STATUS_OPTIONS = ['未発注', '発注済', '入荷済'];
const STATUS_COLORS: Record<string, string> = {
  '作成中': 'bg-yellow-100 text-yellow-700',
  '未発注': 'bg-yellow-100 text-yellow-700',
  '発注済': 'bg-blue-100 text-blue-700',
  '一部入荷': 'bg-orange-100 text-orange-700',
  '入荷済': 'bg-green-100 text-green-700',
  'キャンセル': 'bg-gray-100 text-gray-500',
};
const PO_STATUS = ['作成中', '発注済', '一部入荷', '入荷済', 'キャンセル'];

const PRODUCT_TYPES = ['BFR', 'BFP', 'SCA', 'LCA', 'SRR', 'FLT', 'CY', 'LRG'];

// 入力フォーカス維持のためコンポーネント外で定義（毎レンダー再生成を防ぐ）
function Field({ label, children }: any) {
  return <div><label className="block text-xs text-gray-500 mb-0.5">{label}</label>{children}</div>;
}

export default function ProcurementPage() {
  const [tab, setTab] = useState<'po' | 'materials' | 'bom'>('po');
  const location = useLocation();
  const initialOrder = (location.state as any)?.childOrder || null;

  return (
    <div className="p-4">
      <h1 className="text-xl font-bold text-gray-800 mb-4">仕入（発注）管理</h1>
      <div className="flex gap-1 mb-5 border-b border-gray-200">
        {([['po', '発注書（発注番号）'], ['materials', '部材マスタ'], ['bom', 'BOMマスタ']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'po' && <PurchaseOrdersTab initialOrder={initialOrder} />}
      {tab === 'materials' && <MaterialsTab />}
      {tab === 'bom' && <BomTab />}
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

// ========== 発注管理タブ（旧・未使用） ==========
function OrdersTab() {
  const [orders, setOrders] = useState<any[]>([]);
  const [materials, setMaterials] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [editData, setEditData] = useState<any>({});
  const [showAdd, setShowAdd] = useState(false);
  const [newData, setNewData] = useState<any>({ status: '未発注' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // 方式B: ユニットから一括取込（受注採用見積から自動セット＋編集）
  const [showUnitImport, setShowUnitImport] = useState(false);
  const [units, setUnits] = useState<any[]>([]);
  const [unitRows, setUnitRows] = useState<any[]>([]);   // 選択中ユニット（編集可）
  const [addUnitId, setAddUnitId] = useState('');
  const [importOrder, setImportOrder] = useState<any>(null);
  const [importDue, setImportDue] = useState('');
  const [importMsg, setImportMsg] = useState('');
  const [autoMsg, setAutoMsg] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    Promise.all([
      procurementApi.listMaterialOrders(undefined, statusFilter || undefined),
      procurementApi.listMaterials(),
      procurementApi.listSuppliers(),
    ]).then(([o, m, s]) => {
      setOrders(o.data); setMaterials(m.data); setSuppliers(s.data);
    }).catch((e) => {
      setError('発注データの取得に失敗しました（' + (e?.response?.status || e?.message || 'error') + '）。/setup-bom-master-tables 未実行の可能性があります。');
    }).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [statusFilter]);

  const openUnitImport = () => {
    setShowUnitImport(true); setShowAdd(false);
    procurementApi.listBomUnits().then(r => setUnits(r.data)).catch(() => {});
  };
  // 案件子ID選択 → 受注採用見積のユニットを自動セット
  const onSelectImportOrder = (o: any) => {
    setImportOrder(o); setImportMsg(''); setAutoMsg('読込中...');
    procurementApi.adoptedUnits(o.id).then(r => {
      const us = (r.data.units || []).map((u: any) => ({ ...u, multiplier: u.quantity || 1 }));
      setUnitRows(us);
      if (!us.length) setAutoMsg(r.data.message || '受注採用見積にユニットがありません');
      else setAutoMsg(`採用見積 ${r.data.quotation_no || ''} から ${us.length}ユニットを自動セット`);
    }).catch(() => setAutoMsg('取得に失敗しました'));
  };
  const addUnitRow = () => {
    if (!addUnitId) return;
    const u = units.find(x => x.id === addUnitId);
    if (!u || unitRows.some(r => r.unit_id === u.id)) { setAddUnitId(''); return; }
    setUnitRows(rows => [...rows, {
      unit_id: u.id, unit_code: u.unit_code, unit_name: u.unit_name,
      unit_type: u.unit_type, model_no: u.model_no, material_count: u.material_count, multiplier: 1,
    }]);
    setAddUnitId('');
  };
  const updateRowMult = (idx: number, v: string) =>
    setUnitRows(rows => rows.map((r, i) => i === idx ? { ...r, multiplier: v } : r));
  const removeUnitRow = (idx: number) => setUnitRows(rows => rows.filter((_, i) => i !== idx));
  const doUnitImport = async () => {
    if (!unitRows.length) { alert('ユニットがありません'); return; }
    try {
      const r = await procurementApi.createOrdersFromUnits({
        project_order_id: importOrder?.id || null,
        due_date: importDue || null,
        units: unitRows.map(r => ({ unit_id: r.unit_id, multiplier: Number(r.multiplier) || 1 })),
      });
      if (r.data.created === 0) {
        setImportMsg(`⚠ ${r.data.message}`);
      } else {
        setImportMsg(`✓ ${r.data.message}`);
        setUnitRows([]);
        load();
      }
    } catch (e: any) { setImportMsg(`❌ ${e.response?.data?.detail || 'エラー'}`); }
  };

  const handleSave = async (id: string) => {
    await procurementApi.updateMaterialOrder(id, editData);
    setEditing(null); load();
  };
  const handleAdd = async () => {
    if (!newData.material_id) { setError('部材を選択してください。'); return; }
    try {
      await procurementApi.createMaterialOrder(newData);
      setShowAdd(false); setNewData({ status: '未発注' }); load();
    } catch (e: any) {
      setError('発注の登録に失敗しました（' + (e?.response?.status || e?.message || 'error') + '）。');
    }
  };
  const handleDelete = async (id: string) => {
    if (!confirm('削除しますか？')) return;
    await procurementApi.deleteMaterialOrder(id); load();
  };

  return (
    <div>
      {error && <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded">{error}</div>}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border rounded px-2 py-1 text-sm">
          <option value="">全ステータス</option>
          {STATUS_OPTIONS.map(s => <option key={s}>{s}</option>)}
        </select>
        <button onClick={openUnitImport}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700">
          <Boxes size={14} />ユニットから取込
        </button>
        <button onClick={() => { setShowAdd(true); setShowUnitImport(false); }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
          <Plus size={14} />個別発注
        </button>
      </div>

      {showUnitImport && (
        <div className="mb-4 p-3 border border-indigo-200 rounded-lg bg-indigo-50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-indigo-700">方式B: 受注採用見積のユニットを自動セット → 編集して一括発注（部材は員数×台数で自動展開）</span>
            <button onClick={() => { setShowUnitImport(false); setImportMsg(''); setAutoMsg(''); setUnitRows([]); }} className="text-gray-400"><X size={14} /></button>
          </div>
          <div className="flex flex-wrap gap-2 items-end mb-2">
            <div className="min-w-[280px]">
              <label className="block text-xs text-gray-500 mb-0.5">案件ID / 子ID（受注採用見積からユニットを自動セット）</label>
              <OrderSearchInput onSelect={onSelectImportOrder} placeholder="案件ID または 子ID で検索" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">納期（一括設定）</label>
              <input type="date" value={importDue} onChange={e => setImportDue(e.target.value)} className="border rounded px-2 py-1 text-sm" />
            </div>
            {autoMsg && <span className="text-xs text-indigo-600 pb-1.5">{autoMsg}</span>}
          </div>

          {/* 選択ユニット（編集可） */}
          <div className="bg-white border rounded">
            <table className="w-full text-xs">
              <thead><tr className="bg-gray-50 text-gray-600">
                {['ユニット', '種別', '型式', '部材数', '台数', ''].map(h => <th key={h} className="px-2 py-1.5 text-left font-medium border-b">{h}</th>)}
              </tr></thead>
              <tbody>
                {unitRows.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-4 text-gray-400">案件を選ぶと採用見積のユニットが入ります（手動追加も可）</td></tr>
                ) : unitRows.map((r, idx) => (
                  <tr key={r.unit_id} className="border-b last:border-0">
                    <td className="px-2 py-1.5"><span className="font-mono text-indigo-700">{r.unit_code}</span> {r.unit_name}</td>
                    <td className="px-2 py-1.5">{r.unit_type || '—'}</td>
                    <td className="px-2 py-1.5">{r.model_no || '—'}</td>
                    <td className="px-2 py-1.5 text-center">{r.material_count === 0
                      ? <span className="text-red-500">未登録</span> : r.material_count}</td>
                    <td className="px-2 py-1.5"><input type="number" value={r.multiplier}
                      onChange={e => updateRowMult(idx, e.target.value)} className="border rounded px-1 py-0.5 w-16 text-right" /></td>
                    <td className="px-2 py-1.5"><button onClick={() => removeUnitRow(idx)} className="text-red-400"><Trash2 size={13} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* 手動でユニット追加 */}
            <div className="flex items-center gap-2 px-2 py-1.5 border-t bg-gray-50">
              <span className="text-xs text-gray-400">ユニット追加:</span>
              <select value={addUnitId} onChange={e => setAddUnitId(e.target.value)} className="border rounded px-2 py-1 text-xs min-w-[240px]">
                <option value="">— ユニット選択 —</option>
                {units.map(u => <option key={u.id} value={u.id}>{u.unit_code} / {u.unit_name}（部材{u.material_count}件）</option>)}
              </select>
              <button onClick={addUnitRow} className="flex items-center gap-1 px-2 py-1 bg-gray-700 text-white text-xs rounded hover:bg-gray-800"><Plus size={12} />追加</button>
            </div>
          </div>

          <div className="flex items-center gap-2 mt-2">
            <button onClick={doUnitImport} disabled={!unitRows.length}
              className="flex items-center gap-1 px-4 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50">
              <Check size={14} />一括起票（{unitRows.length}ユニット）
            </button>
            {importMsg && <span className={`text-xs ${importMsg.startsWith('✓') ? 'text-green-700' : 'text-red-500'}`}>{importMsg}</span>}
          </div>
        </div>
      )}

      {showAdd && (
        <div className="mb-4 p-3 border border-blue-200 rounded-lg bg-blue-50 flex flex-wrap gap-2 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">部材</label>
            <select value={newData.material_id || ''} onChange={e => setNewData({...newData, material_id: e.target.value})}
              className="border rounded px-2 py-1 text-sm">
              <option value="">選択</option>
              {materials.map(m => <option key={m.id} value={m.id}>{m.material_name}（{m.material_code}）</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">仕入先</label>
            <select value={newData.supplier_id || ''} onChange={e => setNewData({...newData, supplier_id: e.target.value})}
              className="border rounded px-2 py-1 text-sm">
              <option value="">選択</option>
              {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">数量</label>
            <input type="number" value={newData.order_qty || ''} onChange={e => setNewData({...newData, order_qty: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-24" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">納期</label>
            <input type="date" value={newData.due_date || ''} onChange={e => setNewData({...newData, due_date: e.target.value})}
              className="border rounded px-2 py-1 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">ステータス</label>
            <select value={newData.status} onChange={e => setNewData({...newData, status: e.target.value})}
              className="border rounded px-2 py-1 text-sm">
              {STATUS_OPTIONS.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">備考</label>
            <input type="text" value={newData.notes || ''} onChange={e => setNewData({...newData, notes: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-32" />
          </div>
          <button onClick={handleAdd} className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"><Check size={14} /></button>
          <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 border text-sm rounded hover:bg-gray-50"><X size={14} /></button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="text-sm w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              {['部材名','部材コード','仕入先','数量','単価','発注日','納期','入荷日','ステータス','備考',''].map(h => (
                <th key={h} className="border border-gray-200 px-2 py-2 text-left text-xs font-medium text-gray-600">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={11} className="text-center py-8 text-gray-400">読み込み中...</td></tr>
            ) : orders.length === 0 ? (
              <tr><td colSpan={11} className="text-center py-8 text-gray-400">データなし</td></tr>
            ) : orders.map(o => editing === o.id ? (
              <tr key={o.id} className="bg-blue-50">
                <td className="border border-gray-200 px-2 py-1" colSpan={2}>{o.material_name}（{o.material_code}）</td>
                <td className="border border-gray-200 px-1 py-1">
                  <select value={editData.supplier_id || ''} onChange={e => setEditData({...editData, supplier_id: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs w-full">
                    <option value="">-</option>
                    {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input type="number" value={editData.order_qty ?? ''} onChange={e => setEditData({...editData, order_qty: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs w-20" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input type="number" value={editData.unit_price ?? ''} onChange={e => setEditData({...editData, unit_price: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs w-24" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input type="date" value={editData.order_date || ''} onChange={e => setEditData({...editData, order_date: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input type="date" value={editData.due_date || ''} onChange={e => setEditData({...editData, due_date: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input type="date" value={editData.received_date || ''} onChange={e => setEditData({...editData, received_date: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <select value={editData.status || '未発注'} onChange={e => setEditData({...editData, status: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs">
                    {STATUS_OPTIONS.map(s => <option key={s}>{s}</option>)}
                  </select>
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input type="text" value={editData.notes || ''} onChange={e => setEditData({...editData, notes: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs w-24" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <button onClick={() => handleSave(o.id)} className="p-1 text-green-600 hover:bg-green-50 rounded"><Check size={13} /></button>
                  <button onClick={() => setEditing(null)} className="p-1 text-gray-400 hover:bg-gray-50 rounded"><X size={13} /></button>
                </td>
              </tr>
            ) : (
              <tr key={o.id} className="hover:bg-gray-50">
                <td className="border border-gray-200 px-2 py-1 font-medium">{o.material_name}</td>
                <td className="border border-gray-200 px-2 py-1 text-gray-500 font-mono text-xs">{o.material_code}</td>
                <td className="border border-gray-200 px-2 py-1">{o.supplier_name || '—'}</td>
                <td className="border border-gray-200 px-2 py-1 text-right">{o.order_qty != null ? `${o.order_qty} ${o.unit || ''}` : '—'}</td>
                <td className="border border-gray-200 px-2 py-1 text-right">{o.unit_price != null ? `¥${Number(o.unit_price).toLocaleString()}` : '—'}</td>
                <td className="border border-gray-200 px-2 py-1 text-xs">{o.order_date || '—'}</td>
                <td className="border border-gray-200 px-2 py-1 text-xs">{o.due_date || '—'}</td>
                <td className="border border-gray-200 px-2 py-1 text-xs">{o.received_date || '—'}</td>
                <td className="border border-gray-200 px-2 py-1">
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[o.status] || 'bg-gray-100'}`}>{o.status}</span>
                </td>
                <td className="border border-gray-200 px-2 py-1 text-xs text-gray-500">{o.notes || ''}</td>
                <td className="border border-gray-200 px-1 py-1">
                  <button onClick={() => { setEditing(o.id); setEditData({...o}); }} className="p-1 text-blue-500 hover:bg-blue-50 rounded"><Edit2 size={13} /></button>
                  <button onClick={() => handleDelete(o.id)} className="p-1 text-red-400 hover:bg-red-50 rounded"><Trash2 size={13} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ========== 部材マスタタブ ==========
function MaterialsTab() {
  const [materials, setMaterials] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [editData, setEditData] = useState<any>({});
  const [showAdd, setShowAdd] = useState(false);
  const [newData, setNewData] = useState<any>({ unit: '個', standard_lead_days: 14 });
  const [error, setError] = useState('');

  const load = () => { setError('');
    return Promise.all([
      procurementApi.listMaterials(search || undefined),
      procurementApi.listSuppliers(),
    ]).then(([m, s]) => { setMaterials(m.data); setSuppliers(s.data); })
      .catch((e) => { setError('部材マスタの取得に失敗しました（' + (e?.response?.status || e?.message || 'error') + '）。'); });
  };

  useEffect(() => { load(); }, [search]);

  const handleAdd = async () => {
    await procurementApi.createMaterial(newData);
    setShowAdd(false); setNewData({ unit: '個', standard_lead_days: 14 }); load();
  };
  const handleSave = async (id: string) => {
    await procurementApi.updateMaterial(id, editData);
    setEditing(null); load();
  };
  const handleDelete = async (id: string) => {
    if (!confirm('削除しますか？')) return;
    await procurementApi.deleteMaterial(id); load();
  };

  return (
    <div>
      {error && <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded">{error}</div>}
      <div className="flex items-center gap-2 mb-3">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-2 text-gray-400" />
          <input placeholder="部材名・コードで検索" value={search} onChange={e => setSearch(e.target.value)}
            className="border rounded-lg pl-8 pr-3 py-1.5 text-sm w-56" />
        </div>
        <button onClick={() => setShowAdd(true)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
          <Plus size={14} />部材追加
        </button>
      </div>

      {showAdd && (
        <div className="mb-4 p-3 border border-blue-200 rounded-lg bg-blue-50 flex flex-wrap gap-2 items-end">
          <Field label="部材コード *">
            <input value={newData.material_code || ''} onChange={e => setNewData({...newData, material_code: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-28" placeholder="例: MAT-001" />
          </Field>
          <Field label="部材名 *">
            <input value={newData.material_name || ''} onChange={e => setNewData({...newData, material_name: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-48" />
          </Field>
          <Field label="単位">
            <input value={newData.unit || '個'} onChange={e => setNewData({...newData, unit: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-16" />
          </Field>
          <Field label="優先仕入先">
            <select value={newData.default_supplier_id || ''} onChange={e => setNewData({...newData, default_supplier_id: e.target.value || null})}
              className="border rounded px-2 py-1 text-sm w-40">
              <option value="">-</option>
              {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
          <Field label="リードタイム(日)">
            <input type="number" value={newData.standard_lead_days || 14} onChange={e => setNewData({...newData, standard_lead_days: Number(e.target.value)})}
              className="border rounded px-2 py-1 text-sm w-16" />
          </Field>
          <Field label="備考">
            <input value={newData.notes || ''} onChange={e => setNewData({...newData, notes: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-36" />
          </Field>
          <button onClick={handleAdd} className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded"><Check size={14} /></button>
          <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 border text-sm rounded"><X size={14} /></button>
        </div>
      )}

      <table className="text-sm w-full border-collapse">
        <thead>
          <tr className="bg-gray-50">
            {['部材コード','部材名','単位','優先仕入先','リードタイム(日)','備考',''].map(h => (
              <th key={h} className="border border-gray-200 px-2 py-2 text-left text-xs font-medium text-gray-600">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {materials.map(m => editing === m.id ? (
            <tr key={m.id} className="bg-blue-50">
              <td className="border border-gray-200 px-1 py-1">
                <input value={editData.material_code || ''} onChange={e => setEditData({...editData, material_code: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-24" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input value={editData.material_name || ''} onChange={e => setEditData({...editData, material_name: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-48" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input value={editData.unit || ''} onChange={e => setEditData({...editData, unit: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-12" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <select value={editData.default_supplier_id || ''} onChange={e => setEditData({...editData, default_supplier_id: e.target.value || null})}
                  className="border rounded px-1 py-0.5 text-xs w-36">
                  <option value="">-</option>
                  {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input type="number" value={editData.standard_lead_days ?? ''} onChange={e => setEditData({...editData, standard_lead_days: Number(e.target.value)})}
                  className="border rounded px-1 py-0.5 text-xs w-16" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input value={editData.notes || ''} onChange={e => setEditData({...editData, notes: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-36" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <button onClick={() => handleSave(m.id)} className="p-1 text-green-600 rounded"><Check size={13} /></button>
                <button onClick={() => setEditing(null)} className="p-1 text-gray-400 rounded"><X size={13} /></button>
              </td>
            </tr>
          ) : (
            <tr key={m.id} className="hover:bg-gray-50">
              <td className="border border-gray-200 px-2 py-1 font-mono text-xs">{m.material_code}</td>
              <td className="border border-gray-200 px-2 py-1 font-medium">{m.material_name}</td>
              <td className="border border-gray-200 px-2 py-1 text-gray-500">{m.unit}</td>
              <td className="border border-gray-200 px-2 py-1">{m.default_supplier_name || '—'}</td>
              <td className="border border-gray-200 px-2 py-1 text-center">{m.standard_lead_days}日</td>
              <td className="border border-gray-200 px-2 py-1 text-xs text-gray-500">{m.notes || ''}</td>
              <td className="border border-gray-200 px-1 py-1">
                <button onClick={() => { setEditing(m.id); setEditData({...m}); }} className="p-1 text-blue-500 rounded"><Edit2 size={13} /></button>
                <button onClick={() => handleDelete(m.id)} className="p-1 text-red-400 rounded"><Trash2 size={13} /></button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ========== BOMマスタタブ ==========
function BomTab() {
  const [boms, setBoms] = useState<any[]>([]);
  const [materials, setMaterials] = useState<any[]>([]);
  const [filterType, setFilterType] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [editData, setEditData] = useState<any>({});
  const [showAdd, setShowAdd] = useState(false);
  const [newData, setNewData] = useState<any>({ quantity: 1 });
  const [error, setError] = useState('');

  const load = () => { setError('');
    return Promise.all([
      procurementApi.listBom(filterType || undefined),
      procurementApi.listMaterials(),
    ]).then(([b, m]) => { setBoms(b.data); setMaterials(m.data); })
      .catch((e) => { setError('BOMマスタの取得に失敗しました（' + (e?.response?.status || e?.message || 'error') + '）。'); });
  };

  useEffect(() => { load(); }, [filterType]);

  const handleAdd = async () => {
    await procurementApi.createBom(newData);
    setShowAdd(false); setNewData({ quantity: 1 }); load();
  };
  const handleSave = async (id: string) => {
    await procurementApi.updateBom(id, editData);
    setEditing(null); load();
  };
  const handleDelete = async (id: string) => {
    if (!confirm('削除しますか？')) return;
    await procurementApi.deleteBom(id); load();
  };

  return (
    <div>
      {error && <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded">{error}</div>}
      <div className="flex items-center gap-2 mb-3">
        <select value={filterType} onChange={e => setFilterType(e.target.value)}
          className="border rounded px-2 py-1 text-sm">
          <option value="">全製品種別</option>
          {PRODUCT_TYPES.map(t => <option key={t}>{t}</option>)}
        </select>
        <span className="text-xs text-gray-500 ml-1">{boms.length}件</span>
        <button onClick={() => setShowAdd(true)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
          <Plus size={14} />BOM追加
        </button>
      </div>

      {showAdd && (
        <div className="mb-4 p-3 border border-blue-200 rounded-lg bg-blue-50 flex flex-wrap gap-2 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">製品種別</label>
            <select value={newData.product_type || ''} onChange={e => setNewData({...newData, product_type: e.target.value})}
              className="border rounded px-2 py-1 text-sm">
              <option value="">選択</option>
              {PRODUCT_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">型番</label>
            <input value={newData.model_no || ''} onChange={e => setNewData({...newData, model_no: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-28" placeholder="例: 3X6, 675" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">部材</label>
            <select value={newData.material_id || ''} onChange={e => setNewData({...newData, material_id: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-48">
              <option value="">選択</option>
              {materials.map(m => <option key={m.id} value={m.id}>{m.material_name}（{m.material_code}）</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">数量</label>
            <input type="number" step="0.001" value={newData.quantity || 1} onChange={e => setNewData({...newData, quantity: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-20" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">単位</label>
            <input value={newData.unit || ''} onChange={e => setNewData({...newData, unit: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-16" />
          </div>
          <button onClick={handleAdd} className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded"><Check size={14} /></button>
          <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 border text-sm rounded"><X size={14} /></button>
        </div>
      )}

      <table className="text-sm w-full border-collapse">
        <thead>
          <tr className="bg-gray-50">
            {['製品種別','型番','部材コード','部材名','数量','単位','備考',''].map(h => (
              <th key={h} className="border border-gray-200 px-2 py-2 text-left text-xs font-medium text-gray-600">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {boms.map(b => editing === b.id ? (
            <tr key={b.id} className="bg-blue-50">
              <td className="border border-gray-200 px-1 py-1">
                <select value={editData.product_type || ''} onChange={e => setEditData({...editData, product_type: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs">
                  {PRODUCT_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input value={editData.model_no || ''} onChange={e => setEditData({...editData, model_no: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-20" />
              </td>
              <td className="border border-gray-200 px-1 py-1 text-xs text-gray-500">{b.material_code}</td>
              <td className="border border-gray-200 px-1 py-1">
                <select value={editData.material_id || ''} onChange={e => setEditData({...editData, material_id: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-40">
                  {materials.map(m => <option key={m.id} value={m.id}>{m.material_name}</option>)}
                </select>
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input type="number" step="0.001" value={editData.quantity ?? ''} onChange={e => setEditData({...editData, quantity: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-16" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input value={editData.unit || ''} onChange={e => setEditData({...editData, unit: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-12" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input value={editData.notes || ''} onChange={e => setEditData({...editData, notes: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-28" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <button onClick={() => handleSave(b.id)} className="p-1 text-green-600 rounded"><Check size={13} /></button>
                <button onClick={() => setEditing(null)} className="p-1 text-gray-400 rounded"><X size={13} /></button>
              </td>
            </tr>
          ) : (
            <tr key={b.id} className="hover:bg-gray-50">
              <td className="border border-gray-200 px-2 py-1"><span className="px-1.5 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs font-medium">{b.product_type}</span></td>
              <td className="border border-gray-200 px-2 py-1 font-mono text-xs">{b.model_no}</td>
              <td className="border border-gray-200 px-2 py-1 font-mono text-xs text-gray-500">{b.material_code}</td>
              <td className="border border-gray-200 px-2 py-1">{b.material_name}</td>
              <td className="border border-gray-200 px-2 py-1 text-right">{b.quantity}</td>
              <td className="border border-gray-200 px-2 py-1 text-gray-500">{b.unit}</td>
              <td className="border border-gray-200 px-2 py-1 text-xs text-gray-500">{b.notes || ''}</td>
              <td className="border border-gray-200 px-1 py-1">
                <button onClick={() => { setEditing(b.id); setEditData({...b}); }} className="p-1 text-blue-500 rounded"><Edit2 size={13} /></button>
                <button onClick={() => handleDelete(b.id)} className="p-1 text-red-400 rounded"><Trash2 size={13} /></button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
