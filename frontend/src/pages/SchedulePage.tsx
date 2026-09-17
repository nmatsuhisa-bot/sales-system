import { useState, useEffect, useRef, Fragment } from 'react';
import { authApi, mastersApi, scheduleApi } from '../api';
import SearchSelect from '../components/common/SearchSelect';

interface User { id: string; full_name: string; email: string; department?: string; role?: string; }
interface ScheduleEntry {
  id: string; userId: string; date: string; slot: 'am' | 'pm'; title: string; color: string;
  groupId?: string | null;   // 同じ予定として作られた行をまとめるID（複数参加者・終日）
}

// グリッド列幅（px）。sticky列（日付/時間）のleft値と一致させる必要があるため定数化
const DATE_W = 56, TIME_W = 32, USER_W = 76;

const COLOR_OPTIONS = [
  { label: '青', value: 'bg-blue-200 border-blue-400 text-blue-800' },
  { label: '緑', value: 'bg-green-200 border-green-400 text-green-800' },
  { label: '黄', value: 'bg-yellow-200 border-yellow-400 text-yellow-800' },
  { label: '赤', value: 'bg-red-200 border-red-400 text-red-800' },
  { label: '紫', value: 'bg-purple-200 border-purple-400 text-purple-800' },
  { label: '橙', value: 'bg-orange-200 border-orange-400 text-orange-800' },
];

