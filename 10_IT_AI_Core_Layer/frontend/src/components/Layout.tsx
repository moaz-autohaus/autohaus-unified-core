import { Outlet, Link, useLocation } from 'react-router-dom';
import { Database, LayoutDashboard, Car, Activity, Terminal } from 'lucide-react';
import clsx from 'clsx';

const NAV_ITEMS = [
    { name: 'Command Center', path: '/', icon: LayoutDashboard },
    { name: 'Inventory Matrix', path: '/inventory', icon: Car },
    { name: 'System Ledger', path: '/ledger', icon: Database },
    { name: 'Brain Feed', path: '/feed', icon: Terminal },
];

export function Layout() {
    const location = useLocation();

    return (
        <div className="flex h-screen bg-zinc-950 text-white overflow-hidden font-sans">
            {/* Sidebar */}
            <aside className="w-64 bg-zinc-950 flex flex-col border-r border-zinc-800 shrink-0">
                <div className="h-16 flex items-center px-6 border-b border-zinc-800">
                    <Activity className="text-red-600 mr-3 h-6 w-6" />
                    <span className="text-lg font-bold tracking-tight text-white uppercase tracking-wider text-sm">AutoHaus UCC</span>
                </div>

                <nav className="flex-1 overflow-y-auto py-4">
                    <ul className="space-y-1 px-3">
                        {NAV_ITEMS.map((item) => {
                            const isActive = location.pathname === item.path;
                            return (
                                <li key={item.name}>
                                    <Link
                                        to={item.path}
                                        className={clsx(
                                            'flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
                                            isActive
                                                ? 'bg-zinc-800 text-white'
                                                : 'text-zinc-400 hover:bg-zinc-900 hover:text-white'
                                        )}
                                    >
                                        <item.icon className={clsx('mr-3 h-5 w-5', isActive ? 'text-red-500' : 'text-zinc-500')} />
                                        {item.name}
                                    </Link>
                                </li>
                            );
                        })}
                    </ul>
                </nav>

                <div className="p-4 border-t border-zinc-800">
                    <div className="flex items-center">
                        <div className="h-8 w-8 rounded-full bg-zinc-800 flex items-center justify-center border border-zinc-700">
                            <span className="text-sm font-medium text-zinc-300">AH</span>
                        </div>
                        <div className="ml-3">
                            <p className="text-sm font-medium text-white">Ahsin</p>
                            <p className="text-xs font-medium text-zinc-500">Super Admin (CEO)</p>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-[#0a0a0a]">
                {/* Topbar */}
                <header className="h-16 flex items-center justify-between px-8 border-b border-zinc-800 shrink-0 bg-zinc-950/50 backdrop-blur-sm">
                    <h1 className="text-lg font-medium text-zinc-100">
                        {NAV_ITEMS.find(i => i.path === location.pathname)?.name || 'Command Center'}
                    </h1>
                    <div className="flex items-center space-x-4">
                        <span className="flex h-2 w-2 relative">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                        </span>
                        <span className="text-xs font-medium uppercase tracking-wider text-green-500">CIL Online</span>
                    </div>
                </header>

                {/* Page Content */}
                <div className="flex-1 overflow-auto p-8">
                    <Outlet />
                </div>
            </main>
        </div>
    );
}
