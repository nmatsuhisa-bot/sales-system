import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'https://sales-backend-7nzg.onrender.com';

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

function dateKey(d: Date): string { return d.toISOString().split('T')[0]; }
function formatDate(d: Date): string {
  const w = ['日','月','火','水','木','金','土'];
  return `${d.getMonth()+1}/${d.getDate()}(${w[d.getDay()]})`;
}

function loadData(): ScheduleEntry[] {
  try { return JSON.parse(localStorage.getItem('inoue_schedules') || '[]'); } catch { return []; }
}
function saveData(entries: ScheduleEntry[]) {
  localStorage.setItem('inoue_schedules', JSON.stringify(entries));
}

export default function SchedulePage() {
  const [users, setUsers] = useState<User[]>([]);
  const [schedules, setSchedules] = useState<ScheduleEntry[]>(loadData());
  const [base, setBase] = useState(new Date());
  const [modal, setModal] = useState<{ open: boolean; entry?: ScheduleEntry; userId?: string; date?: string; slot?: 'am'|'pm' }>({ open: false });
  const [form, setForm] = useState({ title: '', color: COLOR_OPTIONS[0].value });
  const dragId = useRef<string | null>(null);
  const weekDates = getWeekDates(base);
  const todayKey = dateKey(new Date());

  useEffect(() => {
    const token = localStorage.getItem('access_token') || localStorage.getItem('token');
    axios.get(`${API_BASE}/api/auth/users`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => setUsers(r.data)).catch(() => {});
  }, []);

  function openNew(userId: string, date: string, slot: 'am'|'pm') {
    setForm({ title: '', color: COLOR_OPTIONS[0].value });
    setModal({ open: true, userId, date, slot });
  }
  function openEdit(entry: ScheduleEntry) {
    setForm({ title: entry.title, color: entry.color });
    setModal({ open: true, entry });
  }
  function saveEntry() {
    if (!form.title.trim()) return;
    let updated: ScheduleEntry[];
    if (modal.entry) {
      updated = schedules.map(s => s.id === modal.entry!.id ? { ...s, ...form } : s);
    } else {
      updated = [...schedules, { id: crypto.randomUUID(), userId: modal.userId!, date: modal.date!, slot: modal.slot!, ...form }];
    }
    setSchedules(updated); saveData(updated); setModal({ open: false });
  }
  function deleteEntry() {
    const updated = schedules.filter(s => s.id !== modal.entry!.id);
    setSchedules(updated); saveData(updated); setModal({ open: false });
  }
  function onDrop(userId: string, date: string, slot: 'am'|'pm') {
    if (!dragId.current) return;
    const updated = schedules.map(s => s.id === dragId.current ? { ...s, userId, date, slot } : s);
    setSchedules(updated); saveData(updated); dragId.current = null;
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
        <table className="border-collapse text-sm" style={{ minWidth: `${200 + users.length * 150}px` }}>
          <thead>
            <tr>
              <th className="border border-gray-300 bg-gray-100 px-2 py-2 w-24 text-center">日付</th>
              <th className="border border-gray-300 bg-gray-100 px-2 py-2 w-12 text-center">時間</th>
              {users.map(u => (
                <th key={u.id} className="border border-gray-300 bg-gray-50 px-2 py-2 text-center" style={{ minWidth: '150px' }}>
                  {u.full_name}
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
                    <td rowSpan={2} className={`border border-gray-300 text-center text-xs font-medium px-1 ${isToday ? 'bg-blue-100 text-blue-700' : isWeekend ? 'bg-red-100 text-red-600' : 'bg-gray-50 text-gray-700'}`}>
                      {formatDate(date)}
                    </td>
                  )}
                  <td className={`border border-gray-300 text-center text-xs px-1 py-1 font-medium ${isToday ? 'bg-blue-50' : isWeekend ? 'bg-red-50' : 'bg-gray-50'}`}>
                    {slot === 'am' ? '午前' : '午後'}
                  </td>
                  {users.map(u => {
                    const entries = schedules.filter(s => s.userId === u.id && s.date === dk && s.slot === slot);
                    return (
                      <td key={u.id} className="border border-gray-300 px-1 py-1 align-top" style={{ height: '52px' }}
                        onDragOver={e => e.preventDefault()}
                        onDrop={() => onDrop(u.id, dk, slot)}
                        onClick={() => entries.length === 0 && openNew(u.id, dk, slot)}>
                        <div className="flex flex-col gap-1 min-h-[44px]">
                          {entries.map(entry => (
                            <div key={entry.id} draggable
                              onDragStart={() => { dragId.current = entry.id; }}
                              onClick={e => { e.stopPropagation(); openEdit(entry); }}
                              className={`text-xs px-1 py-0.5 rounded border cursor-grab truncate ${entry.color}`}
                              title={entry.title}>
                              {entry.title}
                            </div>
                          ))}
                          {entries.length === 0 && (
                            <div className="text-xs text-gray-300 text-center pt-2 cursor-pointer hover:text-gray-400">+</div>
                          )}
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
          <div className="bg-white rounded-lg shadow-xl p-6 w-80">
            <h2 className="text-lg font-bold mb-4">{modal.entry ? '予定を編集' : '予定を追加'}</h2>
            <div className="mb-3">
              <label className="block text-sm font-medium text-gray-700 mb-1">内容</label>
              <input className="border rounded w-full px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                value={form.title} onChange={e => setForm({ ...form, title: e.target.value })}
                onKeyDown={e => e.key === 'Enter' && saveEntry()} autoFocus placeholder="予定を入力..." />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">色</label>
              <div className="flex gap-2 flex-wrap">
                {COLOR_OPTIONS.map(c => (
                  <button key={c.value} onClick={() => setForm({ ...form, color: c.value })}
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