function getWeekDates(base: Date): Date[] {
  const day = base.getDay();
  const monday = new Date(base);
  monday.setDate(base.getDate() - (day === 0 ? 6 : day - 1));
  return Array.from({ length: 7 }, (_, i) => { const d = new Date(monday); d.setDate(monday.getDate() + i); return d; });
}
function getMonthDates(base: Date): Date[] {
  const year = base.getFullYear(), month = base.getMonth();
  const days = new Date(year, month + 1, 0).getDate();
  return Array.from({ length: days }, (_, i) => new Date(year, month, i + 1));
}
function dateKey(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function formatDate(d: Date): string {
  const w = ['日','月','火','水','木','金','土'];
  return `${d.getMonth()+1}/${d.getDate()}\n(${w[d.getDay()]})`;
}

export default function SchedulePage() {
  const [users, setUsers] = useState<User[]>([]);
  const [schedules, setSchedules] = useState<ScheduleEntry[]>([]);
  const [base, setBase] = useState(new Date());
  const [modal, setModal] = useState<{
    open: boolean; entry?: ScheduleEntry;
    defaultUserIds?: string[]; defaultDate?: string; defaultSlot?: 'am'|'pm';
  }>({ open: false });
  const [form, setForm] = useState({
    title: '', color: COLOR_OPTIONS[0].value,
    allDay: false, userIds: [] as string[],
    date: '', slot: 'am' as 'am'|'pm'
  });
  const dragId = useRef<string | null>(null);
  // 編集時に「参加者全員へ反映するか」。複数参加者の予定では既定でON
  const [applyAll, setApplyAll] = useState(true);
  const [viewMode, setViewMode] = useState<'week' | 'month' | 'list'>('week');
  // 一覧で見る期間（週/月）。予定だけを日付順に並べて確認する
  const [listRange, setListRange] = useState<'week' | 'month'>('week');
  const weekDates = getWeekDates(base);
  const monthDates = getMonthDates(base);
  const listDates = listRange === 'week' ? weekDates : monthDates;
  const displayDates = viewMode === 'month' ? monthDates : viewMode === 'list' ? listDates : weekDates;
  const todayKey = dateKey(new Date());
  // 権限: 施工部門は閲覧のみ（管理者は常に編集可）
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  const canEdit = currentUser.role === 'admin' || currentUser.department !== '施工';
  // 部門別フィルタ
  const [deptFilter, setDeptFilter] = useState('');
  const departments = Array.from(new Set(users.map(u => u.department).filter(Boolean))) as string[];
  // 担当者フィルタ（スマホでは1人に絞ると横幅を圧迫せず見やすい）
  const [userFilter, setUserFilter] = useState('');
  const deptUsers = deptFilter ? users.filter(u => u.department === deptFilter) : users;
  const displayUsers = userFilter ? deptUsers.filter(u => u.id === userFilter) : deptUsers;

  useEffect(() => {
    // 全ユーザーを表示（/auth/team は非admin可）。旧listUsersはadmin限定で3名しか出ない不具合の原因。
    // 従業員マスタはユーザーマスタへ統合したため（2026-09-17）、フォールバックは無い
    authApi.listTeam()
      .then(r => { if (Array.isArray(r.data)) setUsers(r.data); })
      .catch(() => {});
  }, []);

  const loadSchedules = () => {
    scheduleApi.list(dateKey(displayDates[0]), dateKey(displayDates[displayDates.length - 1]))
      .then(r => setSchedules((r.data || []).map((s: any) => ({
        id: s.id, userId: s.user_id, date: s.date, slot: s.slot, title: s.title, color: s.color,
        groupId: s.group_id || null,
      }))))
      .catch(() => {});
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadSchedules(); }, [base, viewMode, listRange]);

  function goPrev() {
    const d = new Date(base);
    const byWeek = viewMode === 'week' || (viewMode === 'list' && listRange === 'week');
    if (byWeek) d.setDate(d.getDate() - 7); else d.setMonth(d.getMonth() - 1);
    setBase(d);
  }
  function goNext() {
    const d = new Date(base);
    const byWeek = viewMode === 'week' || (viewMode === 'list' && listRange === 'week');
    if (byWeek) d.setDate(d.getDate() + 7); else d.setMonth(d.getMonth() + 1);
    setBase(d);
  }

  function openNew(userIds: string[], date: string, slot: 'am'|'pm') {
    if (!canEdit) return;
    setForm({ title: '', color: COLOR_OPTIONS[0].value, allDay: false, userIds, date, slot });
    setModal({ open: true, defaultUserIds: userIds, defaultDate: date, defaultSlot: slot });
  }
  /** 一覧ビューの行。同じ予定（参加者・午前午後）を1行にまとめ、日付順に並べる */
  const listRows = (() => {
    const inRange = new Set(displayDates.map(dateKey));
    const visible = new Set(displayUsers.map(u => String(u.id)));
    const groups = new Map<string, ScheduleEntry[]>();
    schedules
      .filter(s => inRange.has(s.date) && visible.has(String(s.userId)))
      .forEach(s => {
        const key = `${s.date}|${s.groupId || `${s.slot}|${s.title}`}`;
        groups.set(key, [...(groups.get(key) || []), s]);
      });
    return Array.from(groups.entries()).map(([key, entries]) => {
      const slots = new Set(entries.map(e => e.slot));
      const d = new Date(entries[0].date + 'T00:00:00');
      const w = ['日', '月', '火', '水', '木', '金', '土'][d.getDay()];
      const names = Array.from(new Set(entries.map(e =>
        users.find(u => String(u.id) === String(e.userId))?.full_name || '—')));
      return {
        key, entries, names,
        title: entries[0].title, color: entries[0].color,
        dateLabel: `${d.getMonth() + 1}/${d.getDate()}(${w})`,
        slotLabel: slots.size > 1 ? '終日' : entries[0].slot === 'am' ? '午前' : '午後',
        isToday: entries[0].date === todayKey,
        isWeekend: d.getDay() === 0 || d.getDay() === 6,
        sortKey: `${entries[0].date}|${entries[0].slot}`,
      };
    }).sort((a, b) => a.sortKey.localeCompare(b.sortKey));
  })();

  /** 同じ予定の行（複数参加者・終日）。group_id が無い古い予定は日付・時間帯・内容で束ねる */
  function groupOf(entry: ScheduleEntry): ScheduleEntry[] {
    if (entry.groupId) return schedules.filter(s => s.groupId === entry.groupId);
    return schedules.filter(s => s.date === entry.date && s.slot === entry.slot && s.title === entry.title);
  }

  function openEdit(entry: ScheduleEntry) {
    const g = groupOf(entry);
    const slots = new Set(g.filter(s => s.userId === entry.userId).map(s => s.slot));
    setForm({
      title: entry.title, color: entry.color,
      allDay: slots.has('am') && slots.has('pm'),
      userIds: Array.from(new Set(g.map(s => s.userId))),
      date: entry.date, slot: entry.slot,
    });
    setApplyAll(g.length > 1);
    setModal({ open: true, entry });
  }
  async function saveEntry() {
    if (!form.title.trim()) { alert('内容を入力してください'); return; }
    if (!modal.entry && form.userIds.length === 0) { alert('対象者を選択してください'); return; }
    try {
      if (modal.entry) {
        const scope = applyAll ? 'group' : 'one';
        await scheduleApi.update(modal.entry.id, {
          title: form.title, color: form.color, date: form.date,
          slot: form.allDay ? 'all' : form.slot,
        }, scope);
      } else {
        // 同時に作る行（参加者×午前午後）へ同じIDを持たせ、あとでまとめて直せるようにする
        const groupId = (crypto as any).randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random());
        const slots: ('am' | 'pm')[] = form.allDay ? ['am', 'pm'] : [form.slot];
        const reqs: Promise<any>[] = [];
        for (const uid of form.userIds) {
          const u = users.find(x => x.id === uid);
          for (const sl of slots) {
            reqs.push(scheduleApi.create({
              user_id: uid, full_name: u?.full_name, date: form.date, slot: sl,
              title: form.title, color: form.color, group_id: groupId,
            }));
          }
        }
        await Promise.all(reqs);
      }
      setModal({ open: false });
      loadSchedules();
    } catch (e: any) {
      alert(e.response?.data?.detail || '登録に失敗しました');
    }
  }
  async function deleteEntry() {
    const g = modal.entry ? groupOf(modal.entry) : [];
    const scope = applyAll && g.length > 1 ? 'group' : 'one';
    if (scope === 'group' && !confirm(`この予定を参加者全員分（${g.length}件）削除します。よろしいですか？`)) return;
    try { await scheduleApi.delete(modal.entry!.id, scope); } catch { /* ignore */ }
    setModal({ open: false });
    loadSchedules();
  }
  async function onDrop(userId: string, date: string, slot: 'am' | 'pm') {
    if (!canEdit || !dragId.current) return;
    const id = dragId.current; dragId.current = null;
    const u = users.find(x => x.id === userId);
    try { await scheduleApi.update(id, { user_id: userId, full_name: u?.full_name, date, slot }); } catch { /* ignore */ }
    loadSchedules();
  }
  function toggleUserId(uid: string) {
    setForm(f => ({ ...f, userIds: f.userIds.includes(uid) ? f.userIds.filter(x => x !== uid) : [...f.userIds, uid] }));
  }

  const handlePrint = () => {
    const win = window.open('', '_blank', 'width=1400,height=900');
    if (!win) return;
    const esc = (s: any) => String(s ?? '').replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' } as any)[c]);
    const head = displayUsers.map(u => `<th>${esc(u.full_name)}${u.department ? `<br><span style="font-size:8px;color:#888">${esc(u.department)}</span>` : ''}</th>`).join('');
    const body = displayDates.map(date => {
      const dk = dateKey(date);
      return (['am', 'pm'] as const).map(slot => {
        const cells = displayUsers.map(u => {
          const es = schedules.filter(s => s.userId === u.id && s.date === dk && s.slot === slot);
          return `<td>${es.map(e => esc(e.title)).join('<br>')}</td>`;
        }).join('');
        const dcell = slot === 'am' ? `<td rowspan="2" class="dt">${esc(formatDate(date).replace('\n', ' '))}</td>` : '';
        return `<tr>${dcell}<td class="sl">${slot === 'am' ? '午前' : '午後'}</td>${cells}</tr>`;
      }).join('');
    }).join('');
    const rangeLabel = viewMode === 'week'
      ? `${dateKey(displayDates[0])}〜${dateKey(displayDates[displayDates.length - 1])}`
      : `${base.getFullYear()}年${base.getMonth() + 1}月`;
    win.document.write(`<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><title>スケジュール</title>
<style>@page{size:A3 landscape;margin:8mm}body{font-family:"Yu Gothic","Meiryo",sans-serif;font-size:10px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #999;padding:2px 4px;text-align:center}th{background:#f0f0f0}td.dt{background:#f7f7f7;font-weight:bold;white-space:nowrap}td.sl{background:#fafafa}</style></head><body>
<h3>スケジュール ${rangeLabel}${deptFilter ? `（${deptFilter}）` : ''}${userFilter ? `　${esc(displayUsers[0]?.full_name || '')}` : ''}</h3>
<table><thead><tr><th>日付</th><th>時間</th>${head}</tr></thead><tbody>${body}</tbody></table>
</body></html>`);
    win.document.close();
    win.onload = () => win.print();
  };

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h1 className="text-lg sm:text-xl font-bold text-gray-800">スケジュール管理
          {!canEdit && <span className="ml-2 text-xs font-normal text-amber-600 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5 align-middle">閲覧のみ</span>}
        </h1>
        <div className="flex gap-1.5 items-center bg-gray-100 rounded-lg p-0.5">
          <button onClick={() => setViewMode('week')}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${viewMode === 'week' ? 'bg-white shadow text-gray-800' : 'text-gray-500'}`}>週</button>
          <button onClick={() => setViewMode('month')}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${viewMode === 'month' ? 'bg-white shadow text-gray-800' : 'text-gray-500'}`}>月</button>
          <button onClick={() => setViewMode('list')}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${viewMode === 'list' ? 'bg-white shadow text-gray-800' : 'text-gray-500'}`}>一覧</button>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex gap-2 items-center flex-wrap">
          <button onClick={goPrev} className="px-3 py-1.5 border rounded text-sm hover:bg-gray-100">&lt; {(viewMode === 'week' || (viewMode === 'list' && listRange === 'week')) ? '前週' : '前月'}</button>
          <button onClick={() => setBase(new Date())} className="px-3 py-1.5 border rounded text-sm bg-blue-50 hover:bg-blue-100">今日</button>
          <button onClick={goNext} className="px-3 py-1.5 border rounded text-sm hover:bg-gray-100">{(viewMode === 'week' || (viewMode === 'list' && listRange === 'week')) ? '次週' : '次月'} &gt;</button>
          <span className="text-sm text-gray-600 font-medium ml-1">
            {(viewMode === 'week' || (viewMode === 'list' && listRange === 'week'))
              ? `${weekDates[0].getMonth()+1}/${weekDates[0].getDate()}〜${weekDates[6].getMonth()+1}/${weekDates[6].getDate()}`
              : `${base.getFullYear()}年${base.getMonth()+1}月`}
          </span>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <select value={deptFilter} onChange={e => { setDeptFilter(e.target.value); setUserFilter(''); }} className="border rounded px-2 py-1.5 text-sm">
            <option value="">全部門</option>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <SearchSelect value={userFilter} onChange={setUserFilter} emptyLabel="全員" className="w-40"
            options={deptUsers.map(u => ({ value: String(u.id), label: u.full_name, sub: u.department || undefined }))} />
          <button onClick={handlePrint} className="px-3 py-1.5 border rounded text-sm bg-gray-700 text-white hover:bg-gray-800">PDF出力</button>
        </div>
      </div>

      {/* 一覧: 予定だけを日付順に並べる（同じ予定は参加者をまとめて1行） */}
      {viewMode === 'list' && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-gray-500">期間</span>
            <div className="flex gap-1 bg-gray-100 rounded p-0.5">
              <button onClick={() => setListRange('week')}
                className={`px-2 py-0.5 rounded text-xs ${listRange === 'week' ? 'bg-white shadow text-gray-800' : 'text-gray-500'}`}>この週</button>
              <button onClick={() => setListRange('month')}
                className={`px-2 py-0.5 rounded text-xs ${listRange === 'month' ? 'bg-white shadow text-gray-800' : 'text-gray-500'}`}>この月</button>
            </div>
            <span className="text-xs text-gray-400">{listRows.length}件</span>
          </div>
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <div className="grid text-xs text-gray-500 bg-gray-50 border-b border-gray-200 px-3 py-2 font-medium"
              style={{ gridTemplateColumns: '110px 60px 1fr 220px' }}>
              <span>日付</span><span>時間</span><span>予定</span><span>参加者</span>
            </div>
            {listRows.length === 0 && (
              <div className="text-center py-10 text-gray-400 text-sm">この期間に予定はありません</div>
            )}
            {listRows.map(row => (
              <div key={row.key}
                onClick={() => openEdit(row.entries[0])}
                className={`grid items-center px-3 py-2 text-sm border-b border-gray-100 hover:bg-blue-50 cursor-pointer ${row.isToday ? 'bg-blue-50/60' : ''}`}
                style={{ gridTemplateColumns: '110px 60px 1fr 220px' }}>
                <span className={`text-xs font-medium ${row.isWeekend ? 'text-red-500' : 'text-gray-600'}`}>
                  {row.dateLabel}
                </span>
                <span className="text-xs text-gray-500">{row.slotLabel}</span>
                <span className="truncate">
                  <span className={`inline-block px-1.5 py-0.5 rounded border text-xs mr-2 align-middle ${row.color}`}>&nbsp;</span>
                  <span className="text-gray-800 align-middle">{row.title || '（内容なし）'}</span>
                </span>
                <span className="text-xs text-gray-500 truncate">{row.names.join('、')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* テーブル要素は使わずCSS Gridで組む。position:sticky を <th>/<td> に使うとSafariの
          table-layout計算が不安定になり、日付/時間列の間にズレ（隙間）が生じるため。 */}
      <div className={`overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0 ${viewMode === 'list' ? 'hidden' : ''}`}>
        <div className="inline-grid border-t border-l border-gray-300" style={{ gridTemplateColumns: `${DATE_W}px ${TIME_W}px` + (displayUsers.length ? ` repeat(${displayUsers.length}, ${USER_W}px)` : '') }}>
          <div className="sticky left-0 z-20 border-r border-b border-gray-300 bg-gray-100 px-1 py-2 text-center text-sm" style={{ gridColumn: 1, gridRow: 1 }}>日付</div>
          <div className="sticky z-20 border-r border-b border-gray-300 bg-gray-100 px-1 py-2 text-center text-sm" style={{ gridColumn: 2, gridRow: 1, left: DATE_W }}>時間</div>
          {displayUsers.map((u, ui) => (
            <div key={u.id} className="border-r border-b border-gray-300 bg-gray-50 px-1 py-1 text-center text-xs leading-tight flex flex-col items-center justify-center"
              style={{ gridColumn: 3 + ui, gridRow: 1 }}>
              {u.full_name.replace(' ', '\n').split('\n').map((line, i) => <div key={i}>{line}</div>)}
            </div>
          ))}

          {displayDates.map((date, di) => {
            const dk = dateKey(date);
            const isToday = dk === todayKey;
            const isWeekend = date.getDay() === 0 || date.getDay() === 6;
            const rowStart = 2 + di * 2;
            const rowBg = isToday ? 'bg-blue-50' : isWeekend ? 'bg-red-50' : 'bg-white';
            return (
              <Fragment key={dk}>
                <div className={`sticky left-0 z-10 border-r border-b border-gray-300 text-center text-xs font-medium px-1 whitespace-pre-line leading-tight flex items-center justify-center ${isToday ? 'bg-blue-100 text-blue-700' : isWeekend ? 'bg-red-100 text-red-600' : 'bg-gray-50 text-gray-700'}`}
                  style={{ gridColumn: 1, gridRow: `${rowStart} / span 2` }}>
                  {formatDate(date)}
                </div>
                {(['am', 'pm'] as const).map((slot, si) => {
                  const rowNum = rowStart + si;
                  return (
                    <Fragment key={`${dk}-${slot}`}>
                      <div className={`sticky z-10 border-r border-b border-gray-300 text-center text-xs px-1 py-1 font-medium flex items-center justify-center ${isToday ? 'bg-blue-50' : isWeekend ? 'bg-red-50' : 'bg-gray-50'}`}
                        style={{ gridColumn: 2, gridRow: rowNum, left: DATE_W }}>
                        {slot === 'am' ? '午前' : '午後'}
                      </div>
                      {displayUsers.map((u, ui) => {
                        const entries = schedules.filter(s => s.userId === u.id && s.date === dk && s.slot === slot);
                        return (
                          <div key={u.id} className={`border-r border-b border-gray-300 px-1 py-1 align-top cursor-pointer ${rowBg}`}
                            style={{ gridColumn: 3 + ui, gridRow: rowNum, height: '48px' }}
                            onDragOver={e => e.preventDefault()}
                            onDrop={() => onDrop(u.id, dk, slot)}
                            onClick={() => entries.length === 0 && openNew([u.id], dk, slot)}>
                            <div className="flex flex-col gap-0.5 min-h-[40px]">
                              {entries.map(entry => (
                                <div key={entry.id} draggable
                                  onDragStart={() => { dragId.current = entry.id; }}
                                  onClick={e => { e.stopPropagation(); openEdit(entry); }}
                                  className={`text-xs px-1 py-0.5 rounded border cursor-grab truncate ${entry.color}`}
                                  title={entry.title}>
                                  {entry.title}
                                </div>
                              ))}
                              {entries.length === 0 && <div className="text-xs text-gray-300 text-center pt-2">+</div>}
                            </div>
                          </div>
                        );
                      })}
                    </Fragment>
                  );
                })}
              </Fragment>
            );
          })}
        </div>
      </div>

      {modal.open && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-sm max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold mb-4">{modal.entry ? '予定を編集' : '予定を追加'}</h2>

            {/* 編集時: この予定の参加者と、全員へ反映するかの指定 */}
            {modal.entry && (() => {
              const g = groupOf(modal.entry!);
              const names = Array.from(new Set(g.map(s =>
                users.find(u => u.id === s.userId)?.full_name || '—')));
              return (
                <div className="mb-3 bg-gray-50 border border-gray-200 rounded p-2">
                  <div className="text-xs text-gray-500">参加者（{names.length}名）</div>
                  <div className="text-sm text-gray-800">{names.join('、')}</div>
                  {g.length > 1 && (
                    <label className="flex items-center gap-1.5 mt-2 text-sm cursor-pointer">
                      <input type="checkbox" checked={applyAll} onChange={e => setApplyAll(e.target.checked)} />
                      参加者全員分に反映する（{g.length}件）
                    </label>
                  )}
                </div>
              );
            })()}

            {/* 日付・時間帯（編集時も変更できる） */}
            {modal.entry && (
              <>
                <div className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">日付</label>
                  <input type="date" value={form.date}
                    onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
                    className="border rounded w-full px-3 py-2 text-sm" />
                </div>
                <div className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">時間帯</label>
                  <div className="flex gap-3">
                    <label className="flex items-center gap-1 text-sm cursor-pointer">
                      <input type="radio" name="eslot" checked={!form.allDay && form.slot === 'am'}
                        onChange={() => setForm(f => ({ ...f, allDay: false, slot: 'am' }))} />午前
                    </label>
                    <label className="flex items-center gap-1 text-sm cursor-pointer">
                      <input type="radio" name="eslot" checked={!form.allDay && form.slot === 'pm'}
                        onChange={() => setForm(f => ({ ...f, allDay: false, slot: 'pm' }))} />午後
                    </label>
                    <label className="flex items-center gap-1 text-sm cursor-pointer">
                      <input type="radio" name="eslot" checked={form.allDay}
                        onChange={() => setForm(f => ({ ...f, allDay: true }))} />終日
                    </label>
                  </div>
                </div>
              </>
            )}

            {!modal.entry && (
              <>
                <div className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">対象者（複数選択可）</label>
                  <div className="flex flex-wrap gap-2 border rounded p-2 max-h-32 overflow-y-auto">
                    {users.map(u => (
                      <label key={u.id} className="flex items-center gap-1 text-sm cursor-pointer">
                        <input type="checkbox" checked={form.userIds.includes(u.id)} onChange={() => toggleUserId(u.id)} />
                        {u.full_name}
                      </label>
                    ))}
                  </div>
                </div>
                <div className="mb-3 flex items-center gap-2">
                  <input type="checkbox" id="allDay" checked={form.allDay} onChange={e => setForm(f => ({ ...f, allDay: e.target.checked }))} />
                  <label htmlFor="allDay" className="text-sm font-medium text-gray-700 cursor-pointer">終日（午前・午後両方に登録）</label>
                </div>
                {!form.allDay && (
                  <div className="mb-3">
                    <label className="block text-sm font-medium text-gray-700 mb-1">時間帯</label>
                    <div className="flex gap-3">
                      <label className="flex items-center gap-1 text-sm cursor-pointer">
                        <input type="radio" name="slot" checked={form.slot === 'am'} onChange={() => setForm(f => ({ ...f, slot: 'am' }))} />午前
                      </label>
                      <label className="flex items-center gap-1 text-sm cursor-pointer">
                        <input type="radio" name="slot" checked={form.slot === 'pm'} onChange={() => setForm(f => ({ ...f, slot: 'pm' }))} />午後
                      </label>
                    </div>
                  </div>
                )}
              </>
            )}

            <div className="mb-3">
              <label className="block text-sm font-medium text-gray-700 mb-1">内容</label>
              <input className="border rounded w-full px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                autoFocus placeholder="予定を入力..." />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">色</label>
              <div className="flex gap-2 flex-wrap">
                {COLOR_OPTIONS.map(c => (
                  <button key={c.value} onClick={() => setForm(f => ({ ...f, color: c.value }))}
                    className={`w-8 h-8 rounded border-2 ${c.value} ${form.color === c.value ? 'ring-2 ring-offset-1 ring-gray-600' : ''}`}
                    title={c.label} />
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              {canEdit && modal.entry && (
                <button onClick={deleteEntry} className="px-3 py-2 text-sm bg-red-50 text-red-600 border border-red-200 rounded hover:bg-red-100">削除</button>
              )}
              <button onClick={() => setModal({ open: false })} className="px-3 py-2 text-sm border rounded hover:bg-gray-100">{canEdit ? 'キャンセル' : '閉じる'}</button>
              {canEdit && (
                <button onClick={saveEntry} className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">保存</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
