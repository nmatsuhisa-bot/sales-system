import { useEffect, useMemo, useState } from 'react';
import { costingApi } from '../api';
import { Calculator, Upload, Download, Save, Plus, Trash2, RefreshCw, AlertTriangle, Search, Settings, FlaskConical, ShieldCheck } from 'lucide-react';

/** 製品原価検証（管理者専用）
 *  ① 製品単位の資材利用状況・単価の検証 ② 販売単価シミュレーション ③ レポート出力
 *  仕様: docs/原価検証システム_要件整理と実装方針_20260907.md
 */

const CATEGORIES = ['鋼板', '面積材', '形鋼', 'パイプ', '購入品', '外注加工', '塗料'];
const PRICE_UNITS = ['kg', 'm', 'm2', '個', '枚', '缶', '本', 'リンク'];
const LINE_TYPES: Record<string, string> = {
  weight: '板金(kg)', measure: '長さ/面積', count: '購入品', subcontract: '外注', paint: '塗料', subassembly: 'サブアセンブリ',
};
const today = () => new Date().toISOString().slice(0, 10);
const yen = (v: any) => (v == null || isNaN(v) ? '—' : Math.round(v).toLocaleString());
const pct = (v: any) => (v == null || isNaN(v) ? '—' : `${(v * 100).toFixed(1)}%`);
const num = (v: any, d = 2) => (v == null || isNaN(v) ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }));
const errMsg = (e: any) => e?.response?.data?.detail || e?.message || 'エラー';

type Tab = 'table' | 'materials' | 'verify' | 'simulation' | 'import' | 'settings';

export default function CostingPage() {
  const [tab, setTab] = useState<Tab>('table');
  const [overview, setOverview] = useState<any>(null);
  const [setupMsg, setSetupMsg] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const loadOverview = () => costingApi.overview().then(r => setOverview(r.data)).catch(e => setSetupMsg(
    e?.response?.status === 500 ? 'テーブルが未作成の可能性があります。「テーブル作成（初回）」を実行してください。' : errMsg(e)));
  useEffect(() => { loadOverview(); }, [reloadKey]);

  const setup = async () => {
    if (!confirm('原価検証用テーブル（cost_*）を作成します。既存テーブルは変更しません。実行しますか？')) return;
    try { const r = await costingApi.setup(); setSetupMsg(r.data.message); setReloadKey(k => k + 1); }
    catch (e: any) { setSetupMsg(errMsg(e)); }
  };

  const tabs: [Tab, string, any][] = [
    ['table', '製品原価表', Calculator], ['materials', '資材・単価', Search], ['verify', '検証', ShieldCheck],
    ['simulation', 'シミュレーション', FlaskConical], ['import', '取込', Upload], ['settings', '設定', Settings],
  ];

  return (
    <div className="p-4">
      <div className="flex items-start justify-between mb-1 gap-2 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-gray-800">製品原価検証 <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded bg-amber-100 text-amber-800">管理者専用</span></h1>
          <p className="text-xs text-gray-500 mt-1">型式ごとの資材利用状況と単価を検証し、販売単価をシミュレーションします。資材・単価は仕入管理の部材マスタと共有しています。</p>
        </div>
        <div className="flex gap-2 items-center shrink-0">
          {overview && (
            <div className="text-xs text-gray-500 hidden md:flex gap-3">
              <span>資材 <b>{overview.materials}</b></span><span>単価 <b>{overview.prices}</b></span>
              <span>型式 <b>{overview.units}</b></span><span>明細 <b>{overview.lines}</b></span>
            </div>
          )}
          <button onClick={setup} className="px-3 py-1.5 bg-white border border-gray-300 text-gray-700 text-sm rounded hover:bg-gray-50">テーブル作成（初回）</button>
        </div>
      </div>
      {setupMsg && <div className="mb-3 text-xs px-3 py-2 rounded bg-blue-50 text-blue-800 border border-blue-200">{setupMsg}</div>}
      <div className="flex gap-1 mb-4 border-b border-gray-200 flex-wrap">
        {tabs.map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === key ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>
      {tab === 'table' && <CostTableTab reloadKey={reloadKey} />}
      {tab === 'materials' && <MaterialsTab />}
      {tab === 'verify' && <VerifyTab />}
      {tab === 'simulation' && <SimulationTab />}
      {tab === 'import' && <ImportTab onApplied={() => setReloadKey(k => k + 1)} />}
      {tab === 'settings' && <SettingsTab />}
    </div>
  );
}

// ================= 共通部品 =================
function Field({ label, v, on, w = 'w-32', type = 'text', placeholder }: any) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-0.5">{label}</label>
      <input type={type} value={v ?? ''} placeholder={placeholder} onChange={e => on(e.target.value)} className={`border rounded px-2 py-1 text-sm ${w}`} />
    </div>
  );
}
function SelectField({ label, v, opts, on, w = '' }: any) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-0.5">{label}</label>
      <select value={v ?? ''} onChange={e => on(e.target.value)} className={`border rounded px-2 py-1 text-sm ${w}`}>
        <option value="">-</option>
        {opts.map((o: any) => typeof o === 'string' ? <option key={o} value={o}>{o}</option> : <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}
function ErrorBanner({ msg }: { msg: string | null }) {
  return msg ? <div className="mb-3 text-sm px-3 py-2 rounded bg-red-50 text-red-700 border border-red-200 flex items-center gap-2"><AlertTriangle size={14} />{msg}</div> : null;
}
function Th({ children, right }: any) {
  return <th className={`border border-gray-200 px-2 py-1.5 font-medium text-gray-600 ${right ? 'text-right' : 'text-left'}`}>{children}</th>;
}
function Td({ children, right, className = '' }: any) {
  return <td className={`border border-gray-100 px-2 py-1 ${right ? 'text-right tabular-nums' : ''} ${className}`}>{children}</td>;
}
function Tile({ label, value, sub, tone = '' }: any) {
  return (
    <div className={`rounded border px-3 py-2 ${tone || 'bg-white border-gray-200'}`}>
      <div className="text-[11px] text-gray-500">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-gray-500">{sub}</div>}
    </div>
  );
}
function useUnits(reloadKey = 0) {
  const [units, setUnits] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { costingApi.listUnits().then(r => setUnits(r.data)).catch(e => setErr(errMsg(e))); }, [reloadKey]);
  return { units, err };
}
function ScenarioForm({ sc, setSc, suppliers }: any) {
  const setCat = (c: string, v: string) => {
    const cf = { ...(sc.category_factors || {}) };
    if (v === '' || Number(v) === 1) delete cf[c]; else cf[c] = Number(v);
    setSc({ ...sc, category_factors: cf });
  };
  return (
    <div className="p-3 border border-indigo-200 rounded-lg bg-indigo-50 flex flex-wrap gap-3 items-end">
      <Field label="鋼材一律 (+%)" type="number" w="w-24" v={sc.steel_pct} on={(v: string) => setSc({ ...sc, steel_pct: v === '' ? undefined : Number(v) })} />
      {CATEGORIES.map(c => (
        <Field key={c} label={`${c} 倍率`} type="number" w="w-20" placeholder="1.00" v={sc.category_factors?.[c]} on={(v: string) => setCat(c, v)} />
      ))}
      <Field label="時間単価 (円/h)" type="number" w="w-24" v={sc.labor_rate} on={(v: string) => setSc({ ...sc, labor_rate: v === '' ? undefined : Number(v) })} />
      <Field label="経費率 (%)" type="number" w="w-20" v={sc.overhead_rate} on={(v: string) => setSc({ ...sc, overhead_rate: v === '' ? undefined : Number(v) })} />
      <Field label="目標粗利率 (%)" type="number" w="w-24" v={sc.target_margin_rate} on={(v: string) => setSc({ ...sc, target_margin_rate: v === '' ? undefined : Number(v) })} />
      {suppliers && <SelectField label="値引き調整の取引先" v={sc.party_id} opts={suppliers.map((s: any) => ({ value: s.id, label: s.name }))} on={(v: string) => setSc({ ...sc, party_id: v || undefined })} />}
      <label className="flex items-center gap-1 text-xs text-gray-600"><input type="checkbox" checked={!!sc.apply_line_markup} onChange={e => setSc({ ...sc, apply_line_markup: e.target.checked || undefined })} />Excel の値上想定倍率を適用</label>
    </div>
  );
}

