import { useEffect, useMemo, useRef, useState } from 'react';
import { equipmentApi } from '../api';
import SearchSelect from '../components/common/SearchSelect';
import {
  Wrench, Map, List, Landmark, Settings, Upload, AlertTriangle, Undo2, Trash2, Check, History, ZoomIn, ZoomOut,
  Maximize, Eye, EyeOff, Search, X, Link2, RefreshCw, Plus, Clock,
} from 'lucide-react';

/** 工場機械・図面管理
 *  ① 機械マスタ（管理ID = 機械一覧表の管理番号）
 *  ② 固定資産台帳（期ごとの取込）との紐付け・突合
 *  ③ 図面上の配置。ドラッグごとに下書き保存 → 「確定」で反映。過去時点の配置を表示できる
 *  仕様: docs/工場機械・図面管理_要件整理と実装方針_20260915.md
 */

type Tab = 'board' | 'machines' | 'assets' | 'setup';
const errMsg = (e: any) => e?.response?.data?.detail || e?.message || 'エラー';
const yen = (v: any) => (v == null || isNaN(v) ? '—' : Math.round(v).toLocaleString());
const fmtDT = (s?: string | null) => (s ? new Date(s).toLocaleString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—');
const STATUS_LABEL: Record<string, string> = { active: '稼働', removed: '除去', disposed: '処分', unknown: '所在不明' };
const LINK_TYPES = ['本体', '付帯工事', '移設費', '親資産に含む', 'リース', 'その他'];
const isAdmin = () => JSON.parse(localStorage.getItem('user') || '{}').role === 'admin';

export default function EquipmentPage() {
  const [tab, setTab] = useState<Tab>('board');
  const [overview, setOverview] = useState<any>(null);
  const [setupMsg, setSetupMsg] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const loadOverview = () => equipmentApi.overview().then(r => setOverview(r.data)).catch(e => setSetupMsg(
    e?.response?.status === 500 ? 'テーブルが未作成の可能性があります。「取込・設定」の「テーブル作成（初回）」を実行してください。' : errMsg(e)));
  useEffect(() => { loadOverview(); }, [reloadKey]);

  const tabs: [Tab, string, any][] = [
    ['board', '図面（配置）', Map], ['machines', '機械一覧', List], ['assets', '固定資産台帳・突合', Landmark], ['setup', '取込・設定', Settings],
  ];
  return (
    <div className="p-4 h-full flex flex-col">
      <div className="flex items-start justify-between mb-1 gap-2 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2"><Wrench size={20} />工場機械管理 <span className="ml-1 text-xs font-normal px-2 py-0.5 rounded bg-amber-100 text-amber-800">管理者専用</span></h1>
          <p className="text-xs text-gray-500 mt-1">機械の管理IDは機械一覧表の管理番号（S1-13 / SK-17 …）をそのまま使います。図面上の移動は下書きとして保存され、「確定」で履歴に残ります。</p>
        </div>
        {overview && (
          <div className="text-xs text-gray-500 hidden md:flex gap-3 items-center">
            <span>機械 <b>{overview.machines}</b></span><span>配置済 <b>{overview.placed}</b></span>
            <span>台帳紐付け済 <b>{overview.linked}</b></span><span>台帳 <b>{overview.assets}</b>{overview.period && <span className="ml-1">({overview.period}期)</span>}</span>
            <span>図面 <b>{overview.drawings}</b></span>
            {overview.draft_moves > 0 && <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800">未確定の移動 {overview.draft_moves} 件</span>}
          </div>
        )}
      </div>
      {setupMsg && <div className="mb-3 text-xs px-3 py-2 rounded bg-blue-50 text-blue-800 border border-blue-200">{setupMsg}</div>}
      <div className="flex gap-1 mb-3 border-b border-gray-200 flex-wrap">
        {tabs.map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === key ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>
      <div className="flex-1 min-h-0">
        {tab === 'board' && <BoardTab reloadKey={reloadKey} onChanged={() => setReloadKey(k => k + 1)} />}
        {tab === 'machines' && <MachinesTab reloadKey={reloadKey} onChanged={() => setReloadKey(k => k + 1)} />}
        {tab === 'assets' && <AssetsTab reloadKey={reloadKey} onChanged={() => setReloadKey(k => k + 1)} />}
        {tab === 'setup' && <SetupTab onChanged={() => { setReloadKey(k => k + 1); setSetupMsg(null); }} />}
      </div>
    </div>
  );
}

// ================= 共通部品 =================
function ErrorBanner({ msg, onClose }: { msg: string | null; onClose?: () => void }) {
  return msg ? (
    <div className="mb-2 text-sm px-3 py-2 rounded bg-red-50 text-red-700 border border-red-200 flex items-center gap-2">
      <AlertTriangle size={14} /><span className="flex-1">{msg}</span>
      {onClose && <button onClick={onClose}><X size={14} /></button>}
    </div>
  ) : null;
}
function Th({ children, right, className = '' }: any) {
  return <th className={`border border-gray-200 px-2 py-1.5 font-medium text-gray-600 whitespace-nowrap ${right ? 'text-right' : 'text-left'} ${className}`}>{children}</th>;
}
function Td({ children, right, className = '' }: any) {
  return <td className={`border border-gray-100 px-2 py-1 ${right ? 'text-right tabular-nums' : ''} ${className}`}>{children}</td>;
}
function Field({ label, v, on, w = 'w-32', type = 'text', placeholder }: any) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-0.5">{label}</label>
      <input type={type} value={v ?? ''} placeholder={placeholder} onChange={e => on(e.target.value)} className={`border rounded px-2 py-1 text-sm ${w}`} />
    </div>
  );
}
function LinkBadge({ l }: { l: any }) {
  const confirmed = l.confidence === 'confirmed';
  return (
    <span title={l.note || ''} className={`inline-block mr-1 mb-0.5 px-1.5 py-0.5 rounded text-[11px] border ${confirmed ? 'bg-green-50 text-green-800 border-green-200' : 'bg-amber-50 text-amber-800 border-amber-200'}`}>
      {l.asset?.asset_no || l.asset_key}{l.link_type !== '本体' && ` (${l.link_type})`}{!confirmed && ' ?'}
    </span>
  );
}
function Modal({ title, onClose, children, wide }: any) {
  return (
    <div className="fixed inset-0 z-40 bg-black/30 flex items-start justify-center overflow-auto p-4" onClick={onClose}>
      <div className={`bg-white rounded shadow-lg w-full ${wide ? 'max-w-5xl' : 'max-w-3xl'} mt-6`} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-2 border-b">
          <div className="font-medium text-gray-800">{title}</div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800"><X size={16} /></button>
        </div>
        <div className="p-4 max-h-[80vh] overflow-auto">{children}</div>
      </div>
    </div>
  );
}

// ================= ① 図面（配置） =================
function BoardTab({ reloadKey, onChanged }: { reloadKey: number; onChanged: () => void }) {
  const [drawings, setDrawings] = useState<any[]>([]);
  const [drawingId, setDrawingId] = useState<string>(() => { try { return localStorage.getItem('eq_drawing') || ''; } catch { return ''; } });
  const [board, setBoard] = useState<any>(null);
  const [asOf, setAsOf] = useState<string>('');
  const [showOriginal, setShowOriginal] = useState(false);
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);   // machine id
  const [search, setSearch] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [machineHistory, setMachineHistory] = useState<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgCache = useRef<Record<string, string>>({});

  useEffect(() => {
    equipmentApi.drawings().then(r => {
      setDrawings(r.data);
      if (!drawingId && r.data.length) setDrawingId(r.data[0].id);
      if (drawingId && !r.data.some((d: any) => d.id === drawingId)) setDrawingId(r.data[0]?.id || '');
    }).catch(e => setErr(errMsg(e)));
  }, [reloadKey]);

  const loadBoard = () => {
    if (!drawingId) { setBoard(null); return; }
    equipmentApi.board(drawingId, asOf || undefined).then(r => { setBoard(r.data); setErr(null); }).catch(e => setErr(errMsg(e)));
  };
  useEffect(() => { loadBoard(); try { localStorage.setItem('eq_drawing', drawingId); } catch {} }, [drawingId, asOf, reloadKey]);

  // 画像は JWT 付きで取って blob URL にする（図面ごと・元図面/背景ごとにキャッシュ）
  useEffect(() => {
    if (!drawingId) { setImgUrl(null); return; }
    const key = `${drawingId}:${showOriginal ? 'o' : 'i'}`;
    if (imgCache.current[key]) { setImgUrl(imgCache.current[key]); return; }
    let cancelled = false;
    equipmentApi.drawingImage(drawingId, showOriginal).then(r => {
      const url = URL.createObjectURL(r.data);
      imgCache.current[key] = url;
      if (!cancelled) setImgUrl(url);
    }).catch(e => setErr(errMsg(e)));
    return () => { cancelled = true; };
  }, [drawingId, showOriginal]);

  const drawing = board?.drawing;
  const W = drawing ? drawing.width_px * zoom : 0;
  const H = drawing ? drawing.height_px * zoom : 0;
  const fit = () => {
    const el = containerRef.current;
    if (!el || !drawing) return;
    const z = Math.min((el.clientWidth - 16) / drawing.width_px, (el.clientHeight - 16) / drawing.height_px);
    setZoom(Math.max(0.05, z));
  };
  useEffect(() => { if (drawing) setTimeout(fit, 0); }, [drawing?.id]);

  const readOnly = !!asOf;
  const drafts: any[] = board?.draft_moves || [];

  const toRatio = (clientX: number, clientY: number) => {
    const el = containerRef.current!.firstElementChild as HTMLElement;
    const rect = el.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
    return { x: Math.round(x * 1e6) / 1e6, y: Math.round(y * 1e6) / 1e6 };
  };

  const post = async (fn: () => Promise<any>) => {
    if (busy) return;
    setBusy(true);
    try { await fn(); loadBoard(); onChanged(); }
    catch (e: any) { setErr(errMsg(e)); }
    finally { setBusy(false); }
  };

  // チップのドラッグ（ポインタイベント）
  const dragRef = useRef<{ id: string; startX: number; startY: number; moved: boolean; el: HTMLElement } | null>(null);
  const onChipPointerDown = (e: React.PointerEvent, p: any) => {
    if (readOnly) { setSelected(p.id); return; }
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    dragRef.current = { id: p.id, startX: e.clientX, startY: e.clientY, moved: false, el: e.currentTarget as HTMLElement };
    setSelected(p.id);
  };
  const onChipPointerMove = (e: React.PointerEvent) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = e.clientX - d.startX, dy = e.clientY - d.startY;
    if (!d.moved && Math.hypot(dx, dy) < 3) return;
    d.moved = true;
    d.el.style.transform = `translate(-50%, -50%) translate(${dx}px, ${dy}px)`;
  };
  const onChipPointerUp = (e: React.PointerEvent, p: any) => {
    const d = dragRef.current;
    dragRef.current = null;
    if (!d) return;
    d.el.style.transform = '';
    if (!d.moved) return;
    const { x, y } = toRatio(e.clientX, e.clientY);
    post(() => equipmentApi.addMove(drawingId, { machine_id: p.id, kind: 'move', x, y }));
  };
  // 未配置リストからのドロップ（HTML5 DnD）
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const mid = e.dataTransfer.getData('text/machine-id');
    if (!mid || readOnly) return;
    const { x, y } = toRatio(e.clientX, e.clientY);
    post(() => equipmentApi.addMove(drawingId, { machine_id: mid, kind: 'place', x, y }));
  };

  const commit = () => {
    const memo = prompt(`未確定の移動 ${drafts.length} 件を確定します。メモ（任意）:`);
    if (memo === null) return;
    post(() => equipmentApi.commit(drawingId, memo));
  };
  const undo = () => post(() => equipmentApi.undoMove(drawingId));
  const discard = () => { if (confirm(`未確定の移動 ${drafts.length} 件をすべて取り消します。よろしいですか？`)) post(() => equipmentApi.discardDraft(drawingId)); };
  const removeSelected = () => {
    const p = board?.placements?.find((x: any) => x.id === selected);
    if (!p) return;
    if (confirm(`${p.code} ${p.name} をこの図面から外します（確定するまで未確定です）`)) post(() => equipmentApi.addMove(drawingId, { machine_id: p.id, kind: 'remove' }));
  };
  const openMachineHistory = (id: string) => equipmentApi.machineHistory(id).then(r => setMachineHistory(r.data)).catch(e => setErr(errMsg(e)));

  // 未配置リストの項目は軽量（台帳紐付けを持たない）ので、選択時に機械詳細を取って補う
  const [selectedDetail, setSelectedDetail] = useState<any>(null);
  useEffect(() => {
    setSelectedDetail(null);
    if (!selected || board?.placements?.some((x: any) => x.id === selected)) return;
    equipmentApi.machine(selected).then(r => setSelectedDetail(r.data)).catch(() => {});
  }, [selected]);
  const selectedP = board?.placements?.find((x: any) => x.id === selected)
    || (selectedDetail && selectedDetail.id === selected ? selectedDetail : null)
    || board?.unplaced?.find((x: any) => x.id === selected) || null;
  const unplaced: any[] = useMemo(() => {
    const s = search.trim().toLowerCase();
    return (board?.unplaced || []).filter((m: any) => !s || `${m.code} ${m.name} ${m.model || ''} ${m.list_site || ''}`.toLowerCase().includes(s));
  }, [board, search]);

  if (!drawings.length) {
    return <div className="text-sm text-gray-500 p-4 border rounded bg-white">図面が登録されていません。「取込・設定」タブで図面（PNG/JPEG）を登録してください。</div>;
  }
  return (
    <div className="flex flex-col h-full gap-2">
      <ErrorBanner msg={err} onClose={() => setErr(null)} />
      <div className="flex items-center gap-2 flex-wrap text-sm">
        <select value={drawingId} onChange={e => { setDrawingId(e.target.value); setSelected(null); }} className="border rounded px-2 py-1">
          {drawings.map(d => <option key={d.id} value={d.id}>{d.site_name ? `[${d.site_name}] ` : ''}{d.name}{d.draft_count ? `（未確定 ${d.draft_count}）` : ''}</option>)}
        </select>
        <div className="flex items-center gap-1 text-xs text-gray-600">
          <Clock size={14} /><span>時点</span>
          <input type="date" value={asOf} onChange={e => setAsOf(e.target.value)} className="border rounded px-1 py-0.5" />
          {asOf && <button onClick={() => setAsOf('')} className="px-1.5 py-0.5 border rounded hover:bg-gray-50">現在に戻す</button>}
        </div>
        <div className="flex items-center gap-1 ml-auto">
          {drawing?.has_original && (
            <button onClick={() => setShowOriginal(v => !v)} className={`flex items-center gap-1 px-2 py-1 border rounded text-xs ${showOriginal ? 'bg-indigo-50 border-indigo-300 text-indigo-700' : 'hover:bg-gray-50'}`} title="番号入りの元図面を背景にする（初期配置の目安に）">
              {showOriginal ? <EyeOff size={14} /> : <Eye size={14} />}元図面
            </button>
          )}
          <button onClick={() => setZoom(z => Math.max(0.05, z / 1.25))} className="p-1 border rounded hover:bg-gray-50" title="縮小"><ZoomOut size={14} /></button>
          <span className="text-xs w-12 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom(z => Math.min(6, z * 1.25))} className="p-1 border rounded hover:bg-gray-50" title="拡大"><ZoomIn size={14} /></button>
          <button onClick={fit} className="p-1 border rounded hover:bg-gray-50" title="全体表示"><Maximize size={14} /></button>
          <button onClick={() => setHistoryOpen(true)} className="flex items-center gap-1 px-2 py-1 border rounded text-xs hover:bg-gray-50"><History size={14} />確定履歴</button>
        </div>
      </div>

      {/* 下書きバー */}
      {readOnly ? (
        <div className="text-xs px-3 py-1.5 rounded bg-slate-100 text-slate-700 border border-slate-200 flex items-center gap-2">
          <Clock size={14} />{asOf} 時点の配置を表示しています（閲覧のみ。配置 {board?.placements?.length ?? 0} 台）
        </div>
      ) : (
        <div className={`text-xs px-3 py-1.5 rounded border flex items-center gap-2 flex-wrap ${drafts.length ? 'bg-amber-50 border-amber-200 text-amber-900' : 'bg-white border-gray-200 text-gray-600'}`}>
          {drafts.length ? <span className="font-medium">未確定の移動 {drafts.length} 件</span> : <span>未確定の移動はありません。チップをドラッグで移動、右の未配置リストから図面へドロップで配置できます。</span>}
          {board?.last_commit && <span className="text-gray-500">最終確定 {fmtDT(board.last_commit.committed_at)} {board.last_commit.user_name}{board.last_commit.memo ? `「${board.last_commit.memo}」` : ''}</span>}
          <div className="ml-auto flex gap-1">
            <button disabled={!drafts.length || busy} onClick={undo} className="flex items-center gap-1 px-2 py-1 border rounded bg-white hover:bg-gray-50 disabled:opacity-40"><Undo2 size={12} />1つ戻す</button>
            <button disabled={!drafts.length || busy} onClick={discard} className="flex items-center gap-1 px-2 py-1 border rounded bg-white hover:bg-gray-50 disabled:opacity-40"><Trash2 size={12} />すべて破棄</button>
            <button disabled={!drafts.length || busy} onClick={commit} className="flex items-center gap-1 px-3 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40"><Check size={12} />確定</button>
          </div>
        </div>
      )}

      <div className="flex-1 min-h-0 flex gap-2">
        {/* キャンバス */}
        <div ref={containerRef} className="flex-1 min-w-0 overflow-auto border rounded bg-gray-100 relative" style={{ minHeight: 420 }}
          onDragOver={e => { if (!readOnly) e.preventDefault(); }} onDrop={onDrop} onClick={() => setSelected(null)}>
          {drawing && imgUrl && (
            <div className="relative m-2 bg-white shadow" style={{ width: W, height: H }}>
              <img src={imgUrl} alt={drawing.name} draggable={false} className="absolute inset-0 select-none" style={{ width: W, height: H }} />
              {(board?.placements || []).map((p: any) => (
                <div key={p.id}
                  onPointerDown={e => { e.stopPropagation(); onChipPointerDown(e, p); }} onPointerMove={onChipPointerMove}
                  onPointerUp={e => onChipPointerUp(e, p)} onClick={e => e.stopPropagation()} onDoubleClick={() => openMachineHistory(p.id)}
                  title={`${p.code} ${p.name}${p.model ? ' ' + p.model : ''}`}
                  className={`absolute select-none cursor-move rounded px-1.5 py-0.5 text-[11px] font-semibold leading-tight border shadow-sm whitespace-nowrap
                    ${p.draft ? 'bg-amber-300 border-amber-600 text-amber-950' : 'bg-red-500 border-red-700 text-white'}
                    ${selected === p.id ? 'ring-2 ring-indigo-500 z-20' : 'z-10'}`}
                  style={{ left: p.x * W, top: p.y * H, transform: 'translate(-50%, -50%)', touchAction: 'none' }}>
                  {p.code}
                </div>
              ))}
              {(board?.removed_in_draft || []).map((p: any) => (
                <div key={'rm' + p.id} title="確定すると図面から外れます" className="absolute rounded px-1.5 py-0.5 text-[11px] border border-dashed border-gray-500 text-gray-500 bg-white/70 line-through whitespace-nowrap"
                  style={{ left: p.x * W, top: p.y * H, transform: 'translate(-50%, -50%)' }}>{p.code}</div>
              ))}
            </div>
          )}
        </div>

        {/* 右パネル */}
        <div className="w-72 shrink-0 flex flex-col gap-2 min-h-0">
          {selectedP && (
            <div className="border rounded bg-white p-2 text-xs">
              <div className="flex items-center justify-between">
                <div className="font-bold text-sm text-gray-800">{selectedP.code}</div>
                <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">{STATUS_LABEL[selectedP.status] || selectedP.status}</span>
              </div>
              <div className="text-gray-800">{selectedP.name}</div>
              <div className="text-gray-500">{[selectedP.maker, selectedP.model, selectedP.made_year].filter(Boolean).join(' / ')}</div>
              {selectedP.list_site && <div className="text-gray-500">一覧表の工場: {selectedP.list_site}</div>}
              {selectedP.since && <div className="text-gray-500">この位置に置かれた日時: {fmtDT(selectedP.since)}</div>}
              {selectedP.draft && <div className="text-amber-700">未確定（{selectedP.draft === 'place' ? '新規配置' : selectedP.draft === 'move' ? '移動' : '外す'}）</div>}
              <div className="mt-1">{(selectedP.links || []).length ? selectedP.links.map((l: any) => <LinkBadge key={l.id} l={l} />) : <span className="text-gray-400">台帳未紐付け</span>}</div>
              <div className="flex gap-1 mt-2">
                <button onClick={() => openMachineHistory(selectedP.id)} className="flex items-center gap-1 px-2 py-1 border rounded hover:bg-gray-50"><History size={12} />履歴</button>
                {!readOnly && board?.placements?.some((x: any) => x.id === selected) && (
                  <button onClick={removeSelected} className="flex items-center gap-1 px-2 py-1 border rounded text-red-700 hover:bg-red-50"><X size={12} />図面から外す</button>
                )}
              </div>
            </div>
          )}
          {!readOnly && (
            <div className="border rounded bg-white flex-1 min-h-0 flex flex-col">
              <div className="px-2 py-1.5 border-b text-xs font-medium text-gray-700 flex items-center gap-1">
                この図面に無い機械 <span className="text-gray-400">({board?.unplaced?.length ?? 0})</span>
                <span className="ml-auto text-[10px] font-normal text-gray-400">同じ拠点を先に表示</span>
              </div>
              <div className="px-2 py-1 border-b">
                <div className="flex items-center gap-1 border rounded px-1.5"><Search size={12} className="text-gray-400" />
                  <input value={search} onChange={e => setSearch(e.target.value)} placeholder="番号・名称・工場で絞込" className="text-xs py-1 flex-1 outline-none" /></div>
              </div>
              <div className="flex-1 overflow-auto text-xs">
                {unplaced.map((m: any) => (
                  <div key={m.id} draggable onDragStart={e => { e.dataTransfer.setData('text/machine-id', m.id); e.dataTransfer.effectAllowed = 'move'; }}
                    onClick={() => setSelected(m.id)}
                    className={`px-2 py-1 border-b cursor-grab hover:bg-indigo-50 ${selected === m.id ? 'bg-indigo-50' : ''}`}
                    title="図面へドラッグして配置">
                    <span className="font-semibold text-gray-800">{m.code}</span> <span className="text-gray-700">{m.name}</span>
                    <div className="text-gray-400">{[m.list_site, m.model].filter(Boolean).join(' / ')}{!!m.placed_elsewhere?.length && <span className="ml-1 text-sky-700">他図面: {m.placed_elsewhere.join(', ')}</span>}</div>
                  </div>
                ))}
                {!unplaced.length && <div className="p-2 text-gray-400">該当なし</div>}
              </div>
            </div>
          )}
          {!readOnly && drafts.length > 0 && (
            <div className="border rounded bg-white text-xs max-h-40 overflow-auto">
              <div className="px-2 py-1 border-b font-medium text-gray-700">未確定の移動（新しい順）</div>
              {[...drafts].reverse().map((d: any) => (
                <div key={d.id} className="px-2 py-0.5 border-b text-gray-700">
                  <span className="font-semibold">{d.machine_code}</span> {d.kind === 'place' ? '配置' : d.kind === 'move' ? '移動' : '外す'}
                  <span className="text-gray-400 ml-1">{fmtDT(d.moved_at)} {d.user_name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {historyOpen && <CommitHistoryModal drawingId={drawingId} onClose={() => setHistoryOpen(false)} onPick={(iso: string) => { setAsOf(iso.slice(0, 10)); setHistoryOpen(false); }} />}
      {machineHistory && <MachineHistoryModal data={machineHistory} onClose={() => setMachineHistory(null)} />}
    </div>
  );
}

function CommitHistoryModal({ drawingId, onClose, onPick }: any) {
  const [commits, setCommits] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  useEffect(() => { equipmentApi.commits(drawingId).then(r => setCommits(r.data)); }, [drawingId]);
  const open = (id: string) => equipmentApi.commitDetail(id).then(r => setDetail(r.data));
  return (
    <Modal title="確定履歴（この図面）" onClose={onClose} wide>
      <div className="flex gap-3">
        <div className="w-80 shrink-0">
          {!commits.length && <div className="text-sm text-gray-500">確定履歴はまだありません</div>}
          {commits.map(c => (
            <div key={c.id} className={`border rounded p-2 mb-1 text-xs cursor-pointer hover:bg-gray-50 ${detail?.commit?.id === c.id ? 'bg-indigo-50 border-indigo-200' : ''}`} onClick={() => open(c.id)}>
              <div className="font-medium text-gray-800">{fmtDT(c.committed_at)} <span className="text-gray-500">{c.user_name}</span></div>
              <div className="text-gray-600">{c.move_count} 件の操作{c.memo && ` / ${c.memo}`}</div>
              <button onClick={e => { e.stopPropagation(); onPick(c.committed_at); }} className="mt-1 text-indigo-600 hover:underline">この時点の配置を表示</button>
            </div>
          ))}
        </div>
        <div className="flex-1 text-xs">
          {detail ? (
            <table className="w-full border-collapse">
              <thead><tr><Th>#</Th><Th>機械</Th><Th>操作</Th><Th>移動前</Th><Th>移動後</Th><Th>日時</Th><Th>操作者</Th><Th>状態</Th></tr></thead>
              <tbody>{detail.moves.map((m: any) => (
                <tr key={m.id} className={m.undone_at ? 'text-gray-400 line-through' : ''}>
                  <Td>{m.seq}</Td><Td><b>{m.machine_code}</b> {m.machine_name}</Td><Td>{m.kind === 'place' ? '配置' : m.kind === 'move' ? '移動' : '外す'}</Td>
                  <Td>{m.from_x != null ? `(${(m.from_x * 100).toFixed(1)}, ${(m.from_y * 100).toFixed(1)})` : '—'}</Td>
                  <Td>{m.to_x != null ? `(${(m.to_x * 100).toFixed(1)}, ${(m.to_y * 100).toFixed(1)})` : '—'}</Td>
                  <Td>{fmtDT(m.moved_at)}</Td><Td>{m.user_name}</Td><Td>{m.undone_at ? '取り消し' : '確定'}</Td>
                </tr>))}</tbody>
            </table>
          ) : <div className="text-gray-500">左の確定を選ぶと操作の明細を表示します（座標は図面の左上からの % ）</div>}
        </div>
      </div>
    </Modal>
  );
}

function MachineHistoryModal({ data, onClose }: any) {
  const m = data.machine;
  return (
    <Modal title={`履歴: ${m.code} ${m.name}`} onClose={onClose} wide>
      <div className="text-xs mb-3">
        <div className="font-medium text-gray-700 mb-1">配置の履歴（有効期間）</div>
        <table className="w-full border-collapse">
          <thead><tr><Th>図面</Th><Th>位置(%)</Th><Th>開始</Th><Th>終了</Th></tr></thead>
          <tbody>{data.placements.map((p: any, i: number) => (
            <tr key={i}><Td>{p.drawing_name || '(削除済み図面)'}</Td><Td>({(p.x * 100).toFixed(1)}, {(p.y * 100).toFixed(1)})</Td><Td>{fmtDT(p.valid_from)}</Td><Td>{p.valid_to ? fmtDT(p.valid_to) : <b className="text-green-700">現在</b>}</Td></tr>))}
            {!data.placements.length && <tr><Td>配置履歴なし</Td><Td /><Td /><Td /></tr>}
          </tbody>
        </table>
      </div>
      <div className="text-xs">
        <div className="font-medium text-gray-700 mb-1">移動の履歴（下書き・取り消しを含む）</div>
        <table className="w-full border-collapse">
          <thead><tr><Th>日時</Th><Th>図面</Th><Th>操作</Th><Th>移動前</Th><Th>移動後</Th><Th>操作者</Th><Th>状態</Th></tr></thead>
          <tbody>{data.moves.map((x: any) => (
            <tr key={x.id} className={x.undone_at ? 'text-gray-400 line-through' : ''}>
              <Td>{fmtDT(x.moved_at)}</Td><Td>{x.drawing_name}</Td><Td>{x.kind === 'place' ? '配置' : x.kind === 'move' ? '移動' : '外す'}</Td>
              <Td>{x.from_x != null ? `(${(x.from_x * 100).toFixed(1)}, ${(x.from_y * 100).toFixed(1)})` : '—'}</Td>
              <Td>{x.to_x != null ? `(${(x.to_x * 100).toFixed(1)}, ${(x.to_y * 100).toFixed(1)})` : '—'}</Td>
              <Td>{x.user_name}</Td><Td>{x.undone_at ? '取り消し' : x.commit_id ? `確定 ${fmtDT(x.committed_at)}` : '未確定'}</Td>
            </tr>))}
            {!data.moves.length && <tr><Td>移動履歴なし</Td><Td /><Td /><Td /><Td /><Td /><Td /></tr>}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}

// ================= ② 機械一覧 =================
function MachinesTab({ reloadKey, onChanged }: { reloadKey: number; onChanged: () => void }) {
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState({ search: '', list_site: '', status: '', link_state: '', placed: '' });
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const load = () => equipmentApi.machines(Object.fromEntries(Object.entries(q).filter(([, v]) => v))).then(r => setRows(r.data)).catch(e => setErr(errMsg(e)));
  useEffect(() => { load(); }, [reloadKey, q.list_site, q.status, q.link_state, q.placed]);
  const sites = useMemo(() => Array.from(new Set(rows.map(r => r.list_site).filter(Boolean))).sort(), [rows]);
  const filtered = useMemo(() => {
    const s = q.search.trim().toLowerCase();
    return rows.filter(r => !s || `${r.code} ${r.name} ${r.model || ''} ${r.maker || ''} ${r.notes || ''}`.toLowerCase().includes(s));
  }, [rows, q.search]);
  return (
    <div className="flex flex-col h-full">
      <ErrorBanner msg={err} onClose={() => setErr(null)} />
      <div className="flex gap-2 items-end mb-2 flex-wrap text-sm">
        <Field label="検索" v={q.search} on={(v: string) => setQ({ ...q, search: v })} w="w-48" placeholder="番号・名称・型式" />
        <div><label className="block text-xs text-gray-500 mb-0.5">一覧表の工場</label>
          <select value={q.list_site} onChange={e => setQ({ ...q, list_site: e.target.value })} className="border rounded px-2 py-1 text-sm"><option value="">すべて</option>{sites.map(s => <option key={s} value={s}>{s}</option>)}</select></div>
        <div><label className="block text-xs text-gray-500 mb-0.5">状態</label>
          <select value={q.status} onChange={e => setQ({ ...q, status: e.target.value })} className="border rounded px-2 py-1 text-sm"><option value="">すべて</option>{Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
        <div><label className="block text-xs text-gray-500 mb-0.5">台帳紐付け</label>
          <select value={q.link_state} onChange={e => setQ({ ...q, link_state: e.target.value })} className="border rounded px-2 py-1 text-sm"><option value="">すべて</option><option value="linked">紐付け済（確定）</option><option value="candidate">要確認あり</option><option value="unlinked">未紐付け</option></select></div>
        <div><label className="block text-xs text-gray-500 mb-0.5">配置</label>
          <select value={q.placed} onChange={e => setQ({ ...q, placed: e.target.value })} className="border rounded px-2 py-1 text-sm"><option value="">すべて</option><option value="yes">図面に配置済</option><option value="no">未配置</option></select></div>
        <span className="text-xs text-gray-500 ml-auto">{filtered.length} 件</span>
        <button onClick={() => setEditing({ code: '', name: '', status: 'active' })} className="flex items-center gap-1 px-2 py-1 border rounded text-xs hover:bg-gray-50"><Plus size={12} />機械を追加</button>
      </div>
      <div className="flex-1 overflow-auto border rounded bg-white">
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 bg-gray-50"><tr>
            <Th>管理ID</Th><Th>機器名</Th><Th>型式・仕様</Th><Th>メーカ</Th><Th>製造年</Th><Th right>価格</Th><Th>一覧表の工場</Th><Th>決算資産記載</Th><Th>現在の図面</Th><Th>固定資産台帳</Th><Th>状態</Th><Th />
          </tr></thead>
          <tbody>{filtered.map(r => (
            <tr key={r.id} className="hover:bg-indigo-50/40">
              <Td className="font-semibold whitespace-nowrap">{r.code}</Td><Td>{r.name}</Td><Td>{r.model}</Td><Td>{r.maker}</Td><Td>{r.made_year}</Td>
              <Td right>{r.price != null ? yen(r.price) : (r.price_raw || '')}</Td><Td>{r.list_site}</Td><Td>{r.asset_flag_raw}</Td>
              <Td>{r.placements?.length ? r.placements.map((p: any) => p.drawing_name).join(' / ') : <span className="text-gray-400">未配置</span>}</Td>
              <Td>{r.links.length ? r.links.map((l: any) => <LinkBadge key={l.id} l={l} />) : <span className="text-gray-400">—</span>}</Td>
              <Td><span className={`px-1.5 py-0.5 rounded ${r.status === 'active' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'}`}>{STATUS_LABEL[r.status] || r.status}</span></Td>
              <Td className="whitespace-nowrap">
                <button onClick={() => setEditing(r)} className="text-indigo-600 hover:underline mr-2">編集</button>
                <button onClick={() => equipmentApi.machineHistory(r.id).then(x => setHistory(x.data))} className="text-gray-600 hover:underline">履歴</button>
              </Td>
            </tr>))}</tbody>
        </table>
      </div>
      {editing && <MachineEditModal m={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); onChanged(); }} />}
      {history && <MachineHistoryModal data={history} onClose={() => setHistory(null)} />}
    </div>
  );
}

function MachineEditModal({ m, onClose, onSaved }: any) {
  const [f, setF] = useState<any>({ ...m });
  const [err, setErr] = useState<string | null>(null);
  const [links, setLinks] = useState<any[]>(m.links || []);
  const [assets, setAssets] = useState<any[]>([]);
  const [newLink, setNewLink] = useState({ asset_key: '', link_type: '本体', note: '' });
  const isNew = !m.id;
  useEffect(() => { if (!isNew) equipmentApi.assets({ machine_only: true }).then(r => setAssets(r.data.items)).catch(() => {}); }, []);
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const save = async () => {
    try {
      const body = { ...f }; delete body.links; delete body.placement; delete body.extra_rows;
      if (isNew) await equipmentApi.createMachine(body); else await equipmentApi.updateMachine(m.id, body);
      onSaved();
    } catch (e: any) { setErr(errMsg(e)); }
  };
  const reloadLinks = () => equipmentApi.machine(m.id).then(r => setLinks(r.data.links));
  const addLink = async () => {
    try { await equipmentApi.createLink({ machine_id: m.id, ...newLink, confidence: 'confirmed' }); setNewLink({ asset_key: '', link_type: '本体', note: '' }); reloadLinks(); }
    catch (e: any) { setErr(errMsg(e)); }
  };
  const fields: [string, string, string?][] = [
    ['name', '機器名'], ['category1', '分類1'], ['category2', '分類2'], ['maker', 'メーカ'], ['dealer', '商社'], ['model', '型式・仕様'],
    ['made_year', '製造年'], ['electric_spec', '電気仕様'], ['list_site', '一覧表の工場'], ['price_raw', '価格'],
    ['asset_flag_raw', '決算資産記載'], ['depreciation_raw', '償却資'], ['work_content', '工場作業内容'], ['legal_inspection', '法令点検'], ['inspector', '検査委託先'],
  ];
  return (
    <Modal title={isNew ? '機械を追加' : `機械を編集: ${m.code}`} onClose={onClose} wide>
      <ErrorBanner msg={err} onClose={() => setErr(null)} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
        <Field label="管理ID" v={f.code} on={(v: string) => set('code', v)} w="w-full" placeholder="例 SK-41" />
        {fields.map(([k, label]) => <Field key={k} label={label} v={f[k]} on={(v: string) => set(k, v)} w="w-full" />)}
        <div><label className="block text-xs text-gray-500 mb-0.5">状態</label>
          <select value={f.status || 'active'} onChange={e => set('status', e.target.value)} className="border rounded px-2 py-1 text-sm w-full">{Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2 text-sm">
        <div><label className="block text-xs text-gray-500 mb-0.5">備考</label><textarea value={f.notes || ''} onChange={e => set('notes', e.target.value)} className="border rounded px-2 py-1 text-sm w-full" rows={2} /></div>
        <div><label className="block text-xs text-gray-500 mb-0.5">修理記録</label><textarea value={f.repair_log || ''} onChange={e => set('repair_log', e.target.value)} className="border rounded px-2 py-1 text-sm w-full" rows={2} /></div>
      </div>
      {!!(m.extra_rows || []).length && (
        <div className="mt-2 text-xs text-gray-600"><b>付帯行（一覧表で同じ番号の行）:</b> {m.extra_rows.map((x: any, i: number) => <span key={i} className="ml-2">{x.name} {x.price_raw} {x.made_year}</span>)}</div>
      )}
      {!isNew && (
        <div className="mt-3 border-t pt-2 text-xs">
          <div className="font-medium text-gray-700 mb-1 flex items-center gap-1"><Link2 size={12} />固定資産台帳との紐付け</div>
          {links.map((l: any) => (
            <div key={l.id} className="flex items-center gap-2 py-0.5 border-b">
              <LinkBadge l={l} />
              <span className="text-gray-700">{l.asset ? `${l.asset.name}（${l.asset.account}・${l.asset.acquired_on || ''}・¥${yen(l.asset.price)}）` : <span className="text-red-600">最新期の台帳に無い</span>}</span>
              <span className="text-gray-400 flex-1 truncate">{l.note}</span>
              {l.confidence !== 'confirmed' && <button onClick={() => equipmentApi.updateLink(l.id, { confidence: 'confirmed' }).then(reloadLinks)} className="text-green-700 hover:underline">確定</button>}
              <button onClick={() => { if (confirm('紐付けを削除しますか？')) equipmentApi.deleteLink(l.id).then(reloadLinks); }} className="text-red-600 hover:underline">削除</button>
            </div>
          ))}
          <div className="flex items-end gap-2 mt-2 flex-wrap">
            <div className="w-96"><label className="block text-xs text-gray-500 mb-0.5">台帳の資産を追加（管理番号・名称で検索）</label>
              <SearchSelect value={newLink.asset_key} onChange={v => setNewLink({ ...newLink, asset_key: v })} placeholder="資産名・管理番号を入力"
                options={assets.map(a => ({ value: a.asset_key, label: `${a.asset_no || '(番号なし)'} ${a.name}`, sub: `${a.account} ${a.acquired_on || ''} ¥${yen(a.price)}${a.links.length ? ' 紐付け済: ' + a.links.map((x: any) => x.machine_code).join(',') : ''}` }))} /></div>
            <div><label className="block text-xs text-gray-500 mb-0.5">種別</label>
              <select value={newLink.link_type} onChange={e => setNewLink({ ...newLink, link_type: e.target.value })} className="border rounded px-2 py-1 text-sm">{LINK_TYPES.map(t => <option key={t}>{t}</option>)}</select></div>
            <Field label="メモ" v={newLink.note} on={(v: string) => setNewLink({ ...newLink, note: v })} w="w-48" />
            <button disabled={!newLink.asset_key} onClick={addLink} className="px-2 py-1 border rounded hover:bg-gray-50 disabled:opacity-40">紐付ける</button>
          </div>
        </div>
      )}
      <div className="flex justify-end gap-2 mt-3">
        <button onClick={onClose} className="px-3 py-1.5 border rounded text-sm">閉じる</button>
        <button onClick={save} className="px-3 py-1.5 rounded bg-indigo-600 text-white text-sm hover:bg-indigo-700">保存</button>
      </div>
    </Modal>
  );
}

// ================= ③ 固定資産台帳・突合 =================
function AssetsTab({ reloadKey, onChanged }: { reloadKey: number; onChanged: () => void }) {
  const [periods, setPeriods] = useState<any[]>([]);
  const [period, setPeriod] = useState('');
  const [rec, setRec] = useState<any>(null);
  const [assets, setAssets] = useState<any[]>([]);
  const [machines, setMachines] = useState<any[]>([]);
  const [q, setQ] = useState({ search: '', machine_only: true, unlinked: false });
  const [err, setErr] = useState<string | null>(null);
  const [view, setView] = useState<'summary' | 'assets'>('summary');
  const [linking, setLinking] = useState<any>(null);   // asset row being linked
  const [pick, setPick] = useState({ machine_id: '', link_type: '本体', note: '' });

  useEffect(() => { equipmentApi.assetPeriods().then(r => { setPeriods(r.data); if (!period && r.data.length) setPeriod(r.data[0].period); }).catch(e => setErr(errMsg(e))); }, [reloadKey]);
  const load = () => {
    if (!period) return;
    equipmentApi.reconcile(period).then(r => setRec(r.data)).catch(e => setErr(errMsg(e)));
    equipmentApi.assets({ period, machine_only: q.machine_only || undefined, unlinked: q.unlinked || undefined }).then(r => setAssets(r.data.items)).catch(e => setErr(errMsg(e)));
  };
  useEffect(() => { load(); }, [period, q.machine_only, q.unlinked, reloadKey]);
  useEffect(() => { equipmentApi.machines().then(r => setMachines(r.data)).catch(() => {}); }, [reloadKey]);
  const filtered = useMemo(() => {
    const s = q.search.trim().toLowerCase();
    return assets.filter(a => !s || `${a.asset_no || ''} ${a.name} ${a.account || ''} ${a.site_note || ''} ${a.remarks || ''}`.toLowerCase().includes(s));
  }, [assets, q.search]);
  const doLink = async () => {
    try {
      await equipmentApi.createLink({ machine_id: pick.machine_id, asset_key: linking.asset_key, link_type: pick.link_type, note: pick.note, confidence: 'confirmed' });
      setLinking(null); setPick({ machine_id: '', link_type: '本体', note: '' }); load(); onChanged();
    } catch (e: any) { setErr(errMsg(e)); }
  };
  const confirmLink = (id: string) => equipmentApi.updateLink(id, { confidence: 'confirmed' }).then(() => { load(); onChanged(); }).catch(e => setErr(errMsg(e)));
  const deleteLink = (id: string) => { if (confirm('この紐付けを削除しますか？')) equipmentApi.deleteLink(id).then(() => { load(); onChanged(); }).catch(e => setErr(errMsg(e))); };
  const s = rec?.summary;
  if (!periods.length) return <div className="text-sm text-gray-500 p-4 border rounded bg-white">固定資産台帳がまだ取り込まれていません。「取込・設定」タブで台帳 CSV を取り込んでください。</div>;
  return (
    <div className="flex flex-col h-full">
      <ErrorBanner msg={err} onClose={() => setErr(null)} />
      <div className="flex items-center gap-2 mb-2 text-sm flex-wrap">
        <label className="text-xs text-gray-500">期</label>
        <select value={period} onChange={e => setPeriod(e.target.value)} className="border rounded px-2 py-1">{periods.map(p => <option key={p.period} value={p.period}>{p.period}（{p.count} 件）</option>)}</select>
        <div className="flex gap-1 ml-2">
          <button onClick={() => setView('summary')} className={`px-2 py-1 rounded text-xs border ${view === 'summary' ? 'bg-indigo-600 text-white border-indigo-600' : 'hover:bg-gray-50'}`}>突合サマリ</button>
          <button onClick={() => setView('assets')} className={`px-2 py-1 rounded text-xs border ${view === 'assets' ? 'bg-indigo-600 text-white border-indigo-600' : 'hover:bg-gray-50'}`}>台帳の一覧</button>
        </div>
      </div>
      {view === 'summary' && s && (
        <div className="flex-1 overflow-auto">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-3 text-xs">
            {[['機械（一覧表）', s.machines, ''], ['うち台帳未紐付け', s.machines_without_asset, ''], ['一覧表で「有」なのに未紐付け', s.flagged_but_unlinked, s.flagged_but_unlinked ? 'bg-red-50 border-red-200' : ''],
              ['台帳の機械系科目', s.assets_machine_accounts, ''], ['うち機械に未紐付け', s.assets_without_machine, ''], ['要確認の紐付け', s.candidates, s.candidates ? 'bg-amber-50 border-amber-200' : '']].map(([label, v, tone]: any) => (
              <div key={label} className={`rounded border px-3 py-2 ${tone || 'bg-white border-gray-200'}`}><div className="text-gray-500">{label}</div><div className="text-lg font-bold text-gray-800">{v}</div></div>))}
          </div>
          <Section title={`一覧表では決算資産「有」なのに台帳に紐付いていない機械（${rec.machines_flagged_but_unlinked.length}）`} tone="red">
            <SimpleTable head={['管理ID', '機器名', '型式', '価格', '製造年', '一覧表の工場', '決算資産記載']}
              rows={rec.machines_flagged_but_unlinked.map((m: any) => [m.code, m.name, m.model, m.price != null ? yen(m.price) : m.price_raw, m.made_year, m.list_site, m.asset_flag_raw])} />
          </Section>
          <Section title={`要確認の紐付け（自動・CSV取込で候補になったもの。内容を見て確定または削除）（${rec.candidates.length}）`} tone="amber">
            <table className="w-full border-collapse text-xs">
              <thead><tr><Th>機械</Th><Th>台帳</Th><Th>種別</Th><Th>根拠・メモ</Th><Th /></tr></thead>
              <tbody>{rec.candidates.map((l: any) => (
                <tr key={l.id}>
                  <Td><b>{l.machine_code}</b> {l.machine_name}</Td>
                  <Td>{l.asset ? `${l.asset.asset_no || '(番号なし)'} ${l.asset.name}　¥${yen(l.asset.price)} ${l.asset.acquired_on || ''}` : l.asset_key}</Td>
                  <Td>{l.link_type}</Td><Td className="text-gray-600">{l.note}</Td>
                  <Td className="whitespace-nowrap"><button onClick={() => confirmLink(l.id)} className="text-green-700 hover:underline mr-2">確定</button><button onClick={() => deleteLink(l.id)} className="text-red-600 hover:underline">削除</button></Td>
                </tr>))}</tbody>
            </table>
          </Section>
          <Section title={`台帳の機械系科目で機械に紐付いていない資産（${rec.assets_without_machine.length}。PC・什器など機械以外も含む）`}>
            <table className="w-full border-collapse text-xs">
              <thead><tr><Th>管理番号</Th><Th>資産名</Th><Th>勘定科目</Th><Th>取得日</Th><Th right>取得価額</Th><Th>仕訳摘要</Th><Th /></tr></thead>
              <tbody>{rec.assets_without_machine.map((a: any) => (
                <tr key={a.asset_key}><Td>{a.asset_no || <span className="text-gray-400">なし</span>}</Td><Td>{a.name}</Td><Td>{a.account}</Td><Td>{a.acquired_on}</Td><Td right>{yen(a.price)}</Td><Td>{a.site_note}</Td>
                  <Td><button onClick={() => setLinking(a)} className="text-indigo-600 hover:underline">機械に紐付け</button></Td></tr>))}</tbody>
            </table>
          </Section>
          <Section title={`台帳に紐付いていない機械（${rec.machines_without_asset.length}。少額・除去済み・記載なしを含む）`}>
            <SimpleTable head={['管理ID', '機器名', '型式', '価格', '製造年', '一覧表の工場', '決算資産記載', '状態']}
              rows={rec.machines_without_asset.map((m: any) => [m.code, m.name, m.model, m.price != null ? yen(m.price) : m.price_raw, m.made_year, m.list_site, m.asset_flag_raw, STATUS_LABEL[m.status] || m.status])} />
          </Section>
        </div>
      )}
      {view === 'assets' && (
        <div className="flex-1 min-h-0 flex flex-col">
          <div className="flex gap-3 items-end mb-2 text-sm flex-wrap">
            <Field label="検索" v={q.search} on={(v: string) => setQ({ ...q, search: v })} w="w-56" placeholder="管理番号・資産名・摘要" />
            <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={q.machine_only} onChange={e => setQ({ ...q, machine_only: e.target.checked })} />機械系科目のみ（機械装置・工具器具備品・一括償却・リース）</label>
            <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={q.unlinked} onChange={e => setQ({ ...q, unlinked: e.target.checked })} />未紐付けのみ</label>
            <span className="text-xs text-gray-500 ml-auto">{filtered.length} 件</span>
          </div>
          <div className="flex-1 overflow-auto border rounded bg-white">
            <table className="w-full border-collapse text-xs">
              <thead className="sticky top-0 bg-gray-50"><tr><Th>管理番号</Th><Th>資産名</Th><Th>勘定科目</Th><Th>取得日</Th><Th right>取得価額</Th><Th right>未償却残高</Th><Th>仕訳摘要</Th><Th>紐付け先の機械</Th><Th /></tr></thead>
              <tbody>{filtered.map(a => (
                <tr key={a.asset_key} className="hover:bg-indigo-50/40">
                  <Td className="whitespace-nowrap">{a.asset_no || <span className="text-gray-400">なし</span>}</Td><Td>{a.name}</Td><Td>{a.account}</Td><Td>{a.acquired_on}</Td>
                  <Td right>{yen(a.price)}</Td><Td right>{yen(a.ending_balance)}</Td><Td>{a.site_note}</Td>
                  <Td>{a.links.map((l: any) => (
                    <span key={l.id} className={`inline-flex items-center gap-1 mr-1 mb-0.5 px-1.5 py-0.5 rounded text-[11px] border ${l.confidence === 'confirmed' ? 'bg-green-50 text-green-800 border-green-200' : 'bg-amber-50 text-amber-800 border-amber-200'}`} title={l.note || ''}>
                      <b>{l.machine_code}</b> {l.machine_name}{l.link_type !== '本体' && ` (${l.link_type})`}
                      {l.confidence !== 'confirmed' && <button onClick={() => confirmLink(l.id)} className="text-green-700" title="確定"><Check size={10} /></button>}
                      <button onClick={() => deleteLink(l.id)} className="text-red-600" title="削除"><X size={10} /></button>
                    </span>))}</Td>
                  <Td><button onClick={() => setLinking(a)} className="text-indigo-600 hover:underline whitespace-nowrap">紐付け</button></Td>
                </tr>))}</tbody>
            </table>
          </div>
        </div>
      )}
      {linking && (
        <Modal title={`機械に紐付け: ${linking.asset_no || ''} ${linking.name}`} onClose={() => setLinking(null)}>
          <div className="text-xs text-gray-600 mb-2">{linking.account}・取得 {linking.acquired_on}・¥{yen(linking.price)}・{linking.site_note}</div>
          <div className="flex flex-col gap-2 text-sm">
            <div><label className="block text-xs text-gray-500 mb-0.5">機械（管理ID・名称で検索）</label>
              <SearchSelect value={pick.machine_id} onChange={v => setPick({ ...pick, machine_id: v })} placeholder="管理ID・機器名を入力"
                options={machines.map(m => ({ value: m.id, label: `${m.code} ${m.name}`, sub: `${m.list_site || ''} ${m.model || ''} ${m.price != null ? '¥' + yen(m.price) : m.price_raw || ''} ${m.made_year || ''}` }))} /></div>
            <div className="flex gap-2">
              <div><label className="block text-xs text-gray-500 mb-0.5">種別</label>
                <select value={pick.link_type} onChange={e => setPick({ ...pick, link_type: e.target.value })} className="border rounded px-2 py-1 text-sm">{LINK_TYPES.map(t => <option key={t}>{t}</option>)}</select></div>
              <Field label="メモ" v={pick.note} on={(v: string) => setPick({ ...pick, note: v })} w="w-72" />
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => setLinking(null)} className="px-3 py-1.5 border rounded text-sm">閉じる</button>
            <button disabled={!pick.machine_id} onClick={doLink} className="px-3 py-1.5 rounded bg-indigo-600 text-white text-sm hover:bg-indigo-700 disabled:opacity-40">紐付ける（確定）</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Section({ title, tone, children }: any) {
  const [open, setOpen] = useState(true);
  const cls = tone === 'red' ? 'border-red-200' : tone === 'amber' ? 'border-amber-200' : 'border-gray-200';
  return (
    <div className={`border rounded bg-white mb-3 ${cls}`}>
      <button onClick={() => setOpen(o => !o)} className="w-full text-left px-3 py-1.5 text-xs font-medium text-gray-700 border-b flex items-center gap-2">{open ? '▾' : '▸'} {title}</button>
      {open && <div className="p-2 overflow-auto max-h-96">{children}</div>}
    </div>
  );
}
function SimpleTable({ head, rows }: { head: string[]; rows: any[][] }) {
  if (!rows.length) return <div className="text-xs text-gray-400 px-1">該当なし</div>;
  return (
    <table className="w-full border-collapse text-xs">
      <thead><tr>{head.map(h => <Th key={h}>{h}</Th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <Td key={j}>{c}</Td>)}</tr>)}</tbody>
    </table>
  );
}

// ================= ④ 取込・設定 =================
function SetupTab({ onChanged }: { onChanged: () => void }) {
  const admin = isAdmin();
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sites, setSites] = useState<any[]>([]);
  const [drawings, setDrawings] = useState<any[]>([]);
  const [mFile, setMFile] = useState<File | null>(null); const [mOverwrite, setMOverwrite] = useState(false); const [mPreview, setMPreview] = useState<any>(null);
  const [aFile, setAFile] = useState<File | null>(null); const [aPeriod, setAPeriod] = useState(''); const [aPreview, setAPreview] = useState<any>(null);
  const [lFile, setLFile] = useState<File | null>(null); const [lPreview, setLPreview] = useState<any>(null);
  const [dForm, setDForm] = useState<any>({ site_id: '', name: '', scale_note: '', valid_from: '', file: null, original: null });
  const [pFile, setPFile] = useState<File | null>(null); const [pPreview, setPPreview] = useState<any>(null);
  const [newSite, setNewSite] = useState({ code: '', name: '' });
  const [busy, setBusy] = useState(false);

  const load = () => {
    equipmentApi.sites().then(r => { setSites(r.data); if (!dForm.site_id && r.data.length) setDForm((f: any) => ({ ...f, site_id: r.data[0].id })); }).catch(() => {});
    equipmentApi.drawings({ include_inactive: true }).then(r => setDrawings(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);
  const run = async (fn: () => Promise<any>, okMsg?: (r: any) => string) => {
    setBusy(true); setErr(null);
    try { const r = await fn(); if (okMsg) setMsg(okMsg(r.data)); load(); onChanged(); return r.data; }
    catch (e: any) { setErr(errMsg(e)); }
    finally { setBusy(false); }
  };
  const setup = () => { if (confirm('機械管理用テーブル（eq_*）を作成します。既存テーブルは変更しません。実行しますか？')) run(() => equipmentApi.setup(), r => r.message); };

  if (!admin) return <div className="text-sm text-gray-500 p-4 border rounded bg-white">取込・図面登録は管理者のみ行えます。</div>;
  return (
    <div className="overflow-auto h-full text-sm">
      <ErrorBanner msg={err} onClose={() => setErr(null)} />
      {msg && <div className="mb-2 text-xs px-3 py-2 rounded bg-blue-50 text-blue-800 border border-blue-200 flex items-center gap-2"><span className="flex-1">{msg}</span><button onClick={() => setMsg(null)}><X size={12} /></button></div>}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card title="① テーブル作成（初回のみ）">
          <p className="text-xs text-gray-500 mb-2">本番（Render）は移行ツールを使わないため、初回にこのボタンでテーブルを作ります（何度押しても安全）。</p>
          <button onClick={setup} disabled={busy} className="px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50">テーブル作成（初回）</button>
        </Card>
        <Card title="② 機械一覧表の取込（CSV）">
          <p className="text-xs text-gray-500 mb-2">PDF の一覧表は <code>tools/equipment_machine_list_pdf2csv.py</code> で CSV にしてから取り込みます（列名は一覧表のまま）。同じ管理番号の複数行は本体＋付帯行として 1 台にまとめます。</p>
          <input type="file" accept=".csv" onChange={e => { setMFile(e.target.files?.[0] || null); setMPreview(null); }} className="text-xs" />
          <label className="flex items-center gap-1 text-xs mt-1"><input type="checkbox" checked={mOverwrite} onChange={e => setMOverwrite(e.target.checked)} />登録済みの機械も CSV の内容で上書きする（状態は保持）</label>
          <div className="flex gap-2 mt-2">
            <button disabled={!mFile || busy} onClick={() => run(() => equipmentApi.importMachines(mFile!, false, mOverwrite)).then(d => d && setMPreview(d))} className="px-3 py-1.5 border rounded hover:bg-gray-50 disabled:opacity-40">プレビュー</button>
            <button disabled={!mPreview || busy} onClick={() => run(() => equipmentApi.importMachines(mFile!, true, mOverwrite), r => `機械を取り込みました（新規 ${r.created} / 更新 ${r.updated} / 据え置き ${r.unchanged}）`).then(() => setMPreview(null))} className="px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40">取込を確定</button>
          </div>
          {mPreview && <div className="mt-2 text-xs bg-gray-50 border rounded p-2">
            行 {mPreview.rows} → 機械 {mPreview.machines} 台（新規 {mPreview.created} / 更新 {mPreview.updated} / 据え置き {mPreview.unchanged}、付帯行 {mPreview.attached_rows}）
            {!!mPreview.skipped.length && <div className="text-gray-500 mt-1">管理番号が無く取り込まない行: {mPreview.skipped.join('、')}</div>}
          </div>}
        </Card>
        <Card title="③ 固定資産台帳の取込（CSV・期ごと）">
          <p className="text-xs text-gray-500 mb-2">会計ソフトの台帳 CSV（Shift_JIS 可）をそのまま。期はファイル名の「2026年02月〜」から推定します。同じ期を再取込すると置き換えます。</p>
          <div className="flex items-end gap-2 flex-wrap">
            <input type="file" accept=".csv" onChange={e => { setAFile(e.target.files?.[0] || null); setAPreview(null); }} className="text-xs" />
            <Field label="期（YYYY-MM）" v={aPeriod} on={setAPeriod} w="w-28" placeholder="自動" />
          </div>
          <div className="flex gap-2 mt-2">
            <button disabled={!aFile || busy} onClick={() => run(() => equipmentApi.importAssets(aFile!, false, aPeriod || undefined)).then(d => d && setAPreview(d))} className="px-3 py-1.5 border rounded hover:bg-gray-50 disabled:opacity-40">プレビュー</button>
            <button disabled={!aPreview || busy} onClick={() => run(() => equipmentApi.importAssets(aFile!, true, aPreview.period), r => `台帳 ${r.period} 期を取り込みました（${r.rows} 件）`).then(() => setAPreview(null))} className="px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40">取込を確定</button>
          </div>
          {aPreview && <div className="mt-2 text-xs bg-gray-50 border rounded p-2">
            <div>期 <b>{aPreview.period}</b>・{aPreview.rows} 件{aPreview.replaced ? `（既存 ${aPreview.replaced} 件を置き換え）` : ''}</div>
            <div className="text-gray-600">{Object.entries(aPreview.accounts).map(([k, v]) => `${k} ${v}`).join(' / ')}</div>
            {aPreview.diff.prev_period && <div className="mt-1">前期 {aPreview.diff.prev_period} との差分: 新規 {aPreview.diff.added.length} / 消滅 {aPreview.diff.removed.length} / 価額変更 {aPreview.diff.price_changed.length}
              <ul className="ml-3 mt-1 max-h-40 overflow-auto">
                {aPreview.diff.added.map((x: any) => <li key={'a' + x.asset_key} className="text-green-700">＋ {x.asset_key} {x.name} ¥{yen(x.price)}</li>)}
                {aPreview.diff.removed.map((x: any) => <li key={'r' + x.asset_key} className="text-red-700">－ {x.asset_key} {x.name} ¥{yen(x.price)}</li>)}
                {aPreview.diff.price_changed.map((x: any) => <li key={'p' + x.asset_key} className="text-amber-700">± {x.asset_key} {x.name} ¥{yen(x.before)} → ¥{yen(x.after)}</li>)}
              </ul></div>}
          </div>}
        </Card>
        <Card title="④ 台帳との紐付け">
          <p className="text-xs text-gray-500 mb-2">「自動紐付け」は台帳の資産名先頭の番号（SKF-07 = 桜田 F-07 のような工場プレフィックス付きを含む）で機械を探し、価額が一致すれば確定、しなければ要確認で登録します。番号が無い資産は CSV（machine_code, asset_key, link_type, confidence, note）で取り込めます（tools/equipment_initial_links.py）。</p>
          <button disabled={busy} onClick={() => run(() => equipmentApi.autoLink(), r => `自動紐付け: 登録 ${r.created}（確定 ${r.confirmed} / 要確認 ${r.candidate}）、番号で見つからず ${r.no_match}`)} className="flex items-center gap-1 px-3 py-1.5 border rounded hover:bg-gray-50 disabled:opacity-40"><RefreshCw size={12} />自動紐付けを実行</button>
          <div className="flex items-end gap-2 mt-3 flex-wrap">
            <input type="file" accept=".csv" onChange={e => { setLFile(e.target.files?.[0] || null); setLPreview(null); }} className="text-xs" />
            <button disabled={!lFile || busy} onClick={() => run(() => equipmentApi.importLinks(lFile!, false)).then(d => d && setLPreview(d))} className="px-3 py-1.5 border rounded hover:bg-gray-50 disabled:opacity-40">プレビュー</button>
            <button disabled={!lPreview || busy} onClick={() => run(() => equipmentApi.importLinks(lFile!, true), r => `紐付け CSV: ${r.created} 件登録`).then(() => setLPreview(null))} className="px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40">取込を確定</button>
          </div>
          {lPreview && <div className="mt-2 text-xs bg-gray-50 border rounded p-2">登録予定 {lPreview.created} 件{!!lPreview.errors.length && <div className="text-red-700 mt-1">{lPreview.errors.map((e: string) => <div key={e}>{e}</div>)}</div>}</div>}
        </Card>
        <Card title="⑤ 図面の登録">
          <p className="text-xs text-gray-500 mb-2">背景用の画像（PNG/JPEG）を登録します。配置図 PDF は <code>tools/equipment_prepare_drawings.py</code> で「赤い機械番号を消した画像」と「元図面」の 2 枚にできます。座標は画像に対する比率で持つので、同じ縦横比なら画像を差し替えても配置はずれません。</p>
          <div className="grid grid-cols-2 gap-2">
            <div><label className="block text-xs text-gray-500 mb-0.5">拠点</label>
              <select value={dForm.site_id} onChange={e => setDForm({ ...dForm, site_id: e.target.value })} className="border rounded px-2 py-1 text-sm w-full">{sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <Field label="図面名" v={dForm.name} on={(v: string) => setDForm({ ...dForm, name: v })} w="w-full" placeholder="例 桜田工場北 製缶" />
            <Field label="縮尺メモ" v={dForm.scale_note} on={(v: string) => setDForm({ ...dForm, scale_note: v })} w="w-full" placeholder="1/200" />
            <Field label="図面の日付" type="date" v={dForm.valid_from} on={(v: string) => setDForm({ ...dForm, valid_from: v })} w="w-full" />
            <div><label className="block text-xs text-gray-500 mb-0.5">背景画像（必須）</label><input type="file" accept="image/png,image/jpeg" onChange={e => setDForm({ ...dForm, file: e.target.files?.[0] || null })} className="text-xs" /></div>
            <div><label className="block text-xs text-gray-500 mb-0.5">元図面（番号入り・任意）</label><input type="file" accept="image/png,image/jpeg" onChange={e => setDForm({ ...dForm, original: e.target.files?.[0] || null })} className="text-xs" /></div>
          </div>
          <button disabled={!dForm.file || !dForm.name || !dForm.site_id || busy} onClick={() => {
            const fd = new FormData(); fd.append('site_id', dForm.site_id); fd.append('name', dForm.name); fd.append('file', dForm.file);
            if (dForm.original) fd.append('original', dForm.original); if (dForm.scale_note) fd.append('scale_note', dForm.scale_note); if (dForm.valid_from) fd.append('valid_from', dForm.valid_from);
            run(() => equipmentApi.createDrawing(fd), r => `図面を登録しました（${r.width_px}×${r.height_px}px）`).then(() => setDForm({ ...dForm, name: '', file: null, original: null }));
          }} className="mt-2 flex items-center gap-1 px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40"><Upload size={12} />登録</button>
          <div className="mt-3 text-xs">
            <div className="font-medium text-gray-700 mb-1">登録済みの図面</div>
            <table className="w-full border-collapse">
              <thead><tr><Th>拠点</Th><Th>図面名</Th><Th>サイズ</Th><Th>配置</Th><Th>未確定</Th><Th>状態</Th><Th /></tr></thead>
              <tbody>{drawings.map(d => (
                <tr key={d.id} className={d.is_active ? '' : 'text-gray-400'}>
                  <Td>{d.site_name}</Td><Td>{d.name}{d.has_original && <span className="ml-1 text-gray-400">(元図面あり)</span>}</Td><Td>{d.width_px}×{d.height_px}</Td><Td>{d.placed_count}</Td><Td>{d.draft_count || ''}</Td>
                  <Td>{d.is_active ? '有効' : '無効'}</Td>
                  <Td className="whitespace-nowrap">
                    <button onClick={() => { const n = prompt('図面名', d.name); if (n) run(() => equipmentApi.updateDrawing(d.id, { name: n })); }} className="text-indigo-600 hover:underline mr-2">名称</button>
                    <button onClick={() => run(() => equipmentApi.updateDrawing(d.id, { is_active: !d.is_active }))} className="text-gray-600 hover:underline mr-2">{d.is_active ? '無効化' : '有効化'}</button>
                    <button onClick={() => { if (confirm(`図面「${d.name}」を削除します（配置履歴があれば無効化にとどめます）`)) run(() => equipmentApi.deleteDrawing(d.id), r => r.message); }} className="text-red-600 hover:underline">削除</button>
                  </Td>
                </tr>))}</tbody>
            </table>
          </div>
        </Card>
        <Card title="⑦ 初期配置の取込（CSV）">
          <p className="text-xs text-gray-500 mb-2">CSV（drawing, machine_code, x, y）で図面上の位置を一括登録します。drawing は⑤で登録した図面名、x/y は画像の左上からの比率（0〜1）。図面ごとに「初期配置（CSV取込）」として確定され、既にその図面に置かれている機械は飛ばします。元図面の赤枠から作った CSV は <code>tools/equipment_extract_positions.py</code> で作れます。</p>
          <div className="flex items-end gap-2 flex-wrap">
            <input type="file" accept=".csv" onChange={e => { setPFile(e.target.files?.[0] || null); setPPreview(null); }} className="text-xs" />
            <button disabled={!pFile || busy} onClick={() => run(() => equipmentApi.importPlacements(pFile!, false)).then(d => d && setPPreview(d))} className="px-3 py-1.5 border rounded hover:bg-gray-50 disabled:opacity-40">プレビュー</button>
            <button disabled={!pPreview || busy} onClick={() => run(() => equipmentApi.importPlacements(pFile!, true), r => `初期配置を ${r.placed} 件登録しました`).then(() => setPPreview(null))} className="px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40">取込を確定</button>
          </div>
          {pPreview && <div className="mt-2 text-xs bg-gray-50 border rounded p-2">
            <div>配置予定 <b>{pPreview.placed}</b> 件（{pPreview.drawings.map((d: any) => `${d.drawing} ${d.to_place}/${d.rows}`).join(' / ')}）</div>
            {!!pPreview.skipped.length && <div className="text-gray-500 mt-1">飛ばす: {pPreview.skipped.join('、')}</div>}
            {!!pPreview.errors.length && <div className="text-red-700 mt-1">{pPreview.errors.map((e: string) => <div key={e}>{e}</div>)}</div>}
          </div>}
        </Card>
        <Card title="⑥ 拠点">
          <div className="flex flex-wrap gap-1 mb-2 text-xs">{sites.map(s => <span key={s.id} className={`px-2 py-0.5 rounded border ${s.is_active ? 'bg-white' : 'bg-gray-100 text-gray-400'}`}>{s.name} <span className="text-gray-400">({s.code})</span></span>)}</div>
          <div className="flex items-end gap-2">
            <Field label="コード" v={newSite.code} on={(v: string) => setNewSite({ ...newSite, code: v })} w="w-28" placeholder="例 daiichi" />
            <Field label="名称" v={newSite.name} on={(v: string) => setNewSite({ ...newSite, name: v })} w="w-40" placeholder="例 第1倉庫" />
            <button disabled={!newSite.code || !newSite.name || busy} onClick={() => run(() => equipmentApi.createSite(newSite), () => '拠点を追加しました').then(() => setNewSite({ code: '', name: '' }))} className="px-3 py-1.5 border rounded hover:bg-gray-50 disabled:opacity-40">追加</button>
          </div>
        </Card>
      </div>
    </div>
  );
}
function Card({ title, children }: any) {
  return <div className="border rounded bg-white p-3"><div className="font-medium text-gray-800 mb-2">{title}</div>{children}</div>;
}
