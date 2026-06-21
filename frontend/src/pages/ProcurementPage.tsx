import { useEffect, useState } from 'react';
import { procurementApi } from '../api';
import { Plus, Trash2, Edit2, Check, X, Search } from 'lucide-react';

const STATUS_OPTIONS = ['未発注', '発注済', '入荷済'];
const STATUS_COLORS: Record<string, string> = {
  '未発注': 'bg-yellow-100 text-yellow-700',
  '発注済': 'bg-blue-100 text-blue-700',
  '入荷済': 'bg-green-100 text-green-700',
};

const PRODUCT_TYPES = ['BFR', 'BFP', 'SCA', 'LCA', 'SRR', 'FLT', 'CY', 'LRG'];

export default function ProcurementPage() {
  const [tab, setTab] = useState<'orders' | 'materials' | 'bom'>('orders');

  return (
    <div className="p-4">
      <h1 className="text-xl font-bold text-gray-800 mb-4">仕入（発注）管理</h1>
      <div className="flex gap-1 mb-5 border-b border-gray-200">
        {([['orders', '発注管理'], ['materials', '部材マスタ'], ['bom', 'BOMマスタ']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'orders' && <OrdersTab />}
      {tab === 'materials' && <MaterialsTab />}
      {tab === 'bom' && <BomTab />}
    </div>
  );
}

// ========== 発注管理タブ ==========
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

  const load = () => {
    setLoading(true);
    Promise.all([
      procurementApi.listMaterialOrders(undefined, statusFilter || undefined),
      procurementApi.listMaterials(),
      procurementApi.listSuppliers(),
    ]).then(([o, m, s]) => {
      setOrders(o.data); setMaterials(m.data); setSuppliers(s.data);
    }).catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [statusFilter]);

  const handleSave = async (id: string) => {
    await procurementApi.updateMaterialOrder(id, editData);
    setEditing(null); load();
  };
  const handleAdd = async () => {
    await procurementApi.createMaterialOrder(newData);
    setShowAdd(false); setNewData({ status: '未発注' }); load();
  };
  const handleDelete = async (id: string) => {
    if (!confirm('削除しますか？')) return;
    await procurementApi.deleteMaterialOrder(id); load();
  };

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border rounded px-2 py-1 text-sm">
          <option value="">全ステータス</option>
          {STATUS_OPTIONS.map(s => <option key={s}>{s}</option>)}
        </select>
        <button onClick={() => setShowAdd(true)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
          <Plus size={14} />新規発注
        </button>
      </div>

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

  const load = () => Promise.all([
    procurementApi.listMaterials(search || undefined),
    procurementApi.listSuppliers(),
  ]).then(([m, s]) => { setMaterials(m.data); setSuppliers(s.data); });

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

  const Field = ({ label, children }: any) => (
    <div><label className="block text-xs text-gray-500 mb-0.5">{label}</label>{children}</div>
  );

  return (
    <div>
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

  const load = () => Promise.all([
    procurementApi.listBom(filterType || undefined),
    procurementApi.listMaterials(),
  ]).then(([b, m]) => { setBoms(b.data); setMaterials(m.data); });

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
