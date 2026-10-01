import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useForm, useFieldArray } from 'react-hook-form';
import { quotationApi, customerApi, productApi } from '../api';
import { Plus, Trash2, ChevronDown, ChevronUp, Save, ArrowLeft } from 'lucide-react';

const STATUS_LABELS: Record<string, string> = {
  draft: '下書き', submitted: '提出済', approved: '承認済',
  rejected: '却下', converted: '受注変換済'
};

export default function QuotationFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = !!id;
  const [customers, setCustomers] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [options, setOptions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Record<number, boolean>>({});

  const { register, control, handleSubmit, watch, setValue, reset, formState: { errors } } = useForm({
    defaultValues: {
      customer_id: '',
      title: '',
      issue_date: new Date().toISOString().split('T')[0],
      valid_until: '',
      delivery_terms: '受注後　　ヶ月',
      payment_terms: '納品後30日以内',
      delivery_location: '',
      notes: '',
      internal_notes: '',
      items: [] as any[]
    }
  });

  const { fields, append, remove } = useFieldArray({ control, name: 'items' });
  const watchedItems = watch('items');

  // 合計計算
  const subtotal = watchedItems?.reduce((sum, item) => {
    const itemAmt = (Number(item.unit_price) || 0) * (Number(item.quantity) || 1);
    const optAmt = (item.options || []).reduce((s: number, o: any) => s + (Number(o.price) || 0), 0);
    return sum + itemAmt + optAmt;
  }, 0) || 0;
  const tax = Math.floor(subtotal * 0.1);
  const total = subtotal + tax;

  useEffect(() => {
    customerApi.list({ per_page: 200 }).then(r => setCustomers(r.data.items || []));
    productApi.list({ per_page: 200 }).then(r => setProducts(r.data.items || []));
    productApi.listOptions().then(r => setOptions(r.data || []));
    if (isEdit) {
      quotationApi.get(id!).then(r => {
        const q = r.data;
        reset({
          customer_id: q.customer_id,
          title: q.title || '',
          issue_date: q.issue_date,
          valid_until: q.valid_until || '',
          delivery_terms: q.delivery_terms || '',
          payment_terms: q.payment_terms || '',
          delivery_location: q.delivery_location || '',
          notes: q.notes || '',
          internal_notes: q.internal_notes || '',
          items: q.items || []
        });
      });
    }
  }, []);

  const addItem = () => {
    append({
      line_no: fields.length + 1,
      product_id: '',
      item_name: '',
      description: '',
      quantity: 1,
      unit: '式',
      unit_price: 0,
      notes: '',
      options: []
    });
    setExpandedItems(prev => ({ ...prev, [fields.length]: true }));
  };

  const onProductSelect = (index: number, productId: string) => {
    const p = products.find(p => p.id === productId);
    if (p) {
      setValue(`items.${index}.item_name`, p.name);
      setValue(`items.${index}.unit_price`, p.standard_price || 0);
      setValue(`items.${index}.unit`, p.unit || '式');
      if (p.description) setValue(`items.${index}.description`, p.description);
    }
  };

  const addOption = (itemIndex: number) => {
    const current = watch(`items.${itemIndex}.options`) || [];
    setValue(`items.${itemIndex}.options`, [...current, { option_name: '', price: 0, notes: '' }]);
  };

  const removeOption = (itemIndex: number, optIndex: number) => {
    const current = watch(`items.${itemIndex}.options`) || [];
    setValue(`items.${itemIndex}.options`, current.filter((_: any, i: number) => i !== optIndex));
  };

  const onSubmit = async (data: any) => {
    setLoading(true);
    try {
      // 行番号を整理
      const items = data.items.map((item: any, i: number) => ({
        ...item,
        line_no: i + 1,
        unit_price: Number(item.unit_price) || 0,
        quantity: Number(item.quantity) || 1,
        options: (item.options || []).map((o: any) => ({ ...o, price: Number(o.price) || 0 }))
      }));
      const payload = { ...data, items };
      if (isEdit) {
        await quotationApi.update(id!, payload);
      } else {
        await quotationApi.create(payload);
      }
      navigate('/quotations');
    } catch (e: any) {
      alert(e.response?.data?.detail || '保存に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/quotations')} className="text-gray-500 hover:text-gray-700">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-2xl font-bold text-gray-800">
          {isEdit ? '見積書編集' : '新規見積書作成'}
        </h1>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* ヘッダ情報 */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">基本情報</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">顧客 <span className="text-red-500">*</span></label>
              <select
                {...register('customer_id', { required: true })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                <option value="">-- 顧客を選択 --</option>
                {customers.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">件名</label>
              <input
                {...register('title')}
                placeholder="例：集塵装置 BFQ-5 一式"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">見積日 <span className="text-red-500">*</span></label>
              <input
                type="date"
                {...register('issue_date', { required: true })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">有効期限</label>
              <input
                type="date"
                {...register('valid_until')}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">納期</label>
              <input
                {...register('delivery_terms')}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">支払条件</label>
              <input
                {...register('payment_terms')}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">納入場所</label>
              <input
                {...register('delivery_location')}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">備考（顧客向け）</label>
              <textarea
                {...register('notes')}
                rows={2}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">社内メモ</label>
              <textarea
                {...register('internal_notes')}
                rows={2}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* 明細 */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-700">見積明細</h2>
            <button
              type="button"
              onClick={addItem}
              className="flex items-center gap-1 bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-blue-700"
            >
              <Plus size={16} /> 明細追加
            </button>
          </div>

          <div className="space-y-3">
            {fields.map((field, index) => {
              const isExpanded = expandedItems[index] !== false;
              const itemTotal = (Number(watchedItems?.[index]?.unit_price) || 0) * (Number(watchedItems?.[index]?.quantity) || 1)
                + ((watchedItems?.[index]?.options || []).reduce((s: number, o: any) => s + (Number(o.price) || 0), 0));
              const itemOptions = watch(`items.${index}.options`) || [];

              return (
                <div key={field.id} className="border border-gray-200 rounded-lg overflow-hidden">
                  {/* 明細ヘッダ */}
                  <div
                    className="flex items-center gap-2 p-3 bg-gray-50 cursor-pointer"
                    onClick={() => setExpandedItems(prev => ({ ...prev, [index]: !isExpanded }))}
                  >
                    <span className="text-xs text-gray-400 w-5">{index + 1}</span>
                    <span className="flex-1 text-sm font-medium text-gray-700 truncate">
                      {watchedItems?.[index]?.item_name || '（未入力）'}
                    </span>
                    <span className="text-sm font-bold text-blue-700">
                      ¥{itemTotal.toLocaleString()}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); remove(index); }}
                      className="text-red-400 hover:text-red-600 ml-2"
                    >
                      <Trash2 size={14} />
                    </button>
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </div>

                  {/* 明細詳細 */}
                  {isExpanded && (
                    <div className="p-4 space-y-3">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">商品マスタから選択</label>
                          <select
                            onChange={(e) => onProductSelect(index, e.target.value)}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                          >
                            <option value="">-- 商品を選択（任意）--</option>
                            {products.map(p => (
                              <option key={p.id} value={p.id}>[{p.product_type}] {p.product_code} - {p.name}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">品名 *</label>
                          <input
                            {...register(`items.${index}.item_name`, { required: true })}
                            placeholder="例：バグフィルタ集塵機 BFQ5"
                            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-xs text-gray-600 mb-1">仕様・説明</label>
                        <textarea
                          {...register(`items.${index}.description`)}
                          rows={3}
                          placeholder="例：排風機3.7kW4P 1400Lホッパ フィルター25本 電動シェーキング仕様"
                          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                        />
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">数量</label>
                          <input
                            type="number"
                            step="0.01"
                            {...register(`items.${index}.quantity`)}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-right focus:ring-2 focus:ring-blue-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">単位</label>
                          <select
                            {...register(`items.${index}.unit`)}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                          >
                            {['式', '台', '基', '本', '個', 'm', 'm²', '式一式'].map(u => (
                              <option key={u} value={u}>{u}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">単価（円）</label>
                          <input
                            type="number"
                            {...register(`items.${index}.unit_price`)}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-right focus:ring-2 focus:ring-blue-500 focus:outline-none"
                          />
                        </div>
                      </div>

                      {/* オプション */}
                      <div className="border-t pt-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-medium text-gray-600">オプション・追加仕様</span>
                          <button
                            type="button"
                            onClick={() => addOption(index)}
                            className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                          >
                            <Plus size={12} /> オプション追加
                          </button>
                        </div>
                        {itemOptions.map((opt: any, oi: number) => (
                          <div key={oi} className="flex items-center gap-2 mb-2">
                            <select
                              value={opt.option_name || ''}
                              onChange={(e) => {
                                const selected = options.find(o => o.option_name === e.target.value || o.name === e.target.value);
                                const current = [...itemOptions];
                                current[oi] = {
                                  ...current[oi],
                                  option_name: e.target.value,
                                  price: selected?.price || current[oi].price
                                };
                                setValue(`items.${index}.options`, current);
                              }}
                              className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                            >
                              <option value="">-- オプション選択 --</option>
                              {options.map(o => (
                                <option key={o.id} value={o.name}>{o.name}</option>
                              ))}
                              <option value="__custom__">手動入力</option>
                            </select>
                            {opt.option_name === '__custom__' && (
                              <input
                                placeholder="オプション名"
                                value={opt.custom_name || ''}
                                onChange={(e) => {
                                  const current = [...itemOptions];
                                  current[oi] = { ...current[oi], option_name: e.target.value, custom_name: e.target.value };
                                  setValue(`items.${index}.options`, current);
                                }}
                                className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs"
                              />
                            )}
                            <input
                              type="number"
                              placeholder="金額"
                              value={opt.price || 0}
                              onChange={(e) => {
                                const current = [...itemOptions];
                                current[oi] = { ...current[oi], price: Number(e.target.value) };
                                setValue(`items.${index}.options`, current);
                              }}
                              className="w-28 border border-gray-200 rounded-lg px-2 py-1.5 text-xs text-right"
                            />
                            <button
                              type="button"
                              onClick={() => removeOption(index, oi)}
                              className="text-red-400 hover:text-red-600"
                            >
                              <Trash2 size={12} />
                            </button>
                          </div>
                        ))}
                      </div>

                      {/* 小計 */}
                      <div className="text-right text-sm text-gray-600">
                        明細小計: <span className="font-bold text-gray-800 ml-1">¥{itemTotal.toLocaleString()}</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {fields.length === 0 && (
            <div className="text-center py-8 text-gray-400 text-sm">
              「明細追加」ボタンで品目を追加してください
            </div>
          )}
        </div>

        {/* 合計 */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex justify-end">
            <div className="w-72 space-y-2">
              <div className="flex justify-between text-sm text-gray-600">
                <span>小計</span>
                <span>¥{subtotal.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-sm text-gray-600">
                <span>消費税（10%）</span>
                <span>¥{tax.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-lg font-bold text-gray-800 border-t pt-2">
                <span>合計金額</span>
                <span className="text-blue-700">¥{total.toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ボタン */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/quotations')}
            className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
          >
            キャンセル
          </button>
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60"
          >
            <Save size={16} />
            {loading ? '保存中...' : '保存する'}
          </button>
        </div>
      </form>
    </div>
  );
}
