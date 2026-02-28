import { useState, useEffect, useCallback } from 'react';
import { CheckCircle2, XCircle, Mail, Truck, DollarSign, Loader2, AlertCircle, RefreshCw } from 'lucide-react';

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

function getApiBase(): string {
    return '';
}

interface ToastMessage {
    id: string;
    type: 'error' | 'success';
    message: string;
}

function getTier(e: HitlEvent): string {
    let p = e.payload;
    if (typeof p === 'string') {
        try { p = JSON.parse(p); } catch { return 'OTHER'; }
    }
    return ((p as Record<string, unknown>)?.evidence_tier as string) || 'OTHER';
}

export function ActionCenter() {
    const [queue, setQueue] = useState<HitlEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [toasts, setToasts] = useState<ToastMessage[]>([]);
    const [approvingId, setApprovingId] = useState<string | null>(null);
    const [rejectingId, setRejectingId] = useState<string | null>(null);
    const [selectedTier, setSelectedTier] = useState<string>('TIER_1_CONFIRMED');

    const dismissToast = (id: string) => setToasts(prev => prev.filter(t => t.id !== id));

    const addToast = useCallback((type: 'error' | 'success', message: string) => {
        const id = Math.random().toString(36).slice(2);
        setToasts(prev => [...prev, { id, type, message }]);
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
            setQueue(prev => prev.filter(e => getEventId(e) !== eid));
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
            setQueue(prev => prev.filter(e => getEventId(e) !== eid));
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
                return <pre style={{ fontSize: 14, fontFamily: 'monospace', color: '#a1a1aa', whiteSpace: 'pre-wrap' }}>{p as string}</pre>;
            }
        }
        const payload = p as Record<string, unknown>;

        if (event.action_type === 'GMAIL_DRAFT_PROPOSAL' || event.event_type === 'EMAIL_DRAFTED') {
            return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#a1a1aa', fontSize: 14 }}>
                        <Mail size={16} />
                        <span>To: {String(payload.recipient || payload.to || '')}</span>
                    </div>
                    <div style={{ fontWeight: 600, color: '#e8e8e8', fontSize: 16 }}>
                        Subject: {String(payload.subject || '')}
                    </div>
                    <div style={{ color: '#a1a1aa', fontSize: 14, lineHeight: 1.5, background: '#0a0a0a', padding: 12, borderRadius: 6, border: '1px solid #1c1c1c', fontStyle: 'italic' }}>
                        "{String(payload.body || payload.content || '')}"
                    </div>
                </div>
            );
        }

        if (event.action_type === 'FINANCIAL_JOURNAL_PROPOSAL') {
            return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#a1a1aa', fontSize: 14 }}>
                        <DollarSign size={16} />
                        <span>QuickBooks Journal Entry</span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {Object.entries(payload).map(([k, v]) => (
                            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1c1c1c50', padding: '6px 0', fontSize: 14, alignItems: 'center', gap: 8 }}>
                                <span style={{ color: '#a1a1aa', textTransform: 'uppercase', fontFamily: 'monospace', fontSize: 12 }}>{k}</span>
                                <span style={{ color: '#e8e8e8', fontFamily: 'monospace' }}>{String(v)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            );
        }

        if (event.action_type === 'ENTITY_MODIFICATION' || event.action_type === 'FIELD_OVERRIDE') {
            const evidenceChain = payload.evidence_chain as string[] | undefined;
            const conflictDetected = payload.conflict_detected as boolean | undefined;
            const conflictQuestion = payload.conflict_question as string | undefined;
            const extractedFinancials = payload.extracted_financials as string[] | undefined;
            const docMentions = payload.doc_mentions as number | undefined;
            const relationshipType = payload.relationship_type as string | undefined;
            const evidenceTier = payload.evidence_tier as string | undefined;
            const skipKeys = new Set(['evidence_chain', 'evidence_tier', 'conflict_detected', 'conflict_question', 'extracted_financials', 'doc_mentions', 'relationship_type']);
            const entries = Object.entries(payload).filter(([k]) => !skipKeys.has(k));

            const financialColor = (line: string): string => {
                if (line.startsWith('[TRANSACTION]')) return '#22C55E';
                if (line.startsWith('[COVERAGE_LIMIT]')) return '#3B82F6';
                if (line.startsWith('[THIRD_PARTY_CERT]')) return '#71717a';
                if (line.startsWith('[BALANCE_SNAPSHOT]')) return '#F59E0B';
                return '#a1a1aa';
            };

            const tierColor = evidenceTier === 'TIER_1_CONFIRMED' ? '#22C55E' : evidenceTier === 'TIER_2_PROBABLE' ? '#F59E0B' : '#71717a';

            return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        {relationshipType && (
                            <span style={{ fontSize: 11, fontFamily: 'monospace', fontWeight: 700, padding: '3px 8px', borderRadius: 4, background: '#C5A05915', border: '1px solid #C5A05933', color: '#C5A059', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                {relationshipType.replace(/_/g, ' ')}
                            </span>
                        )}
                        <span style={{ fontSize: 11, fontFamily: 'monospace', fontWeight: 700, padding: '3px 8px', borderRadius: 4, background: event.target_type === 'VENDOR' ? '#3B82F610' : event.target_type === 'PERSON' ? '#A855F710' : '#F59E0B10', border: `1px solid ${event.target_type === 'VENDOR' ? '#3B82F633' : event.target_type === 'PERSON' ? '#A855F733' : '#F59E0B33'}`, color: event.target_type === 'VENDOR' ? '#3B82F6' : event.target_type === 'PERSON' ? '#A855F7' : '#F59E0B', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            {event.target_type}
                        </span>
                        {evidenceTier && (
                            <span style={{ fontSize: 11, fontFamily: 'monospace', fontWeight: 700, padding: '3px 8px', borderRadius: 4, background: `${tierColor}10`, border: `1px solid ${tierColor}33`, color: tierColor, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                {evidenceTier.replace(/_/g, ' ')}
                            </span>
                        )}
                    </div>

                    {docMentions != null && (
                        <span style={{ fontSize: 12, color: '#a1a1aa' }}>Referenced in {docMentions} document{docMentions !== 1 ? 's' : ''}</span>
                    )}

                    {extractedFinancials && extractedFinancials.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            {extractedFinancials.map((line, i) => (
                                <div key={i} style={{ fontSize: 13, fontFamily: 'monospace', padding: '5px 8px', borderLeft: `3px solid ${financialColor(line)}`, color: financialColor(line), background: '#0a0a0a', borderRadius: '0 4px 4px 0' }}>
                                    {line}
                                </div>
                            ))}
                        </div>
                    )}

                    {conflictDetected && conflictQuestion && (
                        <div style={{
                            background: '#F59E0B10', border: '2px solid #F59E0B44', padding: 14, borderRadius: 8,
                            display: 'flex', alignItems: 'flex-start', gap: 12,
                        }}>
                            <AlertCircle size={20} color="#F59E0B" style={{ flexShrink: 0, marginTop: 2 }} />
                            <div>
                                <span style={{ color: '#F59E0B', fontWeight: 700, fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 4 }}>Conflict Detected</span>
                                <p style={{ color: '#e8e8e8', fontSize: 14, lineHeight: 1.5, margin: 0 }}>{conflictQuestion}</p>
                            </div>
                        </div>
                    )}

                    {evidenceChain && evidenceChain.length > 0 && (
                        <div style={{ background: '#0a0a0a', padding: 10, borderRadius: 6, border: '1px solid #1c1c1c' }}>
                            <span style={{ fontSize: 11, color: '#a1a1aa', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 6 }}>Evidence Chain</span>
                            {evidenceChain.map((msgId, i) => (
                                <div key={i} style={{ fontSize: 12, color: '#a1a1aa', fontFamily: 'monospace', display: 'flex', alignItems: 'center', gap: 6, wordBreak: 'break-all' }}>
                                    <span style={{ color: '#525252' }}>↳</span> {msgId}
                                </div>
                            ))}
                        </div>
                    )}

                    {entries.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            {entries.map(([k, v]) => (
                                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1c1c1c50', padding: '6px 0', fontSize: 13, alignItems: 'center', gap: 8 }}>
                                    <span style={{ color: '#a1a1aa', textTransform: 'uppercase', flexShrink: 0, fontFamily: 'monospace', fontSize: 11 }}>{k}</span>
                                    <span style={{ color: '#e8e8e8', fontFamily: 'monospace', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis' }}>{String(v)}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            );
        }

        return (
            <pre style={{ fontSize: 14, fontFamily: 'monospace', color: '#a1a1aa', background: '#0a0a0a', padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 200, whiteSpace: 'pre-wrap', margin: 0 }}>
                {JSON.stringify(payload, null, 2)}
            </pre>
        );
    };

    const byTier = queue.reduce((acc, e) => {
        const t = getTier(e);
        if (!acc[t]) acc[t] = 0;
        acc[t]++;
        return acc;
    }, {} as Record<string, number>);

    const tier1Count = byTier['TIER_1_CONFIRMED'] || 0;
    const tier2Count = byTier['TIER_2_PROBABLE'] || 0;
    const tier3Count = byTier['TIER_3_UNCONFIRMED'] || 0;
    const otherCount = queue.length - tier1Count - tier2Count - tier3Count;

    const filteredQueue = queue.filter(e => getTier(e) === selectedTier);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, height: '100%' }}>
            {toasts.length > 0 && (
                <div style={{ position: 'fixed', top: 16, right: 16, zIndex: 50, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {toasts.map(toast => (
                        <div
                            key={toast.id}
                            onClick={() => dismissToast(toast.id)}
                            style={{
                                cursor: 'pointer', padding: '14px 18px', borderRadius: 8, fontSize: 14, fontWeight: 500,
                                border: `1px solid ${toast.type === 'error' ? '#E3061344' : '#22C55E44'}`,
                                background: toast.type === 'error' ? '#E306130d' : '#22C55E0d',
                                color: toast.type === 'error' ? '#fca5a5' : '#86efac',
                                display: 'flex', alignItems: 'center', gap: 10, maxWidth: 400,
                            }}
                        >
                            {toast.type === 'error' ? <AlertCircle size={18} style={{ flexShrink: 0 }} /> : <CheckCircle2 size={18} style={{ flexShrink: 0 }} />}
                            {toast.message}
                            <span style={{ marginLeft: 'auto', fontSize: 18, color: '#a1a1aa', flexShrink: 0 }}>✕</span>
                        </div>
                    ))}
                </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h2 style={{ fontSize: 24, fontWeight: 700, color: 'white', margin: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
                        Action Center
                        <span style={{
                            padding: '4px 12px', background: '#F59E0B10', border: '1px solid #F59E0B33',
                            color: '#F59E0B', fontSize: 13, borderRadius: 20, fontFamily: 'monospace', fontWeight: 700,
                        }}>
                            {queue.length} Pending
                        </span>
                    </h2>
                    <p style={{ fontSize: 14, color: '#a1a1aa', marginTop: 4 }}>Sandbox governance queue. Review and authorize AI-proposed operations.</p>
                </div>
                <button
                    onClick={fetchQueue}
                    disabled={loading}
                    style={{
                        padding: '10px 18px', minHeight: 44, background: '#141414', border: '1px solid #242424',
                        color: 'white', borderRadius: 8, fontSize: 14, fontWeight: 500, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: 8, opacity: loading ? 0.5 : 1,
                    }}
                >
                    {loading ? <Loader2 size={18} /> : <RefreshCw size={18} />}
                    {loading ? 'Syncing...' : 'Sync Queue'}
                </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: '#0f0f0f', border: '1px solid #1c1c1c', borderRadius: 8, padding: 4, width: 'max-content' }}>
                {[
                    { key: 'TIER_1_CONFIRMED', label: 'Confirmed', count: tier1Count },
                    { key: 'TIER_2_PROBABLE', label: 'Probable', count: tier2Count },
                    { key: 'TIER_3_UNCONFIRMED', label: 'Unconfirmed', count: tier3Count },
                    ...(otherCount > 0 ? [{ key: 'OTHER', label: 'Other', count: otherCount }] : []),
                ].map(tier => (
                    <button
                        key={tier.key}
                        onClick={() => setSelectedTier(tier.key)}
                        style={{
                            padding: '10px 20px', minHeight: 44, borderRadius: 6, border: 'none',
                            background: selectedTier === tier.key ? '#242424' : 'transparent',
                            color: selectedTier === tier.key ? 'white' : '#a1a1aa',
                            fontSize: 14, fontWeight: 600, cursor: 'pointer',
                        }}
                    >
                        {tier.count} {tier.label}
                    </button>
                ))}
            </div>

            {!loading && filteredQueue.length === 0 && (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: 0.4 }}>
                    <CheckCircle2 size={48} color="#a1a1aa" />
                    <p style={{ color: '#a1a1aa', fontFamily: 'monospace', fontSize: 14, textTransform: 'uppercase', letterSpacing: '0.15em', marginTop: 12 }}>INBOX ZERO — Category Empty</p>
                </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 16, overflow: 'auto', paddingBottom: 20 }}>
                {filteredQueue.map((event) => {
                    const eid = getEventId(event);
                    const isApproving = approvingId === eid;
                    const isRejecting = rejectingId === eid;
                    const isProcessing = isApproving || isRejecting;
                    return (
                        <div
                            key={eid}
                            style={{
                                background: '#0f0f0f', border: '1px solid #1c1c1c', borderRadius: 12,
                                display: 'flex', flexDirection: 'column', overflow: 'hidden',
                                opacity: isProcessing ? 0.6 : 1,
                            }}
                        >
                            <div style={{ padding: 16, borderBottom: '1px solid #1c1c1c', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div>
                                    <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#a1a1aa', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'block', marginBottom: 4 }}>
                                        {event.action_type}
                                    </span>
                                    <h3 style={{ color: 'white', fontWeight: 700, fontSize: 18, margin: 0 }}>
                                        {event.target_id}
                                    </h3>
                                    <span style={{ fontSize: 12, color: '#a1a1aa', fontFamily: 'monospace', display: 'block', marginTop: 2 }} title={eid}>
                                        {eid}
                                    </span>
                                </div>
                                <span style={{ fontSize: 13, color: '#a1a1aa', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                                    {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            </div>

                            <div style={{ padding: 16, flex: 1 }}>
                                {renderPayload(event)}
                                {event.reason && (
                                    <p style={{ marginTop: 14, fontSize: 14, color: '#a1a1aa', fontStyle: 'italic', borderLeft: '3px solid #242424', paddingLeft: 12, lineHeight: 1.5 }}>
                                        "{event.reason}"
                                    </p>
                                )}
                            </div>

                            <div style={{ padding: 12, borderTop: '1px solid #1c1c1c', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                <button
                                    id={`reject-${eid}`}
                                    onClick={() => handleReject(event)}
                                    disabled={isProcessing}
                                    style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                                        minHeight: 44, borderRadius: 8, border: '1px solid #E3061333',
                                        background: 'transparent', color: '#E30613', fontSize: 13,
                                        fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
                                        cursor: isProcessing ? 'not-allowed' : 'pointer', opacity: isProcessing ? 0.5 : 1,
                                    }}
                                    onMouseEnter={e => { if (!isProcessing) e.currentTarget.style.background = '#E306130d'; }}
                                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                                >
                                    {isRejecting ? <Loader2 size={16} /> : <XCircle size={16} />}
                                    {isRejecting ? 'Archiving...' : 'Reject'}
                                </button>
                                <button
                                    id={`approve-${eid}`}
                                    onClick={() => handleApprove(event)}
                                    disabled={isProcessing}
                                    style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                                        minHeight: 44, borderRadius: 8, border: '1px solid #C5A05933',
                                        background: '#C5A0590d', color: '#C5A059', fontSize: 13,
                                        fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
                                        cursor: isProcessing ? 'not-allowed' : 'pointer', opacity: isProcessing ? 0.5 : 1,
                                    }}
                                    onMouseEnter={e => { if (!isProcessing) e.currentTarget.style.background = '#C5A0591a'; }}
                                    onMouseLeave={e => { e.currentTarget.style.background = '#C5A0590d'; }}
                                >
                                    {isApproving ? <Loader2 size={16} /> : <CheckCircle2 size={16} />}
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
