import { useEffect, useState } from 'react';
import { processApi } from '../api';
import { Plus, Trash2, Edit2, Check, X, Printer, ChevronDown, ChevronUp, Eye } from 'lucide-react';
import OrderSearchInput from '../components/common/OrderSearchInput';

const PRODUCT_TYPES = ['BFR', 'BFP', 'SCA', 'LCA', 'SRR', 'FLT', 'CY', 'LRG'];
const ROW_TYPES = ['task', 'equipment', 'note', 'blank'];
const ROW_TYPE_LABELS: Record<string, string> = { task: '作業', equipment: '機材', note: '備考', blank: '空白' };
const STATUS_OPTIONS = ['作成中', '確定', '発行済'];
const COLORS = ['#3b82f6','#0ea5e9','#8b5cf6','#f59e0b','#f97316','#10b981','#ef4444','#6b7280','#ec4899'];

// suppress unused warning
void COLORS;

function currentYear() { return new Date().getFullYear(); }
function currentMonth() { return new Date().getMonth() + 1; }

// 月の日数
function daysInMonth(year: number, month: number) {
  return new Date(year, month, 0).getDate();
}

// 曜日取得
function dayOfWeek(year: number, month: number, day: number) {
  return new Date(year, month - 1, day).getDay(); // 0=Sun
}

// ===== 日付ユーティリティ（絶対日付ガント用） =====
const DOW_JP = ['日', '月', '火', '水', '木', '金', '土'];
const pad2 = (n: number) => String(n).padStart(2, '0');
const toISO = (d: Date) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const fromISO = (s: string) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, (m || 1) - 1, d || 1); };
const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

type GCol = { start: Date; end: Date; label: string; sub: string; w: number; bg: string; color: string };
function buildCols(unit: 'day' | 'week' | 'month', start: Date, end: Date): GCol[] {
  const cols: GCol[] = [];
  if (unit === 'month') {
    let c = new Date(start.getFullYear(), start.getMonth(), 1);
    while (c <= end) {
      const last = new Date(c.getFullYear(), c.getMonth() + 1, 0);
      cols.push({ start: new Date(c), end: last, label: `${c.getFullYear()}/${c.getMonth() + 1}`, sub: '', w: 64, bg: '#f3f4f6', color: '#374151' });
      c = new Date(c.getFullYear(), c.getMonth() + 1, 1);
    }
  } else if (unit === 'week') {
    let c = addDays(start, -((start.getDay() + 6) % 7)); // 月曜始まり
    while (c <= end) {
      const we = addDays(c, 6);
      cols.push({ start: new Date(c), end: we, label: `${c.getMonth() + 1}/${c.getDate()}`, sub: '週', w: 44, bg: '#f3f4f6', color: '#374151' });
      c = addDays(c, 7);
    }
  } else {
    let c = new Date(start);
    while (c <= end) {
      const wd = c.getDay();
      cols.push({ start: new Date(c), end: new Date(c), label: `${c.getDate()}`, sub: DOW_JP[wd], w: 22,
        bg: wd === 0 ? '#fecaca' : wd === 6 ? '#bfdbfe' : '#f9fafb', color: wd === 0 ? '#dc2626' : wd === 6 ? '#1d4ed8' : '#666' });
      c = addDays(c, 1);
    }
  }
  return cols;
}

