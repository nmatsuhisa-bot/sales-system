import { useEffect, useState } from 'react';
import { Printer } from 'lucide-react';
import api from '../api';

const STATUS_OPTIONS = ['営業中', '内示', '受注', '検収済', '請求済', '入金済', '失注'];
const STATUS_COLORS: Record<string, string> = {
  '営業中': 'bg-blue-100 text-blue-700',
  '内示': 'bg-orange-100 text-orange-700',
  '受注': 'bg-yellow-100 text-yellow-700',
  '検収済': 'bg-teal-100 text-teal-700',
  '請求済': 'bg-green-100 text-green-700',
  '入金済': 'bg-emerald-100 text-emerald-700',
  '失注': 'bg-gray-100 text-gray-500',
};
const STATUS_PRINT_COLORS: Record<string, string> = {
  '営業中': 'text-blue-700', '内示': 'text-orange-700', '受注': 'text-yellow-700',
  '検収済': 'text-teal-700', '請求済': 'text-green-700', '入金済': 'text-emerald-700', '失注': 'text-gray-500',
};
const STATUS_PRINT_HEX: Record<string, string> = {
  '営業中': '#1d4ed8', '内示': '#c2410c', '受注': '#a16207',
  '検収済': '#0f766e', '請求済': '#15803d', '入金済': '#047857', '失注': '#6b7280',
};

// 単番判定: 案件合計がこの金額未満なら単番（一覧には出さず集計行へ）
const TANBAN_MAX = 3000000;

interface Row {
  child_no: string; project_no: string; project_name: string;
  customer_name: string; agency_name: string; delivery_name: string;
  sales_person_name: string; status: string;
  sales_date: string; month: number; amount: number;
}

interface Proj {
  customer: string; child_no: string; project_name: string; status: string;
  delivery_name: string; sales_person: string; sales_date: string;
  months: Record<number, number>; total: number;
}

function currentFiscalYear(): number {
  const today = new Date();
  const m = today.getMonth() + 1;
  const d = today.getDate();
  return (m > 2 || (m === 2 && d > 20)) ? today.getFullYear() : today.getFullYear() - 1;
}

const MONTH_LIST = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2];
const LEFT_COLS = 6; // 顧客名/案件番号/案件名/納品先/営業担当/ステータス

