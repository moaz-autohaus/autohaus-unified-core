import { useState, useEffect, useCallback } from 'react';

interface HitlEvent {
    id?: string;
    hitl_event_id?: string;
    event_type: string;
    action_type: string;
    target_type: string;
    target_id: string;
    status: string;
    payload: string | Record<string, unknown>;
    reason?: string;
    created_at: string;
}

function getEventId(event: HitlEvent): string {
    return event.hitl_event_id || event.id || '';
}

function parsePayload(raw: string | Record<string, unknown>): Record<string, unknown> | string {
    if (typeof raw !== 'string') return raw as Record<string, unknown>;
    try { return JSON.parse(raw); } catch { return raw; }
}

const T = {
    bg: '#0a0a0a', surface: '#111', card: '#141414', border: '#1e1e1e',
    text: '#e8e8e8', dim: '#888', muted: '#555',
    gold: '#C5A059', red: '#E30613', green: '#22C55E', blue: '#3B82F6',
};

const PAGE_SIZE = 15;

export function ActionCenter() {
    const [queue, setQueue] = useState<HitlEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [toast, setToast] = useState<{ type: string; msg: string } | null>(null);
    const [busyId, setBusyId] = useState<string | null>(null);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [page, setPage] = useState(0);
    const [filterType, setFilterType] = useState<string>('ALL');
    const [search, setSearch] = useState('');

    const showToast = (type: string, msg: string) => {
        setToast({ type, msg });
        setTimeout(() => setToast(null), 4000);
    };

    const fetchQueue = useCallback(async () => {
        setLoading(true);
        try {
            const backendUrl = import.meta.env.VITE_BACKEND_URL || '';
            const res = await fetch(`${backendUrl}/api/hitl/queue`);
            if (!res.ok) throw new Error(`${res.status}`);
            const data: HitlEvent[] = await res.json();
            setQueue(data.map(e => ({ ...e, payload: parsePayload(e.payload) })));
        } catch (err: unknown) {
            showToast('error', `Failed to load queue: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchQueue(); }, [fetchQueue]);

    const handleAction = async (event: HitlEvent, action: 'approve' | 'reject') => {
        const eid = getEventId(event);
        setBusyId(eid);
        try {
            const backendUrl = import.meta.env.VITE_BACKEND_URL || '';
            const res = await fetch(`${backendUrl}/api/hitl/${eid}/${action}`, { method: 'POST' });
            if (!res.ok) throw new Error(await res.text());
            setQueue(prev => prev.filter(e => getEventId(e) !== eid));
            showToast('success', action === 'approve' ? 'Approved and applied.' : 'Rejected and archived.');
            if (expandedId === eid) setExpandedId(null);
        } catch (err: unknown) {
            showToast('error', `Action failed: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setBusyId(null);
        }
    };

    const actionTypes = ['ALL', ...Array.from(new Set(queue.map(e => e.action_type)))];

    const filtered = queue.filter(e => {
        if (filterType !== 'ALL' && e.action_type !== filterType) return false;
        if (search) {
            const s = search.toLowerCase();
            const eid = getEventId(e).toLowerCase();
            const tid = e.target_id.toLowerCase();
            const payStr = typeof e.payload === 'string' ? e.payload.toLowerCase() : JSON.stringify(e.payload).toLowerCase();
            if (!eid.includes(s) && !tid.includes(s) && !e.action_type.toLowerCase().includes(s) && !payStr.includes(s)) return false;
        }
        return true;
    });

    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    const safePage = Math.min(page, totalPages - 1);
    const paged = filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

    const actionLabel = (t: string) => t.replace(/_/g, ' ');
    const actionColor = (t: string) => {
        if (t.includes('EMAIL') || t.includes('GMAIL')) return T.blue;
        if (t.includes('FINANCIAL') || t.includes('JOURNAL')) return T.green;
        if (t.includes('MEDIA') || t.includes('INGEST')) return '#A855F7';
        if (t.includes('POLICY')) return '#F59E0B';
        return T.dim;
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: T.bg, color: T.text, fontFamily: "'DM Sans', sans-serif" }}>

            {toast && (
                <div onClick={() => setToast(null)} style={{
                    position: 'fixed', top: 16, right: 16, zIndex: 999, padding: '12px 18px', borderRadius: 8,
                    background: toast.type === 'error' ? '#E306130d' : '#22C55E0d',
                    border: `1px solid ${toast.type === 'error' ? '#E3061344' : '#22C55E44'}`,
                    color: toast.type === 'error' ? '#fca5a5' : '#86efac',
                    fontSize: 13, cursor: 'pointer', maxWidth: 380,
                }}>
                    {toast.msg}
                </div>
            )}

            <div style={{ padding: '20px 24px 0', flexShrink: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10 }}>
                            Action Center
                            <span style={{ padding: '3px 10px', background: '#F59E0B10', border: '1px solid #F59E0B33', color: '#F59E0B', fontSize: 12, borderRadius: 12, fontFamily: 'monospace', fontWeight: 700 }}>
                                {queue.length}
                            </span>
                        </h2>
                        <p style={{ margin: '4px 0 0', fontSize: 12, color: T.dim, fontFamily: 'monospace' }}>
                            HITL GOVERNANCE QUEUE — Review and authorize AI proposals
                        </p>
                    </div>
                    <button onClick={fetchQueue} disabled={loading} style={{
                        padding: '8px 16px', background: T.card, border: `1px solid ${T.border}`, color: T.text,
                        borderRadius: 6, fontSize: 13, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.5 : 1,
                    }}>
                        {loading ? 'Syncing...' : 'Refresh'}
                    </button>
                </div>

                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
                    <select value={filterType} onChange={e => { setFilterType(e.target.value); setPage(0); }}
                        style={{ padding: '6px 10px', background: T.card, border: `1px solid ${T.border}`, color: T.text, borderRadius: 6, fontSize: 12, fontFamily: 'monospace' }}>
                        {actionTypes.map(t => (
                            <option key={t} value={t}>
                                {t === 'ALL' ? `ALL TYPES (${queue.length})` : `${actionLabel(t)} (${queue.filter(e => e.action_type === t).length})`}
                            </option>
                        ))}
                    </select>
                    <input value={search} onChange={e => { setSearch(e.target.value); setPage(0); }}
                        placeholder="Search by ID, target, or content..."
                        style={{ flex: 1, minWidth: 200, padding: '6px 10px', background: T.card, border: `1px solid ${T.border}`, color: T.text, borderRadius: 6, fontSize: 12, fontFamily: 'monospace', outline: 'none' }}
                    />
                    <span style={{ fontSize: 11, color: T.muted, fontFamily: 'monospace' }}>
                        {filtered.length} result{filtered.length !== 1 ? 's' : ''}
                    </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 120px 140px', gap: 0, padding: '8px 16px', fontSize: 10, fontFamily: 'monospace', color: T.muted, textTransform: 'uppercase', letterSpacing: '0.08em', borderBottom: `1px solid ${T.border}` }}>
                    <span>Target</span>
                    <span>Type</span>
                    <span>Status</span>
                    <span>Time</span>
                    <span style={{ textAlign: 'right' }}>Actions</span>
                </div>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: '0 24px' }}>
                {loading && paged.length === 0 && (
                    <div style={{ padding: 40, textAlign: 'center', color: T.dim }}>Loading queue...</div>
                )}
                {!loading && filtered.length === 0 && (
                    <div style={{ padding: 40, textAlign: 'center', color: T.dim, fontFamily: 'monospace' }}>
                        {search || filterType !== 'ALL' ? 'No matching proposals.' : 'Queue empty — all clear.'}
                    </div>
                )}

                {paged.map(event => {
                    const eid = getEventId(event);
                    const isBusy = busyId === eid;
                    const isOpen = expandedId === eid;
                    const color = actionColor(event.action_type);

                    return (
                        <div key={eid} style={{ borderBottom: `1px solid ${T.border}` }}>
                            <div
                                onClick={() => setExpandedId(isOpen ? null : eid)}
                                style={{
                                    display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 120px 140px', gap: 0,
                                    padding: '12px 16px', alignItems: 'center', cursor: 'pointer',
                                    background: isOpen ? T.card : 'transparent',
                                    transition: 'background 0.1s',
                                }}
                                onMouseEnter={e => { if (!isOpen) e.currentTarget.style.background = '#0f0f0f'; }}
                                onMouseLeave={e => { if (!isOpen) e.currentTarget.style.background = 'transparent'; }}
                            >
                                <div style={{ overflow: 'hidden' }}>
                                    <div style={{ fontSize: 13, fontWeight: 600, color: T.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                        {event.target_id}
                                    </div>
                                    <div style={{ fontSize: 11, color: T.muted, fontFamily: 'monospace', marginTop: 2 }}>
                                        {event.target_type}
                                    </div>
                                </div>
                                <div>
                                    <span style={{
                                        fontSize: 10, fontFamily: 'monospace', fontWeight: 700, padding: '2px 8px',
                                        borderRadius: 4, background: `${color}12`, border: `1px solid ${color}30`,
                                        color, textTransform: 'uppercase', letterSpacing: '0.03em', whiteSpace: 'nowrap',
                                    }}>
                                        {actionLabel(event.action_type)}
                                    </span>
                                </div>
                                <div>
                                    <span style={{
                                        fontSize: 10, fontFamily: 'monospace', fontWeight: 600, padding: '2px 8px',
                                        borderRadius: 4, background: '#F59E0B10', border: '1px solid #F59E0B30',
                                        color: '#F59E0B', textTransform: 'uppercase',
                                    }}>
                                        {event.status}
                                    </span>
                                </div>
                                <span style={{ fontSize: 11, color: T.dim, fontFamily: 'monospace' }}>
                                    {new Date(event.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                </span>
                                <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }} onClick={e => e.stopPropagation()}>
                                    <button
                                        onClick={() => handleAction(event, 'approve')}
                                        disabled={isBusy}
                                        title="Approve"
                                        style={{
                                            padding: '5px 12px', fontSize: 11, fontWeight: 700, fontFamily: 'monospace',
                                            background: '#C5A0590d', border: `1px solid ${T.gold}33`, color: T.gold,
                                            borderRadius: 5, cursor: isBusy ? 'not-allowed' : 'pointer',
                                            opacity: isBusy ? 0.4 : 1, textTransform: 'uppercase', letterSpacing: '0.03em',
                                        }}
                                    >
                                        {isBusy ? '...' : 'Approve'}
                                    </button>
                                    <button
                                        onClick={() => handleAction(event, 'reject')}
                                        disabled={isBusy}
                                        title="Reject"
                                        style={{
                                            padding: '5px 12px', fontSize: 11, fontWeight: 700, fontFamily: 'monospace',
                                            background: 'transparent', border: `1px solid ${T.red}33`, color: T.red,
                                            borderRadius: 5, cursor: isBusy ? 'not-allowed' : 'pointer',
                                            opacity: isBusy ? 0.4 : 1, textTransform: 'uppercase', letterSpacing: '0.03em',
                                        }}
                                    >
                                        {isBusy ? '...' : 'Reject'}
                                    </button>
                                </div>
                            </div>

                            {isOpen && (
                                <div style={{ padding: '0 16px 16px', background: T.card }}>
                                    <div style={{ fontSize: 11, color: T.muted, fontFamily: 'monospace', marginBottom: 8 }}>
                                        ID: {eid}
                                    </div>

                                    {event.reason && (
                                        <p style={{ fontSize: 13, color: T.dim, fontStyle: 'italic', borderLeft: `3px solid ${T.border}`, paddingLeft: 12, margin: '0 0 12px', lineHeight: 1.5 }}>
                                            "{event.reason}"
                                        </p>
                                    )}

                                    <div style={{ background: T.bg, borderRadius: 6, border: `1px solid ${T.border}`, padding: 12, overflow: 'auto', maxHeight: 300 }}>
                                        {(() => {
                                            const p = parsePayload(event.payload);
                                            if (typeof p === 'string') return <pre style={{ margin: 0, fontSize: 12, fontFamily: 'monospace', color: T.dim, whiteSpace: 'pre-wrap' }}>{p}</pre>;
                                            return (
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                                    {Object.entries(p).map(([k, v]) => (
                                                        <div key={k} style={{ display: 'flex', gap: 12, fontSize: 12, padding: '4px 0', borderBottom: `1px solid ${T.border}50` }}>
                                                            <span style={{ color: T.muted, fontFamily: 'monospace', fontSize: 11, textTransform: 'uppercase', minWidth: 140, flexShrink: 0 }}>{k}</span>
                                                            <span style={{ color: T.text, fontFamily: 'monospace', wordBreak: 'break-all' }}>
                                                                {Array.isArray(v) ? v.join(', ') : typeof v === 'object' && v !== null ? JSON.stringify(v, null, 2) : String(v)}
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            );
                                        })()}
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {totalPages > 1 && (
                <div style={{ padding: '10px 24px', borderTop: `1px solid ${T.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0, background: T.surface }}>
                    <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={safePage === 0}
                        style={{ padding: '6px 14px', background: T.card, border: `1px solid ${T.border}`, color: safePage === 0 ? T.muted : T.text, borderRadius: 5, fontSize: 12, cursor: safePage === 0 ? 'not-allowed' : 'pointer' }}>
                        Previous
                    </button>
                    <span style={{ fontSize: 12, color: T.dim, fontFamily: 'monospace' }}>
                        Page {safePage + 1} of {totalPages} — showing {safePage * PAGE_SIZE + 1}–{Math.min((safePage + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}
                    </span>
                    <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={safePage >= totalPages - 1}
                        style={{ padding: '6px 14px', background: T.card, border: `1px solid ${T.border}`, color: safePage >= totalPages - 1 ? T.muted : T.text, borderRadius: 5, fontSize: 12, cursor: safePage >= totalPages - 1 ? 'not-allowed' : 'pointer' }}>
                        Next
                    </button>
                </div>
            )}
        </div>
    );
}
