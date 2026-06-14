import { useEffect, useState } from 'react';
import { projectApi, quotationApi } from '../api';
import { Search, Plus, ChevronDown, ChevronRight, Edit2, Trash2, Link, FileText } from 'lucide-react';

const STATUS_OPTIONS = ['営業中', '受注', '受注済', '失注'];
const DIST_OPTIONS = ['直接', '代理店'];

const STATUS_COLORS: Record<string, string> = {
  '営業中': 'bg-blue-100 text-blue-700',
  '受注': 'bg-yellow-100 text-yellow-700',
  '受注済': 'bg-green-100 text-green-700',
  '失注': 'bg-gray-100 text-gray-500',
};

// Excelシリアル値 → 日付文字列変換
function excelDateToString(serial: number | null): string {
  if (!serial) return '';
  const d = new Date((serial - 25569) * 86400 * 1000);
  return d.toISOString().split('T')[0];
}

const EMPTY_PROJECT = {
  project_no: '', seq_no: '', project_name: '', project_summary: '',
  customer_code_1: '', customer_name_1: '', customer_code_2: '', customer_name_2: '',
  sales_person_name: '', sales_person_code: '', status: '営業中', distribution_type: '',
  budget_amount: '', estimated_sales_total: '', final_order_amount: '', cost_price: '',
  profit_amount: '', profit_rate: '',
  inquiry_date: '', sales_date: '', drawing_request_date: '',
  order_date: '', expected_order_date: '', expected_shipment_date: '', created_date: '',
  notes: '',
};

const EMPTY_ORDER = {
  child_no: '', project_name: '', project_summary: '',
  customer_code: '', customer_name: '', agency_code: '', agency_name: '',
  sales_person_name: '', sales_person_code: '', status: '',
  quotation_amount: '', budget_amount: '',
  sales_date: '', inquiry_date: '', order_date: '', expected_order_date: '',
  shipment_date: '', expected_shipment_date: '',
  quotation_no: '', quotation_total: '', quotation_issue_date: '',
  notes: '',
};

