import { useEffect, useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { estimateApi, API_BASE } from '../api';
import { Plus, FileText, Search, Printer, Copy, X, Upload } from 'lucide-react';
import OrderSearchInput from '../components/common/OrderSearchInput';
import { scanDxf } from '../utils/dxfScan';

// 見積ステータス: 下書 / 受注（採用済）/ 受注済（受注票発行済）
const STATUS_LABELS: Record<string, string> = { draft: '下書', adopted: '受注', received: '受注済' };
const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600', adopted: 'bg-blue-100 text-blue-700', received: 'bg-green-100 text-green-700'
};

// 社内の管理金額は税抜（機器・工事 + 社内工数）で統一。
// 工番/単番は案件子IDで登録された区分（2026-07-18〜。金額による自動判定は廃止）
const TICKET_TYPE_LABELS: Record<string, string> = { koban: '工番', tanban: '単番' };
// 税抜合計（機器・工事＋社内工数−出精値引）。APIのnet_amountを優先し、無ければ計算
export const netAmount = (q: any) =>
  q?.net_amount ?? ((q?.subtotal || 0) + (q?.labor_total || 0) - (q?.discount_amount || 0));

export default function EstimateListPage() {
  const [searchParams] = useSearchParams();
  const childNo = searchParams.get('child_no') || '';
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [dupFor, setDupFor] = useState<any>(null); // 複製対象の見積
  const [showCad, setShowCad] = useState(false);   // CADから見積作成モーダル
  const navigate = useNavigate();

  const doDuplicate = async (order: any) => {
    if (!dupFor) return;
    try {
      const r = await estimateApi.duplicate(dupFor.id, order.id);
      setDupFor(null);
      alert(`複製しました: ${r.data.quotation_no}（子ID: ${r.data.child_no}）`);
      navigate(`/estimates/${r.data.id}/edit`);
    } catch (e: any) { alert(e.response?.data?.detail || '複製に失敗しました'); }
  };

  const load = () => {
    estimateApi.list({ child_no: childNo || undefined, search: search || undefined, per_page: 50 })
      .then(r => { setItems(r.data.items || []); setTotal(r.data.total || 0); });
  };
  useEffect(() => { load(); }, [childNo, search]);

  const handleAdopt = async (q: any) => {
    if (!q.project_order_id) { alert('この見積は子IDに紐付いていません'); return; }
    const isAdopted = q.is_adopted;
    if (!confirm(`${isAdopted ? '採用を解除' : '採用'}しますか？\n${q.quotation_no}`)) return;
    try {
      if (isAdopted) { await estimateApi.unadoptQuotation(q.id); alert('採用を解除しました'); }
      else { const r = await estimateApi.adoptQuotation(q.id); alert(`採用しました！\n子ID: ${r.data.child_no} に反映されました`); }
      load();
    } catch (e: any) { alert(e.response?.data?.detail || 'エラー'); }
  };

  const handlePdf = (id: string) => {
    const url = `${API_BASE}/estimate-quotations/${id}/pdf`;
    window.open(url, '_blank');
  };

  const handleFanInstruction = (id: string) => {
    window.open(`${API_BASE}/estimate-quotations/${id}/fan-instruction-pdf`, '_blank');
  };

  const handleFanInspection = (id: string) => {
    window.open(`${API_BASE}/estimate-quotations/${id}/fan-inspection-pdf`, '_blank');
  };

  const handleControlPanel = (id: string) => {
    window.open(`${API_BASE}/estimate-quotations/${id}/control-panel-pdf`, '_blank');
  };

  const handleIssueTicket = async (id: string, ticketType?: string) => {
    if (!ticketType) {
      alert('案件子IDに工番/単番が設定されていません。\n案件管理で区分を設定してから発行してください。');
      return;
    }
    const confirmMsg = `受注票を発行します。\n種別: ${TICKET_TYPE_LABELS[ticketType]}（案件で登録された区分）\nよろしいですか？`;
    if (!confirm(confirmMsg)) return;
    try {
      const r = await estimateApi.issueOrderTicket(id);
      const { ticket_no, id: ticketId } = r.data;
      if (r.data.has_previous) { alert(`受注票を再発行しました: ${ticket_no}\n旧受注票は非表示になりました`); } else { alert(`受注票発行: ${ticket_no}`); }
      const url = `${API_BASE}/estimate-quotations/order-ticket/${ticketId}/pdf`;
      window.open(url, '_blank');
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラー');
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">見積管理</h1>
          {childNo && <p className="text-sm text-blue-600 mt-1">子ID: {childNo} の見積一覧</p>}
          <p className="text-sm text-gray-500 mt-1">全 {total} 件</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowCad(true)}
            className="flex items-center gap-2 bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700 text-sm">
            <Upload size={16} /> CADから見積作成
          </button>
          <Link
            to={`/estimates/new${childNo ? `?child_no=${childNo}` : ''}`}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
            <Plus size={16} /> 新規見積作成
          </Link>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-3 mb-4 flex items-center gap-2 border border-gray-100">
        <Search size={16} className="text-gray-400" />
        <input placeholder="見積番号・注文主・件名・子IDで検索" value={search}
          onChange={e => setSearch(e.target.value)} className="flex-1 outline-none text-sm" />
        {search && <button onClick={() => setSearch('')} className="text-gray-400 hover:text-gray-600"><X size={15} /></button>}
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">見積番号</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注番号(COID)</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">注文主</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">件名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">見積日</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">合計金額（税抜）</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">状態</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(q => (
              <tr key={q.id} className="hover:bg-blue-50">
                <td className="px-4 py-3">
                  <Link to={`/estimates/${q.id}/edit`} className="text-blue-600 font-medium hover:underline flex items-center gap-1">
                    <FileText size={13} /> {q.quotation_no}
                  </Link>
                </td>
                <td className="px-4 py-3 text-gray-500 font-mono text-xs">{q.child_no || '—'}</td>
                <td className="px-4 py-3 text-gray-700">{q.customer_name || '—'}</td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{q.title || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{q.issue_date || '—'}</td>
                <td className="px-4 py-3 text-right font-bold text-gray-800">
                  ¥{netAmount(q).toLocaleString()}
                  {q.ticket_type ? (
                    <span className={`ml-2 text-xs ${q.ticket_type === 'koban' ? 'text-purple-600' : 'text-orange-600'}`}>
                      {TICKET_TYPE_LABELS[q.ticket_type]}
                    </span>
                  ) : (
                    <span className="ml-2 text-xs text-red-500" title="案件子IDに工番/単番が未設定です">区分未設定</span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  <div className="flex flex-col gap-1 items-center">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[q.status] || 'bg-gray-100'}`}>
                      {STATUS_LABELS[q.status] || q.status}
                    </span>
                    {q.approval_status === 'approved' ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-green-100 text-green-700">承認済</span>
                    ) : q.approval_status === 'pending' ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700">承認待ち</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-500">draft</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-center">
                  <div className="flex flex-col gap-1 items-center">
                    <div className="flex gap-1">
                      <button onClick={() => handlePdf(q.id)}
                        className="text-xs text-green-600 hover:text-green-800 flex items-center gap-1">
                        <Printer size={12} /> 見積PDF
                      </button>
                      <button onClick={() => handleIssueTicket(q.id, q.ticket_type)}
                        className="text-xs bg-purple-600 text-white px-2 py-0.5 rounded hover:bg-purple-700">
                        受注票
                      </button>
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => handleFanInstruction(q.id)}
                        className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded hover:bg-blue-200">
                        ファン指示書
                      </button>
                      <button onClick={() => handleFanInspection(q.id)}
                        className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded hover:bg-orange-200">
                        検査記録
                      </button>
                      <button onClick={() => handleControlPanel(q.id)}
                        className="text-xs bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded hover:bg-gray-200">
                        制御盤
                      </button>
                      <button onClick={() => setDupFor(q)}
                        className="text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded hover:bg-emerald-200 flex items-center gap-0.5">
                        <Copy size={11} />複製
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="text-center py-12 text-gray-400">見積書がありません</div>}
      </div>

      {/* 見積複製モーダル（案件子ID必須） */}
      {dupFor && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold text-gray-800">見積を複製</h2>
              <button onClick={() => setDupFor(null)} className="text-gray-400"><X size={18} /></button>
            </div>
            <p className="text-xs text-gray-500 mb-1">複製元: <span className="font-mono">{dupFor.quotation_no}</span> {dupFor.title || ''}</p>
            <p className="text-xs text-red-500 mb-2">複製先の案件子IDの選択は必須です。</p>
            <label className="block text-xs text-gray-500 mb-1">複製先 案件ID / 子ID</label>
            <OrderSearchInput onSelect={doDuplicate} placeholder="案件ID または 子ID で検索して選択" />
            <p className="text-[11px] text-gray-400 mt-3">※ 選択するとその子IDに紐付いた新しい見積（下書き）が作成され、編集画面が開きます。</p>
          </div>
        </div>
      )}

      {showCad && <CadEstimateModal onClose={() => setShowCad(false)} onCreated={(id) => navigate(`/estimates/${id}/edit`)} />}
    </div>
  );
}

// ========== CADから見積作成（プロトタイプ・ダクトは概算） ==========
function CadEstimateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [order, setOrder] = useState<any>(null);
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const [phase, setPhase] = useState('');

  const run = async () => {
    if (!file) { setError('DXFファイルを選択してください'); return; }
    setBusy(true); setError('');
    try {
      // 図面は数十MBあるためブラウザ内で走査し、抽出結果だけを送る
      setPhase('図面を解析中...');
      const scan = await scanDxf(file);
      setPhase('見積を作成中...');
      const r = await estimateApi.createFromCadExtract({
        filename: file.name,
        block_names: scan.block_names,
        texts: scan.texts,
        insunits: scan.insunits,
        acadver: scan.acadver,
        project_order_id: order?.id,
        title: title || undefined,
      });
      setResult({ ...r.data, scan: scan.stats });
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || '解析に失敗しました');
    } finally { setBusy(false); setPhase(''); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold text-gray-800">CAD図面から見積を作成</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>

        {!result ? (<>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-xs text-amber-800">
            <p className="font-semibold mb-1">プロトタイプです。生成結果は必ず確認してください。</p>
            <ul className="list-disc pl-4 space-y-0.5">
              <li>図面のブロック名・文字から自社製品の型式を抽出し、パターンマスタの単価を当てます</li>
              <li><b>ダクトは概算</b>です（図面から実長が取れないため、径と注記数から算出）</li>
              <li>取付工費・運送費・工数は図面外の情報のため<b>含まれません</b></li>
              <li>DWGしか無い場合は AutoCAD の <b>DXFOUT</b> で「AutoCAD 2018 DXF」に書き出してください</li>
            </ul>
          </div>

          <label className="block text-xs text-gray-500 mb-1">DXFファイル</label>
          <input type="file" accept=".dxf" onChange={e => { setFile(e.target.files?.[0] || null); setError(''); }}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mb-1" />
          {file && <p className="text-[11px] text-gray-500 mb-3">{file.name}（{(file.size / 1024 / 1024).toFixed(1)}MB）</p>}

          <label className="block text-xs text-gray-500 mb-1 mt-3">案件ID / 子ID（任意・注文主と納入先を引き継ぎます）</label>
          <OrderSearchInput onSelect={(o: any) => setOrder(o)} placeholder="案件ID または 子ID で検索" />
          {order && <p className="text-[11px] text-blue-600 mt-1">✓ {order.child_no || order.project_no} を選択中</p>}

          <label className="block text-xs text-gray-500 mb-1 mt-3">件名（任意）</label>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="空欄なら案件名またはファイル名"
            className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" />

          {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

          <div className="flex justify-end gap-2 mt-5">
            <button onClick={onClose} className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50">キャンセル</button>
            <button onClick={run} disabled={busy || !file}
              className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm hover:bg-teal-700 disabled:opacity-50">
              {busy ? (phase || '解析中...') : '解析して見積を作成'}
            </button>
          </div>
        </>) : (<>
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-3 text-sm">
            <p className="font-bold text-green-800">{result.quotation_no} を作成しました（draft）</p>
            <p className="text-green-700 mt-1">機器・ダクト概算 合計 ¥{Number(result.subtotal).toLocaleString()}（税抜）</p>
            {result.scan && (
              <p className="text-[11px] text-green-600 mt-1">
                解析: {(result.scan.bytes / 1024 / 1024).toFixed(1)}MB / ブロック{result.scan.blocks}件 / 文字{result.scan.texts}件（{result.scan.ms}ms）
              </p>
            )}
          </div>

          <div className="text-xs text-gray-600 mb-3">
            <p className="font-semibold mb-1">図面から抽出した型式</p>
            <div className="flex flex-wrap gap-1">
              {Object.entries(result.models || {}).map(([m, c]: any) => (
                <span key={m} className="bg-gray-100 px-2 py-0.5 rounded">{m} ×{c}</span>
              ))}
            </div>
          </div>

          {result.duct?.lines?.length > 0 && (
            <div className="text-xs text-gray-600 mb-3">
              <p className="font-semibold mb-1">ダクト概算 ¥{Number(result.duct.total).toLocaleString()}</p>
              <div className="max-h-32 overflow-y-auto border rounded p-2 space-y-0.5">
                {result.duct.lines.map((l: any) => (
                  <div key={l.dia}>φ{l.dia}：注記{l.count}件 → {l.run_m}m × {Number(l.rate_per_m).toLocaleString()}円/m = ¥{Number(l.amount).toLocaleString()}</div>
                ))}
              </div>
            </div>
          )}

          {result.warnings?.length > 0 && (
            <ul className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800 list-disc pl-6 space-y-1 mb-3">
              {result.warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}
            </ul>
          )}

          <div className="flex justify-end gap-2 mt-4">
            <button onClick={onClose} className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50">閉じる</button>
            <button onClick={() => onCreated(result.id)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
              見積を開いて編集
            </button>
          </div>
        </>)}
      </div>
    </div>
  );
}