export default function SalesPlanPage() {
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(currentFiscalYear());
  const [rows, setRows] = useState<Row[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>(['営業中', '内示', '受注', '検収済', '請求済', '入金済']);
  const [loading, setLoading] = useState(false);

  const currentMonth = new Date().getMonth() + 1;

  useEffect(() => {
    setLoading(true);
    api.get(`/reports/sales-plan?year=${year}`)
      .then(r => setRows(r.data.rows || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [year]);

  const filtered = rows.filter(r => selectedStatuses.includes(r.status));

  // 案件（子ID）単位に集計
  const projectMap: Record<string, Proj> = {};
  for (const r of filtered) {
    const key = r.child_no || r.project_no;
    if (!projectMap[key]) {
      projectMap[key] = {
        customer: r.customer_name || '（未設定）', child_no: r.child_no, project_name: r.project_name,
        status: r.status, delivery_name: r.delivery_name || '', sales_person: r.sales_person_name || '',
        sales_date: r.sales_date || '', months: {}, total: 0,
      };
    }
    projectMap[key].months[r.month] = (projectMap[key].months[r.month] || 0) + r.amount;
    projectMap[key].total += r.amount;
  }
  const projects = Object.values(projectMap);
  const kobanProjects = projects.filter(p => p.total >= TANBAN_MAX);
  const tanbanProjects = projects.filter(p => p.total < TANBAN_MAX);

  // 工番のみ一覧表示（売上計上日順。顧客小計は表示しない）
  const sortedKoban = [...kobanProjects].sort((a, b) =>
    (a.sales_date || '').localeCompare(b.sales_date || '') || (a.customer || '').localeCompare(b.customer || ''));

  // 単番（集計）
  const tanbanMonths: Record<number, number> = {};
  let tanbanTotal = 0;
  for (const p of tanbanProjects) {
    for (const m of Object.keys(p.months)) tanbanMonths[+m] = (tanbanMonths[+m] || 0) + p.months[+m];
    tanbanTotal += p.total;
  }

  // 月別合計（工番＋単番すべて）
  const monthTotals: Record<number, number> = {};
  for (const p of projects) for (const m of Object.keys(p.months)) monthTotals[+m] = (monthTotals[+m] || 0) + p.months[+m];
  const grandTotal = projects.reduce((s, p) => s + p.total, 0);

  function toggleStatus(s: string) {
    setSelectedStatuses(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  }

  const M = (v: number) => v ? (v / 1000000).toFixed(1) + 'M' : '';
  const thClass = "border border-gray-300 px-2 py-2 text-right";
  const tdClass = (m: number) => `border border-gray-300 px-2 py-1 text-right ${m === currentMonth ? 'bg-blue-50' : ''}`;

  function handlePrint() {
    const win = window.open('', '_blank', 'width=1400,height=900');
    if (!win) return;
    const C = {
      border: '#d1d5db', thBg: '#f3f4f6', custBg: '#eff6ff', custText: '#1e40af',
      custMonthText: '#1d4ed8', curMonthBg: '#dbeafe', curMonthHeaderBg: '#bfdbfe',
      totalBg: '#f3f4f6', grandTotalBg: '#e5e7eb', projTotalBg: '#f9fafb',
      tanbanBg: '#fef3c7', gray700: '#374151', gray400: '#9ca3af',
    };
    const cell = (content: string, style: string) =>
      `<td style="border:1px solid ${C.border};padding:3px 6px;white-space:nowrap;${style}">${content}</td>`;
    const th = (content: string, style: string) =>
      `<th style="border:1px solid ${C.border};padding:4px 6px;white-space:nowrap;background:${C.thBg};${style}">${content}</th>`;

    const headerRow = `<tr>
      ${th('顧客名', 'text-align:left;min-width:110px')}
      ${th('案件番号', 'text-align:left;min-width:70px')}
      ${th('案件名', 'text-align:left;min-width:130px')}
      ${th('納品先', 'text-align:left;min-width:100px')}
      ${th('営業担当', 'text-align:left;min-width:70px')}
      ${th('ステータス', 'text-align:left;min-width:56px')}
      ${MONTH_LIST.map(m => th(`${m}月`, `text-align:right;min-width:44px;${m === currentMonth ? `background:${C.curMonthHeaderBg}` : ''}`)).join('')}
      ${th('合計', `text-align:right;min-width:56px;background:${C.grandTotalBg}`)}
    </tr>`;

    const dataRows = sortedKoban.map(p => `<tr>
        ${cell(p.customer, `font-weight:600;color:${C.custText}`)}
        ${cell(p.child_no, `font-family:monospace;color:${C.gray700}`)}
        ${cell(p.project_name || '—', `color:${C.gray700};max-width:170px;overflow:hidden;text-overflow:ellipsis`)}
        ${cell(p.delivery_name || '—', `color:${C.gray700}`)}
        ${cell(p.sales_person || '—', `color:${C.gray700}`)}
        ${cell(`<span style="color:${STATUS_PRINT_HEX[p.status] || C.gray700};font-weight:600">${p.status}</span>`, '')}
        ${MONTH_LIST.map(m => cell(M(p.months[m] || 0), `text-align:right;color:${C.gray700};background:${m === currentMonth ? C.curMonthBg : '#fff'}`)).join('')}
        ${cell(M(p.total), `text-align:right;font-weight:500;background:${C.projTotalBg}`)}
      </tr>`).join('');

    const tanbanRow = tanbanProjects.length ? `<tr style="background:${C.tanbanBg};font-weight:700">
      <td colspan="6" style="border:1px solid ${C.border};padding:4px 6px">単番（集計） ${tanbanProjects.length}件</td>
      ${MONTH_LIST.map(m => cell(M(tanbanMonths[m] || 0), `text-align:right;background:${m === currentMonth ? C.curMonthBg : C.tanbanBg}`)).join('')}
      ${cell(M(tanbanTotal), `text-align:right;background:${C.curMonthBg}`)}
    </tr>` : '';

    const footerRow = `<tr style="background:${C.totalBg};font-weight:700">
      <td colspan="6" style="border:1px solid ${C.border};padding:4px 6px">合計</td>
      ${MONTH_LIST.map(m => cell(M(monthTotals[m] || 0), `text-align:right;background:${m === currentMonth ? C.curMonthBg : C.totalBg}`)).join('')}
      ${cell(M(grandTotal), `text-align:right;background:${C.grandTotalBg}`)}
    </tr>`;

    win.document.write(`<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><title>売上計画表 ${year}年度</title>
<style>
  @page { size: A3 landscape; margin: 10mm; }
  body { font-family: "Hiragino Sans","Yu Gothic",sans-serif; font-size: 9.5px; margin:0; padding:8px; }
  h2 { font-size:13px; margin:0 0 3px; } p { font-size:9px; color:#555; margin:0 0 8px; }
  table { border-collapse:collapse; width:100%; }
  * { -webkit-print-color-adjust:exact; print-color-adjust:exact; }
</style></head><body>
<h2>売上計画表　${year}年度（${year}/2/21〜${year + 1}/2/20）</h2>
<p>対象ステータス：${selectedStatuses.join('・')}　／　単番（合計${(TANBAN_MAX / 1000000)}M未満）は最下部に集計　／　出力日：${new Date().toLocaleDateString('ja-JP')}</p>
<table>${headerRow}<tbody>${dataRows}</tbody><tfoot>${tanbanRow}${footerRow}</tfoot></table>
</body></html>`);
    win.document.close();
    win.onload = () => { win.print(); win.onafterprint = () => win.close(); };
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">売上計画表</h1>
        <div className="flex gap-2 items-center">
          <select value={year} onChange={e => setYear(Number(e.target.value))} className="border rounded px-2 py-1 text-sm">
            {[thisYear - 2, thisYear - 1, thisYear, thisYear + 1].map(y => (
              <option key={y} value={y}>{y}年度（{y}/2/21〜{y + 1}/2/20）</option>
            ))}
          </select>
          <button onClick={handlePrint} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 text-white text-sm rounded hover:bg-gray-800">
            <Printer size={14} />PDF出力
          </button>
        </div>
      </div>

      <div className="no-print flex gap-2 mb-4 flex-wrap">
        {STATUS_OPTIONS.map(s => (
          <label key={s} className="flex items-center gap-1 cursor-pointer text-sm">
            <input type="checkbox" checked={selectedStatuses.includes(s)} onChange={() => toggleStatus(s)} />
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[s] || 'bg-gray-100'}`}>{s}</span>
          </label>
        ))}
      </div>

      {loading ? (
        <div className="no-print text-center py-12 text-gray-400">読み込み中...</div>
      ) : (
        <div className="overflow-x-auto">
          <table id="sales-plan-table" className="border-collapse text-xs w-full">
            <thead>
              <tr className="bg-gray-100">
                <th className="border border-gray-300 px-2 py-2 text-left sticky left-0 bg-gray-100 z-10" style={{ minWidth: '110px' }}>顧客名</th>
                <th className="border border-gray-300 px-2 py-2 text-left" style={{ minWidth: '78px' }}>案件番号</th>
                <th className="border border-gray-300 px-2 py-2 text-left" style={{ minWidth: '150px' }}>案件名</th>
                <th className="border border-gray-300 px-2 py-2 text-left" style={{ minWidth: '110px' }}>納品先</th>
                <th className="border border-gray-300 px-2 py-2 text-left" style={{ minWidth: '70px' }}>営業担当</th>
                <th className="border border-gray-300 px-2 py-2 text-left" style={{ minWidth: '64px' }}>ステータス</th>
                {MONTH_LIST.map(m => (
                  <th key={m} className={`${thClass} ${m === currentMonth ? 'bg-blue-50' : ''}`} style={{ minWidth: '48px' }}>{m}月</th>
                ))}
                <th className="border border-gray-300 px-2 py-2 text-right bg-gray-200" style={{ minWidth: '60px' }}>合計</th>
              </tr>
            </thead>
            <tbody>
              {sortedKoban.map(p => (
                <tr key={`proj-${p.child_no}`} className="hover:bg-gray-50">
                  <td className="border border-gray-300 px-2 py-1 sticky left-0 bg-white z-10 text-blue-800 font-medium">{p.customer}</td>
                  <td className="border border-gray-300 px-2 py-1 font-mono text-gray-700">{p.child_no}</td>
                  <td className="border border-gray-300 px-2 py-1 text-gray-700" title={p.project_name}>{p.project_name || '—'}</td>
                  <td className="border border-gray-300 px-2 py-1 text-gray-700">{p.delivery_name || '—'}</td>
                  <td className="border border-gray-300 px-2 py-1 text-gray-700">{p.sales_person || '—'}</td>
                  <td className="border border-gray-300 px-2 py-1">
                    <span className={`text-xs font-medium ${STATUS_PRINT_COLORS[p.status] || 'text-gray-600'}`}>{p.status}</span>
                  </td>
                  {MONTH_LIST.map(m => <td key={m} className={tdClass(m)}>{M(p.months[m] || 0)}</td>)}
                  <td className="border border-gray-300 px-2 py-1 text-right font-medium bg-gray-50">{M(p.total)}</td>
                </tr>
              ))}
              {sortedKoban.length === 0 && (
                <tr><td colSpan={LEFT_COLS + MONTH_LIST.length + 1} className="text-center py-8 text-gray-400">該当案件なし</td></tr>
              )}
            </tbody>
            <tfoot>
              {tanbanProjects.length > 0 && (
                <tr className="bg-amber-50 font-semibold">
                  <td className="border border-gray-300 px-2 py-2 sticky left-0 bg-amber-50 z-10 text-amber-800" colSpan={LEFT_COLS}>
                    単番（集計） {tanbanProjects.length}件 <span className="text-[10px] text-amber-600 font-normal">合計{(TANBAN_MAX / 1000000)}M未満</span>
                  </td>
                  {MONTH_LIST.map(m => (
                    <td key={m} className={`border border-gray-300 px-2 py-2 text-right text-amber-800 ${m === currentMonth ? 'bg-blue-100' : ''}`}>{M(tanbanMonths[m] || 0)}</td>
                  ))}
                  <td className="border border-gray-300 px-2 py-2 text-right bg-blue-100 text-amber-800">{M(tanbanTotal)}</td>
                </tr>
              )}
              <tr className="bg-gray-100 font-bold">
                <td className="border border-gray-300 px-2 py-2 sticky left-0 bg-gray-100 z-10" colSpan={LEFT_COLS}>合計</td>
                {MONTH_LIST.map(m => (
                  <td key={m} className={`border border-gray-300 px-2 py-2 text-right ${m === currentMonth ? 'bg-blue-100' : ''}`}>{M(monthTotals[m] || 0)}</td>
                ))}
                <td className="border border-gray-300 px-2 py-2 text-right bg-gray-200">{M(grandTotal)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      <div className="mt-4 text-xs text-gray-400">
        ※ 売上計上日（顧客納期）が設定されている案件のみ表示。金額は百万円単位（M）。年度は{year}/2/21〜{year + 1}/2/20。
        単番（案件合計が{(TANBAN_MAX / 1000000)}M未満）は一覧に出さず最下部に集計表示。
      </div>
    </div>
  );
}
