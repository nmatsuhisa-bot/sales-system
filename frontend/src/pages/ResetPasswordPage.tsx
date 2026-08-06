import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api';

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [pw1, setPw1] = useState('');
  const [pw2, setPw2] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (pw1.length < 6) { setError('パスワードは6文字以上にしてください'); return; }
    if (pw1 !== pw2) { setError('パスワードが一致しません'); return; }
    setSaving(true);
    try {
      await authApi.resetPassword(token, pw1);
      setDone(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '再設定に失敗しました。お手数ですが再度お手続きください');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="text-3xl font-bold text-slate-800 mb-1">井上電設株式会社</div>
          <div className="text-gray-500 text-sm">パスワード再設定</div>
        </div>

        {!token ? (
          <div className="text-center space-y-4">
            <p className="text-red-500 text-sm">リンクが正しくありません。メール内のリンクからアクセスしてください。</p>
            <button onClick={() => navigate('/login')} className="text-sm text-blue-600 hover:underline">
              ログイン画面へ
            </button>
          </div>
        ) : done ? (
          <div className="text-center space-y-4">
            <p className="text-green-600">パスワードを再設定しました。</p>
            <button
              onClick={() => navigate('/login')}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              ログイン画面へ
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">新しいパスワード</label>
              <input
                type="password"
                value={pw1}
                onChange={e => setPw1(e.target.value)}
                required
                placeholder="6文字以上"
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">新しいパスワード（確認）</label>
              <input
                type="password"
                value={pw2}
                onChange={e => setPw2(e.target.value)}
                required
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            {error && <div className="text-red-500 text-sm text-center">{error}</div>}
            <button
              type="submit"
              disabled={saving}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-60 transition-colors"
            >
              {saving ? '設定中...' : 'パスワードを設定'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
