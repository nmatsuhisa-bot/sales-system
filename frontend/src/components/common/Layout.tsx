import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, FileText, ShoppingCart,
  BarChart3, LogOut, Menu, X, Boxes, Briefcase, Database, UserCog, Calendar,
  ShoppingBag, Factory, ClipboardList, GitBranch, HelpCircle
} from 'lucide-react';
import { useState } from 'react';

type NavEntry = { to: string; icon: any; label: string; end?: boolean } | { divider: true };

const navItems: NavEntry[] = [
  // 主要業務フロー（案件→見積→受注→仕入→製造→工程）
  { to: '/', icon: LayoutDashboard, label: 'ダッシュボード', end: true },
  { to: '/sales-plan', icon: BarChart3, label: '売上計画表' },
  { to: '/projects', icon: Briefcase, label: '案件管理' },
  { to: '/estimates', icon: FileText, label: '見積管理' },
  { to: '/orders', icon: ShoppingCart, label: '受注管理' },
  { to: '/procurement', icon: ShoppingBag, label: '仕入（発注）管理' },
  { to: '/manufacturing', icon: Factory, label: '製造計画' },
  { to: '/process', icon: ClipboardList, label: '工程管理' },
  { divider: true },
  // マスタ・その他
  { to: '/inventory', icon: Boxes, label: '在庫管理' },
  { to: '/bom-master', icon: GitBranch, label: '製品BOMマスタ' },
  { to: '/masters', icon: Database, label: 'マスタ管理' },
  { to: '/schedule', icon: Calendar, label: 'スケジュール' },
  { to: '/users', icon: UserCog, label: 'ユーザー管理' },
  { to: '/help', icon: HelpCircle, label: 'ヘルプ' },
];

export default function Layout() {
  // スマホでは折りたたみ状態で開始（サイドバーが画面幅の大半を占有するのを防ぐ）
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768);
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* サイドバー */}
      <aside className={`${sidebarOpen ? 'w-64' : 'w-16'} bg-slate-800 text-white flex flex-col transition-all duration-200`}>
        {/* ロゴ */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-slate-700">
          {sidebarOpen && (
            <div>
              <div className="text-sm font-bold text-white leading-tight">井上電設</div>
              <div className="text-xs text-slate-400">販売管理システム</div>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="ml-auto text-slate-400 hover:text-white"
          >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        {/* ナビ */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {navItems.map((item, idx) =>
            'divider' in item ? (
              <div key={`div-${idx}`} className="my-2 mx-4 border-t border-slate-700" />
            ) : (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 text-sm transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                  }`
                }
              >
                <item.icon size={20} className="shrink-0" />
                {sidebarOpen && <span>{item.label}</span>}
              </NavLink>
            )
          )}
        </nav>

        {/* ユーザー情報 */}
        <div className="border-t border-slate-700 p-4">
          {sidebarOpen && (
            <div className="text-xs text-slate-400 mb-2">
              <div className="text-white font-medium">{user.full_name || 'ユーザー'}</div>
              <div>{user.email}</div>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-slate-400 hover:text-white text-sm"
          >
            <LogOut size={16} />
            {sidebarOpen && 'ログアウト'}
          </button>
        </div>
      </aside>

      {/* メインコンテンツ */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
