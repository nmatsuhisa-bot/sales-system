import { useEffect, useState } from 'react';
import { authApi } from '../api';
import { Plus, Edit2, Trash2, Key } from 'lucide-react';

export default function UsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [modal, setModal] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  // 機能権限の定義はサーバから取得（app/roles.py に追加すれば画面にも自動で出る）
  const [functionRoles, setFunctionRoles] = useState<any[]>([]);

  const load = () => authApi.listUsers().then(r => setUsers(r.data || []));
  useEffect(() => {
    load();
    authApi.listFunctionRoles().then(r => setFunctionRoles(r.data.function_roles || [])).catch(() => {});
  }, []);

  const openNew = () => { setForm({ role: 'user', password: 'user1234', function_roles: [] }); setModal({ isNew: true }); };
  const openEdit = (u: any) => { setForm({ ...u, password: '', function_roles: u.function_roles || [] }); setModal({ isNew: false }); };

  // 機能権限は複数選択（1ユーザーが複数の役割を担える）
  const toggleFunctionRole = (key: string) => {
    setForm((f: any) => {
      const cur: string[] = f.function_roles || [];
      return { ...f, function_roles: cur.includes(key) ? cur.filter(k => k !== key) : [...cur, key] };
    });
  };

  const handleSave = async () => {
    try {
      const roles = form.function_roles || [];
      if (modal.isNew) {
        await authApi.createUser({ email: form.email, full_name: form.full_name, password: form.password, role: form.role || 'user', function_roles: roles, department: form.department || null });
      } else {
        await authApi.updateUser(form.id, { email: form.email, full_name: form.full_name, role: form.role, function_roles: roles, department: form.department || null, password: form.password || undefined });
      }
      setModal(null);
      load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラーが発生しました');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('このユーザーを無効化しますか？')) return;
    await authApi.deleteUser(id);
    load();
  };

  const handleResetPassword = async (u: any) => {
    const newPass = prompt(`${u.full_name}の新しいパスワードを入力してください：`, 'user1234');
    if (!newPass) return;
    await authApi.updateUser(u.id, { password: newPass });
    alert('パスワードを変更しました');
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">ユーザー管理</h1>
        <button onClick={openNew}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} /> 新規ユーザー追加
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">氏名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">メールアドレス</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">部門</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">権限</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">機能権限</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {users.map(u => (
              <tr key={u.id} className="hover:bg-blue-50">
                <td className="px-4 py-3 font-medium text-gray-800">{u.full_name}</td>
                <td className="px-4 py-3 text-gray-600">{u.email}</td>
                <td className="px-4 py-3 text-center">
                  {u.department
                    ? <span className="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700">{u.department}</span>
                    : <span className="text-xs text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${u.role === 'admin' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>
                    {u.role === 'admin' ? '管理者' : 'ユーザー'}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  {(u.function_roles || []).length > 0 ? (
                    <span className="flex flex-wrap gap-1 justify-center">
                      {(u.function_roles || []).map((k: string) => (
                        <span key={k} className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-700">
                          {functionRoles.find(r => r.key === k)?.label || k}
                        </span>
                      ))}
                    </span>
                  ) : <span className="text-xs text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-center flex items-center justify-center gap-2">
                  <button onClick={() => handleResetPassword(u)} className="text-yellow-500 hover:text-yellow-700" title="パスワード変更"><Key size={14} /></button>
                  <button onClick={() => openEdit(u)} className="text-blue-400 hover:text-blue-600"><Edit2 size={14} /></button>
                  {u.role !== 'admin' && <button onClick={() => handleDelete(u.id)} className="text-red-300 hover:text-red-500"><Trash2 size={14} /></button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {users.length === 0 && <div className="text-center py-10 text-gray-400">ユーザーがいません</div>}
      </div>

      {modal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-bold text-gray-800 mb-4">{modal.isNew ? '新規ユーザー追加' : 'ユーザー編集'}</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">氏名 *</label>
                <input value={form.full_name || ''} onChange={e => setForm((f: any) => ({ ...f, full_name: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" placeholder="例: 井上 太郎" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">メールアドレス *</label>
                <input type="email" value={form.email || ''} onChange={e => setForm((f: any) => ({ ...f, email: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" placeholder="例: taro@inoue-densetsu.co.jp" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">パスワード {modal.isNew ? '*' : '（変更する場合のみ入力）'}</label>
                <input type="password" value={form.password || ''} onChange={e => setForm((f: any) => ({ ...f, password: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" placeholder={modal.isNew ? 'user1234' : '変更しない場合は空白'} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">権限</label>
                <select value={form.role || 'user'} onChange={e => setForm((f: any) => ({ ...f, role: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="user">ユーザー</option>
                  <option value="admin">管理者</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">所属部門<span className="text-[10px] text-gray-400 ml-1">スケジュール絞込・権限用（施工＝閲覧のみ）</span></label>
                <select value={form.department || ''} onChange={e => setForm((f: any) => ({ ...f, department: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">（未設定）</option>
                  <option value="営業">営業</option>
                  <option value="施工">施工</option>
                  <option value="製造">製造</option>
                  <option value="管理部">管理部</option>
                </select>
              </div>
              {/* 機能権限（複数選択可）。1ユーザーが複数の役割を担える */}
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  機能権限
                  <span className="text-[10px] text-gray-400 ml-1">複数選択可。担当する業務機能を指定します</span>
                </label>
                <div className="border border-gray-200 rounded-lg divide-y divide-gray-100">
                  {functionRoles.map(r => {
                    const checked = (form.function_roles || []).includes(r.key);
                    return (
                      <label key={r.key}
                        className={`flex items-start gap-2 px-3 py-2 cursor-pointer hover:bg-gray-50 ${checked ? 'bg-blue-50' : ''}`}>
                        <input type="checkbox" checked={checked}
                          onChange={() => toggleFunctionRole(r.key)} className="mt-0.5" />
                        <span>
                          <span className="text-sm font-medium text-gray-800">{r.label}</span>
                          {r.description && <span className="block text-[11px] text-gray-500">{r.description}</span>}
                        </span>
                      </label>
                    );
                  })}
                  {functionRoles.length === 0 && (
                    <p className="px-3 py-2 text-xs text-gray-400">選択できる機能権限がありません</p>
                  )}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setModal(null)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">キャンセル</button>
              <button onClick={handleSave} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
