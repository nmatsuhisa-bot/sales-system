import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [forgotMsg, setForgotMsg] = useState('');
  const [forgotSending, setForgotSending] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const r = await authApi.login(email, password);
      localStorage.setItem('access_token', r.data.access_token);
      localStorage.setItem('user', JSON.stringify(r.data.user));
      navigate('/');
    } catch {
      setError('メールアドレスまたはパスワードが間違っています');
    } finally {
      setLoading(false);
    }
  };

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault();
    setForgotSending(true);
    setForgotMsg('');
    setError('');
    try {
      await authApi.forgotPassword(email);
      setForgotMsg('登録済みのメールアドレスであれば、再設定用のリンクを送信しました。メールをご確認ください。');
    } catch (err: any) {
      setError(err?.response?.data?.detail || '送信に失敗しました。時間をおいて再度お試しください');
    } finally {
      setForgotSending(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="text-3xl font-bold text-slate-800 mb-1">井上電設株式会社</div>
          <div className="text-gray-500 text-sm">販売管理システム</div>
        </div>
        {!forgot ? (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">メールアドレス</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="admin@inoue-densen.co.jp"
                required
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">パスワード</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            {error && <div className="text-red-500 text-sm text-center">{error}</div>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-60 transition-colors"
            >
              {loading ? 'ログイン中...' : 'ログイン'}
            </button>
            <div className="text-center">
              <button
                type="button"
                onClick={() => { setForgot(true); setError(''); setForgotMsg(''); }}
                className="text-sm text-blue-600 hover:underline"
              >
                パスワードをお忘れの方
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleForgot} className="space-y-4">
            <p className="text-sm text-gray-600">
              ご登録のメールアドレスを入力してください。再設定用のリンクをお送りします。
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">メールアドレス</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="admin@inoue-densen.co.jp"
                required
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            {error && <div className="text-red-500 text-sm text-center">{error}</div>}
            {forgotMsg && <div className="text-green-600 text-sm text-center">{forgotMsg}</div>}
            <button
              type="submit"
              disabled={forgotSending}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-60 transition-colors"
            >
              {forgotSending ? '送信中...' : '再設定リンクを送信'}
            </button>
            <div className="text-center">
              <button
                type="button"
                onClick={() => { setForgot(false); setError(''); setForgotMsg(''); }}
                className="text-sm text-gray-500 hover:underline"
              >
                ← ログインに戻る
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
