import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, Package, FileText, ShoppingCart,
  Truck, BarChart3, LogOut, Menu, X, Boxes, Briefcase, Database, UserCog, Calendar,
  ShoppingBag, Factory, ClipboardList, GitBranch
} from 'lucide-react';
import { useState } from 'react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'ダッシュボード', end: true },
  { to: '/estimates', icon: FileText, label: '見積管理' },
  { to: '/orders', icon: ShoppingCart, label: '受注管理' },
  { to: '/purchase-orders', icon: Truck, label: '発注・仕入管理' },
  { to: '/inventory', icon: Boxes, label: '在庫管理' },
  { to: '/projects', icon: Briefcase, label: '案件管理' },
  { to: '/masters', icon: Database, label: 'マスタ管理' },
  { to: '/users', icon: UserCog, label: 'ユーザー管理' },
  { to: '/schedule', icon: Calendar, label: 'スケジュール' },
  { to: '/sales-plan', icon: BarChart3, label: '売上計画表' },
  { to: '/bom-master', icon: GitBranch, label: '製品BOMマスタ' },
  { to: '/procurement', icon: ShoppingBag, label: '仕入（発注）管理' },
  { to: '/manufacturing', icon: Factory, label: '製造計画' },
  { to: '/process', icon: ClipboardList, label: '工程管理' },
];

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
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
          {navItems.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                }`
              }
            >
              <Icon size={20} className="shrink-0" />
              {sidebarOpen && <span>{label}</span>}
            </NavLink>
          ))}
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