export default function ProjectsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [projectModal, setProjectModal] = useState<any>(null);
  const [orderModal, setOrderModal] = useState<any>(null); // { project, order }
  const [form, setForm] = useState<any>({});
  const [orderForm, setOrderForm] = useState<any>({});

  const load = () => {
    projectApi.list({ search: search || undefined, status: statusFilter || undefined, per_page: 50 })
      .then(r => { setItems(r.data.items || []); setTotal(r.data.total || 0); });
  };

  useEffect(() => { load(); }, [search, statusFilter]);

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // 親保存
  const handleSaveProject = async () => {
    try {
      const payload = { ...form };
      // 空文字をnullに
      Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null; });
      if (form.id) {
        await projectApi.update(form.id, payload);
      } else {
        if (!payload.project_no) { alert('案件IDは必須です'); return; }
        await projectApi.create({ ...payload, orders: [] });
      }
      setProjectModal(null);
      load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラーが発生しました');
    }
  };

  // 子保存
  const handleSaveOrder = async () => {
    try {
      const payload = { ...orderForm };
      Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null; });
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

  const openProjectNew = () => { setForm({ ...EMPTY_PROJECT }); setProjectModal({ isNew: true }); };
  const openProjectEdit = (p: any) => { setForm({ ...p }); setProjectModal({ isNew: false }); };
  const openOrderNew = (project: any) => {
    setOrderForm({ ...EMPTY_ORDER, status: project.status, sales_person_name: project.sales_person_name, sales_person_code: project.sales_person_code });
    setOrderModal({ project, order: null });
  };
  const openOrderEdit = (project: any, order: any) => {
    setOrderForm({ ...order });
    setOrderModal({ project, order });
  };

  const Field = ({ label, name, type = 'text', formSetter, formState, cols = 1 }: any) => (
    <div className={cols === 2 ? 'md:col-span-2' : ''}>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input type={type} value={formState[name] || ''} onChange={e => formSetter((f: any) => ({ ...f, [name]: e.target.value }))}
        className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
    </div>
  );

  const SelectField = ({ label, name, options, formSetter, formState }: any) => (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <select value={formState[name] || ''} onChange={e => formSetter((f: any) => ({ ...f, [name]: e.target.value }))}
        className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
        <option value="">—</option>
        {options.map((o: string) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );

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

      {/* フィルタ */}
      <div className="bg-white rounded-xl shadow-sm p-3 mb-4 flex gap-3">
        <div className="flex items-center gap-2 flex-1 border border-gray-200 rounded-lg px-3 py-2">
          <Search size={15} className="text-gray-400" />
          <input placeholder="案件ID・案件名・顧客名・担当者で検索" value={search}
            onChange={e => setSearch(e.target.value)} className="flex-1 outline-none text-sm" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="">全ステータス</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* 案件一覧（親子折りたたみ） */}
      <div className="space-y-2">
        {items.map(p => {
          const expanded = expandedIds.has(p.id);
          return (
            <div key={p.id} className="bg-white rounded-xl shadow-sm overflow-hidden">
              {/* 親行 */}
              <div
                className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 border-b border-gray-50"
                onClick={() => toggleExpand(p.id)}
              >
                <span className="text-gray-400 shrink-0">
                  {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </span>
                <span className="font-bold text-blue-700 w-28 shrink-0 text-sm">{p.project_no}</span>
                <span className="flex-1 font-medium text-gray-800 text-sm truncate">{p.project_name || '（案件名未設定）'}</span>
                <span className="text-xs text-gray-500 w-32 truncate hidden md:block">{p.customer_name_2 || p.customer_name_1 || '—'}</span>
                <span className="text-xs text-gray-500 w-24 hidden lg:block">{p.sales_person_name || '—'}</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${STATUS_COLORS[p.status] || 'bg-gray-100 text-gray-500'}`}>
                  {p.status || '—'}
                </span>
                <span className="text-xs text-gray-400 hidden xl:block w-20 shrink-0">{p.distribution_type || ''}</span>
                <span className="text-sm font-bold text-gray-700 w-32 text-right shrink-0">
                  {p.final_order_amount != null ? `¥${p.final_order_amount.toLocaleString()}` : '—'}
                </span>
                <span className="text-xs text-gray-400 w-6 text-center shrink-0">{p.order_count || 0}件</span>
                <div className="flex items-center gap-1 ml-2" onClick={e => e.stopPropagation()}>
                  <button onClick={() => openProjectEdit(p)} className="text-blue-400 hover:text-blue-600 p-1">
                    <Edit2 size={13} />
                  </button>
                  <button onClick={() => handleDeleteProject(p.id)} className="text-red-300 hover:text-red-500 p-1">
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              {/* 子一覧 */}
              {expanded && (
                <div className="bg-gray-50">
                  {/* 子ヘッダ */}
                  <div className="grid text-xs text-gray-400 px-10 py-1 border-b border-gray-100"
                    style={{ gridTemplateColumns: '140px 1fr 130px 90px 110px 110px 110px 110px 120px 60px' }}>
                    <span>案件ID_子</span><span>案件名</span><span>顧客名</span><span>担当者</span>
                    <span>引き合い日</span><span>受注予定日</span><span>出荷予定日</span><span>見積金額</span>
                    <span>紐付け見積</span><span></span>
                  </div>
                  {(p.orders || []).map((o: any) => (
                    <div key={o.id} className="grid items-center px-10 py-2 text-sm border-b border-gray-100 hover:bg-blue-50"
                      style={{ gridTemplateColumns: '140px 1fr 130px 90px 110px 110px 110px 110px 120px 60px' }}>
                      <span className="font-mono text-xs text-blue-600 font-medium">{o.child_no}</span>
                      <span className="truncate text-gray-700">{o.project_name || '—'}</span>
                      <span className="truncate text-gray-500 text-xs">{o.customer_name || o.agency_name || '—'}</span>
                      <span className="text-gray-500 text-xs">{o.sales_person_name || '—'}</span>
                      <span className="text-gray-400 text-xs">{o.inquiry_date || '—'}</span>
                      <span className="text-gray-400 text-xs">{o.expected_order_date || '—'}</span>
                      <span className="text-gray-400 text-xs">{o.expected_shipment_date || '—'}</span>
                      <span className="text-gray-700 font-medium text-xs">
                        {o.quotation_amount != null ? `¥${Number(o.quotation_amount).toLocaleString()}` : '—'}
                      </span>
                      <div className="flex flex-col gap-0.5">
                        {(o.linked_quotations || []).map((lq: any) => (
                          <span key={lq.id} className="text-xs text-purple-600 flex items-center gap-0.5">
                            <FileText size={10} />{lq.quotation_no}
                            {lq.quotation_total ? ` ¥${Number(lq.quotation_total).toLocaleString()}` : ''}
                          </span>
                        ))}
                        {(!o.linked_quotations || o.linked_quotations.length === 0) && (
                          <span className="text-xs text-gray-300">—</span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        <button onClick={() => openOrderEdit(p, o)} className="text-blue-400 hover:text-blue-600 p-0.5">
                          <Edit2 size={12} />
                        </button>
                        <button onClick={() => handleDeleteOrder(o.id)} className="text-red-300 hover:text-red-500 p-0.5">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                  {/* 子追加ボタン */}
                  <div className="px-10 py-2">
                    <button onClick={() => openOrderNew(p)}
                      className="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <Plus size={12} /> 子レコード追加
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {items.length === 0 && (
          <div className="bg-white rounded-xl shadow-sm text-center py-16 text-gray-400">案件データがありません</div>
        )}
      </div>

      {/* ===== 親モーダル ===== */}
      {projectModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
            <h2 className="text-lg font-bold text-gray-800 mb-4">
              {projectModal.isNew ? '新規案件登録' : '案件編集'}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Field label="案件ID_親 *" name="project_no" formSetter={setForm} formState={form} />
              <Field label="連番" name="seq_no" formSetter={setForm} formState={form} />
              <Field label="案件名" name="project_name" formSetter={setForm} formState={form} cols={2} />
              <Field label="案件概要" name="project_summary" formSetter={setForm} formState={form} cols={2} />
              <Field label="顧客ID_1（代理店）" name="customer_code_1" formSetter={setForm} formState={form} />
              <Field label="顧客名_1（代理店）" name="customer_name_1" formSetter={setForm} formState={form} />
              <Field label="顧客ID_2（エンドユーザー）" name="customer_code_2" formSetter={setForm} formState={form} />
              <Field label="顧客名_2（エンドユーザー）" name="customer_name_2" formSetter={setForm} formState={form} />
              <Field label="自社営業担当" name="sales_person_name" formSetter={setForm} formState={form} />
              <Field label="自社営業担当者ID" name="sales_person_code" formSetter={setForm} formState={form} />
              <SelectField label="案件ステータス" name="status" options={STATUS_OPTIONS} formSetter={setForm} formState={form} />
              <SelectField label="商流判定" name="distribution_type" options={DIST_OPTIONS} formSetter={setForm} formState={form} />
              <Field label="予算金額" name="budget_amount" type="number" formSetter={setForm} formState={form} />
              <Field label="見込売上合計（仕切りベース）" name="estimated_sales_total" type="number" formSetter={setForm} formState={form} />
              <Field label="最終受注金額" name="final_order_amount" type="number" formSetter={setForm} formState={form} />
              <Field label="案件原価" name="cost_price" type="number" formSetter={setForm} formState={form} />
              <Field label="利益額" name="profit_amount" type="number" formSetter={setForm} formState={form} />
              <Field label="利益率" name="profit_rate" type="number" formSetter={setForm} formState={form} />
              <Field label="引き合い日" name="inquiry_date" type="date" formSetter={setForm} formState={form} />
              <Field label="顧客納期/売上計上日" name="sales_date" type="date" formSetter={setForm} formState={form} />
              <Field label="社内出図希望日" name="drawing_request_date" type="date" formSetter={setForm} formState={form} />
              <Field label="受注日" name="order_date" type="date" formSetter={setForm} formState={form} />
              <Field label="受注予定日" name="expected_order_date" type="date" formSetter={setForm} formState={form} />
              <Field label="出荷予定日" name="expected_shipment_date" type="date" formSetter={setForm} formState={form} />
              <Field label="作成日" name="created_date" type="date" formSetter={setForm} formState={form} />
              <div className="md:col-span-2">
                <label className="block text-xs text-gray-500 mb-1">備考</label>
                <textarea value={form.notes || ''} rows={2}
                  onChange={e => setForm((f: any) => ({ ...f, notes: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setProjectModal(null)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">キャンセル</button>
              <button onClick={handleSaveProject} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">保存</button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 子モーダル ===== */}
      {orderModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
            <h2 className="text-lg font-bold text-gray-800 mb-1">
              {orderModal.order ? '子レコード編集' : '子レコード追加'}
            </h2>
            <p className="text-sm text-gray-500 mb-4">案件: {orderModal.project.project_no} {orderModal.project.project_name}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Field label="案件ID_子（省略時は自動採番）" name="child_no" formSetter={setOrderForm} formState={orderForm} cols={2} />
              <Field label="案件名" name="project_name" formSetter={setOrderForm} formState={orderForm} cols={2} />
              <Field label="案件概要" name="project_summary" formSetter={setOrderForm} formState={orderForm} cols={2} />
              <Field label="顧客ID" name="customer_code" formSetter={setOrderForm} formState={orderForm} />
              <Field label="顧客名（エンドユーザー）" name="customer_name" formSetter={setOrderForm} formState={orderForm} />
              <Field label="代理店ID" name="agency_code" formSetter={setOrderForm} formState={orderForm} />
              <Field label="代理店名" name="agency_name" formSetter={setOrderForm} formState={orderForm} />
              <Field label="自社営業担当" name="sales_person_name" formSetter={setOrderForm} formState={orderForm} />
              <Field label="自社営業担当ID" name="sales_person_code" formSetter={setOrderForm} formState={orderForm} />
              <SelectField label="ステータス" name="status" options={STATUS_OPTIONS} formSetter={setOrderForm} formState={orderForm} />
              <Field label="見積金額（見積書引用）" name="quotation_amount" type="number" formSetter={setOrderForm} formState={orderForm} />
              <Field label="予算金額（親参照）" name="budget_amount" type="number" formSetter={setOrderForm} formState={orderForm} />
              <Field label="引き合い日" name="inquiry_date" type="date" formSetter={setOrderForm} formState={orderForm} />
              <Field label="顧客納期/売上計上日" name="sales_date" type="date" formSetter={setOrderForm} formState={orderForm} />
              <Field label="受注日" name="order_date" type="date" formSetter={setOrderForm} formState={orderForm} />
              <Field label="受注予定日" name="expected_order_date" type="date" formSetter={setOrderForm} formState={orderForm} />
              <Field label="出荷日" name="shipment_date" type="date" formSetter={setOrderForm} formState={orderForm} />
              <Field label="出荷予定日" name="expected_shipment_date" type="date" formSetter={setOrderForm} formState={orderForm} />
              {/* 見積紐付け（主） */}
              <div className="md:col-span-2 border-t pt-3 mt-1">
                <p className="text-xs font-medium text-gray-600 mb-2">紐付け見積（主）</p>
                <div className="grid grid-cols-3 gap-2">
                  <Field label="見積NO" name="quotation_no" formSetter={setOrderForm} formState={orderForm} />
                  <Field label="見積総計" name="quotation_total" type="number" formSetter={setOrderForm} formState={orderForm} />
                  <Field label="見積発行日" name="quotation_issue_date" type="date" formSetter={setOrderForm} formState={orderForm} />
                </div>
              </div>
              <div className="md:col-span-2">
                <label className="block text-xs text-gray-500 mb-1">備考</label>
                <textarea value={orderForm.notes || ''} rows={2}
                  onChange={e => setOrderForm((f: any) => ({ ...f, notes: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setOrderModal(null)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">キャンセル</button>
              <button onClick={handleSaveOrder} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
