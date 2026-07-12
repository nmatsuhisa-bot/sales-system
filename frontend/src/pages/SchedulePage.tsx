import { useState, useEffect, useRef, Fragment } from 'react';
import { authApi, mastersApi, scheduleApi } from '../api';

interface User { id: string; full_name: string; email: string; department?: string; role?: string; }
interface ScheduleEntry {
  id: string; userId: string; date: string; slot: 'am' | 'pm'; title: string; color: string;
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
  const [viewMode, setViewMode] = useState<'week' | 'month'>('week');
  const weekDates = getWeekDates(base);
  const monthDates = getMonthDates(base);
  const displayDates = viewMode === 'week' ? weekDates : monthDates;
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
    // 全ユーザーを表示（/auth/team は非admin可）。旧listUsersはadmin限定で3名しか出ない不具合の原因
    authApi.listTeam()
      .then(r => {
        if (Array.isArray(r.data) && r.data.length) setUsers(r.data);
        else throw new Error('empty');
      })
      .catch(() => {
        mastersApi.listEmployees()
          .then(r => setUsers((r.data.items || r.data).map((e: any) => ({
            id: e.id, full_name: e.employee_name, email: ''
          })))).catch(() => {});
      });
  }, []);

  const loadSchedules = () => {
    scheduleApi.list(dateKey(displayDates[0]), dateKey(displayDates[displayDates.length - 1]))
      .then(r => setSchedules((r.data || []).map((s: any) => ({
        id: s.id, userId: s.user_id, date: s.date, slot: s.slot, title: s.title, color: s.color,
      }))))
      .catch(() => {});
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadSchedules(); }, [base, viewMode]);

  function goPrev() {
    const d = new Date(base);
    if (viewMode === 'week') d.setDate(d.getDate() - 7); else d.setMonth(d.getMonth() - 1);
    setBase(d);
  }
  function goNext() {
    const d = new Date(base);
    if (viewMode === 'week') d.setDate(d.getDate() + 7); else d.setMonth(d.getMonth() + 1);
    setBase(d);
  }

  function openNew(userIds: string[], date: string, slot: 'am'|'pm') {
    if (!canEdit) return;
    setForm({ title: '', color: COLOR_OPTIONS[0].value, allDay: false, userIds, date, slot });
    setModal({ open: true, defaultUserIds: userIds, defaultDate: date, defaultSlot: slot });
  }
  function openEdit(entry: ScheduleEntry) {
    setForm({ title: entry.title, color: entry.color, allDay: false, userIds: [entry.userId], date: entry.date, slot: entry.slot });
    setModal({ open: true, entry });
  }
  async function saveEntry() {
    if (!form.title.trim()) { alert('内容を入力してください'); return; }
    if (!modal.entry && form.userIds.length === 0) { alert('対象者を選択してください'); return; }
    try {
      if (modal.entry) {
        await scheduleApi.update(modal.entry.id, { title: form.title, color: form.color });
      } else {
        const slots: ('am' | 'pm')[] = form.allDay ? ['am', 'pm'] : [form.slot];
        const reqs: Promise<any>[] = [];
        for (const uid of form.userIds) {
          const u = users.find(x => x.id === uid);
          for (const sl of slots) {
            reqs.push(scheduleApi.create({
              user_id: uid, full_name: u?.full_name, date: form.date, slot: sl,
              title: form.title, color: form.color,
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
    try { await scheduleApi.delete(modal.entry!.id); } catch { /* ignore */ }
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
        </div>
      </div>

      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex gap-2 items-center flex-wrap">
          <button onClick={goPrev} className="px-3 py-1.5 border rounded text-sm hover:bg-gray-100">&lt; {viewMode === 'week' ? '前週' : '前月'}</button>
          <button onClick={() => setBase(new Date())} className="px-3 py-1.5 border rounded text-sm bg-blue-50 hover:bg-blue-100">今日</button>
          <button onClick={goNext} className="px-3 py-1.5 border rounded text-sm hover:bg-gray-100">{viewMode === 'week' ? '次週' : '次月'} &gt;</button>
          <span className="text-sm text-gray-600 font-medium ml-1">
            {viewMode === 'week'
              ? `${weekDates[0].getMonth()+1}/${weekDates[0].getDate()}〜${weekDates[6].getMonth()+1}/${weekDates[6].getDate()}`
              : `${base.getFullYear()}年${base.getMonth()+1}月`}
          </span>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <select value={deptFilter} onChange={e => { setDeptFilter(e.target.value); setUserFilter(''); }} className="border rounded px-2 py-1.5 text-sm">
            <option value="">全部門</option>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <select value={userFilter} onChange={e => setUserFilter(e.target.value)} className="border rounded px-2 py-1.5 text-sm max-w-[140px]">
            <option value="">全員</option>
            {deptUsers.map(u => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </select>
          <button onClick={handlePrint} className="px-3 py-1.5 border rounded text-sm bg-gray-700 text-white hover:bg-gray-800">PDF出力</button>
        </div>
      </div>

      {/* テーブル要素は使わずCSS Gridで組む。position:sticky を <th>/<td> に使うとSafariの
          table-layout計算が不安定になり、日付/時間列の間にズレ（隙間）が生じるため。 */}
      <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
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
                onKeyDown={e => e.key === 'Enter' && saveEntry()} autoFocus placeholder="予定を入力..." />
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