export default function ProcessPage() {
  const [tab, setTab] = useState<'schedules' | 'templates'>('schedules');
  return (
    <div className="p-4">
      <h1 className="text-xl font-bold text-gray-800 mb-4">工程管理</h1>
      <div className="flex gap-1 mb-5 border-b border-gray-200">
        {([['schedules', '工程表管理'], ['templates', 'テンプレート管理']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === key ? 'border-purple-600 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'schedules' && <SchedulesTab />}
      {tab === 'templates' && <TemplatesTab />}
    </div>
  );
}

// ========== 工程表一覧タブ ==========
function SchedulesTab() {
  const [schedules, setSchedules] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [yearFilter, setYearFilter] = useState(currentYear());
  const [monthFilter, setMonthFilter] = useState<number | ''>('');
  const [editModal, setEditModal] = useState<any>(null); // null | { isNew, schedule }
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    Promise.all([
      processApi.listSchedules(yearFilter, monthFilter || undefined),
      processApi.listTemplates(),
    ]).then(([s, t]) => { setSchedules(s.data); setTemplates(t.data); })
      .catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [yearFilter, monthFilter]);

  const handleDelete = async (id: string) => {
    if (!confirm('削除しますか？')) return;
    await processApi.deleteSchedule(id); load();
  };

  const handlePrint = (id: string, unit: string) => {
    window.open(processApi.pdfUrl(id, unit), '_blank');
  };

  const openNew = () => {
    const today = new Date();
    setEditModal({
      isNew: true,
      schedule: {
        work_year: today.getFullYear(),
        work_month: today.getMonth() + 1,
        created_date: today.toISOString().slice(0, 10),
        status: '作成中',
        items: [],
      }
    });
  };

  const openEdit = async (id: string) => {
    const r = await processApi.getSchedule(id);
    setEditModal({ isNew: false, schedule: r.data });
  };

  const thisYear = new Date().getFullYear();

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <select value={yearFilter} onChange={e => setYearFilter(Number(e.target.value))}
          className="border rounded px-2 py-1 text-sm">
          {[thisYear-1, thisYear, thisYear+1].map(y => <option key={y} value={y}>{y}年</option>)}
        </select>
        <select value={monthFilter} onChange={e => setMonthFilter(e.target.value ? Number(e.target.value) : '')}
          className="border rounded px-2 py-1 text-sm">
          <option value="">全月</option>
          {Array.from({length:12}, (_,i) => i+1).map(m => <option key={m} value={m}>{m}月</option>)}
        </select>
        <button onClick={openNew}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700">
          <Plus size={14} />工程表作成
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="text-sm w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              {['工程月','工番','工事名','納入先','担当者','ステータス','操作'].map(h => (
                <th key={h} className="border border-gray-200 px-3 py-2 text-left text-xs font-medium text-gray-600">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center py-8 text-gray-400">読み込み中...</td></tr>
            ) : schedules.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-8 text-gray-400">工程表なし</td></tr>
            ) : schedules.map(s => (
              <tr key={s.id} className="hover:bg-gray-50">
                <td className="border border-gray-200 px-3 py-2 font-medium">{s.work_year}年{s.work_month}月</td>
                <td className="border border-gray-200 px-3 py-2 font-mono text-xs">{s.work_no || '—'}</td>
                <td className="border border-gray-200 px-3 py-2 max-w-xs truncate">{s.work_name || '—'}</td>
                <td className="border border-gray-200 px-3 py-2">{s.customer_name || '—'}</td>
                <td className="border border-gray-200 px-3 py-2">{s.responsible_person || '—'}</td>
                <td className="border border-gray-200 px-3 py-2">
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                    s.status === '発行済' ? 'bg-green-100 text-green-700' :
                    s.status === '確定' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
                  }`}>{s.status}</span>
                </td>
                <td className="border border-gray-200 px-2 py-2">
                  <div className="flex gap-1 items-center">
                    <button onClick={() => setPreviewId(s.id)} className="p-1 text-teal-500 hover:bg-teal-50 rounded" title="簡易表示"><Eye size={14} /></button>
                    <button onClick={() => openEdit(s.id)} className="p-1 text-blue-500 hover:bg-blue-50 rounded" title="編集"><Edit2 size={13} /></button>
                    <span className="flex items-center gap-0.5 border border-purple-200 rounded px-1 py-0.5" title="印刷（単位を選択）">
                      <Printer size={12} className="text-purple-500" />
                      {([['day','日'],['week','週'],['month','月']] as const).map(([u, lbl]) => (
                        <button key={u} onClick={() => handlePrint(s.id, u)}
                          className="text-[11px] px-1 rounded text-purple-600 hover:bg-purple-100">{lbl}</button>
                      ))}
                    </span>
                    <button onClick={() => handleDelete(s.id)} className="p-1 text-red-400 hover:bg-red-50 rounded" title="削除"><Trash2 size={13} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editModal && (
        <ScheduleEditModal
          schedule={editModal.schedule}
          isNew={editModal.isNew}
          templates={templates}
          onClose={() => setEditModal(null)}
          onSaved={() => { setEditModal(null); load(); }}
        />
      )}
      {previewId && <SchedulePreviewModal id={previewId} onClose={() => setPreviewId(null)} />}
    </div>
  );
}

// ========== 工程表 簡易プレビュー（読み取り専用ガント） ==========
function SchedulePreviewModal({ id, onClose }: { id: string; onClose: () => void }) {
  const [s, setS] = useState<any>(null);
  const [unit, setUnit] = useState<'day' | 'week' | 'month'>('day');
  useEffect(() => { processApi.getSchedule(id).then(r => setS(r.data)).catch(() => {}); }, [id]);

  if (!s) {
    return <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"><div className="bg-white rounded-xl p-8 text-gray-400">読み込み中...</div></div>;
  }

  const wy = Number(s.work_year), wm = Number(s.work_month);
  const items = (s.items || []).map((it: any) => {
    const n = { ...it };
    if (!n.start_date && n.start_day && wy && wm) n.start_date = toISO(new Date(wy, wm - 1, n.start_day));
    if (!n.end_date && n.end_day && wy && wm) n.end_date = toISO(new Date(wy, wm - 1, n.end_day));
    return n;
  });
  const dates: Date[] = items.flatMap((it: any) => [it.start_date, it.end_date]).filter(Boolean).map(fromISO);
  let rs: Date, re: Date;
  if (dates.length) { rs = new Date(Math.min(...dates.map(d => +d))); re = new Date(Math.max(...dates.map(d => +d))); }
  else if (s.delivery_date) { const d = fromISO(s.delivery_date); rs = new Date(d.getFullYear(), d.getMonth(), 1); re = new Date(d.getFullYear(), d.getMonth() + 1, 0); }
  else { rs = new Date(wy || currentYear(), (wm || 1) - 1, 1); re = new Date(wy || currentYear(), (wm || 1) - 1, daysInMonth(wy || currentYear(), wm || 1)); }
  rs = addDays(rs, -2); re = addDays(re, 2);
  const cols = buildCols(unit, rs, re);
  const monthBand: { label: string; span: number }[] = [];
  cols.forEach(c => {
    const key = `${c.start.getFullYear()}/${c.start.getMonth() + 1}`;
    const last = monthBand[monthBand.length - 1];
    if (last && last.label === key) last.span += 1; else monthBand.push({ label: key, span: 1 });
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-6xl max-h-[92vh] flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-800">{s.work_name || '工程表'}</h2>
            <p className="text-xs text-gray-500">工番 {s.work_no || '—'} ／ 納入先 {s.customer_name || '—'} ／ 納期 {s.delivery_date || '—'}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-gray-200 overflow-hidden">
              {([['day', '日'], ['week', '週'], ['month', '月']] as const).map(([u, lbl]) => (
                <button key={u} onClick={() => setUnit(u)}
                  className={`px-2.5 py-1 text-xs ${unit === u ? 'bg-purple-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}>{lbl}</button>
              ))}
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={20} /></button>
          </div>
        </div>
        <div className="overflow-auto flex-1 p-4">
          <table className="text-xs border-collapse">
            <thead>
              <tr className="bg-gray-200">
                <th className="border border-gray-300 px-2" colSpan={2}></th>
                {monthBand.map((b, i) => <th key={i} colSpan={b.span} className="border border-gray-300 text-center" style={{ fontSize: '9px', padding: '1px 0' }}>{b.label}</th>)}
              </tr>
              <tr className="bg-gray-100">
                <th className="border border-gray-300 px-2 py-1 w-40 text-left">工程名</th>
                <th className="border border-gray-300 px-2 py-1 w-16 text-left">機材</th>
                {cols.map((c, i) => (
                  <th key={i} style={{ background: c.bg, width: `${c.w}px` }} className="border border-gray-300 text-center">
                    <div style={{ fontSize: '9px' }}>{c.label}</div>
                    <div style={{ fontSize: '8px', color: c.color }}>{c.sub}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.filter((it: any) => it.row_type !== 'blank').map((it: any, i: number) => {
                const sd = it.start_date ? fromISO(it.start_date) : null;
                const ed = it.end_date ? fromISO(it.end_date) : sd;
                return (
                  <tr key={i} className="h-7">
                    <td className="border border-gray-300 px-2 whitespace-nowrap">{it.step_name}</td>
                    <td className="border border-gray-300 px-2 text-gray-500 whitespace-nowrap">{it.equipment || ''}</td>
                    {cols.map((c, ci) => {
                      const inRange = !!sd && !!ed && sd <= c.end && ed >= c.start;
                      return <td key={ci} style={{ background: inRange ? (it.color || '#3b82f6') : 'white', border: '1px solid #d1d5db' }} />;
                    })}
                  </tr>
                );
              })}
              {items.length === 0 && <tr><td colSpan={2 + cols.length} className="text-center py-6 text-gray-400">工程行がありません</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ========== 工程表編集モーダル ==========
function ScheduleEditModal({ schedule: initSchedule, isNew, templates, onClose, onSaved }: any) {
  // 旧データ（start_day）を絶対日付に正規化して読み込み
  const normItems = (initSchedule.items || []).map((it: any) => {
    const wy = Number(initSchedule.work_year), wm = Number(initSchedule.work_month);
    const n = { ...it };
    if (!n.start_date && n.start_day && wy && wm) n.start_date = toISO(new Date(wy, wm - 1, n.start_day));
    if (!n.end_date && n.end_day && wy && wm) n.end_date = toISO(new Date(wy, wm - 1, n.end_day));
    return n;
  });
  const [form, setForm] = useState<any>({ ...initSchedule });
  const [items, setItems] = useState<any[]>(normItems);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [saving, setSaving] = useState(false);
  const [viewUnit, setViewUnit] = useState<'day' | 'week' | 'month'>('day');
  const handleOrderSelect = (o: any) => {
    // 納期は案件子IDの顧客納期を優先（無ければ売上計上日を補完）
    const deliveryDate = o.customer_delivery_date || o.sales_date || '';
    const salesYear = deliveryDate ? Number(deliveryDate.slice(0, 4)) : currentYear();
    const salesMonth = deliveryDate ? Number(deliveryDate.slice(5, 7)) : currentMonth();
    setForm((f: any) => ({
      ...f,
      project_order_id: o.id,
      work_no: o.child_no,
      work_name: o.project_name || f.work_name,
      customer_name: o.customer_name || f.customer_name,
      responsible_person: o.sales_person_name || f.responsible_person,
      delivery_date: deliveryDate,
      work_year: salesYear,
      work_month: salesMonth,
    }));
  };

  const year = Number(form.work_year) || currentYear();
  const month = Number(form.work_month) || currentMonth();

  // ガント表示範囲を明細日付（無ければ納期月）から算出し、単位別に列生成
  const itemDates: Date[] = items.flatMap((it: any) => [it.start_date, it.end_date]).filter(Boolean).map(fromISO);
  let rngStart: Date, rngEnd: Date;
  if (itemDates.length) {
    rngStart = new Date(Math.min(...itemDates.map(d => +d)));
    rngEnd = new Date(Math.max(...itemDates.map(d => +d)));
  } else if (form.delivery_date) {
    const d = fromISO(form.delivery_date);
    rngStart = new Date(d.getFullYear(), d.getMonth(), 1);
    rngEnd = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  } else {
    rngStart = new Date(year, month - 1, 1);
    rngEnd = new Date(year, month - 1, daysInMonth(year, month));
  }
  rngStart = addDays(rngStart, -2); rngEnd = addDays(rngEnd, 2);
  const cols = buildCols(viewUnit, rngStart, rngEnd);
  const ganttWidth = 280 + cols.reduce((s, c) => s + c.w, 0);

  // 月バンド（連続列を年月でまとめる）
  const monthBand: { label: string; span: number }[] = [];
  cols.forEach(c => {
    const key = `${c.start.getFullYear()}/${c.start.getMonth() + 1}`;
    const last = monthBand[monthBand.length - 1];
    if (last && last.label === key) last.span += 1;
    else monthBand.push({ label: key, span: 1 });
  });

  const setItemDates = (i: number, start_date: string | null, end_date: string | null) =>
    setItems(prev => prev.map((it, idx) => idx === i ? { ...it, start_date, end_date } : it));

  const onCellClick = (i: number, col: GCol) => {
    const it = items[i];
    const cs = toISO(col.start), ce = toISO(col.end);
    if (!it.start_date) { setItemDates(i, cs, ce); return; }
    const curS = fromISO(it.start_date);
    const curE = it.end_date ? fromISO(it.end_date) : curS;
    // 選択が1バケット内に収まりそのバケットを再クリック → 解除
    if (curS >= col.start && curE <= col.end) { setItemDates(i, null, null); return; }
    if (col.start < curS) setItemDates(i, cs, it.end_date || ce);   // 開始を前へ
    else setItemDates(i, it.start_date, ce);                         // 終了を後へ
  };

  const applyTemplate = async () => {
    if (!selectedTemplateId || !form.delivery_date) {
      alert('テンプレートと納期を選択してください'); return;
    }
    try {
      const r = await processApi.generateSchedule({
        template_id: selectedTemplateId,
        delivery_date: form.delivery_date,
        project_order_id: form.project_order_id,
        customer_name: form.customer_name,
        delivery_name: form.delivery_name,
        work_name: form.work_name,
        work_no: form.work_no,
        responsible_person: form.responsible_person,
      });
      setForm((f: any) => ({...f, ...r.data, items: undefined}));
      setItems(r.data.items || []);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラー');
    }
  };

  const addItem = () => {
    setItems(prev => [...prev, {
      step_no: prev.length + 1, row_type: 'task',
      step_name: '', start_date: null, end_date: null,
      equipment: '', color: '#3b82f6', notes: '',
    }]);
  };

  const removeItem = (i: number) => setItems(prev => prev.filter((_, idx) => idx !== i));

  const updateItem = (i: number, field: string, val: any) => {
    setItems(prev => prev.map((item, idx) => idx === i ? {...item, [field]: val} : item));
  };

  const moveItem = (i: number, dir: -1 | 1) => {
    if (i + dir < 0 || i + dir >= items.length) return;
    const arr = [...items];
    [arr[i], arr[i+dir]] = [arr[i+dir], arr[i]];
    setItems(arr.map((item, idx) => ({...item, step_no: idx+1})));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = { ...form, items: items.map((item, i) => ({...item, step_no: i+1})) };
      if (isNew) {
        await processApi.createSchedule(payload);
      } else {
        await processApi.updateSchedule(form.id, payload);
      }
      onSaved();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラー');
    } finally {
      setSaving(false);
    }
  };

  const DOW_LABELS = ['日','月','火','水','木','金','土'];

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center overflow-y-auto py-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-7xl mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-bold text-gray-800">{isNew ? '工程表作成' : '工程表編集'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <div className="p-6">
          {/* 子ID参照 */}
          <div className="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
            <label className="block text-xs text-gray-500 mb-1">案件ID または 子ID で検索して情報を自動入力</label>
            <OrderSearchInput onSelect={handleOrderSelect} />
          </div>

          {/* ヘッダー情報 */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-5">
            <div>
              <label className="block text-xs text-gray-500 mb-1">納入先（顧客）</label>
              <input value={form.customer_name || ''} onChange={e => setForm((f: any) => ({...f, customer_name: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm" placeholder="ウッドリンク(株)能町工場" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">御担当者</label>
              <input value={form.delivery_name || ''} onChange={e => setForm((f: any) => ({...f, delivery_name: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">担当者</label>
              <input value={form.responsible_person || ''} onChange={e => setForm((f: any) => ({...f, responsible_person: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-gray-500 mb-1">工事名</label>
              <input value={form.work_name || ''} onChange={e => setForm((f: any) => ({...f, work_name: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">工番</label>
              <input value={form.work_no || ''} onChange={e => setForm((f: any) => ({...f, work_no: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">工程年月</label>
              <div className="flex gap-1">
                <input type="number" value={form.work_year || ''} onChange={e => setForm((f: any) => ({...f, work_year: e.target.value}))}
                  className="w-24 border rounded px-2 py-1.5 text-sm" placeholder="2026" />
                <select value={form.work_month || ''} onChange={e => setForm((f: any) => ({...f, work_month: Number(e.target.value)}))}
                  className="border rounded px-2 py-1.5 text-sm">
                  <option value="">月</option>
                  {Array.from({length:12},(_,i)=>i+1).map(m => <option key={m} value={m}>{m}月</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">納期<span className="text-[10px] text-gray-400 ml-1">顧客納期を自動取得</span></label>
              <input type="date" value={form.delivery_date || ''} onChange={e => setForm((f: any) => ({...f, delivery_date: e.target.value}))}
                className="border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">作成日</label>
              <input type="date" value={form.created_date || ''} onChange={e => setForm((f: any) => ({...f, created_date: e.target.value}))}
                className="border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">ステータス</label>
              <select value={form.status || '作成中'} onChange={e => setForm((f: any) => ({...f, status: e.target.value}))}
                className="border rounded px-2 py-1.5 text-sm">
                {STATUS_OPTIONS.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* テンプレート適用 */}
          <div className="flex items-end gap-2 mb-5 p-3 bg-purple-50 rounded-lg border border-purple-100">
            <div>
              <label className="block text-xs text-gray-500 mb-1">テンプレートから自動生成</label>
              <select value={selectedTemplateId} onChange={e => setSelectedTemplateId(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-48">
                <option value="">テンプレート選択</option>
                {templates.map((t: any) => <option key={t.id} value={t.id}>{t.template_name}（{t.product_type}）</option>)}
              </select>
            </div>
            <button onClick={applyTemplate}
              className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 whitespace-nowrap">
              工程を自動生成
            </button>
            <p className="text-xs text-gray-400">※ 納期を先に設定してください。既存の行は上書きされます。</p>
          </div>

          {/* ガントチャートエディタ */}
          <div className="mb-3 flex items-center justify-between flex-wrap gap-2">
            <h3 className="text-sm font-semibold text-gray-700">工程行 ({items.length}行)</h3>
            <div className="flex items-center gap-2">
              <div className="flex rounded-lg border border-gray-200 overflow-hidden">
                {([['day','日'],['week','週'],['month','月']] as const).map(([u, lbl]) => (
                  <button key={u} onClick={() => setViewUnit(u)}
                    className={`px-3 py-1 text-xs ${viewUnit === u ? 'bg-purple-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}>
                    {lbl}単位
                  </button>
                ))}
              </div>
              <button onClick={addItem}
                className="flex items-center gap-1 px-2 py-1 border border-purple-300 text-purple-600 text-xs rounded hover:bg-purple-50">
                <Plus size={12} />行追加
              </button>
            </div>
          </div>

          <div className="overflow-x-auto border rounded-lg">
            <table className="text-xs border-collapse" style={{minWidth: `${ganttWidth}px`}}>
              <thead>
                <tr className="bg-gray-200">
                  <th className="border border-gray-300" colSpan={4}></th>
                  {monthBand.map((b, idx) => (
                    <th key={idx} colSpan={b.span} className="border border-gray-300 text-center" style={{ fontSize: '9px', padding: '1px 0' }}>{b.label}</th>
                  ))}
                  <th className="border border-gray-300"></th>
                </tr>
                <tr className="bg-gray-100">
                  <th className="border border-gray-300 px-1 py-1 w-8 text-center">種別</th>
                  <th className="border border-gray-300 px-2 py-1 w-44 text-left">工程名</th>
                  <th className="border border-gray-300 px-1 py-1 w-6 text-center">色</th>
                  <th className="border border-gray-300 px-1 py-1 w-16 text-left">機材</th>
                  {cols.map((c, ci) => (
                    <th key={ci} style={{ background: c.bg, width: `${c.w}px` }} className="border border-gray-300 text-center">
                      <div style={{ fontSize: '9px' }}>{c.label}</div>
                      <div style={{ fontSize: '8px', color: c.color }}>{c.sub}</div>
                    </th>
                  ))}
                  <th className="border border-gray-300 px-1 py-1 w-16 text-center">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={i} className={item.row_type === 'blank' ? 'h-4' : 'h-8'}>
                    {item.row_type === 'blank' ? (
                      <td colSpan={4 + cols.length + 1} className="border border-gray-200 px-1">
                        <button onClick={() => removeItem(i)} className="text-red-300 hover:text-red-500"><X size={11}/></button>
                      </td>
                    ) : (
                      <>
                        <td className="border border-gray-300 px-1 py-0.5">
                          <select value={item.row_type} onChange={e => updateItem(i, 'row_type', e.target.value)}
                            className="text-xs border rounded w-full py-0.5">
                            {ROW_TYPES.map(t => <option key={t} value={t}>{ROW_TYPE_LABELS[t]}</option>)}
                          </select>
                        </td>
                        <td className="border border-gray-300 px-1 py-0.5">
                          <input value={item.step_name} onChange={e => updateItem(i, 'step_name', e.target.value)}
                            className="text-xs border-0 w-full outline-none" placeholder="工程名" />
                        </td>
                        <td className="border border-gray-300 px-1 py-0.5 text-center">
                          <input type="color" value={item.color || '#3b82f6'} onChange={e => updateItem(i, 'color', e.target.value)}
                            className="w-5 h-5 cursor-pointer rounded border-0 p-0" />
                        </td>
                        <td className="border border-gray-300 px-1 py-0.5">
                          <input value={item.equipment || ''} onChange={e => updateItem(i, 'equipment', e.target.value)}
                            className="text-xs border-0 w-full outline-none" placeholder="機材" />
                        </td>
                        {cols.map((c, ci) => {
                          const sd = item.start_date ? fromISO(item.start_date) : null;
                          const ed = item.end_date ? fromISO(item.end_date) : sd;
                          const inRange = !!sd && !!ed && sd <= c.end && ed >= c.start;
                          return (
                            <td key={ci}
                              style={{ background: inRange ? (item.color || '#3b82f6') : 'white', cursor: 'pointer', border: '1px solid #d1d5db' }}
                              title={`${toISO(c.start)}${viewUnit !== 'day' ? '〜' + toISO(c.end) : ''}`}
                              onClick={() => onCellClick(i, c)}
                            />
                          );
                        })}
                        <td className="border border-gray-300 px-1 py-0.5">
                          <div className="flex gap-0.5 justify-center">
                            <button onClick={() => moveItem(i, -1)} className="p-0.5 text-gray-400 hover:text-gray-600"><ChevronUp size={11}/></button>
                            <button onClick={() => moveItem(i, 1)} className="p-0.5 text-gray-400 hover:text-gray-600"><ChevronDown size={11}/></button>
                            <button onClick={() => removeItem(i)} className="p-0.5 text-red-400 hover:text-red-600"><X size={11}/></button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={4 + cols.length + 1} className="text-center py-6 text-gray-400 text-xs">
                      行がありません。「行追加」またはテンプレートから生成してください。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-400 mt-1">日/週/月で表示単位を切替。セルをクリックで開始→終了を設定、選択範囲内を再クリックで解除。複数月にまたがって設定できます。</p>

          {/* 備考 */}
          <div className="mt-3">
            <label className="block text-xs text-gray-500 mb-1">備考（※御支給工事等）</label>
            <textarea value={form.notes || ''} onChange={e => setForm((f: any) => ({...f, notes: e.target.value}))}
              rows={2} className="w-full border rounded px-2 py-1.5 text-sm" />
          </div>
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t bg-gray-50">
          <button onClick={onClose} className="px-4 py-2 border rounded text-sm hover:bg-gray-100">キャンセル</button>
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 disabled:opacity-50 flex items-center gap-1">
            <Check size={14} />{saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ========== テンプレート管理タブ ==========
function TemplatesTab() {
  const [templates, setTemplates] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newTemplate, setNewTemplate] = useState({ product_type: '', template_name: '', steps: [] as any[] });

  // suppress unused warning
  void expanded;

  const load = () => processApi.listTemplates().then(r => setTemplates(r.data));
  useEffect(() => { load(); }, []);

  const handleAddTemplate = async () => {
    await processApi.createTemplate(newTemplate);
    setShowAdd(false); setNewTemplate({ product_type: '', template_name: '', steps: [] }); load();
  };

  const handleUpdateTemplate = async (id: string, data: any) => {
    await processApi.updateTemplate(id, data);
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm('削除しますか？')) return;
    await processApi.deleteTemplate(id); load();
  };

  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div>
      <div className="flex justify-end mb-3">
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700">
          <Plus size={14} />テンプレート追加
        </button>
      </div>

      {showAdd && (
        <div className="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
          <div className="flex gap-2 items-end flex-wrap">
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">製品種別</label>
              <select value={newTemplate.product_type} onChange={e => setNewTemplate(t => ({...t, product_type: e.target.value}))}
                className="border rounded px-2 py-1.5 text-sm">
                <option value="">-</option>
                {PRODUCT_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div className="flex-1 min-w-48">
              <label className="block text-xs text-gray-500 mb-0.5">テンプレート名</label>
              <input value={newTemplate.template_name} onChange={e => setNewTemplate(t => ({...t, template_name: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm" placeholder="例: SCA標準工程" />
            </div>
            <button onClick={handleAddTemplate} className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded"><Check size={14}/></button>
            <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 border text-sm rounded"><X size={14}/></button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {templates.map(t => (
          <div key={t.id} className="border rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 cursor-pointer"
              onClick={() => setExpandedId(expandedId === t.id ? null : t.id)}>
              <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 text-xs rounded font-medium">{t.product_type || '汎用'}</span>
              <span className="font-medium text-sm text-gray-800 flex-1">{t.template_name}</span>
              <span className="text-xs text-gray-400">{t.steps.length}ステップ</span>
              <button onClick={e => { e.stopPropagation(); handleDelete(t.id); }} className="p-1 text-red-400 hover:text-red-600"><Trash2 size={13}/></button>
            </div>

            {expandedId === t.id && (
              <TemplateStepEditor template={t} onSave={(data: any) => handleUpdateTemplate(t.id, data)} />
            )}
          </div>
        ))}
        {templates.length === 0 && (
          <div className="text-center py-8 text-gray-400 text-sm">テンプレートがありません</div>
        )}
      </div>
    </div>
  );
}

function TemplateStepEditor({ template, onSave }: any) {
  const [steps, setSteps] = useState<any[]>(template.steps.map((s: any) => ({...s})));

  const addStep = () => setSteps(prev => [...prev, {
    step_no: prev.length + 1, step_name: '', offset_start_days: -7,
    duration_days: 1, equipment: '', color: '#3b82f6',
  }]);

  const removeStep = (i: number) => setSteps(prev => prev.filter((_, idx) => idx !== i));

  const updateStep = (i: number, field: string, val: any) => {
    setSteps(prev => prev.map((s, idx) => idx === i ? {...s, [field]: val} : s));
  };

  const handleSave = () => {
    onSave({ ...template, steps: steps.map((s, i) => ({...s, step_no: i+1})) });
  };

  return (
    <div className="p-4">
      <table className="text-xs w-full border-collapse mb-3">
        <thead>
          <tr className="bg-gray-50">
            {['#','工程名','納期からのオフセット(日)','作業日数','機材','色',''].map(h => (
              <th key={h} className="border border-gray-200 px-2 py-1.5 text-left font-medium text-gray-600">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {steps.map((s, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="border border-gray-200 px-2 py-1 text-gray-400 w-6">{i+1}</td>
              <td className="border border-gray-200 px-1 py-1">
                <input value={s.step_name} onChange={e => updateStep(i, 'step_name', e.target.value)}
                  className="w-full border-0 outline-none text-xs" placeholder="工程名" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input type="number" value={s.offset_start_days ?? -7} onChange={e => updateStep(i, 'offset_start_days', Number(e.target.value))}
                  className="w-16 border rounded px-1 py-0.5 text-xs text-right" />
                <span className="ml-1 text-gray-400">日前</span>
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input type="number" value={s.duration_days ?? 1} onChange={e => updateStep(i, 'duration_days', Number(e.target.value))}
                  className="w-12 border rounded px-1 py-0.5 text-xs text-right" />
                <span className="ml-1 text-gray-400">日</span>
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input value={s.equipment || ''} onChange={e => updateStep(i, 'equipment', e.target.value)}
                  className="w-full border-0 outline-none text-xs" placeholder="レッカー車等" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <input type="color" value={s.color || '#3b82f6'} onChange={e => updateStep(i, 'color', e.target.value)}
                  className="w-6 h-5 cursor-pointer border-0 p-0" />
              </td>
              <td className="border border-gray-200 px-1 py-1">
                <button onClick={() => removeStep(i)} className="text-red-400 hover:text-red-600"><X size={12}/></button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2">
        <button onClick={addStep} className="flex items-center gap-1 px-2 py-1 border border-purple-300 text-purple-600 text-xs rounded hover:bg-purple-50">
          <Plus size={11}/>ステップ追加
        </button>
        <button onClick={handleSave} className="flex items-center gap-1 px-3 py-1 bg-purple-600 text-white text-xs rounded hover:bg-purple-700">
          <Check size={11}/>保存
        </button>
      </div>
    </div>
  );
}
