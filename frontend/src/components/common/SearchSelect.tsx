import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown } from 'lucide-react';
import { fuzzyFilter } from '../../utils/fuzzy';

export interface SearchOption {
  value: string;
  label: string;
  /** 候補の2行目に小さく出す補足（コード・価格など）。検索対象にも含む */
  sub?: string;
  /** 表示はしないが検索に使う語（読み仮名・旧名など） */
  keywords?: string;
}

interface Props {
  value: string | null | undefined;
  onChange: (value: string) => void;
  options: SearchOption[];
  placeholder?: string;
  /** 指定すると先頭に「未選択に戻す」候補を出す（例: 「なし」「直接取引(なし)」） */
  emptyLabel?: string;
  disabled?: boolean;
  className?: string;
  /** 候補の最大表示件数（多すぎると重くなるため） */
  limit?: number;
  /** xs: 表の中など狭い場所向けの小さい表示 */
  size?: 'sm' | 'xs';
}

/**
 * 文字を入力すると候補を曖昧検索で絞り込める選択欄（<select> の置き換え）。
 * ↑↓で移動、Enterで確定、Escで取り消し。選択しないまま離れると元の値に戻る。
 */
export default function SearchSelect({
  value, onChange, options, placeholder = '入力して検索', emptyLabel,
  disabled = false, className = '', limit = 100, size = 'sm',
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [pos, setPos] = useState<{ left: number; top: number; width: number; maxH: number; up: boolean } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const current = options.find(o => o.value === (value ?? ''));
  const shownLabel = current ? current.label : (value || '');

  const filtered = useMemo(
    () => fuzzyFilter(options, query, o => `${o.label} ${o.sub || ''} ${o.keywords || ''}`),
    [options, query],
  );
  const rows: SearchOption[] = useMemo(() => {
    const head = emptyLabel != null && !query.trim() ? [{ value: '', label: emptyLabel }] : [];
    return [...head, ...filtered.slice(0, limit)];
  }, [filtered, emptyLabel, query, limit]);

  const place = () => {
    const r = inputRef.current?.getBoundingClientRect();
    if (!r) return;
    const below = window.innerHeight - r.bottom - 8;
    const above = r.top - 8;
    const up = below < 200 && above > below;
    setPos({
      left: r.left, width: Math.max(r.width, 260),
      top: up ? r.top - 4 : r.bottom + 4,
      maxH: Math.min(320, up ? above : below), up,
    });
  };

  useLayoutEffect(() => { if (open) place(); }, [open]);
  useEffect(() => {
    if (!open) return;
    const onScroll = (e: Event) => {
      if (listRef.current && listRef.current.contains(e.target as Node)) return;
      place();
    };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (inputRef.current?.contains(t) || listRef.current?.contains(t)) return;
      close();
    };
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', place);
    document.addEventListener('mousedown', onDown);
    return () => {
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', place);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open]);

  // ハイライト中の候補を見える位置へ
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [active, open]);

  const openList = () => {
    if (disabled) return;
    setQuery('');
    const idx = rows.findIndex(o => o.value === (value ?? ''));
    setActive(idx >= 0 ? idx : 0);
    setOpen(true);
  };
  const close = () => { setOpen(false); setQuery(''); };
  const pick = (o: SearchOption) => {
    if (o.value !== (value ?? '')) onChange(o.value);
    close();
    inputRef.current?.blur();
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) { e.preventDefault(); openList(); return; }
    if (!open) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(i => Math.min(i + 1, rows.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(i => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); if (rows[active]) pick(rows[active]); }
    else if (e.key === 'Escape') { e.preventDefault(); close(); inputRef.current?.blur(); }
    else if (e.key === 'Tab') { close(); }
  };

  const more = filtered.length - limit;

  return (
    <div className={`relative ${className.includes('w-') ? '' : 'w-full'} ${className}`}>
      <input
        ref={inputRef}
        value={open ? query : shownLabel}
        placeholder={open ? (shownLabel || placeholder) : (emptyLabel && !value ? emptyLabel : placeholder)}
        onFocus={openList}
        onClick={() => { if (!open) openList(); }}
        onChange={e => { setQuery(e.target.value); setActive(0); if (!open) setOpen(true); }}
        onKeyDown={onKey}
        disabled={disabled}
        autoComplete="off"
        className={`w-full border border-gray-200 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:bg-gray-100 disabled:text-gray-500 truncate ${
          size === 'xs' ? 'rounded pl-1.5 pr-6 py-0.5 text-xs' : 'rounded-lg pl-3 pr-7 py-1.5 text-sm'}`}
      />
      <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
      {open && pos && createPortal(
        <div
          ref={listRef}
          style={{
            position: 'fixed', left: pos.left, width: pos.width, maxHeight: pos.maxH,
            ...(pos.up ? { bottom: window.innerHeight - pos.top } : { top: pos.top }),
          }}
          className="z-[1000] bg-white border border-gray-200 rounded-lg shadow-lg overflow-y-auto text-sm"
        >
          {rows.length === 0 && <div className="px-3 py-2 text-gray-400">該当なし</div>}
          {rows.map((o, i) => (
            <div
              key={`${o.value}-${i}`}
              data-idx={i}
              onMouseDown={e => { e.preventDefault(); pick(o); }}
              onMouseEnter={() => setActive(i)}
              className={`px-3 py-1.5 cursor-pointer ${i === active ? 'bg-blue-50' : ''} ${o.value === (value ?? '') ? 'font-semibold text-blue-700' : 'text-gray-800'} ${o.value === '' ? 'text-gray-500' : ''}`}
            >
              <div className="truncate">{o.label}</div>
              {o.sub && <div className="text-[11px] text-gray-400 truncate">{o.sub}</div>}
            </div>
          ))}
          {more > 0 && (
            <div className="px-3 py-1.5 text-[11px] text-gray-400 border-t">他 {more} 件。文字を入力して絞り込んでください</div>
          )}
        </div>,
        document.body,
      )}
    </div>
  );
}
