import { useEffect, useState } from 'react';
import { Printer } from 'lucide-react';
import api from '../api';

const STATUS_OPTIONS = ['営業中','見積発行','受注','失注','請求済'];
const STATUS_COLORS: Record<string,string> = {
  '営業中': 'bg-blue-100 text-blue-700',
  '見積発行': 'bg-yellow-100 text-yellow-700',
  '受注': 'bg-green-100 text-green-700',
  '失注': 'bg-red-100 text-red-700',
  '請求済': 'bg-gray-100 text-gray-700',
};
// print時は背景色なしで代替テキスト色
const STATUS_PRINT_COLORS: Record<string,string> = {
  '営業中': 'text-blue-700',
  '見積発行': 'text-yellow-700',
  '受注': 'text-green-700',
  '失注': 'text-red-700',
  '請求済': 'text-gray-600',
};

interface Row {
  child_no: string; project_no: string; project_name: string;
  customer_name: string; agency_name: string; status: string;
  sales_date: string; month: number; amount: number;
}

function currentFiscalYear(): number {
  const today = new Date();
  const m = today.getMonth() + 1;
  const d = today.getDate();
  return (m > 2 || (m === 2 && d > 20)) ? today.getFullYear() : today.getFullYear() - 1;
}

const MONTH_LIST = [3,4,5,6,7,8,9,10,11,12,1,2];

