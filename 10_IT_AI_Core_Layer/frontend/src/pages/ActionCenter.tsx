import { useState, useEffect, useCallback } from 'react';
import { CheckCircle2, XCircle, Mail, Car, DollarSign, Loader2, AlertCircle, RefreshCw } from 'lucide-react';

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

/** Resolves the canonical event ID from either 'id' or 'hitl_event_id' field. */
function getEventId(event: HitlEvent): string {
    return event.hitl_event_id || event.id || '';
}

/** API base URL: uses window origin on Replit, localhost otherwise. */
function getApiBase(): string {
    if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
        return `${window.location.protocol}//${window.location.host}`;
    }
    return 'http://localhost:8000';
}

interface ToastMessage {
    id: string;
    type: 'error' | 'success';
    message: string;
}

export function ActionCenter() {
    const [queue, setQueue] = useState<HitlEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [toasts, setToasts] = useState<ToastMessage[]>([]);
    const [approvingId, setApprovingId] = useState<string | null>(null);
    const [rejectingId, setRejectingId] = useState<string | null>(null);
    const [selectedTier, setSelectedTier] = useState<string>('TIER_1_CONFIRMED');

    const addToast = useCallback((type: 'error' | 'success', message: string) => {
        const id = Math.random().toString(36).slice(2);
        setToasts(prev => [...prev, { id, type, message }]);
        setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
    }, []);

    const fetchQueue = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${getApiBase()}/api/hitl/queue`);
            if (!res.ok) throw new Error(`Queue fetch returned ${res.status}: ${res.statusText}`);
            const data: HitlEvent[] = await res.json();
            setQueue(data);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            console.error('[ActionCenter] fetchQueue failed:', msg);
            addToast('error', `Governance Sync Failed: ${msg}`);
        } finally {
            setLoading(false);
        }
    }, [addToast]);

    useEffect(() => {
        fetchQueue();
    }, [fetchQueue]);

    const handleApprove = async (event: HitlEvent) => {
        const eid = getEventId(event);
        setApprovingId(eid);
        try {
            const res = await fetch(`${getApiBase()}/api/hitl/${eid}/approve`, { method: 'POST' });
            if (!res.ok) {
                const errBody = await res.text();
                throw new Error(`${res.status}: ${errBody}`);
            }
            // Optimistic removal with animation delay
            setTimeout(() => {
                setQueue(prev => prev.filter(e => getEventId(e) !== eid));
            }, 600);
            addToast('success', 'Proposal approved and applied.');
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            console.error('[ActionCenter] approve failed:', msg);
            addToast('error', `Governance Sync Failed: ${msg}`);
        } finally {
            setApprovingId(null);
        }
    };

    const handleReject = async (event: HitlEvent) => {
        const eid = getEventId(event);
        setRejectingId(eid);
        try {
            const res = await fetch(`${getApiBase()}/api/hitl/${eid}/reject`, { method: 'POST' });
            if (!res.ok) {
                const errBody = await res.text();
                throw new Error(`${res.status}: ${errBody}`);
            }
            setTimeout(() => {
                setQueue(prev => prev.filter(e => getEventId(e) !== eid));
            }, 600);
            addToast('success', 'Proposal rejected and archived.');
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            console.error('[ActionCenter] reject failed:', msg);
            addToast('error', `Governance Sync Failed: ${msg}`);
        } finally {
            setRejectingId(null);
        }
    };

    const renderPayload = (event: HitlEvent) => {
        let p = event.payload;
        if (typeof p === 'string') {
            try { p = JSON.parse(p as string); } catch {
                return <pre className="text-[10px] text-zinc-500">{p as string}</pre>;
            }
        }
        const payload = p as Record<string, unknown>;

        if (event.action_type === 'GMAIL_DRAFT_PROPOSAL' || event.event_type === 'EMAIL_DRAFTED') {
            return (
                <div className="space-y-2">
                    <div className="flex items-center gap-2 text-zinc-400 text-[11px]">
                        <Mail className="w-3 h-3" />
                        <span>To: {String(payload.recipient || payload.to || '')}</span>
                    </div>
                    <div className="font-semibold text-zinc-200 text-xs">
                        Subject: {String(payload.subject || '')}
                    </div>
                    <div className="text-zinc-500 text-[11px] line-clamp-3 bg-zinc-950 p-2 rounded border border-zinc-800 italic">
                        "{String(payload.body || payload.content || '')}"
                    </div>
                </div>
            );
        }

        if (event.action_type === 'FINANCIAL_JOURNAL_PROPOSAL') {
            return (
                <div className="space-y-2">
                    <div className="flex items-center gap-2 text-zinc-400 text-[11px]">
                        <DollarSign className="w-3 h-3" />
                        <span>QuickBooks Journal Entry</span>
                    </div>
                    <div className="grid grid-cols-1 gap-1">
                        {Object.entries(payload).map(([k, v]) => (
                            <div key={k} className="flex justify-between border-b border-zinc-800/50 py-1 text-[10px]">
                                <span className="text-zinc-500 uppercase">{k}</span>
                                <span className="text-zinc-300 font-mono">{String(v)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            );
        }

        if (event.action_type === 'ENTITY_MODIFICATION' || event.action_type === 'FIELD_OVERRIDE') {
            const evidenceChain = payload.evidence_chain as string[] | undefined;
            const entries = Object.entries(payload).filter(([k]) => k !== 'evidence_chain' && k !== 'evidence_tier');
            return (
                <div className="space-y-2">
                    <div className="flex items-center gap-2 text-zinc-400 text-[11px]">
                        <Car className="w-3 h-3" />
                        <span>Target: {event.target_id} ({event.target_type})</span>
                    </div>
                    {evidenceChain && evidenceChain.length > 0 && (
                        <div className="bg-zinc-950/50 p-2 rounded border border-zinc-800/80 my-2">
                            <span className="text-[9px] text-zinc-500 font-bold uppercase tracking-wider mb-1 block">Evidence Chain</span>
                            {evidenceChain.map((msgId, i) => (
                                <div key={i} className="text-[10px] text-zinc-400 font-mono flex items-center gap-1.5 break-all">
                                    <span className="text-zinc-600">↳</span> {msgId}
                                </div>
                            ))}
                        </div>
                    )}
                    <div className="grid grid-cols-1 gap-1">
                        {entries.map(([k, v]) => (
                            <div key={k} className="flex justify-between border-b border-zinc-800/50 py-1 text-[10px] items-center gap-2">
                                <span className="text-zinc-500 uppercase flex-shrink-0">{k}</span>
                                <span className="text-zinc-300 font-mono text-right truncate max-w-[60%]">{String(v)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            );
        }

        return (
            <pre className="text-[10px] text-zinc-500 bg-zinc-950 p-2 rounded overflow-auto max-h-32">
                {JSON.stringify(payload, null, 2)}
            </pre>
        );
    };

    return (
        <div className="h-full flex flex-col space-y-6">
            {/* Toast Notifications */}
            <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
                {toasts.map(toast => (
                    <div
                        key={toast.id}
                        onClick={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}
                        className={`pointer-events-auto cursor-pointer px-4 py-3 rounded-xl text-sm font-medium border flex items-center gap-2 shadow-xl animate-in slide-in-from-right transition-all
                            ${toast.type === 'error'
                                ? 'bg-red-950/90 border-red-800/50 text-red-300'
                                : 'bg-green-950/90 border-green-800/50 text-green-300'
                            }`}
                    >
                        {toast.type === 'error' ? <AlertCircle className="w-4 h-4 flex-shrink-0" /> : <CheckCircle2 className="w-4 h-4 flex-shrink-0" />}
                        {toast.message}
                    </div>
                ))}
            </div>

            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
                        Action Center
                        <span className="px-2 py-0.5 bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-[10px] rounded-full uppercase tracking-widest font-mono">
                            {queue.length} Pending
                        </span>
                    </h2>
                    <p className="text-sm text-zinc-400">Sandbox governance queue. Review and authorize AI-proposed operations.</p>
                </div>
                <button
                    onClick={fetchQueue}
                    disabled={loading}
                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-sm font-medium transition-all flex items-center gap-2 border border-zinc-700 disabled:opacity-50"
                >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    {loading ? 'Syncing...' : 'Sync Queue'}
                </button>
            </div>

            {/* Evidence Tier Controls */}
            {(() => {
                const getTier = (e: HitlEvent) => {
                    if (typeof e.payload === "object" && e.payload !== null && "evidence_tier" in e.payload) {
                        return (e.payload as any).evidence_tier;
                    } else if (typeof e.payload === "string" && e.payload.includes("evidence_tier")) {
                        try {
                            const p = JSON.parse(e.payload);
                            return p.evidence_tier;
                        } catch { return 'OTHER'; }
                    }
                    return 'OTHER';
                };

                const byTier = queue.reduce((acc, e) => {
                    const t = getTier(e) || 'OTHER';
                    if (!acc[t]) acc[t] = 0;
                    acc[t]++;
                    return acc;
                }, {} as Record<string, number>);

                const tier1Count = byTier['TIER_1_CONFIRMED'] || 0;
                const tier2Count = byTier['TIER_2_PROBABLE'] || 0;
                const tier3Count = byTier['TIER_3_UNCONFIRMED'] || 0;
                const otherCount = queue.length - tier1Count - tier2Count - tier3Count;

                return (
                    <div className="flex items-center gap-4 bg-zinc-900 border border-zinc-800 rounded-lg p-1.5 w-max text-xs font-medium">
                        <button
                            onClick={() => setSelectedTier('TIER_1_CONFIRMED')}
                            className={`px-4 py-1.5 rounded-md transition-all ${selectedTier === 'TIER_1_CONFIRMED' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-500 hover:text-zinc-300'}`}
                        >
                            {tier1Count} Confirmed
                        </button>
                        <button
                            onClick={() => setSelectedTier('TIER_2_PROBABLE')}
                            className={`px-4 py-1.5 rounded-md transition-all ${selectedTier === 'TIER_2_PROBABLE' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-500 hover:text-zinc-300'}`}
                        >
                            {tier2Count} Probable
                        </button>
                        <button
                            onClick={() => setSelectedTier('TIER_3_UNCONFIRMED')}
                            className={`px-4 py-1.5 rounded-md transition-all ${selectedTier === 'TIER_3_UNCONFIRMED' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-500 hover:text-zinc-300'}`}
                        >
                            {tier3Count} Unconfirmed
                        </button>
                        {otherCount > 0 && (
                            <button
                                onClick={() => setSelectedTier('OTHER')}
                                className={`px-4 py-1.5 rounded-md transition-all ${selectedTier === 'OTHER' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-500 hover:text-zinc-300'}`}
                            >
                                {otherCount} Other
                            </button>
                        )}
                    </div>
                );
            })()}

            {/* Empty State */}
            {!loading && queue.filter(e => {
                let p = e.payload;
                if (typeof p === 'string') { try { p = JSON.parse(p); } catch { } }
                const evtTier = ((p as any)?.evidence_tier) || 'OTHER';
                return evtTier === selectedTier;
            }).length === 0 && (
                    <div className="flex-1 flex flex-col items-center justify-center opacity-30 select-none">
                        <CheckCircle2 className="w-16 h-16 text-zinc-500 mb-4" />
                        <p className="text-zinc-500 font-mono text-xs uppercase tracking-[0.2em]">INBOX ZERO — Category Empty</p>
                    </div>
                )}

            {/* Card Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 overflow-auto pb-8">
                {queue.filter(e => {
                    let p = e.payload;
                    if (typeof p === 'string') { try { p = JSON.parse(p); } catch { } }
                    const evtTier = ((p as any)?.evidence_tier) || 'OTHER';
                    return evtTier === selectedTier;
                }).map((event) => {
                    const eid = getEventId(event);
                    const isApproving = approvingId === eid;
                    const isRejecting = rejectingId === eid;
                    const isProcessing = isApproving || isRejecting;
                    return (
                        <div
                            key={eid}
                            className={`bg-zinc-900/50 border border-zinc-800 rounded-2xl flex flex-col overflow-hidden group hover:border-zinc-700 transition-all duration-300 ${isProcessing ? 'opacity-60 scale-[0.98]' : ''}`}
                        >
                            {/* Card Header */}
                            <div className="p-4 border-b border-zinc-800 bg-zinc-950/30 flex justify-between items-start">
                                <div>
                                    <span className="text-[9px] font-mono font-bold text-zinc-500 uppercase tracking-tighter block mb-1">
                                        {event.action_type}
                                    </span>
                                    <h3 className="text-zinc-100 font-bold text-sm truncate max-w-[160px]">
                                        {event.target_id}
                                    </h3>
                                    <span className="text-[8px] text-zinc-600 font-mono block mt-0.5 truncate max-w-[160px]" title={eid}>
                                        {eid}
                                    </span>
                                </div>
                                <span className="text-[9px] text-zinc-600 font-mono italic whitespace-nowrap">
                                    {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            </div>

                            {/* Card Body */}
                            <div className="p-5 flex-1 bg-gradient-to-b from-transparent to-zinc-950/20">
                                {renderPayload(event)}
                                {event.reason && (
                                    <p className="mt-4 text-[11px] text-zinc-500 italic border-l-2 border-zinc-800 pl-3">
                                        "{event.reason}"
                                    </p>
                                )}
                            </div>

                            {/* Card Actions */}
                            <div className="p-4 bg-zinc-950/50 border-t border-zinc-800 grid grid-cols-2 gap-3">
                                <button
                                    id={`reject-${eid}`}
                                    onClick={() => handleReject(event)}
                                    disabled={isProcessing}
                                    className="flex items-center justify-center gap-2 py-2.5 rounded-xl border border-red-900/30 text-red-500 text-[10px] font-bold uppercase tracking-wider hover:bg-red-900/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {isRejecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
                                    {isRejecting ? 'Archiving...' : 'Reject'}
                                </button>
                                <button
                                    id={`approve-${eid}`}
                                    onClick={() => handleApprove(event)}
                                    disabled={isProcessing}
                                    className="flex items-center justify-center gap-2 py-2.5 rounded-xl bg-green-500/10 border border-green-500/30 text-green-500 text-[10px] font-bold uppercase tracking-wider hover:bg-green-500/20 transition-all shadow-[0_0_15px_-5px_rgba(34,197,94,0.4)] disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {isApproving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                                    {isApproving ? 'Applying...' : 'Approve'}
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
