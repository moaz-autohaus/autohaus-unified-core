import { Outlet, Link, useLocation } from 'react-router-dom';
import { Database, LayoutDashboard, Car, Activity, Terminal, FlaskConical } from 'lucide-react';
import clsx from 'clsx';
import { useOrchestrator } from '../contexts/OrchestratorContext';

const NAV_ITEMS = [
    { name: 'Command Center', path: '/', icon: LayoutDashboard },
    { name: 'Action Center', path: '/actions', icon: Activity },
    { name: 'Inventory Matrix', path: '/inventory', icon: Car },
    { name: 'System Ledger', path: '/ledger', icon: Database },
    { name: 'Brain Feed', path: '/feed', icon: Terminal },
];

const DEV_NAV_ITEMS = [
    { name: 'Public API Test', path: '/dev/public-api', icon: FlaskConical },
];

export function Layout() {
    const location = useLocation();
    const { activeSkin } = useOrchestrator();

    const isClientSkin = activeSkin === 'CLIENT_HANDSHAKE';
    const isFieldSkin = activeSkin === 'FIELD_DIAGNOSTIC';

    return (
        <div className="flex h-screen w-full overflow-hidden font-sans">
            {/* Sidebar - Dynamically sized by Orchestrator Skin */}
            <aside
                className={clsx(
                    "bg-[var(--bg-primary)] flex flex-col border-r border-[var(--brand-border)] shrink-0 transition-all duration-300",
                    isClientSkin ? "w-0 overflow-hidden border-none" : (isFieldSkin ? "w-16" : "w-64")
                )}
            >
                <div className={clsx("h-16 flex items-center border-b border-[var(--brand-border)] transition-all", isFieldSkin ? "justify-center px-0" : "px-6")}>
                    <Activity className="text-[var(--accent-primary)] h-6 w-6 shrink-0" />
                    {!isFieldSkin && <span className="ml-3 text-lg font-bold tracking-wider text-white uppercase text-sm whitespace-nowrap">AutoHaus UCC</span>}
                </div>

                <nav className="flex-1 overflow-y-auto py-4 overflow-x-hidden">
                    <ul className="space-y-1 px-3">
                        {NAV_ITEMS.map((item) => {
                            const isActive = location.pathname === item.path;
                            return (
                                <li key={item.name}>
                                    <Link
                                        to={item.path}
                                        title={isFieldSkin ? item.name : undefined}
                                        className={clsx(
                                            'flex items-center py-2 text-sm font-medium rounded-md transition-colors',
                                            isFieldSkin ? 'justify-center px-0' : 'px-3',
                                            isActive
                                                ? 'bg-zinc-800/50 text-white'
                                                : 'text-zinc-400 hover:bg-zinc-800/30 hover:text-white'
                                        )}
                                    >
                                        <item.icon className={clsx('h-5 w-5 shrink-0', isActive ? 'text-[var(--accent-primary)]' : 'text-zinc-500', !isFieldSkin && 'mr-3')} />
                                        {!isFieldSkin && <span className="whitespace-nowrap">{item.name}</span>}
                                    </Link>
                                </li>
                            );
                        })}
                    </ul>
                    {/* Dev-only nav */}
                    {!isFieldSkin && (
                        <div className="mt-6 px-3">
                            <p className="text-[9px] text-zinc-600 uppercase tracking-widest font-mono mb-2 px-0">Dev Tools</p>
                            <ul className="space-y-1">
                                {DEV_NAV_ITEMS.map((item) => {
                                    const isActive = location.pathname === item.path;
                                    return (
                                        <li key={item.name}>
                                            <Link
                                                to={item.path}
                                                className={clsx(
                                                    'flex items-center py-2 px-3 text-sm font-medium rounded-md transition-colors',
                                                    isActive
                                                        ? 'bg-orange-900/30 text-orange-300'
                                                        : 'text-zinc-600 hover:bg-zinc-800/30 hover:text-zinc-400'
                                                )}
                                            >
                                                <item.icon className={clsx('h-5 w-5 shrink-0 mr-3', isActive ? 'text-orange-400' : 'text-zinc-600')} />
                                                <span className="whitespace-nowrap">{item.name}</span>
                                            </Link>
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    )}
                </nav>

                <div className="p-4 border-t border-[var(--brand-border)]">
                    <div className={clsx("flex items-center", isFieldSkin && "justify-center")}>
                        <div className="h-8 w-8 rounded-full bg-zinc-800 flex items-center justify-center border border-zinc-700 shrink-0">
                            <span className="text-sm font-medium text-zinc-300">AH</span>
                        </div>
                        {!isFieldSkin && (
                            <div className="ml-3 whitespace-nowrap overflow-hidden">
                                <p className="text-sm font-medium text-white truncate">Ahsin</p>
                                <p className="text-xs font-medium text-zinc-500 truncate">Super Admin (CEO)</p>
                            </div>
                        )}
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-[var(--bg-primary)]">
                {/* Topbar */}
                <header className="h-16 flex items-center justify-between px-8 border-b border-[var(--brand-border)] shrink-0 bg-[var(--bg-primary)] backdrop-blur-sm transition-colors">
                    <h1 className="text-lg font-medium text-[var(--text-primary)]">
                        {[...NAV_ITEMS, ...DEV_NAV_ITEMS].find(i => i.path === location.pathname)?.name || 'Command Center'}
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
                <div className="flex-1 overflow-auto p-8 relative">
                    <Outlet />
                    {/* Ghost Skin Overlay */}
                    {activeSkin === 'GHOST' && (
                        <div className="absolute inset-0 bg-zinc-950/80 backdrop-blur-sm z-50 flex items-center justify-center pointer-events-none transition-opacity duration-500">
                            <span className="text-zinc-500 tracking-widest uppercase text-sm flex items-center gap-2">
                                <Activity className="w-4 h-4 animate-pulse" />
                                Processing Ambient Event
                            </span>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
