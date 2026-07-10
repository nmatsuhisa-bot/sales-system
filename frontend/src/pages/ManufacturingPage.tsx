import { useEffect, useState } from 'react';
import { manufacturingApi, projectApi } from '../api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Plus, Trash2, Edit2, Check, X, AlertTriangle, FileText } from 'lucide-react';
import OrderSearchInput from '../components/common/OrderSearchInput';

const STATUS_OPTIONS = ['未着手', '製造中', '完了'];
const STATUS_COLORS: Record<string, string> = {
  '未着手': 'bg-gray-100 text-gray-600',
  '製造中': 'bg-blue-100 text-blue-700',
  '完了': 'bg-green-100 text-green-700',
};
const PRODUCT_TYPES = ['BFR', 'BFP', 'SCA', 'LCA', 'SRR', 'FLT', 'CY', 'LRG'];
const MONTH_NAMES = ['3月','4月','5月','6月','7月','8月','9月','10月','11月','12月','1月','2月'];

function currentFiscalYear(): number {
  const today = new Date();
  const m = today.getMonth() + 1;
  const d = today.getDate();
  return (m > 2 || (m === 2 && d > 20)) ? today.getFullYear() : today.getFullYear() - 1;
}

export default function ManufacturingPage() {
  const [tab, setTab] = useState<'plans' | 'gantt' | 'capacity' | 'hours'>('plans');
  const [fiscalYear, setFiscalYear] = useState(currentFiscalYear());
  const thisYear = new Date().getFullYear();

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">製造計画</h1>
        <select value={fiscalYear} onChange={e => setFiscalYear(Number(e.target.value))}
          className="border rounded px-2 py-1 text-sm">
          {[thisYear-1, thisYear, thisYear+1].map(y => (
            <option key={y} value={y}>{y}年度</option>
          ))}
        </select>
      </div>
      <div className="flex gap-1 mb-5 border-b border-gray-200">
        {([['plans', '製造計画'], ['gantt', 'ガント'], ['capacity', '生産能力マスタ'], ['hours', '製品所要工数マスタ']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === key ? 'border-green-600 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'plans' && <PlansTab fiscalYear={fiscalYear} />}
      {tab === 'gantt' && <GanttTab fiscalYear={fiscalYear} />}
      {tab === 'capacity' && <CapacityTab fiscalYear={fiscalYear} />}
      {tab === 'hours' && <ProductHoursTab />}
    </div>
  );
}

// ========== 製造計画ガント（旬単位グリッド・PDF準拠） ==========
function GanttTab({ fiscalYear }: { fiscalYear: number }) {
  const [plans, setPlans] = useState<any[]>([]);
  const [loadData, setLoadData] = useState<any[]>([]);

  useEffect(() => {
    manufacturingApi.listPlans(fiscalYear).then(r => setPlans(r.data)).catch(() => {});
    manufacturingApi.getMonthlyLoad(fiscalYear).then(r => setLoadData(r.data.monthly || [])).catch(() => {});
  }, [fiscalYear]);

  // 年度の週カラム（3月〜翌2月、各月を7日区切りの週に分割）
  const FY_MONTHS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2];
  const lastDay = (y: number, m: number) => new Date(y, m, 0).getDate();
  const cols: any[] = [];
  FY_MONTHS.forEach(m => {
    const y = m >= 3 ? fiscalYear : fiscalYear + 1;
    const ld = lastDay(y, m);
    let s = 1, wk = 1;
    while (s <= ld) {
      const e = Math.min(s + 6, ld);
      cols.push({ y, m, s, e, label: `${wk}週` });
      s = e + 1; wk++;
    }
  });
  const monthCounts = FY_MONTHS.map(m => cols.filter(c => c.m === m).length);

  const toD = (iso: string) => { const [yy, mm, dd] = iso.split('-').map(Number); return new Date(yy, mm - 1, dd); };
  const dayMs = 86400000;

  // 計画ごとの旬別工数
  const planCells = (p: any): number[] => {
    const arr = new Array(cols.length).fill(0);
    if (!p.planned_start || !p.planned_end || !p.total_hours) return arr;
    const ps = toD(p.planned_start), pe = toD(p.planned_end);
    const totalDays = Math.round((+pe - +ps) / dayMs) + 1;
    const perDay = p.total_hours / Math.max(totalDays, 1);
    cols.forEach((c, ci) => {
      const cs = new Date(c.y, c.m - 1, c.s), ce = new Date(c.y, c.m - 1, c.e);
      const ovS = Math.max(+ps, +cs), ovE = Math.min(+pe, +ce);
      if (ovE >= ovS) arr[ci] = perDay * (Math.round((ovE - ovS) / dayMs) + 1);
    });
    return arr;
  };

  const rows = plans.map(p => ({ p, cells: planCells(p) }));
  // 旬別合計
  const colTotal = cols.map((_, ci) => rows.reduce((s, r) => s + r.cells[ci], 0));
  // 週別 使用可能（月の available を旬数で按分）
  const capByMonth: Record<number, number> = {};
  loadData.forEach((d: any) => { capByMonth[d.month] = d.available_hours || 0; });
  const colCap = cols.map(c => Math.round((capByMonth[c.m] || 0) * (c.e - c.s + 1) / lastDay(c.y, c.m)));

  const today = new Date();
  const STATUS_BG: Record<string, string> = { '完了': '#dcfce7', '製造中': '#dbeafe', '未着手': '#f1f5f9' };

  const unitLabel = (p: any) => p.unit_name || `${p.product_type || ''}${p.model_no ? `/${p.model_no}` : ''}`;

  const handlePrint = () => {
    const win = window.open('', '_blank', 'width=1600,height=1000');
    if (!win) return;
    const esc = (s: any) => String(s ?? '').replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' } as any)[c]);
    const monthHead = FY_MONTHS.map((m, i) => `<th colspan="${monthCounts[i]}">${m}月</th>`).join('');
    const weekHead = cols.map(c => `<th class="wk">${c.label}</th>`).join('');
    const bodyRows = rows.map(({ p, cells }) => `<tr>
      <td class="l mono">${esc(p.child_no)}${p.breakdown_no ? '-' + esc(p.breakdown_no) : ''}</td>
      <td class="l">${esc(p.customer_name)}</td>
      <td class="l"></td>
      <td class="l">${esc(unitLabel(p))}</td>
      <td class="r">${p.total_hours ? p.total_hours + 'h' : ''}</td>
      ${cells.map((h: number) => `<td class="c" style="background:${h > 0 ? (STATUS_BG[p.status] || '#dcfce7') : '#fff'}">${h > 0 ? Math.round(h) : ''}</td>`).join('')}
    </tr>`).join('');
    const footRow = `<tr class="ft"><td class="l" colspan="4">週別 計画工数</td><td class="r">${Math.round(colTotal.reduce((a, b) => a + b, 0))}h</td>${colTotal.map((t, ci) => { const over = colCap[ci] > 0 && t > colCap[ci]; return `<td class="c" style="${over ? 'background:#fecaca;color:#b91c1c;font-weight:bold' : ''}">${t > 0 ? Math.round(t) : ''}</td>`; }).join('')}</tr>`;
    win.document.write(`<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><title>製造計画_${fiscalYear}年度</title>
<style>
  @page { size: A3 landscape; margin: 8mm; }
  body { font-family: "MS Gothic","Meiryo",sans-serif; font-size: 9px; margin: 0; }
  h2 { font-size: 14px; margin: 0 0 4px; }
  table { border-collapse: collapse; width: 100%; table-layout: fixed; }
  th, td { border: 1px solid #999; padding: 1px 3px; overflow: hidden; white-space: nowrap; }
  th { background: #f0f0f0; }
  td.l { text-align: left; } td.r { text-align: right; } td.c { text-align: center; }
  td.mono { font-family: monospace; }
  .wk { font-weight: normal; width: 18px; }
  .ft td { background: #f3f4f6; font-weight: 600; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
</style></head><body>
<h2>製造計画　${fiscalYear}年度（${fiscalYear}/3〜${fiscalYear + 1}/2）</h2>
<table><thead>
  <tr><th rowspan="2">案件ID</th><th rowspan="2">納入先</th><th rowspan="2">地域</th><th rowspan="2">品名/型式</th><th rowspan="2">工数</th>${monthHead}</tr>
  <tr>${weekHead}</tr>
</thead><tbody>${bodyRows}</tbody><tfoot>${footRow}</tfoot></table>
</body></html>`);
    win.document.close();
    win.onload = () => { win.print(); };
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <p className="text-xs text-gray-500">行＝計画 ／ 横軸＝月×週 ／ セル＝その週の計画工数(h)。最下部は週別の合計と使用可能時間（超過は赤）。</p>
        <button onClick={handlePrint} disabled={!rows.length}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 text-white text-sm rounded hover:bg-gray-800 disabled:opacity-50">
          <FileText size={14} />PDF出力
        </button>
      </div>
      <div className="overflow-x-auto border rounded-lg">
        <table className="text-[11px] border-collapse" style={{ minWidth: `${360 + cols.length * 30}px` }}>
          <thead>
            <tr className="bg-gray-100">
              <th rowSpan={2} className="border border-gray-300 px-2 py-1 sticky left-0 bg-gray-100 text-left" style={{ minWidth: '170px' }}>案件ID / 納入先 / 地域</th>
              <th rowSpan={2} className="border border-gray-300 px-1 py-1 text-right" style={{ width: '52px' }}>計画工数</th>
              {FY_MONTHS.map((m, i) => (
                <th key={m} colSpan={monthCounts[i]} className="border border-gray-300 text-center py-0.5">{m}月</th>
              ))}
            </tr>
            <tr className="bg-gray-50">
              {cols.map((c, ci) => {
                const isThis = today.getFullYear() === c.y && today.getMonth() + 1 === c.m &&
                  today.getDate() >= c.s && today.getDate() <= c.e;
                return <th key={ci} className={`border border-gray-300 text-center font-normal ${isThis ? 'bg-red-100' : ''}`} style={{ width: '34px' }}>{c.label}</th>;
              })}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={2 + cols.length} className="text-center py-8 text-gray-400">計画なし</td></tr>
            ) : rows.map(({ p, cells }) => (
              <tr key={p.id}>
                <td className="border border-gray-300 px-2 py-1 sticky left-0 bg-white whitespace-nowrap">
                  <div><span className="font-mono text-gray-700">{p.child_no}{p.breakdown_no ? `-${p.breakdown_no}` : ''}</span>
                    <span className="text-gray-500 ml-1">{unitLabel(p)}</span></div>
                  <div className="text-[10px] text-gray-500">納入先: {p.customer_name || '—'}　地域: {p.region || ''}</div>
                </td>
                <td className="border border-gray-300 px-1 py-1 text-right font-semibold">{p.total_hours ? `${p.total_hours}h` : '—'}</td>
                {cells.map((h, ci) => (
                  <td key={ci} className="border border-gray-200 text-center"
                    style={{ background: h > 0 ? (STATUS_BG[p.status] || '#dcfce7') : 'white' }}>
                    {h > 0 ? Math.round(h) : ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-gray-50 font-medium">
              <td className="border border-gray-300 px-2 py-1 sticky left-0 bg-gray-50">週別 計画工数</td>
              <td className="border border-gray-300 px-1 py-1 text-right">{Math.round(colTotal.reduce((a, b) => a + b, 0))}h</td>
              {colTotal.map((t, ci) => {
                const over = colCap[ci] > 0 && t > colCap[ci];
                return <td key={ci} className={`border border-gray-300 text-center ${over ? 'bg-red-200 text-red-700 font-bold' : ''}`}>{t > 0 ? Math.round(t) : ''}</td>;
              })}
            </tr>
            <tr className="bg-white text-gray-500">
              <td className="border border-gray-300 px-2 py-1 sticky left-0 bg-white">週別 使用可能</td>
              <td className="border border-gray-300"></td>
              {colCap.map((c, ci) => <td key={ci} className="border border-gray-200 text-center">{c > 0 ? c : ''}</td>)}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

// ========== 製造計画タブ ==========
function PlansTab({ fiscalYear }: { fiscalYear: number }) {
  const [plans, setPlans] = useState<any[]>([]);
  const [loadData, setLoadData] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newData, setNewData] = useState<any>({ status: '未着手' });
  const [editing, setEditing] = useState<string | null>(null);
  const [editData, setEditData] = useState<any>({});
  const [showDraft, setShowDraft] = useState(false);
  const [draftMsg, setDraftMsg] = useState('');

  const handleDraft = async (o: any) => {
    setDraftMsg('作成中...');
    try {
      const r = await manufacturingApi.draftFromEstimate(o.id);
      setDraftMsg((r.data.created === 0 ? '⚠ ' : '✓ ') + r.data.message);
      load();
    } catch (e: any) { setDraftMsg(`❌ ${e.response?.data?.detail || 'エラー'}`); }
  };

  const load = () => {
    manufacturingApi.listPlans(fiscalYear).then(r => setPlans(r.data)).catch(() => {});
    manufacturingApi.getMonthlyLoad(fiscalYear).then(r => setLoadData(r.data.monthly || [])).catch(() => {});
    projectApi.list({ status: '受注' }).catch(() => {});
  };
  useEffect(() => { load(); }, [fiscalYear]);

  const handleAdd = async () => {
    if (!newData.project_order_id) { alert('案件ID / 子ID を選択してください'); return; }
    try {
      await manufacturingApi.createPlan(newData);
      setShowAdd(false); setNewData({ status: '未着手' }); load();
    } catch (e: any) { alert(e.response?.data?.detail || '登録に失敗しました'); }
  };
  const handleSave = async (id: string) => {
    await manufacturingApi.updatePlan(id, editData);
    setEditing(null); load();
  };
  const handleDelete = async (id: string) => {
    if (!confirm('削除しますか？')) return;
    await manufacturingApi.deletePlan(id); load();
  };

  // Gantt chart data
  const today = new Date().toISOString().slice(0, 10);
  const yearStart = `${fiscalYear}-03-01`;
  const yearEnd = `${fiscalYear + 1}-02-28`;
  const totalDays = (new Date(yearEnd).getTime() - new Date(yearStart).getTime()) / 86400000;
  const toPercent = (d: string) => Math.max(0, Math.min(100,
    (new Date(d).getTime() - new Date(yearStart).getTime()) / (totalDays * 86400000) * 100
  ));

  const chartData = MONTH_NAMES.map((name, i) => {
    const m = [3,4,5,6,7,8,9,10,11,12,1,2][i];
    const row = loadData.find(r => r.month === m);
    return { name, 計画工数: row?.planned_hours || 0, 使用可能: row?.available_hours || 0, overloaded: row?.overloaded };
  });
  const hasOverload = chartData.some(d => d.overloaded);

  return (
    <div>
      {/* 月別負荷グラフ */}
      <div className="bg-white rounded-xl border p-4 mb-5">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-sm font-semibold text-gray-700">月別製造負荷（{fiscalYear}年度）</h2>
          {hasOverload && (
            <span className="flex items-center gap-1 text-xs text-red-600 font-medium">
              <AlertTriangle size={13} />能力超過あり
            </span>
          )}
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} barGap={2}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(v: number) => `${v}h`} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: any, name: string) => [`${v}h`, name]} />
            <Bar dataKey="使用可能" fill="#d1d5db" radius={[3,3,0,0]} name="使用可能時間" />
            <Bar dataKey="計画工数" radius={[3,3,0,0]} name="計画工数">
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.overloaded ? '#ef4444' : '#22c55e'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="flex gap-4 mt-1 text-xs text-gray-500">
          <span><span className="inline-block w-3 h-3 bg-gray-300 rounded mr-1"></span>使用可能時間</span>
          <span><span className="inline-block w-3 h-3 bg-green-500 rounded mr-1"></span>計画工数（正常）</span>
          <span><span className="inline-block w-3 h-3 bg-red-500 rounded mr-1"></span>計画工数（超過）</span>
        </div>
      </div>

      {/* 製造計画一覧 + ガント */}
      <div className="flex items-center gap-2 mb-3">
        <button onClick={() => { setShowDraft(!showDraft); setShowAdd(false); }}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700">
          <FileText size={14} />見積からドラフト作成
        </button>
        <button onClick={() => { setShowAdd(true); setShowDraft(false); }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700">
          <Plus size={14} />計画追加
        </button>
      </div>

      {showDraft && (
        <div className="mb-4 p-3 border border-indigo-200 rounded-lg bg-indigo-50">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-semibold text-indigo-700">案件ID / 子ID を選ぶと、受注採用見積の本体（型式）から製造計画を仮日程付きで自動作成</span>
            <button onClick={() => { setShowDraft(false); setDraftMsg(''); }} className="text-gray-400"><X size={14} /></button>
          </div>
          <OrderSearchInput onSelect={handleDraft} placeholder="案件ID または 子ID で検索" />
          {draftMsg && <p className={`mt-1.5 text-xs ${draftMsg.startsWith('✓') ? 'text-green-700' : draftMsg.startsWith('⚠') ? 'text-amber-600' : 'text-red-500'}`}>{draftMsg}</p>}
        </div>
      )}

      {showAdd && (
        <div className="mb-4 p-3 border border-green-200 rounded-lg bg-green-50 flex flex-wrap gap-2 items-end">
          <div className="w-full pb-2 border-b border-green-200 mb-1">
            <label className="block text-xs text-gray-500 mb-0.5">案件ID または 子ID で検索して情報を自動入力</label>
            <OrderSearchInput onSelect={(o: any) => {
              setNewData((d: any) => ({
                ...d,
                project_order_id: o.id,
                planned_end: o.sales_date || d.planned_end,
              }));
            }} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">製品種別</label>
            <select value={newData.product_type || ''} onChange={e => setNewData({...newData, product_type: e.target.value})}
              className="border rounded px-2 py-1 text-sm">
              <option value="">-</option>
              {PRODUCT_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">型番</label>
            <input value={newData.model_no || ''} onChange={e => setNewData({...newData, model_no: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-24" placeholder="例: 675" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">開始予定</label>
            <input type="date" value={newData.planned_start || ''} onChange={e => setNewData({...newData, planned_start: e.target.value})}
              className="border rounded px-2 py-1 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">完了予定</label>
            <input type="date" value={newData.planned_end || ''} onChange={e => setNewData({...newData, planned_end: e.target.value})}
              className="border rounded px-2 py-1 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">担当者</label>
            <input value={newData.assigned_to || ''} onChange={e => setNewData({...newData, assigned_to: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-24" />
          </div>
          <button onClick={handleAdd} className="px-3 py-1.5 bg-green-600 text-white text-sm rounded"><Check size={14} /></button>
          <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 border text-sm rounded"><X size={14} /></button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="text-xs w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              {['案件ID','案件名','顧客','製品','型番','開始予定','完了予定','担当','ステータス','計画工数',''].map(h => (
                <th key={h} className="border border-gray-200 px-2 py-2 text-left font-medium text-gray-600 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {plans.length === 0 ? (
              <tr><td colSpan={11} className="text-center py-8 text-gray-400">製造計画なし</td></tr>
            ) : plans.map(p => editing === p.id ? (
              <tr key={p.id} className="bg-green-50">
                <td className="border border-gray-200 px-2 py-1 font-mono">{p.child_no}</td>
                <td className="border border-gray-200 px-2 py-1">{p.project_name}</td>
                <td className="border border-gray-200 px-2 py-1">{p.customer_name}</td>
                <td className="border border-gray-200 px-1 py-1">
                  <select value={editData.product_type || ''} onChange={e => setEditData({...editData, product_type: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs">
                    <option value="">-</option>
                    {PRODUCT_TYPES.map(t => <option key={t}>{t}</option>)}
                  </select>
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input value={editData.model_no || ''} onChange={e => setEditData({...editData, model_no: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs w-16" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input type="date" value={editData.planned_start || ''} onChange={e => setEditData({...editData, planned_start: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input type="date" value={editData.planned_end || ''} onChange={e => setEditData({...editData, planned_end: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <input value={editData.assigned_to || ''} onChange={e => setEditData({...editData, assigned_to: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs w-16" />
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <select value={editData.status || '未着手'} onChange={e => setEditData({...editData, status: e.target.value})}
                    className="border rounded px-1 py-0.5 text-xs">
                    {STATUS_OPTIONS.map(s => <option key={s}>{s}</option>)}
                  </select>
                </td>
                <td className="border border-gray-200 px-2 py-1 text-right">{p.total_hours ? `${p.total_hours}h` : '—'}</td>
                <td className="border border-gray-200 px-1 py-1">
                  <button onClick={() => handleSave(p.id)} className="p-1 text-green-600 rounded"><Check size={12} /></button>
                  <button onClick={() => setEditing(null)} className="p-1 text-gray-400 rounded"><X size={12} /></button>
                </td>
              </tr>
            ) : (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="border border-gray-200 px-2 py-1 font-mono whitespace-nowrap">{p.child_no}{p.breakdown_no ? <span className="text-indigo-600">-{p.breakdown_no}</span> : ''}</td>
                <td className="border border-gray-200 px-2 py-1 max-w-xs truncate">{p.project_name || '—'}</td>
                <td className="border border-gray-200 px-2 py-1 max-w-xs truncate">{p.customer_name || '—'}</td>
                <td className="border border-gray-200 px-2 py-1">{p.product_type || '—'}</td>
                <td className="border border-gray-200 px-2 py-1">
                  <span className="font-mono">{p.model_no || '—'}</span>
                  {p.unit_name && <div className="text-[10px] text-gray-400 truncate max-w-[160px]" title={p.unit_name}>{p.unit_name}</div>}
                </td>
                <td className="border border-gray-200 px-2 py-1 whitespace-nowrap">{p.planned_start || '—'}</td>
                <td className="border border-gray-200 px-2 py-1 whitespace-nowrap">{p.planned_end || '—'}</td>
                <td className="border border-gray-200 px-2 py-1">{p.assigned_to || '—'}</td>
                <td className="border border-gray-200 px-2 py-1">
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[p.status] || 'bg-gray-100'}`}>{p.status}</span>
                </td>
                <td className="border border-gray-200 px-2 py-1 whitespace-nowrap text-right">
                  <div className="font-semibold text-gray-800">{p.total_hours ? `${p.total_hours}h` : '—'}</div>
                  {p.monthly_hours && Object.keys(p.monthly_hours).length > 0 && (
                    <div className="text-[10px] text-gray-400 leading-tight">
                      {Object.entries(p.monthly_hours).map(([m, h]: any) => `${m}月 ${h}h`).join(' / ')}
                    </div>
                  )}
                </td>
                <td className="border border-gray-200 px-1 py-1">
                  <button onClick={() => { setEditing(p.id); setEditData({...p}); }} className="p-1 text-blue-500 rounded"><Edit2 size={12} /></button>
                  <button onClick={() => handleDelete(p.id)} className="p-1 text-red-400 rounded"><Trash2 size={12} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ========== 生産能力マスタタブ ==========
function CapacityTab({ fiscalYear }: { fiscalYear: number }) {
  const [caps, setCaps] = useState<any[]>([]);
  const MONTHS = [3,4,5,6,7,8,9,10,11,12,1,2];

  const load = () => manufacturingApi.listCapacity(fiscalYear).then(r => setCaps(r.data));
  useEffect(() => { load(); }, [fiscalYear]);

  const getRow = (m: number) => caps.find(c => c.month === m) || { month: m, work_days: 20, regular_workers: 8, temp_workers: 5, hours_per_day: 8, available_hours: 0, fiscal_year: fiscalYear };

  const handleChange = async (m: number, field: string, val: number) => {
    const row = getRow(m);
    await manufacturingApi.upsertCapacity({ factory: '小牧', fiscal_year: fiscalYear, month: m, ...row, [field]: val });
    load();
  };

  return (
    <div>
      <p className="text-xs text-gray-500 mb-3">工場: 小牧　{fiscalYear}年度　各月の出勤日数・人員を設定してください。</p>
      <table className="text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50">
            {['月','出勤日数','正社員(人工)','派遣(人工)','稼働時間/日','使用可能時間(h)'].map(h => (
              <th key={h} className="border border-gray-200 px-3 py-2 text-xs font-medium text-gray-600">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {MONTHS.map(m => {
            const row = getRow(m);
            return (
              <tr key={m} className="hover:bg-gray-50">
                <td className="border border-gray-200 px-3 py-1.5 font-medium text-center">{m}月</td>
                {(['work_days','regular_workers','temp_workers','hours_per_day'] as const).map(field => (
                  <td key={field} className="border border-gray-200 px-2 py-1 text-center">
                    <input type="number" defaultValue={(row as any)[field]}
                      onBlur={e => handleChange(m, field, Number(e.target.value))}
                      className="border rounded px-2 py-0.5 text-sm w-16 text-center" />
                  </td>
                ))}
                <td className="border border-gray-200 px-3 py-1.5 text-center font-medium text-green-700">
                  {row.available_hours}h
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ========== 製品所要工数マスタタブ ==========
function ProductHoursTab() {
  const [hours, setHours] = useState<any[]>([]);
  const [filterType, setFilterType] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [newData, setNewData] = useState<any>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [editData, setEditData] = useState<any>({});

  const load = () => manufacturingApi.listProductHours(filterType || undefined).then(r => setHours(r.data));
  useEffect(() => { load(); }, [filterType]);

  const handleAdd = async () => {
    await manufacturingApi.upsertProductHours(newData);
    setShowAdd(false); setNewData({}); load();
  };
  const handleSave = async (_id: string) => {
    await manufacturingApi.upsertProductHours(editData);
    setEditing(null); load();
  };
  const handleDelete = async (id: string) => {
    if (!confirm('削除しますか？')) return;
    await manufacturingApi.deleteProductHours(id); load();
  };

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <select value={filterType} onChange={e => setFilterType(e.target.value)}
          className="border rounded px-2 py-1 text-sm">
          <option value="">全製品種別</option>
          {PRODUCT_TYPES.map(t => <option key={t}>{t}</option>)}
        </select>
        <button onClick={() => setShowAdd(true)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700">
          <Plus size={14} />工数追加
        </button>
      </div>

      {showAdd && (
        <div className="mb-4 p-3 border border-green-200 rounded-lg bg-green-50 flex gap-2 items-end flex-wrap">
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
            <label className="block text-xs text-gray-500 mb-0.5">所要時間(h)</label>
            <input type="number" value={newData.required_hours || ''} onChange={e => setNewData({...newData, required_hours: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-24" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">備考</label>
            <input value={newData.notes || ''} onChange={e => setNewData({...newData, notes: e.target.value})}
              className="border rounded px-2 py-1 text-sm w-36" />
          </div>
          <button onClick={handleAdd} className="px-3 py-1.5 bg-green-600 text-white text-sm rounded"><Check size={14} /></button>
          <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 border text-sm rounded"><X size={14} /></button>
        </div>
      )}

      <table className="text-sm border-collapse w-full max-w-xl">
        <thead>
          <tr className="bg-gray-50">
            {['製品種別','型番','所要時間(h)','備考',''].map(h => (
              <th key={h} className="border border-gray-200 px-3 py-2 text-left text-xs font-medium text-gray-600">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {hours.map(h => editing === h.id ? (
            <tr key={h.id} className="bg-green-50">
              <td className="border border-gray-200 px-2 py-1">
                <select value={editData.product_type || ''} onChange={e => setEditData({...editData, product_type: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs">
                  {PRODUCT_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </td>
              <td className="border border-gray-200 px-2 py-1">
                <input value={editData.model_no || ''} onChange={e => setEditData({...editData, model_no: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-20" />
              </td>
              <td className="border border-gray-200 px-2 py-1">
                <input type="number" value={editData.required_hours || ''} onChange={e => setEditData({...editData, required_hours: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-20" />
              </td>
              <td className="border border-gray-200 px-2 py-1">
                <input value={editData.notes || ''} onChange={e => setEditData({...editData, notes: e.target.value})}
                  className="border rounded px-1 py-0.5 text-xs w-32" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <button onClick={() => handleSave(h.id)} className="p-1 text-green-600 rounded"><Check size={13} /></button>
                <button onClick={() => setEditing(null)} className="p-1 text-gray-400 rounded"><X size={13} /></button>
              </td>
            </tr>
          ) : (
            <tr key={h.id} className="hover:bg-gray-50">
              <td className="border border-gray-200 px-3 py-1.5"><span className="px-1.5 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs font-medium">{h.product_type}</span></td>
              <td className="border border-gray-200 px-3 py-1.5 font-mono">{h.model_no}</td>
              <td className="border border-gray-200 px-3 py-1.5 font-medium text-right">{h.required_hours}h</td>
              <td className="border border-gray-200 px-3 py-1.5 text-xs text-gray-500">{h.notes || ''}</td>
              <td className="border border-gray-200 px-1 py-1">
                <button onClick={() => { setEditing(h.id); setEditData({...h}); }} className="p-1 text-blue-500 rounded"><Edit2 size={13} /></button>
                <button onClick={() => handleDelete(h.id)} className="p-1 text-red-400 rounded"><Trash2 size={13} /></button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-gray-400">※ 生産能力指数.xlsxのデータを初期値として登録済み。</p>
    </div>
  );
}
