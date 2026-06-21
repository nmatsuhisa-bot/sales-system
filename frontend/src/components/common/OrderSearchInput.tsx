import { useState, useRef, useEffect } from 'react';
import { projectApi } from '../../api';
import { Search } from 'lucide-react';

interface OrderSearchResult {
  id: string;
  child_no: string;
  project_no: string;
  project_name: string;
  customer_name: string;
  sales_person_name: string;
  sales_date: string | null;
  status: string;
}

interface Props {
  onSelect: (order: OrderSearchResult) => void;
  placeholder?: string;
}

export default function OrderSearchInput({ onSelect, placeholder = '案件ID または 子ID で検索' }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<OrderSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<OrderSearchResult | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 外クリックで閉じる
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const search = (q: string) => {
    if (!q.trim()) { setResults([]); setOpen(false); return; }
    setLoading(true);
    projectApi.searchOrders(q)
      .then(r => { setResults(r.data); setOpen(true); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value;
    setQuery(q);
    setSelected(null);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => search(q), 300);
  };

  const handleSelect = (o: OrderSearchResult) => {
    setSelected(o);
    setQuery(o.child_no);
    setOpen(false);
    onSelect(o);
  };

  const STATUS_COLOR: Record<string, string> = {
    '受注': 'text-green-600', '見積発行': 'text-yellow-600',
    '営業中': 'text-blue-600', '失注': 'text-red-400', '完了': 'text-gray-400',
  };

  return (
    <div ref={wrapperRef} className="relative">
      <div className="flex items-center border rounded-lg overflow-hidden focus-within:ring-2 focus-within:ring-blue-400">
        <Search size={14} className="ml-2.5 text-gray-400 shrink-0" />
        <input
          value={query}
          onChange={handleChange}
          onFocus={() => query && results.length > 0 && setOpen(true)}
          placeholder={placeholder}
          className="w-full px-2 py-1.5 text-sm outline-none"
        />
        {loading && <span className="mr-2 text-xs text-gray-400">...</span>}
      </div>

      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full min-w-[400px] bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
          {results.map(o => (
            <button key={o.id} onClick={() => handleSelect(o)}
              className="w-full text-left px-3 py-2 hover:bg-blue-50 border-b border-gray-100 last:border-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-blue-700 w-28 shrink-0">{o.child_no}</span>
                <span className={`text-xs shrink-0 ${STATUS_COLOR[o.status] || 'text-gray-500'}`}>{o.status}</span>
                <span className="text-sm text-gray-800 truncate flex-1">{o.project_name || '—'}</span>
              </div>
              <div className="flex gap-3 mt-0.5 text-xs text-gray-400">
                <span>{o.customer_name || '—'}</span>
                <span>担当: {o.sales_person_name || '—'}</span>
                {o.sales_date && <span className="text-blue-400">納期: {o.sales_date}</span>}
              </div>
            </button>
          ))}
          {results.length === 0 && (
            <p className="px-3 py-3 text-sm text-gray-400">該当なし</p>
          )}
        </div>
      )}

      {selected && (
        <div className="mt-1 text-xs text-green-700 bg-green-50 border border-green-200 rounded px-2 py-1 flex gap-3">
          <span className="font-mono font-bold">{selected.child_no}</span>
          <span>{selected.project_name}</span>
          <span>{selected.customer_name}</span>
          {selected.sales_date && <span>納期: {selected.sales_date}</span>}
        </div>
      )}
    </div>
  );
}
