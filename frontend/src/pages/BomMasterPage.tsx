import { useEffect, useState } from 'react';
import { bomMasterApi, procurementApi } from '../api';
import OrderSearchInput from '../components/common/OrderSearchInput';
import { Plus, Trash2, Edit2, Check, X, ChevronRight, Package, Boxes, GitBranch } from 'lucide-react';

const PRODUCT_TYPES = ['BFR', 'BFP', 'SCA', 'LCA', 'SRR', 'FLT', 'CY', 'LRG'];
const UNIT_TYPES = ['本体', 'ファン', 'RV', 'サイクロン', 'ダンパー', '架台', 'その他'];

export default function BomMasterPage() {
  const [tab, setTab] = useState<'products' | 'units' | 'product-bom' | 'unit-bom' | 'expand'>('products');

  return (
    <div className="p-4">
      <h1 className="text-xl font-bold text-gray-800 mb-4">製品BOMマスタ（製品 → ユニット → 部品）</h1>
      <div className="flex gap-1 mb-5 border-b border-gray-200 flex-wrap">
        {([
          ['products', '製品マスタ'], ['units', 'ユニットマスタ'],
          ['product-bom', '製品構成（製品→ユニット）'], ['unit-bom', 'ユニット構成（ユニット→部品）'],
          ['expand', '案件展開'],
        ] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === key ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'products' && <ProductMasterTab />}
      {tab === 'units' && <UnitMasterTab />}
      {tab === 'product-bom' && <ProductBomTab />}
      {tab === 'unit-bom' && <UnitBomTab />}
      {tab === 'expand' && <ExpandTab />}
    </div>
  );
}

// ========== 製品マスタ ==========
function ProductMasterTab() {
  const [items, setItems] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<any>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<any>({});

  const load = () => bomMasterApi.listProducts().then(r => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.product_code || !form.product_name) { alert('製品コードと製品名は必須です'); return; }
    await bomMasterApi.createProduct(form); setShowAdd(false); setForm({}); load();
  };
  const save = async (id: string) => { await bomMasterApi.updateProduct(id, editForm); setEditing(null); load(); };
  const del = async (id: string) => { if (confirm('削除しますか？')) { await bomMasterApi.deleteProduct(id); load(); } };

  return (
    <div>
      <div className="flex mb-3">
        <button onClick={() => setShowAdd(!showAdd)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700">
          <Plus size={14} />製品追加
        </button>
      </div>
      {showAdd && (
        <div className="mb-4 p-3 border border-indigo-200 rounded-lg bg-indigo-50 flex flex-wrap gap-2 items-end">
          <Field label="製品コード*" v={form.product_code} on={(v: string) => setForm({ ...form, product_code: v })} w="w-32" />
          <Field label="製品名*" v={form.product_name} on={(v: string) => setForm({ ...form, product_name: v })} w="w-48" />
          <SelectField label="種別" v={form.product_type} opts={PRODUCT_TYPES} on={(v: string) => setForm({ ...form, product_type: v })} />
          <Field label="代表型式" v={form.model_no} on={(v: string) => setForm({ ...form, model_no: v })} w="w-24" />
          <Field label="標準販売単価" v={form.standard_price} on={(v: string) => setForm({ ...form, standard_price: v ? Number(v) : null })} w="w-28" type="number" />
          <Field label="標準工数(h)" v={form.standard_hours} on={(v: string) => setForm({ ...form, standard_hours: v ? Number(v) : null })} w="w-20" type="number" />
          <button onClick={add} className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded"><Check size={14} /></button>
          <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 border text-sm rounded"><X size={14} /></button>
        </div>
      )}
      <table className="w-full text-xs border-collapse">
        <thead><tr className="bg-gray-50">
          {['製品コード', '製品名', '種別', '代表型式', '標準販売単価', '標準工数', 'ユニット数', ''].map(h =>
            <th key={h} className="border border-gray-200 px-2 py-2 text-left font-medium text-gray-600">{h}</th>)}
        </tr></thead>
        <tbody>
          {items.length === 0 ? <tr><td colSpan={8} className="text-center py-8 text-gray-400">製品マスタなし</td></tr>
            : items.map(p => editing === p.id ? (
              <tr key={p.id} className="bg-yellow-50">
                <td className="border px-1 py-1"><input className="border rounded px-1 w-24" value={editForm.product_code} onChange={e => setEditForm({ ...editForm, product_code: e.target.value })} /></td>
                <td className="border px-1 py-1"><input className="border rounded px-1 w-40" value={editForm.product_name} onChange={e => setEditForm({ ...editForm, product_name: e.target.value })} /></td>
                <td className="border px-1 py-1">{editForm.product_type}</td>
                <td className="border px-1 py-1"><input className="border rounded px-1 w-20" value={editForm.model_no || ''} onChange={e => setEditForm({ ...editForm, model_no: e.target.value })} /></td>
                <td className="border px-1 py-1"><input type="number" className="border rounded px-1 w-24 text-right" value={editForm.standard_price ?? ''} onChange={e => setEditForm({ ...editForm, standard_price: e.target.value ? Number(e.target.value) : null })} /></td>
                <td className="border px-1 py-1"><input type="number" className="border rounded px-1 w-16 text-right" value={editForm.standard_hours ?? ''} onChange={e => setEditForm({ ...editForm, standard_hours: e.target.value ? Number(e.target.value) : null })} /></td>
                <td className="border px-2 py-1 text-center">{p.unit_count}</td>
                <td className="border px-1 py-1 whitespace-nowrap">
                  <button onClick={() => save(p.id)} className="text-green-600 mr-1"><Check size={14} /></button>
                  <button onClick={() => setEditing(null)} className="text-gray-400"><X size={14} /></button>
                </td>
              </tr>
            ) : (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="border px-2 py-1.5 font-mono font-bold text-indigo-700">{p.product_code}</td>
                <td className="border px-2 py-1.5">{p.product_name}</td>
                <td className="border px-2 py-1.5">{p.product_type || '—'}</td>
                <td className="border px-2 py-1.5">{p.model_no || '—'}</td>
                <td className="border px-2 py-1.5 text-right">{p.standard_price != null ? `¥${p.standard_price.toLocaleString()}` : '—'}</td>
                <td className="border px-2 py-1.5 text-right">{p.standard_hours ?? '—'}</td>
                <td className="border px-2 py-1.5 text-center">{p.unit_count}</td>
                <td className="border px-1 py-1.5 whitespace-nowrap">
                  <button onClick={() => { setEditing(p.id); setEditForm(p); }} className="text-blue-500 mr-2"><Edit2 size={13} /></button>
                  <button onClick={() => del(p.id)} className="text-red-400"><Trash2 size={13} /></button>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

// ========== ユニットマスタ ==========
function UnitMasterTab() {
  const [items, setItems] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<any>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<any>({});

  const load = () => bomMasterApi.listUnits().then(r => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.unit_code || !form.unit_name) { alert('ユニットコードとユニット名は必須です'); return; }
    await bomMasterApi.createUnit(form); setShowAdd(false); setForm({}); load();
  };
  const save = async (id: string) => { await bomMasterApi.updateUnit(id, editForm); setEditing(null); load(); };
  const del = async (id: string) => { if (confirm('削除しますか？')) { await bomMasterApi.deleteUnit(id); load(); } };

  return (
    <div>
      <div className="flex mb-3">
        <button onClick={() => setShowAdd(!showAdd)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700">
          <Plus size={14} />ユニット追加
        </button>
      </div>
      {showAdd && (
        <div className="mb-4 p-3 border border-indigo-200 rounded-lg bg-indigo-50 flex flex-wrap gap-2 items-end">
          <Field label="ユニットコード*" v={form.unit_code} on={(v: string) => setForm({ ...form, unit_code: v })} w="w-32" />
          <Field label="ユニット名*" v={form.unit_name} on={(v: string) => setForm({ ...form, unit_name: v })} w="w-48" />
          <SelectField label="種別" v={form.unit_type} opts={UNIT_TYPES} on={(v: string) => setForm({ ...form, unit_type: v })} />
          <Field label="型式" v={form.model_no} on={(v: string) => setForm({ ...form, model_no: v })} w="w-24" />
          <Field label="標準販売単価" v={form.standard_price} on={(v: string) => setForm({ ...form, standard_price: v ? Number(v) : null })} w="w-28" type="number" />
          <Field label="標準工数(h)" v={form.standard_hours} on={(v: string) => setForm({ ...form, standard_hours: v ? Number(v) : null })} w="w-20" type="number" />
          <button onClick={add} className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded"><Check size={14} /></button>
          <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 border text-sm rounded"><X size={14} /></button>
        </div>
      )}
      <table className="w-full text-xs border-collapse">
        <thead><tr className="bg-gray-50">
          {['ユニットコード', 'ユニット名', '種別', '型式', '標準販売単価', '標準工数', '部品数', ''].map(h =>
            <th key={h} className="border border-gray-200 px-2 py-2 text-left font-medium text-gray-600">{h}</th>)}
        </tr></thead>
        <tbody>
          {items.length === 0 ? <tr><td colSpan={8} className="text-center py-8 text-gray-400">ユニットマスタなし</td></tr>
            : items.map(u => editing === u.id ? (
              <tr key={u.id} className="bg-yellow-50">
                <td className="border px-1 py-1"><input className="border rounded px-1 w-24" value={editForm.unit_code} onChange={e => setEditForm({ ...editForm, unit_code: e.target.value })} /></td>
                <td className="border px-1 py-1"><input className="border rounded px-1 w-40" value={editForm.unit_name} onChange={e => setEditForm({ ...editForm, unit_name: e.target.value })} /></td>
                <td className="border px-1 py-1">{editForm.unit_type}</td>
                <td className="border px-1 py-1"><input className="border rounded px-1 w-20" value={editForm.model_no || ''} onChange={e => setEditForm({ ...editForm, model_no: e.target.value })} /></td>
                <td className="border px-1 py-1"><input type="number" className="border rounded px-1 w-24 text-right" value={editForm.standard_price ?? ''} onChange={e => setEditForm({ ...editForm, standard_price: e.target.value ? Number(e.target.value) : null })} /></td>
                <td className="border px-1 py-1"><input type="number" className="border rounded px-1 w-16 text-right" value={editForm.standard_hours ?? ''} onChange={e => setEditForm({ ...editForm, standard_hours: e.target.value ? Number(e.target.value) : null })} /></td>
                <td className="border px-2 py-1 text-center">{u.material_count}</td>
                <td className="border px-1 py-1 whitespace-nowrap">
                  <button onClick={() => save(u.id)} className="text-green-600 mr-1"><Check size={14} /></button>
                  <button onClick={() => setEditing(null)} className="text-gray-400"><X size={14} /></button>
                </td>
              </tr>
            ) : (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="border px-2 py-1.5 font-mono font-bold text-sky-700">{u.unit_code}</td>
                <td className="border px-2 py-1.5">{u.unit_name}</td>
                <td className="border px-2 py-1.5">{u.unit_type || '—'}</td>
                <td className="border px-2 py-1.5">{u.model_no || '—'}</td>
                <td className="border px-2 py-1.5 text-right">{u.standard_price != null ? `¥${u.standard_price.toLocaleString()}` : '—'}</td>
                <td className="border px-2 py-1.5 text-right">{u.standard_hours ?? '—'}</td>
                <td className="border px-2 py-1.5 text-center">{u.material_count}</td>
                <td className="border px-1 py-1.5 whitespace-nowrap">
                  <button onClick={() => { setEditing(u.id); setEditForm(u); }} className="text-blue-500 mr-2"><Edit2 size={13} /></button>
                  <button onClick={() => del(u.id)} className="text-red-400"><Trash2 size={13} /></button>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

// ========== 製品構成BOM（製品→ユニット）==========
function ProductBomTab() {
  const [products, setProducts] = useState<any[]>([]);
  const [units, setUnits] = useState<any[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [rows, setRows] = useState<any[]>([]);
  const [addUnitId, setAddUnitId] = useState('');
  const [addQty, setAddQty] = useState('1');

  useEffect(() => {
    bomMasterApi.listProducts().then(r => setProducts(r.data)).catch(() => {});
    bomMasterApi.listUnits().then(r => setUnits(r.data)).catch(() => {});
  }, []);
  const loadRows = (pid: string) => bomMasterApi.listProductUnits(pid).then(r => setRows(r.data)).catch(() => {});
  useEffect(() => { if (selected) loadRows(selected); else setRows([]); }, [selected]);

  const add = async () => {
    if (!addUnitId) return;
    await bomMasterApi.addProductUnit({ product_id: selected, unit_id: addUnitId, quantity: Number(addQty) || 1, sort_order: rows.length });
    setAddUnitId(''); setAddQty('1'); loadRows(selected);
  };
  const updateQty = async (id: string, q: string) => { await bomMasterApi.updateProductUnit(id, { quantity: Number(q) || 1 }); loadRows(selected); };
  const del = async (id: string) => { await bomMasterApi.deleteProductUnit(id); loadRows(selected); };

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <Package size={16} className="text-indigo-600" />
        <label className="text-sm text-gray-600">製品を選択:</label>
        <select value={selected} onChange={e => setSelected(e.target.value)} className="border rounded px-2 py-1.5 text-sm min-w-[300px]">
          <option value="">— 製品を選択 —</option>
          {products.map(p => <option key={p.id} value={p.id}>{p.product_code} / {p.product_name}</option>)}
        </select>
      </div>
      {selected && (
        <div className="bg-white border rounded-lg p-4">
          <div className="flex items-end gap-2 mb-3 pb-3 border-b">
            <div className="flex-1">
              <label className="block text-xs text-gray-500 mb-1">ユニットを追加</label>
              <select value={addUnitId} onChange={e => setAddUnitId(e.target.value)} className="w-full border rounded px-2 py-1.5 text-sm">
                <option value="">— ユニット選択 —</option>
                {units.map(u => <option key={u.id} value={u.id}>{u.unit_code} / {u.unit_name}（{u.unit_type || '—'}）</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">員数</label>
              <input type="number" value={addQty} onChange={e => setAddQty(e.target.value)} className="border rounded px-2 py-1.5 text-sm w-20" />
            </div>
            <button onClick={add} className="flex items-center gap-1 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700"><Plus size={14} />追加</button>
          </div>
          <table className="w-full text-xs border-collapse">
            <thead><tr className="bg-gray-50">
              {['ユニットコード', 'ユニット名', '種別', '型式', '員数', ''].map(h => <th key={h} className="border px-2 py-2 text-left font-medium text-gray-600">{h}</th>)}
            </tr></thead>
            <tbody>
              {rows.length === 0 ? <tr><td colSpan={6} className="text-center py-6 text-gray-400">構成ユニットなし</td></tr>
                : rows.map(r => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="border px-2 py-1.5 font-mono text-sky-700">{r.unit_code}</td>
                    <td className="border px-2 py-1.5">{r.unit_name}</td>
                    <td className="border px-2 py-1.5">{r.unit_type || '—'}</td>
                    <td className="border px-2 py-1.5">{r.model_no || '—'}</td>
                    <td className="border px-2 py-1.5 w-24"><input type="number" defaultValue={r.quantity} onBlur={e => updateQty(r.id, e.target.value)} className="border rounded px-1 w-16 text-right" /></td>
                    <td className="border px-1 py-1.5"><button onClick={() => del(r.id)} className="text-red-400"><Trash2 size={13} /></button></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ========== ユニット構成BOM（ユニット→部品）==========
function UnitBomTab() {
  const [units, setUnits] = useState<any[]>([]);
  const [materials, setMaterials] = useState<any[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [rows, setRows] = useState<any[]>([]);
  const [addMatId, setAddMatId] = useState('');
  const [addQty, setAddQty] = useState('1');

  useEffect(() => {
    bomMasterApi.listUnits().then(r => setUnits(r.data)).catch(() => {});
    procurementApi.listMaterials().then(r => setMaterials(r.data)).catch(() => {});
  }, []);
  const loadRows = (uid: string) => bomMasterApi.listUnitMaterials(uid).then(r => setRows(r.data)).catch(() => {});
  useEffect(() => { if (selected) loadRows(selected); else setRows([]); }, [selected]);

  const add = async () => {
    if (!addMatId) return;
    await bomMasterApi.addUnitMaterial({ unit_id: selected, material_id: addMatId, quantity: Number(addQty) || 1, sort_order: rows.length });
    setAddMatId(''); setAddQty('1'); loadRows(selected);
  };
  const updateQty = async (id: string, q: string) => { await bomMasterApi.updateUnitMaterial(id, { quantity: Number(q) || 1 }); loadRows(selected); };
  const del = async (id: string) => { await bomMasterApi.deleteUnitMaterial(id); loadRows(selected); };

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <Boxes size={16} className="text-sky-600" />
        <label className="text-sm text-gray-600">ユニットを選択:</label>
        <select value={selected} onChange={e => setSelected(e.target.value)} className="border rounded px-2 py-1.5 text-sm min-w-[300px]">
          <option value="">— ユニットを選択 —</option>
          {units.map(u => <option key={u.id} value={u.id}>{u.unit_code} / {u.unit_name}</option>)}
        </select>
      </div>
      {selected && (
        <div className="bg-white border rounded-lg p-4">
          <div className="flex items-end gap-2 mb-3 pb-3 border-b">
            <div className="flex-1">
              <label className="block text-xs text-gray-500 mb-1">部品（原材料）を追加</label>
              <select value={addMatId} onChange={e => setAddMatId(e.target.value)} className="w-full border rounded px-2 py-1.5 text-sm">
                <option value="">— 部品選択 —</option>
                {materials.map(m => <option key={m.id} value={m.id}>{m.material_code} / {m.material_name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">員数</label>
              <input type="number" value={addQty} onChange={e => setAddQty(e.target.value)} className="border rounded px-2 py-1.5 text-sm w-20" />
            </div>
            <button onClick={add} className="flex items-center gap-1 px-3 py-1.5 bg-sky-600 text-white text-sm rounded hover:bg-sky-700"><Plus size={14} />追加</button>
          </div>
          <table className="w-full text-xs border-collapse">
            <thead><tr className="bg-gray-50">
              {['部材コード', '部材名', '員数', '単位', ''].map(h => <th key={h} className="border px-2 py-2 text-left font-medium text-gray-600">{h}</th>)}
            </tr></thead>
            <tbody>
              {rows.length === 0 ? <tr><td colSpan={5} className="text-center py-6 text-gray-400">構成部品なし</td></tr>
                : rows.map(r => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="border px-2 py-1.5 font-mono text-amber-700">{r.material_code}</td>
                    <td className="border px-2 py-1.5">{r.material_name}</td>
                    <td className="border px-2 py-1.5 w-24"><input type="number" defaultValue={r.quantity} onBlur={e => updateQty(r.id, e.target.value)} className="border rounded px-1 w-16 text-right" /></td>
                    <td className="border px-2 py-1.5">{r.unit || '—'}</td>
                    <td className="border px-1 py-1.5"><button onClick={() => del(r.id)} className="text-red-400"><Trash2 size={13} /></button></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ========== 案件展開 ==========
function ExpandTab() {
  const [order, setOrder] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [selProduct, setSelProduct] = useState('');
  const [qty, setQty] = useState('1');
  const [genOrders, setGenOrders] = useState(true);
  const [tree, setTree] = useState<any[]>([]);
  const [msg, setMsg] = useState('');

  useEffect(() => { bomMasterApi.listProducts().then(r => setProducts(r.data)).catch(() => {}); }, []);
  const loadTree = (oid: string) => bomMasterApi.projectTree(oid).then(r => setTree(r.data.products || [])).catch(() => {});

  const onSelectOrder = (o: any) => { setOrder(o); loadTree(o.id); };

  const doExpand = async () => {
    if (!order || !selProduct) { alert('案件子IDと製品を選択してください'); return; }
    try {
      const r = await bomMasterApi.expand({ project_order_id: order.id, product_master_id: selProduct, quantity: Number(qty) || 1, generate_orders: genOrders });
      setMsg(`✓ ${r.data.message}`);
      loadTree(order.id);
    } catch (e: any) { setMsg(`❌ ${e.response?.data?.detail || 'エラー'}`); }
  };

  const delProduct = async (id: string) => {
    if (!confirm('この製品NO（配下のユニット・発注含む）を削除しますか？')) return;
    await bomMasterApi.deleteProjectProduct(id); loadTree(order.id);
  };
  const setUnitStatus = async (id: string, status: string) => { await bomMasterApi.updateProjectUnit(id, { status }); loadTree(order.id); };

  const STATUS_COLOR: Record<string, string> = { '計画': 'bg-gray-100 text-gray-600', '製造中': 'bg-blue-100 text-blue-700', '完了': 'bg-green-100 text-green-700' };

  return (
    <div>
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 mb-4">
        <p className="text-xs font-semibold text-indigo-700 mb-2">案件ID または 子ID を選択して、製品マスタを展開（製品NO / ユニットNO / 発注NO を採番）</p>
        <OrderSearchInput onSelect={onSelectOrder} placeholder="案件ID または 子ID で検索" />
        {order && (
          <div className="mt-3 flex flex-wrap items-end gap-2 pt-3 border-t border-indigo-200">
            <div className="flex-1 min-w-[260px]">
              <label className="block text-xs text-gray-500 mb-1">展開する製品</label>
              <select value={selProduct} onChange={e => setSelProduct(e.target.value)} className="w-full border rounded px-2 py-1.5 text-sm">
                <option value="">— 製品を選択 —</option>
                {products.map(p => <option key={p.id} value={p.id}>{p.product_code} / {p.product_name}（ユニット{p.unit_count}件）</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">台数</label>
              <input type="number" value={qty} onChange={e => setQty(e.target.value)} className="border rounded px-2 py-1.5 text-sm w-20" />
            </div>
            <label className="flex items-center gap-1.5 text-sm text-gray-600 pb-1.5">
              <input type="checkbox" checked={genOrders} onChange={e => setGenOrders(e.target.checked)} />部材発注も自動起票
            </label>
            <button onClick={doExpand} className="flex items-center gap-1 px-4 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700">
              <GitBranch size={14} />展開
            </button>
            {msg && <span className={`text-xs ${msg.startsWith('✓') ? 'text-green-700' : 'text-red-500'}`}>{msg}</span>}
          </div>
        )}
      </div>

      {order && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">{order.child_no} の構成ツリー</h3>
          {tree.length === 0 ? <p className="text-sm text-gray-400 py-6 text-center border rounded-lg">まだ展開された製品はありません</p>
            : tree.map(p => (
              <div key={p.id} className="mb-3 border rounded-lg overflow-hidden">
                <div className="flex items-center gap-2 bg-indigo-50 px-3 py-2 border-b">
                  <Package size={14} className="text-indigo-600" />
                  <span className="font-mono font-bold text-indigo-700 text-sm">{p.product_no}</span>
                  <span className="text-sm text-gray-700">{p.product_name}</span>
                  <span className="text-xs text-gray-400">{p.product_type} / {p.model_no || '—'} × {p.quantity}台</span>
                  <button onClick={() => delProduct(p.id)} className="ml-auto text-red-400"><Trash2 size={13} /></button>
                </div>
                <div className="divide-y">
                  {p.units.length === 0 ? <p className="px-4 py-2 text-xs text-gray-400">ユニットなし（製品構成BOM未登録）</p>
                    : p.units.map((u: any) => (
                      <div key={u.id} className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <ChevronRight size={13} className="text-gray-300" />
                          <Boxes size={13} className="text-sky-600" />
                          <span className="font-mono font-bold text-sky-700 text-xs">{u.unit_no}</span>
                          <span className="text-xs text-gray-700">{u.unit_name}</span>
                          <span className="text-xs text-gray-400">{u.unit_type || '—'} × {u.quantity}</span>
                          <select value={u.status} onChange={e => setUnitStatus(u.id, e.target.value)}
                            className={`ml-auto text-xs rounded px-2 py-0.5 border-0 ${STATUS_COLOR[u.status] || ''}`}>
                            {['計画', '製造中', '完了'].map(s => <option key={s} value={s}>{s}</option>)}
                          </select>
                        </div>
                        {u.orders.length > 0 && (
                          <div className="ml-8 mt-1 flex flex-wrap gap-1.5">
                            {u.orders.map((o: any) => (
                              <span key={o.id} className="inline-flex items-center gap-1 text-xs bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5">
                                <span className="font-mono text-amber-700">{o.order_no}</span>
                                <span className="text-gray-600">{o.material_name}</span>
                                <span className="text-gray-400">×{o.order_qty}</span>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

// ========== 共通フィールド ==========
function Field({ label, v, on, w = 'w-32', type = 'text' }: any) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-0.5">{label}</label>
      <input type={type} value={v ?? ''} onChange={e => on(e.target.value)} className={`border rounded px-2 py-1 text-sm ${w}`} />
    </div>
  );
}
function SelectField({ label, v, opts, on }: any) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-0.5">{label}</label>
      <select value={v ?? ''} onChange={e => on(e.target.value)} className="border rounded px-2 py-1 text-sm">
        <option value="">-</option>
        {opts.map((o: string) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
