import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectApi, mastersApi } from '../api';
import { Plus, ChevronDown, ChevronRight, Edit2, Trash2, FileText, Copy } from 'lucide-react';
import ArrangementModal from '../components/ArrangementModal';

const STATUS_OPTIONS = ['営業中', '見積発行', '受注', '失注', '請求済'];
const DIST_OPTIONS = ['直接', '代理店'];
const STATUS_COLORS: Record<string, string> = {
  '営業中': 'bg-blue-100 text-blue-700',
  '見積発行': 'bg-orange-100 text-orange-700',
  '受注': 'bg-yellow-100 text-yellow-700',
  '失注': 'bg-gray-100 text-gray-500',
  '請求済': 'bg-green-100 text-green-700',
};

// ===== トップレベルコンポーネント（1文字入力バグ防止のため関数外に定義）=====
function TextField({ label, value, onChange, cols = 1, placeholder = '', type = 'text' }: any) {
  return (
    <div className={cols === 2 ? 'md:col-span-2' : ''}>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input type={type} placeholder={placeholder} value={value || ''}
        onChange={e => onChange(e.target.value)}
        className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
    </div>
  );
}

function NumberField({ label, value, onChange }: any) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}（円）</label>
      <input type="number" value={value || ''}
        onChange={e => onChange(e.target.value)}
        className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-right focus:ring-2 focus:ring-blue-500 focus:outline-none" />
      {value && <p className="text-xs text-gray-400 mt-0.5 text-right">¥{Number(value).toLocaleString()}</p>}
    </div>
  );
}

function DateField({ label, value, onChange, required = false, readOnly = false }: any) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
        {readOnly && <span className="text-blue-400 ml-1 text-xs">（自動）</span>}
      </label>
      <input type="date" value={value || ''}
        onChange={e => !readOnly && onChange(e.target.value)}
        readOnly={readOnly}
        className={`w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none ${readOnly ? 'bg-gray-50 text-gray-400' : ''}`} />
    </div>
  );
}

