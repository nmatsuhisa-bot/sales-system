import { useState, useEffect, useRef } from 'react';
import { authApi, mastersApi, scheduleApi } from '../api';

interface User { id: string; full_name: string; email: string; }
interface ScheduleEntry {
  id: string; userId: string; date: string; slot: 'am' | 'pm'; title: string; color: string;
}

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
  const weekDates = getWeekDates(base);
  const todayKey = dateKey(new Date());

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
    scheduleApi.list(dateKey(weekDates[0]), dateKey(weekDates[6]))
      .then(r => setSchedules((r.data || []).map((s: any) => ({
        id: s.id, userId: s.user_id, date: s.date, slot: s.slot, title: s.title, color: s.color,
      }))))
      .catch(() => {});
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadSchedules(); }, [base]);

  function openNew(userIds: string[], date: string, slot: 'am'|'pm') {
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
    if (!dragId.current) return;
    const id = dragId.current; dragId.current = null;
    const u = users.find(x => x.id === userId);
    try { await scheduleApi.update(id, { user_id: userId, full_name: u?.full_name, date, slot }); } catch { /* ignore */ }
    loadSchedules();
  }
  function toggleUserId(uid: string) {
    setForm(f => ({ ...f, userIds: f.userIds.includes(uid) ? f.userIds.filter(x => x !== uid) : [...f.userIds, uid] }));
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-gray-800">スケジュール管理</h1>
        <div className="flex gap-2 items-center">
          <button onClick={() => { const d = new Date(base); d.setDate(d.getDate()-7); setBase(d); }} className="px-3 py-1 border rounded text-sm hover:bg-gray-100">&lt; 前週</button>
          <button onClick={() => setBase(new Date())} className="px-3 py-1 border rounded text-sm bg-blue-50 hover:bg-blue-100">今週</button>
          <button onClick={() => { const d = new Date(base); d.setDate(d.getDate()+7); setBase(d); }} className="px-3 py-1 border rounded text-sm hover:bg-gray-100">次週 &gt;</button>
          <span className="text-sm text-gray-500 ml-2">{weekDates[0].getFullYear()}年{weekDates[0].getMonth()+1}月</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="border-collapse text-sm w-full">
          <thead>
            <tr>
              <th className="border border-gray-300 bg-gray-100 px-1 py-2 text-center" style={{width:'60px'}}>日付</th>
              <th className="border border-gray-300 bg-gray-100 px-1 py-2 text-center" style={{width:'36px'}}>時間</th>
              {users.map(u => (
                <th key={u.id} className="border border-gray-300 bg-gray-50 px-1 py-1 text-center text-xs leading-tight" style={{width:'90px', minWidth:'90px'}}>
                  {u.full_name.replace(' ', '\n').split('\n').map((line, i) => <div key={i}>{line}</div>)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weekDates.map(date => {
              const dk = dateKey(date);
              const isToday = dk === todayKey;
              const isWeekend = date.getDay() === 0 || date.getDay() === 6;
              return (['am','pm'] as const).map(slot => (
                <tr key={`${dk}-${slot}`} className={isWeekend ? 'bg-red-50' : isToday ? 'bg-blue-50' : ''}>
                  {slot === 'am' && (
                    <td rowSpan={2} className={`border border-gray-300 text-center text-xs font-medium px-1 whitespace-pre-line leading-tight ${isToday ? 'bg-blue-100 text-blue-700' : isWeekend ? 'bg-red-100 text-red-600' : 'bg-gray-50 text-gray-700'}`}>
                      {formatDate(date)}
                    </td>
                  )}
                  <td className={`border border-gray-300 text-center text-xs px-1 py-1 font-medium ${isToday ? 'bg-blue-50' : isWeekend ? 'bg-red-50' : 'bg-gray-50'}`}>
                    {slot === 'am' ? '午前' : '午後'}
                  </td>
                  {users.map(u => {
                    const entries = schedules.filter(s => s.userId === u.id && s.date === dk && s.slot === slot);
                    return (
                      <td key={u.id} className="border border-gray-300 px-1 py-1 align-top cursor-pointer" style={{height:'48px'}}
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
                      </td>
                    );
                  })}
                </tr>
              ));
            })}
          </tbody>
        </table>
      </div>

      {modal.open && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-96">
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
              {modal.entry && (
                <button onClick={deleteEntry} className="px-3 py-2 text-sm bg-red-50 text-red-600 border border-red-200 rounded hover:bg-red-100">削除</button>
              )}
              <button onClick={() => setModal({ open: false })} className="px-3 py-2 text-sm border rounded hover:bg-gray-100">キャンセル</button>
              <button onClick={saveEntry} className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