// ================= 製品原価表 =================
function CostTableTab({ reloadKey }: { reloadKey: number }) {
  const { units, err: unitErr } = useUnits(reloadKey);
  const [unitId, setUnitId] = useState('');
  const [priceDate, setPriceDate] = useState(today());
  const [compareDate, setCompareDate] = useState('');
  const [priceDates, setPriceDates] = useState<string[]>([]);
  const [res, setRes] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showLines, setShowLines] = useState(true);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => { costingApi.priceDates().then(r => setPriceDates(r.data)).catch(() => {}); }, [reloadKey]);
  useEffect(() => { if (unitId) costingApi.listCalculations(unitId).then(r => setHistory(r.data)).catch(() => {}); }, [unitId, res]);

  const run = async () => {
    if (!unitId) { setErr('型式を選択してください'); return; }
    setLoading(true); setErr(null);
    try {
      const r = await costingApi.calculate({ unit_id: unitId, price_date: priceDate, compare_date: compareDate || undefined });
      setRes(r.data);
    } catch (e: any) { setErr(errMsg(e)); }
    finally { setLoading(false); }
  };
  const exportXlsx = async () => {
    if (!unitId) return;
    try {
      const r = await costingApi.exportExcel(unitId, priceDate, compareDate || undefined);
      const url = URL.createObjectURL(r.data);
      const a = document.createElement('a'); a.href = url; a.download = `原価表_${res?.unit?.unit_code || 'unit'}_${priceDate}.xlsx`; a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) { setErr(errMsg(e)); }
  };
  const save = async () => {
    if (!unitId) return;
    const label = prompt('保存する計算のメモ（任意）') ?? '';
    try { await costingApi.saveCalculation({ unit_id: unitId, price_date: priceDate, label }); setRes({ ...res }); }
    catch (e: any) { setErr(errMsg(e)); }
  };

  const m = res?.material;
  const grouped = useMemo(() => {
    if (!m) return [];
    const map = new Map<string, any[]>();
    m.lines.forEach((l: any) => { const k = l.section || '（部位なし）'; if (!map.has(k)) map.set(k, []); map.get(k)!.push(l); });
    return Array.from(map.entries());
  }, [m]);

  return (
    <div>
      <ErrorBanner msg={err || unitErr} />
      <div className="flex flex-wrap gap-3 items-end mb-4">
        <SelectField label="型式（ユニット）" w="w-72" v={unitId} on={setUnitId}
          opts={units.map((u: any) => ({ value: u.id, label: `${u.unit_code}　${u.unit_name !== u.unit_code ? u.unit_name : ''}（明細 ${u.line_count}）` }))} />
        <Field label="単価時点" type="date" w="w-40" v={priceDate} on={setPriceDate} />
        <Field label="比較する時点（任意）" type="date" w="w-40" v={compareDate} on={setCompareDate} />
        {priceDates.length > 0 && (
          <div className="text-[11px] text-gray-500">登録済みの単価時点: {priceDates.slice(0, 6).map(d => <button key={d} className="underline mr-1" onClick={() => setPriceDate(d)}>{d}</button>)}</div>
        )}
        <button onClick={run} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-60"><Calculator size={14} />{loading ? '計算中…' : '計算'}</button>
        {res && <button onClick={exportXlsx} className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-300 text-sm rounded hover:bg-gray-50"><Download size={14} />Excel 出力</button>}
        {res && <button onClick={save} className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-300 text-sm rounded hover:bg-gray-50"><Save size={14} />計算を保存</button>}
      </div>
      {!res && units.length === 0 && !unitErr && (
        <div className="text-sm text-gray-500 py-8 text-center">原価BOMのある型式がありません。「取込」タブから原価表 Excel を取り込んでください。</div>
      )}
      {res && (
        <div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 mb-4">
            <Tile label="材料費" value={yen(res.material_cost)} sub={`鋼材 ${pct(m.steel_ratio)} / 購入外注 ${pct(1 - m.steel_ratio)}`} />
            <Tile label="加工費" value={yen(res.labor_cost)} sub={res.standard_hours != null ? `${res.standard_hours}h × ${yen(res.labor_rate)}円` : '標準工数が未登録'} />
            <Tile label="経費" value={yen(res.overhead_cost)} sub={res.overhead_rate != null ? `${res.overhead_rate}%` : '経費率は未設定（保留）'} />
            <Tile label="製造原価" value={yen(res.manufacturing_cost)} tone="bg-indigo-50 border-indigo-200" />
            <Tile label="販売価格（標準）" value={yen(res.standard_price)} sub={res.standard_price ? '見積パターン/ユニットマスタ' : '未登録'} />
            <Tile label="粗利率" value={pct(res.gross_margin_rate)} sub={res.gross_margin != null ? `粗利 ${yen(res.gross_margin)}` : ''}
              tone={res.gross_margin_rate != null && res.gross_margin_rate < 0 ? 'bg-red-50 border-red-200' : ''} />
            <Tile label="必要売価" value={yen(res.required_price)} sub={res.target_margin_rate != null ? `目標粗利 ${res.target_margin_rate}%` : '目標粗利率は未設定'} />
          </div>
          {m.warnings.length > 0 && (
            <div className="mb-3 text-xs px-3 py-2 rounded bg-amber-50 text-amber-800 border border-amber-200">
              <b>単価未解決 {m.warnings.length} 行</b>：{m.warnings.slice(0, 8).map((w: any, i: number) => <span key={i} className="mr-2">{w.via ? `[${w.via}] ` : ''}{w.section}/{w.label}</span>)}{m.warnings.length > 8 && '…'}
              　→「資材・単価」タブで別名を登録するか単価を追加してください
            </div>
          )}
          {res.compare && (
            <div className="mb-4 p-3 border rounded bg-white">
              <div className="text-sm font-medium mb-2">{res.compare.date} → {priceDate} の差分：<span className={res.compare.diff >= 0 ? 'text-red-600' : 'text-emerald-700'}>{res.compare.diff >= 0 ? '+' : ''}{yen(res.compare.diff)} 円（{res.compare.diff_rate != null ? `${(res.compare.diff_rate * 100).toFixed(1)}%` : '—'}）</span></div>
              <div className="overflow-x-auto"><table className="text-xs border-collapse w-full">
                <thead><tr className="bg-gray-50"><Th>部位</Th><Th>名称</Th><Th right>旧単価</Th><Th right>新単価</Th><Th right>旧数量</Th><Th right>新数量</Th><Th right>差額</Th><Th right>単価要因</Th><Th right>数量要因</Th></tr></thead>
                <tbody>{res.compare.rows.slice(0, 40).map((r: any, i: number) => (
                  <tr key={i}><Td>{r.section}</Td><Td>{r.label}</Td><Td right>{num(r.base_price)}</Td><Td right>{num(r.other_price)}</Td><Td right>{num(r.base_qty, 3)}</Td><Td right>{num(r.other_qty, 3)}</Td>
                    <Td right className={r.diff >= 0 ? 'text-red-600' : 'text-emerald-700'}>{yen(r.diff)}</Td><Td right>{yen(r.price_effect)}</Td><Td right>{yen(r.qty_effect)}</Td></tr>
                ))}</tbody>
              </table></div>
            </div>
          )}
          <div className="grid md:grid-cols-3 gap-4">
            <div className="md:col-span-1">
              <div className="text-sm font-medium mb-1">部位別</div>
              <table className="w-full text-xs border-collapse">
                <thead><tr className="bg-gray-50"><Th>部位</Th><Th right>鋼材</Th><Th right>購入/外注</Th><Th right>小計</Th></tr></thead>
                <tbody>
                  {m.sections.map((s: any) => <tr key={s.section}><Td>{s.section}</Td><Td right>{yen(s.steel)}</Td><Td right>{yen(s.purchased)}</Td><Td right className="font-medium">{yen(s.total)}</Td></tr>)}
                  <tr className="bg-gray-50 font-medium"><Td>合計</Td><Td right>{yen(m.steel_total)}</Td><Td right>{yen(m.purchased_total)}</Td><Td right>{yen(m.total)}</Td></tr>
                </tbody>
              </table>
              {history.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm font-medium mb-1">保存済みの計算</div>
                  <table className="w-full text-xs border-collapse">
                    <thead><tr className="bg-gray-50"><Th>時点</Th><Th right>材料費</Th><Th right>製造原価</Th><Th>メモ</Th></tr></thead>
                    <tbody>{history.slice(0, 10).map((h: any) => <tr key={h.id}><Td>{h.price_date}</Td><Td right>{yen(h.total)}</Td><Td right>{yen(h.manufacturing_cost)}</Td><Td>{h.label}<span className="text-gray-400 ml-1">{h.created_at?.slice(0, 10)}</span></Td></tr>)}</tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="md:col-span-2">
              <div className="flex items-center justify-between mb-1">
                <div className="text-sm font-medium">内訳（{m.lines.length} 行）</div>
                <button className="text-xs text-indigo-600 underline" onClick={() => setShowLines(!showLines)}>{showLines ? '折りたたむ' : '展開する'}</button>
              </div>
              {showLines && (
                <div className="overflow-x-auto border rounded">
                  <table className="w-full text-xs border-collapse">
                    <thead><tr className="bg-gray-50"><Th>名称</Th><Th>種別</Th><Th>資材</Th><Th right>数量</Th><Th>単位</Th><Th right>単価</Th><Th right>原価</Th><Th>仕入先 / 時点</Th></tr></thead>
                    <tbody>
                      {grouped.map(([sec, lines]) => (
                        <LinesGroup key={sec} sec={sec} lines={lines} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
function LinesGroup({ sec, lines }: { sec: string; lines: any[] }) {
  const sub = lines.reduce((a, l) => a + (l.amount || 0), 0);
  return (
    <>
      <tr className="bg-slate-100"><td colSpan={6} className="px-2 py-1 font-medium text-slate-700">{sec}</td><td className="px-2 py-1 text-right font-medium tabular-nums">{yen(sub)}</td><td /></tr>
      {lines.map((l: any) => (
        <tr key={l.line_id} className={l.warning ? 'bg-amber-50' : ''}>
          <Td>{l.label}{l.qty_expr && <span className="text-gray-400 ml-1" title={l.qty_expr}>ƒ</span>}{l.note && <span className="text-gray-400 ml-1">（{l.note}）</span>}</Td>
          <Td><span className="text-[11px] px-1 rounded bg-gray-100">{LINE_TYPES[l.line_type] || l.line_type}</span></Td>
          <Td>{l.material_name}{l.material_code && <span className="text-gray-400 ml-1">{l.material_code}</span>}</Td>
          <Td right>{num(l.qty, 4)}</Td><Td>{l.price_unit}</Td>
          <Td right>{l.unit_price == null ? <span className="text-amber-700">未解決</span> : num(l.unit_price)}</Td>
          <Td right>{yen(l.amount)}</Td>
          <Td className="text-gray-500">{l.supplier_name || (l.source === 'subassembly' ? '（サブアセンブリ）' : '')}{l.price_date ? ` ${l.price_date}` : ''}{l.source === 'adjusted' ? ' 調整あり' : ''}</Td>
        </tr>
      ))}
    </>
  );
}

// ================= 資材・単価 =================
function MaterialsTab() {
  const [rows, setRows] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [sel, setSel] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [nf, setNf] = useState<any>({ category: '購入品', price_unit: '個' });

  const load = () => costingApi.materials({ search: search || undefined, category: category || undefined }).then(r => setRows(r.data)).catch(e => setErr(errMsg(e)));
  useEffect(() => { load(); }, [category]);
  useEffect(() => { costingApi.suppliers().then(r => setSuppliers(r.data)).catch(() => {}); }, []);

  const createNew = async () => {
    try { await costingApi.createMaterial(nf); setShowNew(false); setNf({ category: '購入品', price_unit: '個' }); load(); }
    catch (e: any) { setErr(errMsg(e)); }
  };

  return (
    <div>
      <ErrorBanner msg={err} />
      <div className="flex flex-wrap gap-2 items-end mb-3">
        <Field label="検索（名称・コード・別名）" w="w-64" v={search} on={setSearch} />
        <SelectField label="種別" v={category} opts={CATEGORIES} on={setCategory} />
        <button onClick={load} className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded"><Search size={14} /></button>
        <button onClick={() => setShowNew(!showNew)} className="ml-auto flex items-center gap-1 px-3 py-1.5 bg-white border text-sm rounded"><Plus size={14} />資材を追加</button>
      </div>
      {showNew && (
        <div className="mb-3 p-3 border border-indigo-200 rounded-lg bg-indigo-50 flex flex-wrap gap-2 items-end">
          <Field label="資材名*" w="w-72" v={nf.material_name} on={(v: string) => setNf({ ...nf, material_name: v })} />
          <Field label="TECHS 品番（空なら仮コード）" w="w-40" v={nf.material_code} on={(v: string) => setNf({ ...nf, material_code: v })} />
          <SelectField label="種別" v={nf.category} opts={CATEGORIES} on={(v: string) => setNf({ ...nf, category: v })} />
          <SelectField label="単価単位" v={nf.price_unit} opts={PRICE_UNITS} on={(v: string) => setNf({ ...nf, price_unit: v })} />
          <Field label="原価表上名称（別名）" w="w-56" v={nf.alias} on={(v: string) => setNf({ ...nf, alias: v })} />
          <button onClick={createNew} className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded">登録</button>
        </div>
      )}
      <div className="grid lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 overflow-x-auto border rounded max-h-[70vh] overflow-y-auto">
          <table className="w-full text-xs border-collapse">
            <thead className="sticky top-0"><tr className="bg-gray-50"><Th>コード</Th><Th>資材名</Th><Th>種別</Th><Th>単位</Th><Th right>最新単価</Th><Th>仕入先</Th><Th right>使用</Th></tr></thead>
            <tbody>
              {rows.length === 0 ? <tr><td colSpan={7} className="text-center py-8 text-gray-400">資材なし</td></tr> : rows.map(m => (
                <tr key={m.id} onClick={() => setSel(m)} className={`cursor-pointer hover:bg-indigo-50 ${sel?.id === m.id ? 'bg-indigo-50' : ''}`}>
                  <Td><span className={m.code_source === 'TECHS' ? '' : 'text-gray-400'}>{m.material_code}</span></Td>
                  <Td>{m.material_name}{m.aliases.length > 1 && <span className="text-gray-400 ml-1">+{m.aliases.length - 1}</span>}</Td>
                  <Td>{m.category || <span className="text-amber-700">未設定</span>}</Td><Td>{m.price_unit}</Td>
                  <Td right>{m.latest_prices.length ? num(Math.min(...m.latest_prices.map((p: any) => p.price))) : <span className="text-amber-700">なし</span>}</Td>
                  <Td className="text-gray-500">{m.latest_prices.map((p: any) => p.supplier_name).join(' / ')}</Td>
                  <Td right>{m.usage}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="lg:col-span-2">
          {sel ? <MaterialDetail m={sel} suppliers={suppliers} onChange={() => { load(); }} /> : <div className="text-sm text-gray-400 py-8 text-center border rounded">資材を選ぶと単価履歴・別名・値引き調整を編集できます</div>}
        </div>
      </div>
    </div>
  );
}
function MaterialDetail({ m, suppliers, onChange }: any) {
  const [ext, setExt] = useState<any>({});
  const [prices, setPrices] = useState<any[]>([]);
  const [adjs, setAdjs] = useState<any[]>([]);
  const [cmp, setCmp] = useState<any>(null);
  const [pf, setPf] = useState<any>({ effective_date: today(), source: '手入力' });
  const [af, setAf] = useState<any>({ adjust_type: 'percent', party_type: 'supplier' });
  const [alias, setAlias] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [aliases, setAliases] = useState<any[]>(m.aliases || []);

  const reload = () => Promise.all([costingApi.prices(m.id), costingApi.adjustments(m.id), costingApi.compare(m.id)])
    .then(([p, a, c]) => { setPrices(p.data); setAdjs(a.data); setCmp(c.data); }).catch(e => setErr(errMsg(e)));
  useEffect(() => {
    setExt({ material_name: m.material_name, material_code: m.material_code, category: m.category, price_unit: m.price_unit, steel_grade: m.steel_grade,
      thickness_mm: m.thickness_mm, stock_size: m.stock_size, preferred_supplier_id: m.preferred_supplier_id, price_policy: m.price_policy,
      basis_note: m.basis_note, piece_weight_kg: m.piece_weight_kg, piece_length_m: m.piece_length_m });
    setAliases(m.aliases || []); reload();
  }, [m.id]);

  const saveExt = async () => { try { await costingApi.updateMaterialExt(m.id, ext); onChange(); } catch (e: any) { setErr(errMsg(e)); } };
  const addPrice = async () => { try { await costingApi.addPrice(m.id, pf); setPf({ ...pf, price: '' }); reload(); onChange(); } catch (e: any) { setErr(errMsg(e)); } };
  const addAdj = async () => { try { await costingApi.addAdjustment(m.id, af); reload(); } catch (e: any) { setErr(errMsg(e)); } };
  const addAliasFn = async () => { if (!alias) return; try { await costingApi.addAlias(m.id, alias); setAliases([...aliases, { id: 'new-' + alias, alias }]); setAlias(''); onChange(); } catch (e: any) { setErr(errMsg(e)); } };

  return (
    <div className="border rounded p-3 bg-white text-xs space-y-3 max-h-[70vh] overflow-y-auto">
      <ErrorBanner msg={err} />
      <div className="font-medium text-sm">{m.material_name} <span className="text-gray-400 font-normal">{m.material_code}（{m.code_source || '仮'}）</span></div>
      <div className="flex flex-wrap gap-2 items-end">
        <Field label="資材名" w="w-64" v={ext.material_name} on={(v: string) => setExt({ ...ext, material_name: v })} />
        <Field label="TECHS 品番" w="w-32" v={ext.material_code} on={(v: string) => setExt({ ...ext, material_code: v })} />
        <SelectField label="種別" v={ext.category} opts={CATEGORIES} on={(v: string) => setExt({ ...ext, category: v })} />
        <SelectField label="単価単位" v={ext.price_unit} opts={PRICE_UNITS} on={(v: string) => setExt({ ...ext, price_unit: v })} />
        <Field label="鋼種" w="w-24" v={ext.steel_grade} on={(v: string) => setExt({ ...ext, steel_grade: v })} />
        <Field label="板厚" w="w-16" type="number" v={ext.thickness_mm} on={(v: string) => setExt({ ...ext, thickness_mm: v })} />
        <Field label="定尺" w="w-16" v={ext.stock_size} on={(v: string) => setExt({ ...ext, stock_size: v })} />
        <SelectField label="採用仕入先" v={ext.preferred_supplier_id} opts={suppliers.map((s: any) => ({ value: s.id, label: s.name }))} on={(v: string) => setExt({ ...ext, preferred_supplier_id: v })} />
        <SelectField label="単価の選び方" v={ext.price_policy} opts={[{ value: 'preferred', label: '採用仕入先' }, { value: 'cheapest', label: '最安' }]} on={(v: string) => setExt({ ...ext, price_policy: v })} />
        <Field label="単価計算根拠" w="w-72" v={ext.basis_note} on={(v: string) => setExt({ ...ext, basis_note: v })} />
        <button onClick={saveExt} className="px-3 py-1.5 bg-indigo-600 text-white rounded"><Save size={12} /></button>
      </div>

      <div>
        <div className="font-medium mb-1">原価表上名称（別名）</div>
        <div className="flex flex-wrap gap-1 items-center">
          {aliases.map((a: any) => <span key={a.id} className="px-1.5 py-0.5 bg-gray-100 rounded">{a.alias}{!a.id.startsWith('new-') && <button className="ml-1 text-gray-400" onClick={async () => { await costingApi.deleteAlias(a.id); setAliases(aliases.filter(x => x.id !== a.id)); onChange(); }}>×</button>}</span>)}
          <input value={alias} onChange={e => setAlias(e.target.value)} placeholder="別名を追加" className="border rounded px-2 py-0.5 w-40" />
          <button onClick={addAliasFn} className="px-2 py-0.5 border rounded">追加</button>
        </div>
      </div>

      <div>
        <div className="font-medium mb-1">仕入先別の単価比較（本日時点）</div>
        {cmp && (cmp.candidates.length ? (
          <table className="w-full border-collapse"><thead><tr className="bg-gray-50"><Th>仕入先</Th><Th right>単価</Th><Th>時点</Th><Th>採用</Th></tr></thead>
            <tbody>{cmp.candidates.map((c: any, i: number) => <tr key={i}><Td>{c.supplier_name}</Td><Td right>{num(c.price, 4)}</Td><Td>{c.effective_date}</Td><Td>{String(c.supplier_id) === String(cmp.chosen_supplier_id) ? <span className="text-emerald-700">● {cmp.source === 'adjusted' ? `調整後 ${num(cmp.chosen_price, 4)}` : ''}</span> : ''}</Td></tr>)}</tbody></table>
        ) : <div className="text-gray-400">単価が登録されていません</div>)}
      </div>

      <div>
        <div className="font-medium mb-1">単価履歴</div>
        <div className="flex flex-wrap gap-2 items-end mb-2 p-2 bg-gray-50 rounded">
          <SelectField label="仕入先" v={pf.supplier_id} opts={suppliers.map((s: any) => ({ value: s.id, label: s.name }))} on={(v: string) => setPf({ ...pf, supplier_id: v })} />
          <Field label="有効開始日" type="date" w="w-36" v={pf.effective_date} on={(v: string) => setPf({ ...pf, effective_date: v })} />
          <Field label={`単価（円/${ext.price_unit || m.price_unit}）`} type="number" w="w-28" v={pf.price} on={(v: string) => setPf({ ...pf, price: v })} />
          <Field label="根拠式" w="w-48" v={pf.basis_expr} on={(v: string) => setPf({ ...pf, basis_expr: v })} />
          <SelectField label="出典" v={pf.source} opts={['手入力', '仕入先見積', '発注実績', 'スプレッドシート']} on={(v: string) => setPf({ ...pf, source: v })} />
          <button onClick={addPrice} className="px-2 py-1.5 bg-indigo-600 text-white rounded"><Plus size={12} /></button>
        </div>
        <table className="w-full border-collapse"><thead><tr className="bg-gray-50"><Th>時点</Th><Th>仕入先</Th><Th right>単価</Th><Th>単位</Th><Th>出典</Th><Th>根拠</Th><Th /></tr></thead>
          <tbody>{prices.map(p => <tr key={p.id}><Td>{p.effective_date}</Td><Td>{p.supplier_name}</Td><Td right>{num(p.price, 4)}</Td><Td>{p.price_unit}</Td><Td>{p.source}</Td><Td className="text-gray-500">{p.basis_expr}</Td>
            <Td><button className="text-red-500" onClick={async () => { if (confirm('削除しますか？')) { await costingApi.deletePrice(p.id); reload(); onChange(); } }}><Trash2 size={12} /></button></Td></tr>)}</tbody></table>
      </div>

      <div>
        <div className="font-medium mb-1">取引先単位の値引き調整（該当が無ければ素の単価）</div>
        <div className="flex flex-wrap gap-2 items-end mb-2 p-2 bg-gray-50 rounded">
          <SelectField label="取引先（仕入先）" v={af.party_id} opts={suppliers.map((s: any) => ({ value: s.id, label: s.name }))} on={(v: string) => setAf({ ...af, party_id: v })} />
          <SelectField label="方式" v={af.adjust_type} opts={[{ value: 'percent', label: '率 (%)' }, { value: 'amount', label: '額 (円)' }]} on={(v: string) => setAf({ ...af, adjust_type: v })} />
          <Field label="調整値（値引きは負）" type="number" w="w-28" v={af.value} on={(v: string) => setAf({ ...af, value: v })} />
          <Field label="開始" type="date" w="w-36" v={af.effective_from} on={(v: string) => setAf({ ...af, effective_from: v })} />
          <Field label="終了" type="date" w="w-36" v={af.effective_to} on={(v: string) => setAf({ ...af, effective_to: v })} />
          <button onClick={addAdj} className="px-2 py-1.5 bg-indigo-600 text-white rounded"><Plus size={12} /></button>
        </div>
        {adjs.length > 0 && <table className="w-full border-collapse"><thead><tr className="bg-gray-50"><Th>取引先</Th><Th>方式</Th><Th right>値</Th><Th>期間</Th><Th /></tr></thead>
          <tbody>{adjs.map(a => <tr key={a.id}><Td>{a.party_name || '（全取引先）'}</Td><Td>{a.adjust_type === 'percent' ? '率' : '額'}</Td><Td right>{a.value}</Td><Td>{a.effective_from || ''}〜{a.effective_to || ''}</Td>
            <Td><button className="text-red-500" onClick={async () => { await costingApi.deleteAdjustment(a.id); reload(); }}><Trash2 size={12} /></button></Td></tr>)}</tbody></table>}
      </div>
    </div>
  );
}

// ================= 検証 =================
function VerifyTab() {
  const [priceDate, setPriceDate] = useState(today());
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [kind, setKind] = useState('');
  const KIND: Record<string, string> = { unresolved_price: '単価未解決', stale_price: '単価が古い', no_category: '種別未設定', orphan_import: 'Excel で小計外', cycle: '循環参照' };
  const run = () => costingApi.verify(priceDate).then(r => setRes(r.data)).catch(e => setErr(errMsg(e)));
  useEffect(() => { run(); }, []);
  const list = (res?.findings || []).filter((f: any) => !kind || f.kind === kind);
  return (
    <div>
      <ErrorBanner msg={err} />
      <div className="flex flex-wrap gap-2 items-end mb-3">
        <Field label="単価時点" type="date" w="w-40" v={priceDate} on={setPriceDate} />
        <button onClick={run} className="flex items-center gap-1 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded"><RefreshCw size={14} />検証を実行</button>
        {res && Object.entries(res.counts).map(([k, v]: any) => (
          <button key={k} onClick={() => setKind(kind === k ? '' : k)} className={`text-xs px-2 py-1 rounded border ${kind === k ? 'bg-indigo-600 text-white' : 'bg-white'}`}>{KIND[k] || k} {v}</button>
        ))}
      </div>
      {res && (
        <div className="grid lg:grid-cols-4 gap-4">
          <div className="lg:col-span-1">
            <div className="text-sm font-medium mb-1">型式別の材料費（{res.price_date}）</div>
            <table className="w-full text-xs border-collapse"><thead><tr className="bg-gray-50"><Th>型式</Th><Th right>材料費</Th><Th right>未解決</Th></tr></thead>
              <tbody>{res.units.map((u: any) => <tr key={u.unit_id} className={u.warnings ? 'bg-amber-50' : ''}><Td>{u.unit_code}</Td><Td right>{yen(u.total)}</Td><Td right>{u.warnings || ''}</Td></tr>)}</tbody></table>
          </div>
          <div className="lg:col-span-3">
            <div className="text-sm font-medium mb-1">指摘事項（{list.length}）</div>
            <div className="overflow-x-auto border rounded max-h-[65vh] overflow-y-auto">
              <table className="w-full text-xs border-collapse"><thead className="sticky top-0"><tr className="bg-gray-50"><Th>区分</Th><Th>型式</Th><Th>部位</Th><Th>名称</Th><Th>内容</Th></tr></thead>
                <tbody>{list.length === 0 ? <tr><td colSpan={5} className="text-center py-8 text-emerald-700">指摘はありません</td></tr> : list.map((f: any, i: number) => (
                  <tr key={i}><Td><span className="px-1 rounded bg-amber-100 text-amber-800">{KIND[f.kind] || f.kind}</span></Td><Td>{f.unit_code}</Td><Td>{f.section}</Td><Td>{f.label}</Td><Td className="text-gray-600">{f.message}</Td></tr>
                ))}</tbody></table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ================= シミュレーション =================
function SimulationTab() {
  const { units, err: unitErr } = useUnits();
  const [selected, setSelected] = useState<string[]>([]);
  const [filter, setFilter] = useState('');
  const [priceDate, setPriceDate] = useState(today());
  const [sc, setSc] = useState<any>({});
  const [rows, setRows] = useState<any[]>([]);
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const loadScenarios = () => costingApi.scenarios().then(r => setScenarios(r.data)).catch(() => {});
  useEffect(() => { loadScenarios(); costingApi.suppliers().then(r => setSuppliers(r.data)).catch(() => {}); }, []);

  const run = async () => {
    if (!selected.length) { setErr('型式を選択してください'); return; }
    setLoading(true); setErr(null);
    try { const r = await costingApi.calculateBatch({ unit_ids: selected, price_date: priceDate, scenario: sc }); setRows(r.data); }
    catch (e: any) { setErr(errMsg(e)); } finally { setLoading(false); }
  };
  const saveSc = async () => {
    const name = prompt('シナリオ名'); if (!name) return;
    try { await costingApi.saveScenario({ name, adjustments: sc }); loadScenarios(); } catch (e: any) { setErr(errMsg(e)); }
  };
  const visible = units.filter((u: any) => !filter || u.unit_code.toLowerCase().includes(filter.toLowerCase()));
  const toggle = (id: string) => setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);

  return (
    <div>
      <ErrorBanner msg={err || unitErr} />
      <div className="grid lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1">
          <div className="flex items-center gap-2 mb-1">
            <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="型式で絞込" className="border rounded px-2 py-1 text-xs w-full" />
            <button className="text-xs underline whitespace-nowrap" onClick={() => setSelected(visible.map((u: any) => u.id))}>全選択</button>
            <button className="text-xs underline whitespace-nowrap" onClick={() => setSelected([])}>解除</button>
          </div>
          <div className="border rounded max-h-[60vh] overflow-y-auto text-xs">
            {visible.map((u: any) => (
              <label key={u.id} className="flex items-center gap-2 px-2 py-1 hover:bg-gray-50 cursor-pointer">
                <input type="checkbox" checked={selected.includes(u.id)} onChange={() => toggle(u.id)} />
                <span>{u.unit_code}</span><span className="text-gray-400 truncate">{u.unit_name !== u.unit_code ? u.unit_name : ''}</span>
              </label>
            ))}
          </div>
        </div>
        <div className="lg:col-span-3">
          <div className="flex flex-wrap gap-2 items-end mb-2">
            <Field label="単価時点" type="date" w="w-40" v={priceDate} on={setPriceDate} />
            <SelectField label="保存済みシナリオ" w="w-56" v="" opts={scenarios.map(s => ({ value: s.id, label: s.name }))} on={(v: string) => { const s = scenarios.find(x => x.id === v); if (s) setSc(s.adjustments || {}); }} />
            <button onClick={saveSc} className="flex items-center gap-1 px-3 py-1.5 bg-white border text-sm rounded"><Save size={14} />シナリオ保存</button>
            <button onClick={() => setSc({})} className="px-3 py-1.5 bg-white border text-sm rounded">条件クリア</button>
            <button onClick={run} disabled={loading} className="flex items-center gap-1 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded disabled:opacity-60"><FlaskConical size={14} />{loading ? '計算中…' : '再計算'}</button>
          </div>
          <ScenarioForm sc={sc} setSc={setSc} suppliers={suppliers} />
          {rows.length > 0 && (
            <div className="overflow-x-auto border rounded mt-3">
              <table className="w-full text-xs border-collapse">
                <thead><tr className="bg-gray-50"><Th>型式</Th><Th right>材料費（基準）</Th><Th right>材料費（条件）</Th><Th right>増減</Th><Th right>製造原価（条件）</Th><Th right>販売価格</Th><Th right>粗利率（基準）</Th><Th right>粗利率（条件）</Th><Th right>必要売価</Th><Th right>鋼材比率</Th></tr></thead>
                <tbody>{rows.map(r => r.error ? <tr key={r.unit_id}><Td>{r.unit_code}</Td><td colSpan={9} className="text-red-600 px-2">{r.error}</td></tr> : (
                  <tr key={r.unit_id} className={r.warnings ? 'bg-amber-50' : ''}>
                    <Td>{r.unit_code}{r.warnings ? <span className="text-amber-700 ml-1" title="単価未解決あり">!</span> : ''}</Td>
                    <Td right>{yen(r.base.material_cost)}</Td><Td right>{yen(r.scenario.material_cost)}</Td>
                    <Td right className={r.scenario.material_cost - r.base.material_cost > 0 ? 'text-red-600' : 'text-emerald-700'}>{r.base.material_cost ? `${((r.scenario.material_cost / r.base.material_cost - 1) * 100).toFixed(1)}%` : '—'}</Td>
                    <Td right>{yen(r.scenario.manufacturing_cost)}</Td><Td right>{yen(r.scenario.standard_price)}</Td>
                    <Td right>{pct(r.base.gross_margin_rate)}</Td><Td right className={r.scenario.gross_margin_rate != null && r.scenario.gross_margin_rate < 0 ? 'text-red-600' : ''}>{pct(r.scenario.gross_margin_rate)}</Td>
                    <Td right>{yen(r.scenario.required_price)}</Td><Td right>{pct(r.scenario.steel_ratio)}</Td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ================= 取込 =================
function ImportTab({ onApplied }: { onApplied: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [includeOrphans, setIncludeOrphans] = useState(false);
  const [preview, setPreview] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const KIND: Record<string, string> = { orphan: '小計外の行', cost_error: '原価セルがエラー', unresolved: 'マスタに名称なし', no_price: '単価なし', cycle: '循環参照' };

  const run = async (apply: boolean) => {
    if (!file) { setErr('原価表 Excel を選択してください'); return; }
    if (apply && !confirm('取込を確定します。同じシートから取り込んだ既存の明細は置き換えられます。よろしいですか？')) return;
    setBusy(true); setErr(null);
    try { const r = await costingApi.importExcel(file, apply, includeOrphans); setPreview(r.data); if (apply) onApplied(); }
    catch (e: any) { setErr(errMsg(e)); } finally { setBusy(false); }
  };
  const kinds: Record<string, number> = {};
  (preview?.warnings || []).forEach((w: any) => { kinds[w.kind] = (kinds[w.kind] || 0) + 1; });

  return (
    <div>
      <ErrorBanner msg={err} />
      <p className="text-xs text-gray-500 mb-3">原価表ブック（BFR / PLD / BFQ 様式。単価マスタシート＋型式シート）を読み取り、資材・別名・単価履歴・原価BOMを登録します。まず「プレビュー」で Excel の合計と計算結果の一致を確認してから「取込を確定」してください。</p>
      <div className="flex flex-wrap gap-3 items-end mb-3">
        <input type="file" accept=".xlsx" onChange={e => setFile(e.target.files?.[0] || null)} className="text-sm" />
        <label className="flex items-center gap-1 text-xs text-gray-600"><input type="checkbox" checked={includeOrphans} onChange={e => setIncludeOrphans(e.target.checked)} />小計外の行も取り込む</label>
        <button onClick={() => run(false)} disabled={busy} className="px-3 py-1.5 bg-white border text-sm rounded disabled:opacity-60">{busy ? '解析中…' : 'プレビュー'}</button>
        <button onClick={() => run(true)} disabled={busy || !preview} className="flex items-center gap-1 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded disabled:opacity-60"><Upload size={14} />取込を確定</button>
      </div>
      {preview && (
        <div>
          <div className="text-xs text-gray-600 mb-2">
            {preview.file}：資材 {preview.materials} 件、単価時点 {preview.price_dates.old} / {preview.price_dates.new}
            {preview.applied && <span className="ml-2 px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">取込済み：{Object.entries(preview.stats || {}).map(([k, v]) => `${k} ${v}`).join('、')}</span>}
          </div>
          <div className="overflow-x-auto border rounded mb-3">
            <table className="w-full text-xs border-collapse">
              <thead><tr className="bg-gray-50"><Th>シート</Th><Th>型式</Th><Th right>明細</Th><Th right>オプション</Th><Th right>小計外</Th><Th right>Excel 合計</Th><Th right>計算（Excel 再現）</Th><Th right>差</Th><Th right>標準原価（倍率なし）</Th><Th right>未解決</Th></tr></thead>
              <tbody>{preview.units.map((u: any) => (
                <tr key={u.sheet} className={u.diff != null && Math.abs(u.diff) > 1 ? 'bg-amber-50' : ''}>
                  <Td>{u.sheet}</Td><Td>{u.unit_code}</Td><Td right>{u.lines}</Td><Td right>{u.options || ''}</Td><Td right>{u.orphans || ''}</Td>
                  <Td right>{yen(u.excel_total)}</Td><Td right>{yen(u.computed_total)}</Td>
                  <Td right className={u.diff != null && Math.abs(u.diff) > 1 ? 'text-amber-700 font-medium' : 'text-emerald-700'}>{u.diff == null ? '—' : num(u.diff, 0)}</Td>
                  <Td right>{yen(u.computed_total_std)}</Td><Td right>{u.unresolved || ''}</Td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          {preview.warnings.length > 0 && (
            <div>
              <div className="text-sm font-medium mb-1">警告 {preview.warnings.length} 件：{Object.entries(kinds).map(([k, v]) => <span key={k} className="mr-2 text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-800">{KIND[k] || k} {v}</span>)}</div>
              <div className="overflow-x-auto border rounded max-h-64 overflow-y-auto">
                <table className="w-full text-xs border-collapse"><thead className="sticky top-0"><tr className="bg-gray-50"><Th>区分</Th><Th>シート</Th><Th right>行</Th><Th>名称</Th><Th>内容</Th></tr></thead>
                  <tbody>{preview.warnings.map((w: any, i: number) => <tr key={i}><Td>{KIND[w.kind] || w.kind}</Td><Td>{w.sheet}</Td><Td right>{w.row}</Td><Td>{w.label}</Td><Td className="text-gray-600">{w.message}</Td></tr>)}</tbody></table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ================= 設定 =================
function SettingsTab() {
  const [data, setData] = useState<any>(null);
  const [form, setForm] = useState<any>({ key: 'labor_rate_per_hour', effective_date: today() });
  const [err, setErr] = useState<string | null>(null);
  const load = () => costingApi.settings().then(r => setData(r.data)).catch(e => setErr(errMsg(e)));
  useEffect(() => { load(); }, []);
  const add = async () => { try { await costingApi.addSetting(form); setForm({ ...form, value: '' }); load(); } catch (e: any) { setErr(errMsg(e)); } };
  return (
    <div>
      <ErrorBanner msg={err} />
      {data && (
        <div className="grid grid-cols-3 gap-2 mb-4 max-w-2xl">
          {Object.entries(data.labels).map(([k, label]: any) => <Tile key={k} label={label} value={data.current[k] == null ? '未設定（保留）' : num(data.current[k])} />)}
        </div>
      )}
      <div className="p-3 border border-indigo-200 rounded-lg bg-indigo-50 flex flex-wrap gap-2 items-end mb-4">
        <SelectField label="項目" v={form.key} opts={data ? Object.entries(data.labels).map(([k, l]: any) => ({ value: k, label: l })) : []} on={(v: string) => setForm({ ...form, key: v })} />
        <Field label="値" type="number" w="w-28" v={form.value} on={(v: string) => setForm({ ...form, value: v })} />
        <Field label="有効開始日" type="date" w="w-40" v={form.effective_date} on={(v: string) => setForm({ ...form, effective_date: v })} />
        <Field label="メモ" w="w-64" v={form.notes} on={(v: string) => setForm({ ...form, notes: v })} />
        <button onClick={add} className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded"><Plus size={14} /></button>
      </div>
      {data && (
        <table className="text-xs border-collapse max-w-3xl w-full"><thead><tr className="bg-gray-50"><Th>項目</Th><Th right>値</Th><Th>有効開始日</Th><Th>メモ</Th><Th /></tr></thead>
          <tbody>{data.history.map((h: any) => <tr key={h.id}><Td>{h.label}</Td><Td right>{h.value == null ? '未設定' : num(h.value)}</Td><Td>{h.effective_date}</Td><Td>{h.notes}</Td>
            <Td><button className="text-red-500" onClick={async () => { if (confirm('削除しますか？')) { await costingApi.deleteSetting(h.id); load(); } }}><Trash2 size={12} /></button></Td></tr>)}</tbody></table>
      )}
      <p className="text-xs text-gray-500 mt-4">時間単価の初期値は 2,500 円/h（2026-09-08 井上電設様回答）。経費率と目標粗利率は保留のため未設定で運用し、決まり次第ここで登録してください。</p>
    </div>
  );
}
