/**
 * PublicApiTest — Phase 9, Task 3
 * Dev-only dashboard for testing the public API surface.
 * Hidden from main nav — accessible at /dev/public-api
 *
 * Sections:
 *  1. Public Inventory Grid — GET /api/public/inventory
 *  2. Lead Intake Form     — POST /api/public/lead
 */
import { useState, useEffect, useCallback } from 'react';
import {
    Car, Send, CheckCircle2, AlertCircle, Loader2,
    Eye, EyeOff, RefreshCw, ShieldAlert, DollarSign,
} from 'lucide-react';

function getApiBase(): string {
    if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
        return `${window.location.protocol}//${window.location.host}`;
    }
    return 'http://localhost:8000';
}

interface PublicVehicle {
    id: string;
    make: string;
    model: string;
    year?: number;
    vin: string;
    status: string;
    listing_price: number;
    // Verify these are NOT present in the response:
    wholesale_cost?: unknown;
    recon_cost?: unknown;
    cost?: unknown;
}

interface LeadForm {
    name: string;
    phone: string;
    email: string;
    interest_vin: string;
}

interface Toast {
    id: string;
    type: 'success' | 'error';
    message: string;
}

export function PublicApiTest() {
    // ── Inventory state ─────────────────────────────────────────────────────
    const [vehicles, setVehicles] = useState<PublicVehicle[]>([]);
    const [inventoryLoading, setInventoryLoading] = useState(false);
    const [inventoryError, setInventoryError] = useState<string | null>(null);
    const [leakedFields, setLeakedFields] = useState<string[]>([]);

    // ── Lead form state ──────────────────────────────────────────────────────
    const [form, setForm] = useState<LeadForm>({
        name: 'Test User',
        phone: '555-0199',
        email: 'test@example.com',
        interest_vin: '',
    });
    const [leadLoading, setLeadLoading] = useState(false);
    const [toasts, setToasts] = useState<Toast[]>([]);

    const addToast = useCallback((type: Toast['type'], message: string) => {
        const id = Math.random().toString(36).slice(2);
        setToasts(prev => [...prev, { id, type, message }]);
        setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 5000);
    }, []);

    // ── Fetch public inventory ───────────────────────────────────────────────
    const fetchInventory = useCallback(async () => {
        setInventoryLoading(true);
        setInventoryError(null);
        setLeakedFields([]);
        try {
            const res = await fetch(`${getApiBase()}/api/public/inventory`);
            if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
            const data: PublicVehicle[] = await res.json();
            setVehicles(data);

            // Security audit: check for leaked internal cost fields
            const FORBIDDEN = ['wholesale_cost', 'recon_cost', 'cost', 'purchase_price', 'internal_notes'];
            const found: string[] = [];
            data.forEach(v => {
                FORBIDDEN.forEach(f => {
                    if (f in v) found.push(f);
                });
            });
            setLeakedFields([...new Set(found)]);
        } catch (err: unknown) {
            setInventoryError(err instanceof Error ? err.message : String(err));
        } finally {
            setInventoryLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchInventory();
    }, [fetchInventory]);

    // ── Submit lead ──────────────────────────────────────────────────────────
    const handleLeadSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLeadLoading(true);
        try {
            const res = await fetch(`${getApiBase()}/api/public/lead`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form),
            });
            if (!res.ok) {
                const body = await res.text();
                throw new Error(`${res.status}: ${body}`);
            }
            addToast('success', `Lead accepted! The CIL will notify the CEO and create a Person entity for ${form.email}.`);
            setForm({ name: 'Test User', phone: '555-0199', email: 'test@example.com', interest_vin: '' });
        } catch (err: unknown) {
            addToast('error', err instanceof Error ? err.message : String(err));
        } finally {
            setLeadLoading(false);
        }
    };

    return (
        <div className="space-y-10">
            {/* Toast stack */}
            <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
                {toasts.map(t => (
                    <div
                        key={t.id}
                        className={`pointer-events-auto px-4 py-3 rounded-xl text-sm font-medium border flex items-center gap-2 shadow-xl
                            ${t.type === 'success' ? 'bg-green-950/90 border-green-800/50 text-green-300' : 'bg-red-950/90 border-red-800/50 text-red-300'}`}
                    >
                        {t.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                        {t.message}
                    </div>
                ))}
            </div>

            {/* Page header */}
            <div className="flex justify-between items-start">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <ShieldAlert className="w-5 h-5 text-orange-400" />
                        <span className="text-orange-400 text-xs font-mono font-bold uppercase tracking-widest">Dev-Only View</span>
                    </div>
                    <h2 className="text-2xl font-bold text-white tracking-tight">Public API Test Dashboard</h2>
                    <p className="text-sm text-zinc-400 mt-1">Verify the public API surface — correct data exposure and lead intake.</p>
                </div>
            </div>

            {/* ─── SECTION 1: Inventory Grid ─────────────────────────────── */}
            <section className="space-y-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                            <Car className="w-5 h-5 text-blue-400" />
                            1. Public Inventory Grid
                        </h3>
                        <p className="text-sm text-zinc-500 mt-0.5">
                            <code className="text-blue-400 text-xs">GET /api/public/inventory</code>
                            {' '}— must only show AVAILABLE vehicles, no cost fields.
                        </p>
                    </div>
                    <button
                        onClick={fetchInventory}
                        disabled={inventoryLoading}
                        className="flex items-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-sm border border-zinc-700 transition-all disabled:opacity-50"
                    >
                        {inventoryLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                        Refresh
                    </button>
                </div>

                {/* Security audit result */}
                <div className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm ${leakedFields.length > 0
                        ? 'bg-red-950/40 border-red-800/50 text-red-400'
                        : 'bg-green-950/30 border-green-800/40 text-green-400'
                    }`}>
                    {leakedFields.length > 0 ? (
                        <><EyeOff className="w-4 h-4" /> <strong>SECURITY FAILURE:</strong> Leaked fields: {leakedFields.join(', ')}</>
                    ) : (
                        <><Eye className="w-4 h-4" /> <strong>Security Pass:</strong> No internal cost fields found in response.</>
                    )}
                </div>

                {inventoryError && (
                    <div className="p-4 bg-red-900/10 border border-red-900/30 rounded-xl flex items-center gap-3 text-red-400 text-sm">
                        <AlertCircle className="w-5 h-5 flex-shrink-0" />
                        {inventoryError}
                    </div>
                )}

                {!inventoryLoading && vehicles.length === 0 && !inventoryError && (
                    <div className="py-12 text-center text-zinc-600 text-sm">
                        No AVAILABLE vehicles returned. Check backend filter.
                    </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {vehicles.map(v => (
                        <div key={v.id || v.vin} className="bg-zinc-900/60 border border-zinc-800 rounded-xl overflow-hidden">
                            <div className="p-4 border-b border-zinc-800 bg-zinc-950/40">
                                <div className="text-xs font-mono text-zinc-500 mb-0.5">{v.vin}</div>
                                <div className="font-semibold text-white">{v.year} {v.make} {v.model}</div>
                                <span className="inline-block mt-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/30 text-green-400 uppercase tracking-wider">
                                    {v.status}
                                </span>
                            </div>
                            <div className="p-4 flex items-center gap-2">
                                <DollarSign className="w-4 h-4 text-zinc-500" />
                                <span className="text-white font-mono font-semibold">
                                    {v.listing_price?.toLocaleString() ?? 'N/A'}
                                </span>
                                <span className="text-zinc-500 text-xs">listing price</span>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* ─── SECTION 2: Lead Intake Form ──────────────────────────── */}
            <section className="space-y-4">
                <div>
                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                        <Send className="w-5 h-5 text-purple-400" />
                        2. Public Lead Intake Form
                    </h3>
                    <p className="text-sm text-zinc-500 mt-0.5">
                        <code className="text-purple-400 text-xs">POST /api/public/lead</code>
                        {' '}— creates a Person entity and notifies CEO.
                    </p>
                </div>

                <form onSubmit={handleLeadSubmit} className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 space-y-4 max-w-lg">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs text-zinc-400 mb-1 uppercase tracking-wider">Name</label>
                            <input
                                id="lead-name"
                                type="text"
                                value={form.name}
                                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                                required
                                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-purple-500 transition-colors"
                            />
                        </div>
                        <div>
                            <label className="block text-xs text-zinc-400 mb-1 uppercase tracking-wider">Phone</label>
                            <input
                                id="lead-phone"
                                type="tel"
                                value={form.phone}
                                onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                                required
                                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-purple-500 transition-colors"
                            />
                        </div>
                    </div>
                    <div>
                        <label className="block text-xs text-zinc-400 mb-1 uppercase tracking-wider">Email</label>
                        <input
                            id="lead-email"
                            type="email"
                            value={form.email}
                            onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                            required
                            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-purple-500 transition-colors"
                        />
                    </div>
                    <div>
                        <label className="block text-xs text-zinc-400 mb-1 uppercase tracking-wider">Interest VIN <span className="normal-case text-zinc-500">(optional)</span></label>
                        <input
                            id="lead-vin"
                            type="text"
                            value={form.interest_vin}
                            onChange={e => setForm(f => ({ ...f, interest_vin: e.target.value }))}
                            placeholder="WBA1234..."
                            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 font-mono focus:outline-none focus:border-purple-500 transition-colors"
                        />
                    </div>

                    {/* Preview payload */}
                    <div className="bg-zinc-950 rounded-lg p-3 border border-zinc-800">
                        <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">POST Payload Preview</p>
                        <pre className="text-[11px] text-zinc-400 font-mono">{JSON.stringify(form, null, 2)}</pre>
                    </div>

                    <button
                        id="lead-submit"
                        type="submit"
                        disabled={leadLoading}
                        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold transition-all shadow-[0_0_20px_-5px_rgba(168,85,247,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {leadLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                        {leadLoading ? 'Submitting Lead...' : 'Submit Test Lead'}
                    </button>
                </form>
            </section>
        </div>
    );
}