function SelectField({ label, name, options, form, setForm }: any) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <select value={form[name] || ''}
        onChange={e => { const v = e.target.value; setForm((f: any) => ({ ...f, [name]: v })); }}
        className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
        <option value="">—</option>
        {options.map((o: string) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [projectModal, setProjectModal] = useState<any>(null);
  const [orderModal, setOrderModal] = useState<any>(null);
  const [arrangeModal, setArrangeModal] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  const [orderForm, setOrderForm] = useState<any>({});
  const [agencies, setAgencies] = useState<any[]>([]);
  const [destinations, setDestinations] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);

  const load = () => {
    projectApi.list({ search: search || undefined, status: statusFilter || undefined, per_page: 50 })
      .then(r => { setItems(r.data.items || []); setTotal(r.data.total || 0); });
  };

  useEffect(() => {
    load();
    mastersApi.listAgencies().then(r => setAgencies(r.data || []));
    mastersApi.listDeliveryDestinations().then(r => setDestinations(r.data || []));
    mastersApi.listEmployees().then(r => setEmployees(r.data || []));
  }, [search, statusFilter]);

  const generateNextProjectNo = (existingItems: any[]) => {
    const year = new Date().getFullYear();
    const prefix = `${year}-`;
    const nums = existingItems
      .map(p => p.project_no)
      .filter(no => no && no.startsWith(prefix))
      .map(no => parseInt(no.replace(prefix, '')))
      .filter(n => !isNaN(n));
    const next = nums.length > 0 ? Math.max(...nums) + 1 : 1;
    return `${prefix}${String(next).padStart(4, '0')}`;
  };

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const openProjectNew = () => {
    setForm({ status: '営業中', project_no: generateNextProjectNo(items), distribution_type: '直接' });
    setProjectModal({ isNew: true });
  };

  const openProjectEdit = (p: any) => { setForm({ ...p }); setProjectModal({ isNew: false }); };

  const openOrderNew = (project: any) => {
    const existingOrders = project.orders || [];
    const maxSeq = existingOrders.reduce((max: number, o: any) => {
      const parts = (o.child_no || '').split('_');
      const seq = parseInt(parts[parts.length - 1]);
      return isNaN(seq) ? max : Math.max(max, seq);
    }, 0);
    const childNo = `${project.project_no}_${String(maxSeq + 1).padStart(2, '0')}`;
    setOrderForm({
      child_no: childNo,
      status: project.status,
      project_name: project.project_name,
      sales_person_name: project.sales_person_name,
      sales_person_code: project.sales_person_code,
      customer_code: project.customer_code_2,
      customer_name: project.customer_name_2,
      agency_code: project.customer_code_1,
      agency_name: project.customer_name_1,
      inquiry_date: project.inquiry_date,
      sales_date: project.sales_date,
      expected_order_date: project.expected_order_date,
      expected_shipment_date: project.expected_shipment_date,
      budget_amount: project.budget_amount,
    });
    setOrderModal({ project, order: null });
  };

  const openOrderEdit = (project: any, order: any) => {
    setOrderForm({ ...order });
    setOrderModal({ project, order });
  };

  const handleSaveProject = async () => {
    try {
      const payload = { ...form };
      Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null; });
      ['budget_amount','estimated_sales_total','cost_price','profit_amount','profit_rate']
        .forEach(k => { if (payload[k]) payload[k] = Number(payload[k]); });
      delete payload.final_order_amount; // 受注票合計から自動計算するため送信しない
      if (projectModal.isNew) {
        await projectApi.create({ ...payload, orders: [] });
      } else {
        await projectApi.update(form.id, payload);
      }
      setProjectModal(null);
      load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラーが発生しました');
    }
  };

  const handleSaveOrder = async () => {
    try {
      const payload = { ...orderForm };
      Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null; });
      ['quotation_amount','budget_amount'].forEach(k => { if (payload[k]) payload[k] = Number(payload[k]); });
      if (orderModal.order?.id) {
        await projectApi.updateOrder(orderModal.order.id, payload);
      } else {
        await projectApi.addOrder(orderModal.project.id, payload);
      }
      setOrderModal(null);
      load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラー');
    }
  };

  const handleDeleteProject = async (id: string) => {
    if (!confirm('この案件を削除しますか？')) return;
    await projectApi.delete(id);
    load();
  };

  const handleDeleteOrder = async (id: string) => {
    if (!confirm('この子レコードを削除しますか？')) return;
    await projectApi.deleteOrder(id);
    load();
  };

  const handleDuplicateOrder = async (o: any) => {
    if (!confirm(`案件子ID「${o.child_no}」を複製します。\n同じ案件の配下に新しい子IDが作成されます（見積・受注の紐付けは引き継ぎません）。\nよろしいですか？`)) return;
    try {
      const r = await projectApi.duplicateOrder(o.id);
      alert(`複製しました: ${r.data.child_no}`);
      load();
    } catch (e: any) { alert(e.response?.data?.detail || '複製に失敗しました'); }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">案件管理</h1>
          <p className="text-sm text-gray-500 mt-1">全 {total} 件</p>
        </div>
        <button onClick={openProjectNew}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} /> 新規案件登録
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-3 mb-4 flex gap-3">
        <input placeholder="案件ID・案件名・顧客名で検索" value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 outline-none text-sm border border-gray-200 rounded-lg px-3 py-2" />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="">全ステータス</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="space-y-2">
        {items.map(p => {
          const expanded = expandedIds.has(p.id);
          return (
            <div key={p.id} className="bg-white rounded-xl shadow-sm overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 border-b border-gray-50"
                onClick={() => toggleExpand(p.id)}>
                <span className="text-gray-400 shrink-0">{expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
                <span className="font-bold text-blue-700 w-32 shrink-0 text-sm font-mono">{p.project_no}</span>
                <span className="flex-1 font-medium text-gray-800 text-sm truncate">{p.project_name || '（案件名未設定）'}</span>
                <span className="text-xs text-gray-500 w-40 truncate hidden md:block">{p.customer_name_2 || p.customer_name_1 || '—'}</span>
                <span className="text-xs text-gray-500 w-20 hidden lg:block">{p.sales_person_name || '—'}</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${STATUS_COLORS[p.status] || 'bg-gray-100'}`}>{p.status}</span>
                <span className="text-xs text-gray-400 w-16 text-center shrink-0">{p.distribution_type || '直接'}</span>
                <span className="text-sm font-bold text-gray-700 w-32 text-right shrink-0">
                  {p.final_order_amount != null ? `¥${Number(p.final_order_amount).toLocaleString()}` : '—'}
                </span>
                <span className="text-xs text-gray-400 w-8 text-center shrink-0">{p.order_count || 0}件</span>
                <div className="flex items-center gap-1 ml-1" onClick={e => e.stopPropagation()}>
                  <button onClick={() => openProjectEdit(p)} className="text-blue-400 hover:text-blue-600 p-1"><Edit2 size={13} /></button>
                  <button onClick={() => handleDeleteProject(p.id)} className="text-red-300 hover:text-red-500 p-1"><Trash2 size={13} /></button>
                </div>
              </div>

              {expanded && (
                <div className="bg-gray-50">
                  <div className="grid text-xs text-gray-400 px-10 py-1.5 border-b border-gray-100 font-medium"
                    style={{ gridTemplateColumns: '140px 1fr 150px 90px 100px 100px 100px 110px 170px 130px' }}>
                    <span>子ID</span>
                    <span>案件名</span>
                    <span>納入先</span>
                    <span>担当者</span>
                    <span>受注予定日</span>
                    <span>出荷予定日</span>
                    <span>売上予定日</span>
                    <span>見積金額</span>
                    <span>採用見積</span>
                    <span>操作</span>
                  </div>

                  {(p.orders || []).map((o: any) => (
                    <div key={o.id}
                      className="grid items-center px-10 py-2 text-sm border-b border-gray-100 hover:bg-blue-50"
                      style={{ gridTemplateColumns: '140px 1fr 150px 90px 100px 100px 100px 110px 170px 130px' }}>
                      <span className="font-mono text-xs text-blue-600 font-bold">{o.child_no}</span>
                      <span className="truncate text-gray-700 text-xs">{o.project_name || p.project_name || '—'}</span>
                      <span className="truncate text-gray-500 text-xs">{o.customer_name || o.agency_name || '—'}</span>
                      <span className="text-gray-500 text-xs">{o.sales_person_name || '—'}</span>
                      <span className="text-gray-400 text-xs">{o.expected_order_date || '—'}</span>
                      <span className="text-gray-400 text-xs">{o.expected_shipment_date || '—'}</span>
                      <span className="text-gray-400 text-xs">{o.sales_date || '—'}</span>
                      <span className="text-gray-700 font-medium text-xs">
                        {o.quotation_amount != null ? `¥${Number(o.quotation_amount).toLocaleString()}` : '—'}
                      </span>
                      <div className="text-xs">
                        {o.quotation_no ? (
                          <div className="flex flex-col gap-0.5">
                            <span className="text-green-600 font-bold">✓ {o.quotation_no}</span>
                            {o.quotation_total && <span className="text-gray-500">¥{Number(o.quotation_total).toLocaleString()}</span>}
                          </div>
                        ) : (
                          <span className="text-gray-300 text-xs">未採用</span>
                        )}
                      </div>
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => navigate(`/estimates/new?child_no=${o.child_no}&project_order_id=${o.id}`)}
                            className="text-green-500 hover:text-green-700 p-0.5" title="見積作成">
                            <FileText size={13} />
                          </button>
                          <button
                            onClick={() => navigate(`/estimates?child_no=${o.child_no}`)}
                            className="text-purple-400 hover:text-purple-600 text-xs p-0.5" title="見積一覧">
                            一覧
                          </button>
                          <button onClick={() => openOrderEdit(p, o)} className="text-blue-400 hover:text-blue-600 p-0.5" title="編集"><Edit2 size={12} /></button>
                          <button onClick={() => handleDuplicateOrder(o)} className="text-emerald-500 hover:text-emerald-700 p-0.5" title="複製"><Copy size={12} /></button>
                          <button onClick={() => handleDeleteOrder(o.id)} className="text-red-300 hover:text-red-500 p-0.5" title="削除"><Trash2 size={12} /></button>
                        </div>
                        <div className="flex items-center gap-1">
                          <button onClick={() => setArrangeModal({ type: 'crane', orderId: o.id, childNo: o.child_no })}
                            className="text-xs bg-orange-100 text-orange-700 px-1 py-0.5 rounded hover:bg-orange-200">クレーン</button>
                          <button onClick={() => setArrangeModal({ type: 'shipping', orderId: o.id, childNo: o.child_no })}
                            className="text-xs bg-blue-100 text-blue-700 px-1 py-0.5 rounded hover:bg-blue-200">送り状</button>
                          <button onClick={() => setArrangeModal({ type: 'hotel', orderId: o.id, childNo: o.child_no })}
                            className="text-xs bg-green-100 text-green-700 px-1 py-0.5 rounded hover:bg-green-200">宿泊</button>
                          <button onClick={() => navigate('/procurement', { state: { childOrder: { id: o.id, child_no: o.child_no, project_name: o.project_name, customer_name: o.customer_name, sales_person_name: o.sales_person_name, sales_date: o.sales_date, status: o.status } } })}
                            className="text-xs bg-indigo-100 text-indigo-700 px-1 py-0.5 rounded hover:bg-indigo-200">発注</button>
                        </div>
                      </div>
                    </div>
                  ))}

                  <div className="px-10 py-2">
                    <button onClick={() => openOrderNew(p)}
                      className="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <Plus size={12} /> 子ID追加
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {items.length === 0 && (
          <div className="bg-white rounded-xl shadow-sm text-center py-16 text-gray-400">
            案件データがありません<br />
            <span className="text-xs mt-1 block">「新規案件登録」から追加してください</span>
          </div>
        )}
      </div>

      {/* ===== 親案件モーダル ===== */}
      {projectModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
            <div className="p-5 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-800">{projectModal.isNew ? '新規案件登録' : '案件編集'}</h2>
              {projectModal.isNew && <p className="text-xs text-blue-600 mt-1">親ID: <strong>{form.project_no}</strong>（自動採番）</p>}
            </div>
            <div className="overflow-y-auto flex-1 p-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">案件ID_親（自動採番）</label>
                  <input value={form.project_no || ''} readOnly
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-gray-50 font-mono font-bold text-blue-700" />
                </div>
                <SelectField label="案件ステータス" name="status" options={STATUS_OPTIONS} form={form} setForm={setForm} />
                <TextField label="案件名" value={form.project_name} onChange={(v: string) => setForm((f: any) => ({ ...f, project_name: v }))} cols={2} />
                <TextField label="案件概要" value={form.project_summary} onChange={(v: string) => setForm((f: any) => ({ ...f, project_summary: v }))} cols={2} />
                <SelectField label="商流判定" name="distribution_type" options={DIST_OPTIONS} form={form} setForm={setForm} />
                <div className="flex items-end pb-1">
                  <p className="text-xs text-gray-400">{form.distribution_type === '代理店' ? '代理店経由：商社＋納入先を選択' : '直接取引：納入先のみ選択'}</p>
                </div>
                {form.distribution_type === '代理店' && (<>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">商社（代理店）</label>
                    <select value={form.customer_code_1 || ''}
                      onChange={e => { const a = agencies.find(a => a.agency_code === e.target.value); setForm((f: any) => ({ ...f, customer_code_1: e.target.value, customer_name_1: a?.agency_name || '' })); }}
                      className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                      <option value="">選択</option>
                      {agencies.map(a => <option key={a.id} value={a.agency_code}>{a.agency_name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">商社名</label>
                    <input value={form.customer_name_1 || ''} readOnly className="w-full border border-gray-100 rounded-lg px-3 py-1.5 text-sm bg-gray-50" />
                  </div>
                </>)}
                <div>
                  <label className="block text-xs text-gray-500 mb-1">納入先(エンドユーザー)</label>
                  <select value={form.customer_code_2 || ''}
                    onChange={e => { const d = destinations.find(d => d.customer_id === e.target.value); setForm((f: any) => ({ ...f, customer_code_2: e.target.value, customer_name_2: d ? `${d.company_name}${d.factory_name ? ' ' + d.factory_name : ''}` : '' })); }}
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                    <option value="">選択</option>
                    {destinations.map(d => <option key={d.id} value={d.customer_id}>{d.company_name}{d.factory_name ? ` ${d.factory_name}` : ''}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">納入先名</label>
                  <input value={form.customer_name_2 || ''} readOnly className="w-full border border-gray-100 rounded-lg px-3 py-1.5 text-sm bg-gray-50" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">自社営業担当</label>
                  <select value={form.sales_person_code || ''}
                    onChange={e => { const emp = employees.find(emp => emp.employee_code === e.target.value); setForm((f: any) => ({ ...f, sales_person_code: e.target.value, sales_person_name: emp?.employee_name || '' })); }}
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                    <option value="">選択</option>
                    {employees.map(e => <option key={e.id} value={e.employee_code}>{e.employee_name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">担当者名</label>
                  <input value={form.sales_person_name || ''} readOnly className="w-full border border-gray-100 rounded-lg px-3 py-1.5 text-sm bg-gray-50" />
                </div>
                <NumberField label="予算金額" value={form.budget_amount} onChange={(v: string) => setForm((f: any) => ({ ...f, budget_amount: v }))} />
                <NumberField label="見込売上合計(仕切りベース)" value={form.estimated_sales_total} onChange={(v: string) => setForm((f: any) => ({ ...f, estimated_sales_total: v }))} />
                <div>
                  <label className="block text-xs text-gray-500 mb-1">最終受注金額</label>
                  <input value={form.final_order_amount != null ? `¥${Number(form.final_order_amount).toLocaleString()}` : '—'} readOnly className="w-full border border-gray-100 rounded-lg px-3 py-1.5 text-sm bg-gray-50 text-right" />
                  <p className="text-xs text-gray-400 mt-0.5">受注票の合計から自動計算</p>
                </div>
                <NumberField label="案件原価" value={form.cost_price} onChange={(v: string) => setForm((f: any) => ({ ...f, cost_price: v }))} />
                <NumberField label="利益額" value={form.profit_amount} onChange={(v: string) => setForm((f: any) => ({ ...f, profit_amount: v }))} />
                <div>
                  <label className="block text-xs text-gray-500 mb-1">利益率(%)</label>
                  <input type="number" step="0.1" value={form.profit_rate || ''}
                    onChange={e => { const v = e.target.value; setForm((f: any) => ({ ...f, profit_rate: v })); }}
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-right focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                </div>
                <DateField label="引き合い日" value={form.inquiry_date} onChange={(v: string) => setForm((f: any) => ({ ...f, inquiry_date: v }))} required />
                <DateField label="受注予定日" value={form.expected_order_date} onChange={(v: string) => setForm((f: any) => ({ ...f, expected_order_date: v }))} required />
                <DateField label="見積作成日" value={form.quotation_issue_date} onChange={(v: string) => setForm((f: any) => ({ ...f, quotation_issue_date: v }))} readOnly />
                <DateField label="受注日" value={form.order_date} onChange={(v: string) => setForm((f: any) => ({ ...f, order_date: v }))} readOnly />
                <DateField label="出荷予定日" value={form.expected_shipment_date} onChange={(v: string) => setForm((f: any) => ({ ...f, expected_shipment_date: v }))} required />
                <DateField label="出荷日" value={form.shipment_date} onChange={(v: string) => setForm((f: any) => ({ ...f, shipment_date: v }))} required />
                <DateField label="顧客納期" value={form.customer_delivery_date} onChange={(v: string) => setForm((f: any) => ({ ...f, customer_delivery_date: v }))} required />
                <DateField label="売上予定日" value={form.sales_date} onChange={(v: string) => setForm((f: any) => ({ ...f, sales_date: v }))} required />
                <DateField label="納品日" value={form.delivery_date} onChange={(v: string) => setForm((f: any) => ({ ...f, delivery_date: v }))} />
                <div className="md:col-span-2">
                  <label className="block text-xs text-gray-500 mb-1">備考</label>
                  <textarea value={form.notes || ''} rows={2}
                    onChange={e => { const v = e.target.value; setForm((f: any) => ({ ...f, notes: v })); }}
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 p-4 border-t border-gray-100">
              <button onClick={() => setProjectModal(null)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">キャンセル</button>
              <button onClick={handleSaveProject} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">保存</button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 手配書編集モーダル ===== */}
      {arrangeModal && (
        <ArrangementModal
          type={arrangeModal.type}
          orderId={arrangeModal.orderId}
          childNo={arrangeModal.childNo}
          onClose={() => setArrangeModal(null)}
        />
      )}

      {/* ===== 子案件モーダル ===== */}
      {orderModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
            <div className="p-5 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-800">{orderModal.order ? '子ID編集' : '子ID追加'}</h2>
              <p className="text-xs text-gray-500 mt-1">
                親: <strong className="text-blue-700">{orderModal.project.project_no}</strong>
                {' → '}子ID: <strong className="text-green-700">{orderForm.child_no}</strong>
              </p>
            </div>
            <div className="overflow-y-auto flex-1 p-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">子ID(自動採番)</label>
                  <input value={orderForm.child_no || ''} readOnly
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-gray-50 font-mono font-bold text-green-700" />
                </div>
                <SelectField label="ステータス" name="status" options={STATUS_OPTIONS} form={orderForm} setForm={setOrderForm} />
                <TextField label="案件名" value={orderForm.project_name} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, project_name: v }))} cols={2} />
                <div>
                  <label className="block text-xs text-gray-500 mb-1">納入先(エンドユーザー)</label>
                  <select value={orderForm.customer_code || ''}
                    onChange={e => { const d = destinations.find(d => d.customer_id === e.target.value); setOrderForm((f: any) => ({ ...f, customer_code: e.target.value, customer_name: d ? `${d.company_name}${d.factory_name ? ' ' + d.factory_name : ''}` : '' })); }}
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                    <option value="">選択</option>
                    {destinations.map(d => <option key={d.id} value={d.customer_id}>{d.company_name}{d.factory_name ? ` ${d.factory_name}` : ''}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">納入先名</label>
                  <input value={orderForm.customer_name || ''} readOnly className="w-full border border-gray-100 rounded-lg px-3 py-1.5 text-sm bg-gray-50" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">代理店(商社)</label>
                  <select value={orderForm.agency_code || ''}
                    onChange={e => { const a = agencies.find(a => a.agency_code === e.target.value); setOrderForm((f: any) => ({ ...f, agency_code: e.target.value, agency_name: a?.agency_name || '' })); }}
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                    <option value="">直接取引(なし)</option>
                    {agencies.map(a => <option key={a.id} value={a.agency_code}>{a.agency_name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">代理店名</label>
                  <input value={orderForm.agency_name || ''} readOnly className="w-full border border-gray-100 rounded-lg px-3 py-1.5 text-sm bg-gray-50" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">自社営業担当</label>
                  <select value={orderForm.sales_person_code || ''}
                    onChange={e => { const emp = employees.find(emp => emp.employee_code === e.target.value); setOrderForm((f: any) => ({ ...f, sales_person_code: e.target.value, sales_person_name: emp?.employee_name || '' })); }}
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                    <option value="">選択</option>
                    {employees.map(e => <option key={e.id} value={e.employee_code}>{e.employee_name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">担当者名</label>
                  <input value={orderForm.sales_person_name || ''} readOnly className="w-full border border-gray-100 rounded-lg px-3 py-1.5 text-sm bg-gray-50" />
                </div>
                <NumberField label="見積金額" value={orderForm.quotation_amount} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, quotation_amount: v }))} />
                <NumberField label="予算金額" value={orderForm.budget_amount} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, budget_amount: v }))} />
                <DateField label="引き合い日" value={orderForm.inquiry_date} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, inquiry_date: v }))} required />
                <DateField label="受注予定日" value={orderForm.expected_order_date} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, expected_order_date: v }))} required />
                <DateField label="見積作成日" value={orderForm.quotation_issue_date} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, quotation_issue_date: v }))} readOnly />
                <DateField label="受注日" value={orderForm.order_date} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, order_date: v }))} readOnly />
                <DateField label="出荷予定日" value={orderForm.expected_shipment_date} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, expected_shipment_date: v }))} required />
                <DateField label="出荷日" value={orderForm.shipment_date} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, shipment_date: v }))} required />
                <DateField label="顧客納期" value={orderForm.customer_delivery_date} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, customer_delivery_date: v }))} required />
                <DateField label="売上予定日" value={orderForm.sales_date} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, sales_date: v }))} required />
                <DateField label="納品日" value={orderForm.delivery_date} onChange={(v: string) => setOrderForm((f: any) => ({ ...f, delivery_date: v }))} />
                <div className="md:col-span-2">
                  <label className="block text-xs text-gray-500 mb-1">備考</label>
                  <textarea value={orderForm.notes || ''} rows={2}
                    onChange={e => { const v = e.target.value; setOrderForm((f: any) => ({ ...f, notes: v })); }}
                    className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 p-4 border-t border-gray-100">
              <button onClick={() => setOrderModal(null)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">キャンセル</button>
              <button onClick={handleSaveOrder} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
