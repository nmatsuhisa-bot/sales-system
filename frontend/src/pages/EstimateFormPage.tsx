import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { estimateApi, projectApi, mastersApi } from '../api';
import { Plus, Trash2, Save, FileText, ArrowLeft, Calculator } from 'lucide-react';

// =============================================
// 型定義
// =============================================
interface LineItem {
  line_no: number;
  section: string;
  sub_section: string;
  item_name: string;
  spec_detail: string;
  quantity: number;
  unit: string;
  unit_price: number;
  product_type: string;
  spec_json?: any;
}

interface LaborDetail {
  labor_item_id?: string;
  item_name: string;
  quantity: number;
  unit: string;
  unit_price: number;
  crane_type?: string;
  notes?: string;
  sort_order: number;
}

export default function EstimateFormPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const childNo = searchParams.get('child_no') || '';
  const projectOrderId = searchParams.get('project_order_id') || '';
  const isEdit = !!id;

  // マスタデータ
  const [bfrBodies, setBfrBodies] = useState<any[]>([]);
  const [scaBodies, setScaBodies] = useState<any[]>([]);
  const [plFans, setPlFans] = useState<any[]>([]);
  const [cyclones, setCyclones] = useState<any[]>([]);
  const [laborMaster, setLaborMaster] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);

  // フォーム
  const [header, setHeader] = useState({
    project_order_id: projectOrderId,
    child_no: childNo,
    customer_name: '', delivery_name: '', title: '',
    delivery_terms: '受注後　　ヶ月', payment_terms: '納品後30日以内',
    valid_until: '', issue_date: new Date().toISOString().split('T')[0],
    sales_person_name: '', notes: '', internal_notes: '',
  });
  const [lineItems, setLineItems] = useState<LineItem[]>([]);
  const [laborDetails, setLaborDetails] = useState<LaborDetail[]>([]);
  const [activeTab, setActiveTab] = useState<'items' | 'labor'>('items');
  const [loading, setLoading] = useState(false);

  // パターン選択用
  const [showBfrPattern, setShowBfrPattern] = useState(false);
  const [showScaPattern, setShowScaPattern] = useState(false);
  const [bfrFans, setBfrFans] = useState<any[]>([]);
  const [bfrRvs, setBfrRvs] = useState<any[]>([]);
  const [bfrSel, setBfrSel] = useState({ body: '', filterType: '', fan: '', rv: '', hasPurgeCircuit: false });
  const [scaSel, setScaSel] = useState({ body: '', hasPl: false, pl: '', hasCyclone: false, cyclone: '' });

  // 合計計算
  const itemsTotal = lineItems.reduce((s, i) => s + i.unit_price * i.quantity, 0);
  const laborTotal = laborDetails.reduce((s, l) => s + l.unit_price * l.quantity, 0);
  const subtotal = itemsTotal + laborTotal;
  const tax = Math.floor(subtotal * 0.1);
  const total = subtotal + tax;

  useEffect(() => {
    estimateApi.getBfrBodies().then(r => setBfrBodies(r.data));
    estimateApi.getScaBodies().then(r => setScaBodies(r.data));
    estimateApi.getPlFans().then(r => setPlFans(r.data));
    estimateApi.getCyclones().then(r => setCyclones(r.data));
    estimateApi.getLaborItems().then(r => setLaborMaster(r.data));
    mastersApi.listEmployees().then(r => setEmployees(r.data));

    if (projectOrderId) {
      projectApi.get(projectOrderId).catch(() => {});
    }
    if (isEdit) {
      estimateApi.get(id!).then(r => {
        const q = r.data;
        setHeader({
          project_order_id: q.project_order_id || '',
          child_no: q.child_no || '',
          customer_name: q.customer_name || '',
          delivery_name: q.delivery_name || '',
          title: q.title || '',
          delivery_terms: q.delivery_terms || '',
          payment_terms: q.payment_terms || '',
          valid_until: q.valid_until || '',
          issue_date: q.issue_date || '',
          sales_person_name: q.sales_person_name || '',
          notes: q.notes || '',
          internal_notes: q.internal_notes || '',
        });
        setLineItems(q.line_items || []);
        setLaborDetails(q.labor_details || []);
      });
    }
  }, []);

  // BFR型式選択時にファン・RVを読み込む
  const onBfrBodySelect = async (modelCode: string) => {
    setBfrSel(s => ({ ...s, body: modelCode, fan: '', rv: '' }));
    if (modelCode) {
      const [fans, rvs] = await Promise.all([
        estimateApi.getBfrFans(modelCode),
        estimateApi.getBfrRvs(modelCode),
      ]);
      setBfrFans(fans.data);
      setBfrRvs(rvs.data);
    }
  };

  // BFRパターンを明細に追加
  const addBfrToItems = () => {
    const body = bfrBodies.find(b => b.model_code === bfrSel.body);
    if (!body) return;
    const variant = body.variants.find((v: any) => v.filter_type === bfrSel.filterType) || body.variants[0];
    const fan = bfrFans.find(f => f.fan_model === bfrSel.fan);
    const rv = bfrRvs.find(r => r.rv_model === bfrSel.rv);

    const items: LineItem[] = [];
    const nextNo = lineItems.length + 1;

    // 本体
    const filterDetail = `フィルター: ${variant.filter_type} ${body.filter_length} × ${variant.filter_count}本\n処理風量: ${body.airflow}㎥/min`;
    items.push({
      line_no: nextNo,
      section: `集塵装置:BFR`,
      sub_section: `BFR本体`,
      item_name: `バグフィルター集塵機 ${bfrSel.body}`,
      spec_detail: filterDetail,
      quantity: 1, unit: '式',
      unit_price: parseInt(variant.base_price) + (parseInt(variant.filter_price) * parseInt(variant.filter_count)),
      product_type: 'BFR',
      spec_json: { model: bfrSel.body, filter_type: bfrSel.filterType, airflow: body.airflow }
    });

    if (fan) {
      items.push({
        line_no: nextNo + 1,
        section: `集塵装置:BFR`, sub_section: `ターボファン`,
        item_name: `ターボファン ${fan.fan_model}`,
        spec_detail: '', quantity: fan.quantity, unit: '台',
        unit_price: fan.price, product_type: 'BFR',
        spec_json: { fan_model: fan.fan_model }
      });
    }
    if (rv) {
      items.push({
        line_no: nextNo + 2,
        section: `集塵装置:BFR`, sub_section: `ロータリーバルブ`,
        item_name: `ロータリーバルブ ${rv.rv_model} ${rv.kw}kW`,
        spec_detail: '', quantity: rv.quantity, unit: '台',
        unit_price: rv.price, product_type: 'BFR',
        spec_json: { rv_model: rv.rv_model, kw: rv.kw }
      });
    }
    if (bfrSel.hasPurgeCircuit) {
      items.push({
        line_no: nextNo + 3,
        section: `集塵装置:BFR`, sub_section: `排気循環ダクト`,
        item_name: `排気循環ダクト`,
        spec_detail: '亜鉛引きスパイラルダクト', quantity: 1, unit: '式',
        unit_price: 300000, product_type: 'BFR', spec_json: {}
      });
    }
    setLineItems(prev => [...prev, ...items]);
    setShowBfrPattern(false);
  };

  // SCAパターンを明細に追加
  const addScaToItems = () => {
    const body = scaBodies.find(b => b.model_code === scaSel.body);
    if (!body) return;
    const items: LineItem[] = [];
    const nextNo = lineItems.length + 1;
    const scDetail = `円筒径φ${body.diameter}　収容量約${body.capacity}m³\nAB: ${body.ab_kw}kW　スクリューコンベヤ×${body.sc_count}台\nRV: ${body.rv1_model} ${body.rv1_kw}kW`;
    items.push({
      line_no: nextNo, section: '定量排出装置', sub_section: 'SCA本体',
      item_name: `定量排出装置 ${body.model_code}`,
      spec_detail: scDetail, quantity: 1, unit: '式',
      unit_price: body.base_price, product_type: 'SCA',
      spec_json: { model: body.model_code, diameter: body.diameter }
    });
    if (scaSel.hasPl) {
      const pl = plFans.find(f => `${f.model_code}_${f.kw}` === scaSel.pl) || plFans.find(f => f.model_code === scaSel.pl);
      if (pl) items.push({
        line_no: nextNo + 1, section: '空気輸送装置', sub_section: 'プレートファン',
        item_name: `プレートファン ${pl.model_code} ${pl.kw}kW`, spec_detail: '屋外仕様',
        quantity: 1, unit: '台', unit_price: pl.price, product_type: '空送',
        spec_json: { fan_model: pl.model_code, kw: pl.kw }
      });
    }
    if (scaSel.hasCyclone) {
      const cy = cyclones.find(c => c.id === scaSel.cyclone);
      if (cy) items.push({
        line_no: nextNo + 2, section: '空気輸送装置', sub_section: 'サイクロン',
        item_name: `サイクロン ${cy.model_code}`, spec_detail: `${cy.shape} ${cy.material}`,
        quantity: 1, unit: '台', unit_price: cy.price, product_type: '空送',
        spec_json: { cyclone_model: cy.model_code }
      });
    }
    setLineItems(prev => [...prev, ...items]);
    setShowScaPattern(false);
  };

  // 工数マスタから追加
  const addLaborFromMaster = (item: any) => {
    setLaborDetails(prev => [...prev, {
      labor_item_id: item.id, item_name: item.item_name,
      quantity: 0, unit: item.unit, unit_price: item.unit_price,
      sort_order: prev.length
    }]);
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      // 空文字のUUIDフィールドをnullに変換
      const cleanHeader = { ...header };
      if (!cleanHeader.project_order_id) cleanHeader.project_order_id = null as any;
      if (!cleanHeader.child_no) cleanHeader.child_no = null as any;
      if (!cleanHeader.valid_until) cleanHeader.valid_until = null as any;
      const payload = {
        ...cleanHeader,
        issue_date: header.issue_date || undefined,
        valid_until: header.valid_until || undefined,
        line_items: lineItems.map((i, idx) => ({ ...i, line_no: idx + 1 })),
        labor_details: laborDetails.map((l, idx) => ({ ...l, sort_order: idx })),
      };
      if (isEdit) {
        await estimateApi.update(id!, payload);
      } else {
        await estimateApi.create(payload);
      }
      navigate(-1);
    } catch (e: any) {
      alert(e.response?.data?.detail || '保存に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const handlePdf = async () => {
    if (!id) { alert('先に保存してください'); return; }
    const url = `${import.meta.env.VITE_API_URL}/estimate-quotations/${id}/pdf`;
    window.open(url, '_blank');
  };

  const F = ({ label, name, type = 'text', cols = 1 }: any) => (
    <div className={cols === 2 ? 'md:col-span-2' : ''}>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input type={type} value={(header as any)[name] || ''}
        onChange={e => setHeader(h => ({ ...h, [name]: e.target.value }))}
        className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
    </div>
  );

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => navigate(-1)} className="text-gray-500 hover:text-gray-700"><ArrowLeft size={18} /></button>
        <h1 className="text-xl font-bold text-gray-800">{isEdit ? '見積書編集' : '新規見積書作成'}</h1>
        {childNo && <span className="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded-full">子ID: {childNo}</span>}
        <div className="ml-auto flex gap-2">
          {isEdit && (
            <button onClick={handlePdf}
              className="flex items-center gap-1 bg-green-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-green-700">
              <FileText size={14} /> PDF出力
            </button>
          )}
          <button onClick={handleSave} disabled={loading}
            className="flex items-center gap-1 bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-60">
            <Save size={14} /> {loading ? '保存中...' : '保存'}
          </button>
        </div>
      </div>

      {/* ヘッダー */}
      <div className="bg-white rounded-xl shadow-sm p-4 mb-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">基本情報</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <F label="件名" name="title" cols={2} />
          <div>
            <label className="block text-xs text-gray-500 mb-1">営業担当</label>
            <select value={header.sales_person_name}
              onChange={e => setHeader(h => ({ ...h, sales_person_name: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
              <option value="">選択</option>
              {employees.map(e => <option key={e.id} value={e.employee_name}>{e.employee_name}</option>)}
            </select>
          </div>
          <F label="顧客名（売上先）" name="customer_name" />
          <F label="納入先" name="delivery_name" />
          <F label="見積日" name="issue_date" type="date" />
          <F label="有効期限" name="valid_until" type="date" />
          <F label="納期" name="delivery_terms" />
          <F label="支払条件" name="payment_terms" />
          <F label="備考" name="notes" cols={2} />
          <F label="社内メモ" name="internal_notes" />
        </div>
      </div>

      {/* タブ */}
      <div className="flex gap-2 mb-3">
        <button onClick={() => setActiveTab('items')}
          className={`px-4 py-2 rounded-lg text-sm font-medium ${activeTab === 'items' ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 text-gray-600'}`}>
          📋 見積明細 ({lineItems.length}件)
        </button>
        <button onClick={() => setActiveTab('labor')}
          className={`px-4 py-2 rounded-lg text-sm font-medium ${activeTab === 'labor' ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 text-gray-600'}`}>
          🔧 社内工数 ({laborDetails.length}件)
        </button>
      </div>

      {/* 見積明細タブ */}
      {activeTab === 'items' && (
        <div className="bg-white rounded-xl shadow-sm p-4 mb-4">
          {/* パターン追加ボタン */}
          <div className="flex flex-wrap gap-2 mb-4">
            <button onClick={() => setShowBfrPattern(true)}
              className="bg-blue-50 border border-blue-300 text-blue-700 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-blue-100">
              + BFR パターン追加
            </button>
            <button onClick={() => setShowScaPattern(true)}
              className="bg-orange-50 border border-orange-300 text-orange-700 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-orange-100">
              + SCA/SCD パターン追加
            </button>
            <button onClick={() => setLineItems(prev => [...prev, {
              line_no: prev.length + 1, section: '', sub_section: '',
              item_name: '', spec_detail: '', quantity: 1, unit: '式', unit_price: 0, product_type: 'その他'
            }])}
              className="bg-gray-50 border border-gray-300 text-gray-700 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-gray-100">
              + 手動追加
            </button>
          </div>

          {/* 明細テーブル */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-2 py-2 text-left font-medium text-gray-500 w-8">#</th>
                  <th className="px-2 py-2 text-left font-medium text-gray-500">大分類</th>
                  <th className="px-2 py-2 text-left font-medium text-gray-500 w-44">品名・仕様</th>
                  <th className="px-2 py-2 text-left font-medium text-gray-500">仕様詳細</th>
                  <th className="px-2 py-2 text-right font-medium text-gray-500 w-16">数量</th>
                  <th className="px-2 py-2 text-center font-medium text-gray-500 w-12">単位</th>
                  <th className="px-2 py-2 text-right font-medium text-gray-500 w-28">単価</th>
                  <th className="px-2 py-2 text-right font-medium text-gray-500 w-28">金額</th>
                  <th className="px-2 py-2 w-6"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {lineItems.map((item, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-2 py-1.5 text-gray-400">{idx + 1}</td>
                    <td className="px-2 py-1.5">
                      <input value={item.section} onChange={e => setLineItems(prev => prev.map((i, j) => j === idx ? { ...i, section: e.target.value } : i))}
                        className="w-full border-0 outline-none text-xs bg-transparent" placeholder="大分類" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input value={item.item_name} onChange={e => setLineItems(prev => prev.map((i, j) => j === idx ? { ...i, item_name: e.target.value } : i))}
                        className="w-full border border-gray-200 rounded px-2 py-1 text-xs" placeholder="品名" />
                    </td>
                    <td className="px-2 py-1.5">
                      <textarea value={item.spec_detail} rows={2}
                        onChange={e => setLineItems(prev => prev.map((i, j) => j === idx ? { ...i, spec_detail: e.target.value } : i))}
                        className="w-full border border-gray-200 rounded px-2 py-1 text-xs resize-none" placeholder="仕様詳細" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input type="number" value={item.quantity}
                        onChange={e => setLineItems(prev => prev.map((i, j) => j === idx ? { ...i, quantity: Number(e.target.value) } : i))}
                        className="w-full border border-gray-200 rounded px-1 py-1 text-xs text-right" />
                    </td>
                    <td className="px-2 py-1.5 text-center text-gray-600">{item.unit}</td>
                    <td className="px-2 py-1.5">
                      <input type="number" value={item.unit_price}
                        onChange={e => setLineItems(prev => prev.map((i, j) => j === idx ? { ...i, unit_price: Number(e.target.value) } : i))}
                        className="w-full border border-gray-200 rounded px-1 py-1 text-xs text-right" />
                    </td>
                    <td className="px-2 py-1.5 text-right font-medium text-gray-700">
                      ¥{(item.unit_price * item.quantity).toLocaleString()}
                    </td>
                    <td className="px-2 py-1.5">
                      <button onClick={() => setLineItems(prev => prev.filter((_, j) => j !== idx))} className="text-red-300 hover:text-red-500">
                        <Trash2 size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {lineItems.length === 0 && <div className="text-center py-8 text-gray-400 text-sm">パターン追加ボタンで明細を追加してください</div>}
          </div>
        </div>
      )}

      {/* 社内工数タブ */}
      {activeTab === 'labor' && (
        <div className="bg-white rounded-xl shadow-sm p-4 mb-4">
          <div className="flex gap-2 mb-4 flex-wrap">
            {laborMaster.map(item => (
              <button key={item.id} onClick={() => addLaborFromMaster(item)}
                className="bg-gray-50 border border-gray-200 text-gray-700 px-2 py-1 rounded text-xs hover:bg-blue-50 hover:border-blue-300">
                + {item.item_name}
              </button>
            ))}
          </div>
          <table className="w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-2 py-2 text-left font-medium text-gray-500">作業項目</th>
                <th className="px-2 py-2 text-center font-medium text-gray-500 w-20">種別</th>
                <th className="px-2 py-2 text-right font-medium text-gray-500 w-16">数量</th>
                <th className="px-2 py-2 text-center font-medium text-gray-500 w-14">単位</th>
                <th className="px-2 py-2 text-right font-medium text-gray-500 w-24">単価</th>
                <th className="px-2 py-2 text-right font-medium text-gray-500 w-24">金額</th>
                <th className="px-2 py-2 w-6"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {laborDetails.map((l, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-2 py-1.5">
                    <input value={l.item_name} onChange={e => setLaborDetails(prev => prev.map((i, j) => j === idx ? { ...i, item_name: e.target.value } : i))}
                      className="w-full border border-gray-200 rounded px-2 py-1 text-xs" />
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={l.crane_type || ''} placeholder="レッカー種別等"
                      onChange={e => setLaborDetails(prev => prev.map((i, j) => j === idx ? { ...i, crane_type: e.target.value } : i))}
                      className="w-full border border-gray-200 rounded px-1 py-1 text-xs" />
                  </td>
                  <td className="px-2 py-1.5">
                    <input type="number" step="0.5" value={l.quantity}
                      onChange={e => setLaborDetails(prev => prev.map((i, j) => j === idx ? { ...i, quantity: Number(e.target.value) } : i))}
                      className="w-full border border-gray-200 rounded px-1 py-1 text-xs text-right" />
                  </td>
                  <td className="px-2 py-1.5 text-center text-gray-600">{l.unit}</td>
                  <td className="px-2 py-1.5">
                    <input type="number" value={l.unit_price}
                      onChange={e => setLaborDetails(prev => prev.map((i, j) => j === idx ? { ...i, unit_price: Number(e.target.value) } : i))}
                      className="w-full border border-gray-200 rounded px-1 py-1 text-xs text-right" />
                  </td>
                  <td className="px-2 py-1.5 text-right font-medium text-gray-700">¥{(l.unit_price * l.quantity).toLocaleString()}</td>
                  <td className="px-2 py-1.5">
                    <button onClick={() => setLaborDetails(prev => prev.filter((_, j) => j !== idx))} className="text-red-300 hover:text-red-500"><Trash2 size={12} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {laborDetails.length === 0 && <div className="text-center py-8 text-gray-400 text-sm">上のボタンから作業項目を追加してください</div>}
        </div>
      )}

      {/* 合計 */}
      <div className="bg-white rounded-xl shadow-sm p-4 mb-4">
        <div className="flex justify-end">
          <div className="w-80 space-y-1.5 text-sm">
            <div className="flex justify-between text-gray-600"><span>機器・工事小計</span><span>¥{itemsTotal.toLocaleString()}</span></div>
            <div className="flex justify-between text-gray-600"><span>社内工数小計</span><span>¥{laborTotal.toLocaleString()}</span></div>
            <div className="flex justify-between text-gray-600"><span>消費税（10%）</span><span>¥{tax.toLocaleString()}</span></div>
            <div className="flex justify-between text-lg font-bold text-gray-800 border-t pt-2">
              <span>合計金額</span><span className="text-blue-700">¥{total.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* BFRパターンモーダル */}
      {showBfrPattern && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-4">BFR パターン選択</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">型式</label>
                <select value={bfrSel.body} onChange={e => onBfrBodySelect(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">選択</option>
                  {Array.from(new Set(bfrBodies.map(b => b.model_code))).map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              {bfrSel.body && (<>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">フィルター種類</label>
                  <select value={bfrSel.filterType} onChange={e => setBfrSel(s => ({ ...s, filterType: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">選択</option>
                    {bfrBodies.find(b => b.model_code === bfrSel.body)?.variants.map((v: any) => (
                      <option key={v.filter_type} value={v.filter_type}>{v.filter_type}（フィルター¥{Number(v.filter_price).toLocaleString()}×{v.filter_count}本）</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">ターボファン</label>
                  <select value={bfrSel.fan} onChange={e => setBfrSel(s => ({ ...s, fan: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">なし</option>
                    {bfrFans.map(f => <option key={f.id} value={f.fan_model}>{f.fan_model} ×{f.quantity}台 ¥{Number(f.price).toLocaleString()}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">ロータリーバルブ</label>
                  <select value={bfrSel.rv} onChange={e => setBfrSel(s => ({ ...s, rv: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">なし</option>
                    {bfrRvs.map(r => <option key={r.id} value={r.rv_model}>{r.rv_model} {r.kw}kW ¥{Number(r.price).toLocaleString()}</option>)}
                  </select>
                </div>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={bfrSel.hasPurgeCircuit}
                    onChange={e => setBfrSel(s => ({ ...s, hasPurgeCircuit: e.target.checked }))} />
                  排気循環ダクト有
                </label>
              </>)}
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setShowBfrPattern(false)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">キャンセル</button>
              <button onClick={addBfrToItems} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">明細に追加</button>
            </div>
          </div>
        </div>
      )}

      {/* SCAパターンモーダル */}
      {showScaPattern && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-4">SCA/SCD パターン選択</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">型式</label>
                <select value={scaSel.body} onChange={e => setScaSel(s => ({ ...s, body: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">選択</option>
                  {scaBodies.map(b => (
                    <option key={b.id} value={b.model_code}>
                      {b.model_code}（φ{b.diameter} 収容量{b.capacity}m³ ¥{Number(b.base_price).toLocaleString()}）
                    </option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={scaSel.hasPl} onChange={e => setScaSel(s => ({ ...s, hasPl: e.target.checked }))} />
                プレートファン（空送）を追加
              </label>
              {scaSel.hasPl && (
                <select value={scaSel.pl} onChange={e => setScaSel(s => ({ ...s, pl: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">型式選択</option>
                  {plFans.map(f => <option key={f.id} value={`${f.model_code}_${f.kw}`}>{f.model_code} {f.kw}kW ¥{Number(f.price).toLocaleString()}</option>)}
                </select>
              )}
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={scaSel.hasCyclone} onChange={e => setScaSel(s => ({ ...s, hasCyclone: e.target.checked }))} />
                サイクロンを追加
              </label>
              {scaSel.hasCyclone && (
                <select value={scaSel.cyclone} onChange={e => setScaSel(s => ({ ...s, cyclone: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">型式選択</option>
                  {cyclones.map(c => <option key={c.id} value={c.id}>{c.model_code} {c.shape} {c.material} ¥{Number(c.price).toLocaleString()}</option>)}
                </select>
              )}
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setShowScaPattern(false)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">キャンセル</button>
              <button onClick={addScaToItems} className="px-4 py-2 bg-orange-600 text-white rounded-lg text-sm hover:bg-orange-700">明細に追加</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
