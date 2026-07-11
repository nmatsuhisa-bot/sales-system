import { useEffect, useState } from 'react';
import { bomMasterApi, procurementApi } from '../api';
import { Plus, Trash2, Edit2, Check, X, Package, Boxes, Download } from 'lucide-react';

const PRODUCT_TYPES = ['BFR', 'BFP', 'SCA', 'LCA', 'SRR', 'FLT', 'CY', 'LRG'];
const UNIT_TYPES = ['本体', 'ファン', 'RV', 'サイクロン', 'ダンパー', '架台', 'その他'];

export default function BomMasterPage() {
  const [tab, setTab] = useState<'products' | 'units' | 'product-bom' | 'unit-bom' | 'materials'>('products');
  const [seeding, setSeeding] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const seed = async () => {
    if (!confirm('既存の見積パターン（BFR本体・ファン・RV・SCA本体・PLファン・サイクロン・自動ダンパー）を製品/ユニットマスタへ取込みます。\n既存コードはスキップされます。実行しますか？')) return;
    setSeeding(true);
    try {
      const r = await bomMasterApi.seedFromEstimatePatterns();
      alert(r.data.message);
      setReloadKey(k => k + 1);
    } catch (e: any) { alert(e.response?.data?.detail || 'エラー'); }
    finally { setSeeding(false); }
  };

  const delSample = async () => {
    try {
      const c = await bomMasterApi.sampleCount();
      if (!confirm(`サンプル取込データを削除します。\n部品マスタ ${c.data.materials}件 / ユニット ${c.data.units}件 が対象です。\nよろしいですか？`)) return;
      const r = await bomMasterApi.deleteSampleData();
      alert(`削除しました（部品 ${r.data.deleted_materials}件 / ユニット ${r.data.deleted_units}件）`);
      setReloadKey(k => k + 1);
    } catch (e: any) { alert(e.response?.data?.detail || 'エラー'); }
  };

  return (
    <div className="p-4">
      <div className="flex items-start justify-between mb-1 gap-2">
        <h1 className="text-xl font-bold text-gray-800">製品BOMマスタ（型式 → ユニット → 部材）</h1>
        <div className="flex gap-2 shrink-0">
          <button onClick={delSample}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-red-300 text-red-600 text-sm rounded hover:bg-red-50">
            <Trash2 size={14} />サンプル削除
          </button>
          <button onClick={seed} disabled={seeding}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white text-sm rounded hover:bg-emerald-700 disabled:opacity-60">
            <Download size={14} />{seeding ? '取込中...' : '見積パターンから取込'}
          </button>
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-4">型式・ユニット・部材の紐付けを定義します。型式は「見積パターンから取込」で既存の見積パターン（BFR本体・ファン等）から一括登録できます。各ユニットに部材を紐付けると、仕入管理の「見積内訳から発注書作成」で部材が自動展開されます。部材そのものの台帳は「部材マスタ」タブで管理します。</p>
      <div className="flex gap-1 mb-5 border-b border-gray-200 flex-wrap">
        {([
          ['products', '製品マスタ'], ['units', 'ユニットマスタ'],
          ['product-bom', '製品構成（製品→ユニット）'], ['unit-bom', 'ユニット構成（ユニット→部品）'],
          ['materials', '部材マスタ'],
        ] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === key ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'products' && <ProductMasterTab reloadKey={reloadKey} />}
      {tab === 'units' && <UnitMasterTab reloadKey={reloadKey} />}
      {tab === 'product-bom' && <ProductBomTab />}
      {tab === 'unit-bom' && <UnitBomTab />}
      {tab === 'materials' && <MaterialsTab />}
    </div>
  );
}

// ========== 製品マスタ ==========
function ProductMasterTab({ reloadKey }: { reloadKey: number }) {
  const [items, setItems] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<any>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<any>({});

  const load = () => bomMasterApi.listProducts().then(r => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, [reloadKey]);

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
function UnitMasterTab({ reloadKey }: { reloadKey: number }) {
  const [items, setItems] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<any>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<any>({});

  const load = () => bomMasterApi.listUnits().then(r => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, [reloadKey]);

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

// ========== 共通フィールド ==========
// ========== 部材マスタ（仕入管理から集約） ==========
function MaterialsTab() {
  const [materials, setMaterials] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [editData, setEditData] = useState<any>({});
  const [showAdd, setShowAdd] = useState(false);
  const [newData, setNewData] = useState<any>({ unit: '個', standard_lead_days: 14 });
  const [error, setError] = useState('');

  const load = () => { setError('');
    return Promise.all([
      procurementApi.listMaterials(search || undefined),
      procurementApi.listSuppliers(),
    ]).then(([m, s]) => { setMaterials(m.data); setSuppliers(s.data); })
      .catch((e) => { setError('部材マスタの取得に失敗しました（' + (e?.response?.status || e?.message || 'error') + '）。'); });
  };
  useEffect(() => { load(); }, [search]);

  const handleAdd = async () => {
    if (!newData.material_code || !newData.material_name) { alert('部材コードと部材名は必須です'); return; }
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

  return (
    <div>
      <p className="text-xs text-gray-500 mb-2">部材（部品）の台帳です。ユニット構成・発注書の明細から参照されます。優先仕入先を設定すると発注書作成時に自動セットされます。</p>
      {error && <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded">{error}</div>}
      <div className="flex items-center gap-2 mb-3">
        <input placeholder="部材名・コードで検索" value={search} onChange={e => setSearch(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm w-56" />
        <span className="text-xs text-gray-500">{materials.length}件</span>
        <button onClick={() => setShowAdd(true)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700">
          <Plus size={14} />部材追加
        </button>
      </div>

      {showAdd && (
        <div className="mb-4 p-3 border border-indigo-200 rounded-lg bg-indigo-50 flex flex-wrap gap-2 items-end">
          <Field label="部材コード*" v={newData.material_code} on={(v: string) => setNewData({ ...newData, material_code: v })} w="w-28" />
          <Field label="部材名*" v={newData.material_name} on={(v: string) => setNewData({ ...newData, material_name: v })} w="w-48" />
          <Field label="単位" v={newData.unit} on={(v: string) => setNewData({ ...newData, unit: v })} w="w-16" />
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">優先仕入先</label>
            <select value={newData.default_supplier_id || ''} onChange={e => setNewData({ ...newData, default_supplier_id: e.target.value || null })}
              className="border rounded px-2 py-1 text-sm w-40">
              <option value="">-</option>
              {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <Field label="リードタイム(日)" v={newData.standard_lead_days} on={(v: string) => setNewData({ ...newData, standard_lead_days: Number(v) })} w="w-20" type="number" />
          <Field label="備考" v={newData.notes} on={(v: string) => setNewData({ ...newData, notes: v })} w="w-36" />
          <button onClick={handleAdd} className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded"><Check size={14} /></button>
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
            <tr key={m.id} className="bg-indigo-50">
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
          {materials.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-gray-400">部材マスタなし</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

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