export default function SalesPlanPage() {
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(currentFiscalYear());
  const [rows, setRows] = useState<Row[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>(['営業中','見積発行','受注','請求済']);
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

  const customerMap: Record<string, { months: Record<number,number>; total: number }> = {};
  for (const r of filtered) {
    const key = r.customer_name || '（顧客未設定）';
    if (!customerMap[key]) customerMap[key] = { months: {}, total: 0 };
    customerMap[key].months[r.month] = (customerMap[key].months[r.month] || 0) + r.amount;
    customerMap[key].total += r.amount;
  }

  const projectMap: Record<string, {
    customer: string; child_no: string; project_name: string; status: string;
    months: Record<number,number>; total: number;
  }> = {};
  for (const r of filtered) {
    const key = r.child_no || r.project_no;
    if (!projectMap[key]) {
      projectMap[key] = {
        customer: r.customer_name || '（未設定）',
        child_no: r.child_no,
        project_name: r.project_name,
        status: r.status,
        months: {},
        total: 0,
      };
    }
    projectMap[key].months[r.month] = (projectMap[key].months[r.month] || 0) + r.amount;
    projectMap[key].total += r.amount;
  }

  const monthTotals: Record<number,number> = {};
  for (const r of filtered) {
    monthTotals[r.month] = (monthTotals[r.month] || 0) + r.amount;
  }
  const grandTotal = filtered.reduce((s, r) => s + r.amount, 0);

  function toggleStatus(s: string) {
    setSelectedStatuses(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  }

  const M = (v: number) => v ? (v / 1000000).toFixed(1) + 'M' : '';

  const customerEntries = Object.entries(customerMap).sort((a, b) => b[1].total - a[1].total);

  const projectsByCustomer: Record<string, typeof projectMap[string][]> = {};
  for (const [, p] of Object.entries(projectMap)) {
    const c = p.customer;
    if (!projectsByCustomer[c]) projectsByCustomer[c] = [];
    projectsByCustomer[c].push(p);
  }
  for (const arr of Object.values(projectsByCustomer)) {
    arr.sort((a, b) => b.total - a.total);
  }

  const thClass = "border border-gray-300 px-2 py-2 text-right";
  const tdClass = (m: number) => `border border-gray-300 px-2 py-1 text-right ${m === currentMonth ? 'bg-blue-50' : ''}`;

  function handlePrint() {
    const win = window.open('', '_blank', 'width=1400,height=900');
    if (!win) return;

    // 色定数
    const C = {
      border: '#d1d5db',
      thBg: '#f3f4f6',
      custBg: '#eff6ff',
      custText: '#1e40af',
      custMonthText: '#1d4ed8',
      curMonthBg: '#dbeafe',
      curMonthHeaderBg: '#bfdbfe',
      totalBg: '#f3f4f6',
      grandTotalBg: '#e5e7eb',
      projTotalBg: '#f9fafb',
      gray700: '#374151',
      gray400: '#9ca3af',
    };
    const statusColor: Record<string,string> = {
      '営業中': '#1d4ed8', '見積発行': '#a16207',
      '受注': '#15803d', '失注': '#b91c1c', '請求済': '#4b5563',
    };

    const cell = (content: string, style: string) =>
      `<td style="border:1px solid ${C.border};padding:3px 6px;white-space:nowrap;${style}">${content}</td>`;
    const th = (content: string, style: string) =>
      `<th style="border:1px solid ${C.border};padding:4px 6px;white-space:nowrap;background:${C.thBg};${style}">${content}</th>`;

    // ヘッダー行
    const headerRow = `<tr>
      ${th('顧客名', 'text-align:left;min-width:120px')}
      ${th('案件番号', 'text-align:left;min-width:75px')}
      ${th('案件名', 'text-align:left;min-width:150px')}
      ${th('ステータス', 'text-align:left;min-width:60px')}
      ${MONTH_LIST.map(m => th(`${m}月`, `text-align:right;min-width:48px;${m === currentMonth ? `background:${C.curMonthHeaderBg}` : ''}`)).join('')}
      ${th('合計', `text-align:right;min-width:60px;background:${C.grandTotalBg}`)}
    </tr>`;

    // データ行
    const dataRows = customerEntries.map(([customer, cg]) => {
      const projects = projectsByCustomer[customer] || [];
      const custRow = `<tr>
        ${cell(customer, `background:${C.custBg};font-weight:700;color:${C.custText}`)}
        <td colspan="3" style="border:1px solid ${C.border};background:${C.custBg}"></td>
        ${MONTH_LIST.map(m => cell(
          M(cg.months[m] || 0),
          `text-align:right;font-weight:600;color:${C.custMonthText};background:${m === currentMonth ? C.curMonthBg : C.custBg}`
        )).join('')}
        ${cell(M(cg.total), `text-align:right;font-weight:700;color:${C.custText};background:${C.curMonthBg}`)}
      </tr>`;

      const projRows = projects.map(p => `<tr>
        ${cell('└', `color:${C.gray400};padding-left:12px`)}
        ${cell(p.child_no, `font-family:monospace;color:${C.gray700}`)}
        ${cell(p.project_name || '—', `color:${C.gray700};max-width:180px;overflow:hidden;text-overflow:ellipsis`)}
        ${cell(`<span style="color:${statusColor[p.status] || C.gray700};font-weight:600">${p.status}</span>`, '')}
        ${MONTH_LIST.map(m => cell(
          M(p.months[m] || 0),
          `text-align:right;color:${C.gray700};background:${m === currentMonth ? C.curMonthBg : '#fff'}`
        )).join('')}
        ${cell(M(p.total), `text-align:right;font-weight:500;background:${C.projTotalBg}`)}
      </tr>`).join('');

      return custRow + projRows;
    }).join('');

    // 合計行
    const footerRow = `<tr style="background:${C.totalBg};font-weight:700">
      <td colspan="4" style="border:1px solid ${C.border};padding:4px 6px">合計</td>
      ${MONTH_LIST.map(m => cell(
        M(monthTotals[m] || 0),
        `text-align:right;background:${m === currentMonth ? C.curMonthBg : C.totalBg}`
      )).join('')}
      ${cell(M(grandTotal), `text-align:right;background:${C.grandTotalBg}`)}
    </tr>`;

    win.document.write(`<!DOCTYPE html>
<html lang="ja"><head>
<meta charset="UTF-8">
<title>売上計画表 ${year}年度</title>
<style>
  @page { size: A3 landscape; margin: 10mm; }
  body { font-family: "Hiragino Sans","Yu Gothic",sans-serif; font-size: 10px; margin:0; padding:8px; }
  h2 { font-size:13px; margin:0 0 3px; }
  p { font-size:9px; color:#555; margin:0 0 8px; }
  table { border-collapse:collapse; width:100%; }
  * { -webkit-print-color-adjust:exact; print-color-adjust:exact; }
</style>
</head><body>
<h2>売上計画表　${year}年度（${year}/2/21〜${year+1}/2/20）</h2>
<p>対象ステータス：${selectedStatuses.join('・')}　　出力日：${new Date().toLocaleDateString('ja-JP')}</p>
<table>${headerRow}<tbody>${dataRows}</tbody><tfoot>${footerRow}</tfoot></table>
</body></html>`);
    win.document.close();
    win.onload = () => { win.print(); win.onafterprint = () => win.close(); };
  }

  return (
    <div className="p-4">
      {/* 通常表示のヘッダー */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h1 className="text-xl font-bold text-gray-800">売上計画表</h1>
          <div className="flex gap-2 items-center">
            <select value={year} onChange={e => setYear(Number(e.target.value))}
              className="border rounded px-2 py-1 text-sm">
              {[thisYear-2, thisYear-1, thisYear, thisYear+1].map(y => (
                <option key={y} value={y}>{y}年度（{y}/2/21〜{y+1}/2/20）</option>
              ))}
            </select>
            <button
              onClick={handlePrint}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 text-white text-sm rounded hover:bg-gray-800"
            >
              <Printer size={14} />
              PDF出力
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
                  <th className="border border-gray-300 px-2 py-2 text-left sticky left-0 bg-gray-100 z-10" style={{minWidth:'120px'}}>顧客名</th>
                  <th className="border border-gray-300 px-2 py-2 text-left" style={{minWidth:'80px'}}>案件番号</th>
                  <th className="border border-gray-300 px-2 py-2 text-left" style={{minWidth:'160px'}}>案件名</th>
                  <th className="border border-gray-300 px-2 py-2 text-left" style={{minWidth:'70px'}}>ステータス</th>
                  {MONTH_LIST.map(m => (
                    <th key={m} className={`${thClass} ${m === currentMonth ? 'bg-blue-50' : ''}`} style={{minWidth:'52px'}}>{m}月</th>
                  ))}
                  <th className="border border-gray-300 px-2 py-2 text-right bg-gray-200" style={{minWidth:'65px'}}>合計</th>
                </tr>
              </thead>
              <tbody>
                {customerEntries.map(([customer, cg]) => {
                  const projects = projectsByCustomer[customer] || [];
                  return [
                    <tr key={`cust-${customer}`} className="bg-blue-50 font-semibold">
                      <td className="border border-gray-300 px-2 py-1.5 sticky left-0 bg-blue-50 z-10 text-blue-800">
                        {customer}
                      </td>
                      <td className="border border-gray-300 px-2 py-1.5" colSpan={3}></td>
                      {MONTH_LIST.map(m => (
                        <td key={m} className={`border border-gray-300 px-2 py-1.5 text-right text-blue-700 ${m === currentMonth ? 'bg-blue-100' : ''}`}>
                          {M(cg.months[m] || 0)}
                        </td>
                      ))}
                      <td className="border border-gray-300 px-2 py-1.5 text-right bg-blue-100 text-blue-800">
                        {M(cg.total)}
                      </td>
                    </tr>,
                    ...projects.map(p => (
                      <tr key={`proj-${p.child_no}`} className="hover:bg-gray-50">
                        <td className="border border-gray-300 px-2 py-1 sticky left-0 bg-white z-10 text-gray-300 pl-4">└</td>
                        <td className="border border-gray-300 px-2 py-1 font-mono text-gray-700">{p.child_no}</td>
                        <td className="border border-gray-300 px-2 py-1 text-gray-700" title={p.project_name}>
                          {p.project_name || '—'}
                        </td>
                        <td className="border border-gray-300 px-2 py-1">
                          <span className={`text-xs font-medium ${STATUS_PRINT_COLORS[p.status] || 'text-gray-600'}`}>{p.status}</span>
                        </td>
                        {MONTH_LIST.map(m => (
                          <td key={m} className={tdClass(m)}>
                            {M(p.months[m] || 0)}
                          </td>
                        ))}
                        <td className="border border-gray-300 px-2 py-1 text-right font-medium bg-gray-50">
                          {M(p.total)}
                        </td>
                      </tr>
                    )),
                  ];
                })}
              </tbody>
              <tfoot>
                <tr className="bg-gray-100 font-bold">
                  <td className="border border-gray-300 px-2 py-2 sticky left-0 bg-gray-100 z-10" colSpan={4}>合計</td>
                  {MONTH_LIST.map(m => (
                    <td key={m} className={`border border-gray-300 px-2 py-2 text-right ${m === currentMonth ? 'bg-blue-100' : ''}`}>
                      {M(monthTotals[m] || 0)}
                    </td>
                  ))}
                  <td className="border border-gray-300 px-2 py-2 text-right bg-gray-200">
                    {M(grandTotal)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}

        <div className="mt-4 text-xs text-gray-400">
          ※ 売上計上日（顧客納期）が設定されている案件のみ表示。金額は百万円単位（M）。年度は{year}/2/21〜{year+1}/2/20。
        </div>
      </div>
  );
}
