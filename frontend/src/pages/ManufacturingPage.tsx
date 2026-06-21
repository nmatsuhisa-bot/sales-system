import { useEffect, useState } from 'react';
import { manufacturingApi, projectApi } from '../api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Plus, Trash2, Edit2, Check, X, AlertTriangle } from 'lucide-react';
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
  const [tab, setTab] = useState<'plans' | 'capacity' | 'hours'>('plans');
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
        {([['plans', '製造計画'], ['capacity', '生産能力マスタ'], ['hours', '製品所要工数マスタ']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === key ? 'border-green-600 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'plans' && <PlansTab fiscalYear={fiscalYear} />}
      {tab === 'capacity' && <CapacityTab fiscalYear={fiscalYear} />}
      {tab === 'hours' && <ProductHoursTab />}
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

  const load = () => {
    manufacturingApi.listPlans(fiscalYear).then(r => setPlans(r.data)).catch(() => {});
    manufacturingApi.getMonthlyLoad(fiscalYear).then(r => setLoadData(r.data.monthly || [])).catch(() => {});
    projectApi.list({ status: '受注' }).catch(() => {});
  };
  useEffect(() => { load(); }, [fiscalYear]);

  const handleAdd = async () => {
    await manufacturingApi.createPlan(newData);
    setShowAdd(false); setNewData({ status: '未着手' }); load();
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
        <button onClick={() => setShowAdd(true)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700">
          <Plus size={14} />計画追加
        </button>
      </div>

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
              {['案件ID','案件名','顧客','製品','型番','開始予定','完了予定','担当','ステータス','ガント（年度）',''].map(h => (
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
                <td className="border border-gray-200 px-2 py-1"></td>
                <td className="border border-gray-200 px-1 py-1">
                  <button onClick={() => handleSave(p.id)} className="p-1 text-green-600 rounded"><Check size={12} /></button>
                  <button onClick={() => setEditing(null)} className="p-1 text-gray-400 rounded"><X size={12} /></button>
                </td>
              </tr>
            ) : (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="border border-gray-200 px-2 py-1 font-mono">{p.child_no}</td>
                <td className="border border-gray-200 px-2 py-1 max-w-xs truncate">{p.project_name || '—'}</td>
                <td className="border border-gray-200 px-2 py-1 max-w-xs truncate">{p.customer_name || '—'}</td>
                <td className="border border-gray-200 px-2 py-1">{p.product_type || '—'}</td>
                <td className="border border-gray-200 px-2 py-1 font-mono">{p.model_no || '—'}</td>
                <td className="border border-gray-200 px-2 py-1 whitespace-nowrap">{p.planned_start || '—'}</td>
                <td className="border border-gray-200 px-2 py-1 whitespace-nowrap">{p.planned_end || '—'}</td>
                <td className="border border-gray-200 px-2 py-1">{p.assigned_to || '—'}</td>
                <td className="border border-gray-200 px-2 py-1">
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[p.status] || 'bg-gray-100'}`}>{p.status}</span>
                </td>
                <td className="border border-gray-200 px-2 py-1" style={{ minWidth: '180px' }}>
                  {p.planned_start && p.planned_end && (
                    <div className="relative h-4 bg-gray-100 rounded">
                      <div className="absolute h-full rounded"
                        style={{
                          left: `${toPercent(p.planned_start)}%`,
                          width: `${Math.max(2, toPercent(p.planned_end) - toPercent(p.planned_start))}%`,
                          backgroundColor: p.status === '完了' ? '#22c55e' : p.status === '製造中' ? '#3b82f6' : '#94a3b8',
                        }} />
                      {/* today line */}
                      <div className="absolute top-0 h-full w-px bg-red-400"
                        style={{ left: `${toPercent(today)}%` }} />
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
