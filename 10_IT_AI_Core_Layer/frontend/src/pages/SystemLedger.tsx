import { useState } from 'react';
import { DatabaseZap } from 'lucide-react';

interface AuditLog {
    event_id: string;
    timestamp: string;
    actor: string;
    action_type: string;
    entity_id: string;
    changes: string;
}

const MOCK_LEDGER: AuditLog[] = [
    { event_id: 'evt_1', timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), actor: 'System (Agentic Router)', action_type: 'CLASSIFY_INTENT', entity_id: 'MSG-0921', changes: 'Routed inbound SMS to SERVICE domain.' },
    { event_id: 'evt_2', timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(), actor: 'UI_Agent', action_type: 'QUOTE_APPROVED', entity_id: 'demo-quote-001', changes: 'Approved items: [li-001, li-002]' },
    { event_id: 'evt_3', timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(), actor: 'Mechanic (Ahsin)', action_type: 'STATUS_UPDATE', entity_id: 'WBS43AZ0XNC', changes: 'Status changed to "Green Tag"' },
    { event_id: 'evt_4', timestamp: new Date(Date.now() - 1000 * 60 * 125).toISOString(), actor: 'System (Trigger)', action_type: 'INTERCOMPANY_INVOICE', entity_id: 'WBS43AZ0XNC', changes: 'Generated $300 labor invoice from Services to KAMM.' },
];

export function SystemLedger() {
    const [logs] = useState<AuditLog[]>(MOCK_LEDGER);

    return (
        <div className="space-y-6 h-full flex flex-col">
            <div className="flex justify-between items-center shrink-0">
                <div>
                    <h2 className="text-2xl font-semibold text-white tracking-tight mb-1 flex items-center">
                        <DatabaseZap className="w-6 h-6 mr-2 text-zinc-500" /> System Ledger
                    </h2>
                    <p className="text-sm text-zinc-400">Immutable audit trail of all manual and AI-driven ecosystem events.</p>
                </div>
                <div className="flex items-center space-x-2">
                    <span className="flex h-2 w-2 relative">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                    </span>
                    <span className="text-xs uppercase tracking-wider text-zinc-400 font-mono">Live Sync</span>
                </div>
            </div>

            <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden flex-1 flex flex-col">
                <div className="overflow-auto flex-1">
                    <table className="w-full text-left text-sm whitespace-nowrap">
                        <thead className="bg-zinc-950 text-zinc-400 border-b border-zinc-800 sticky top-0 z-10">
                            <tr>
                                <th scope="col" className="px-6 py-4 font-medium">Timestamp</th>
                                <th scope="col" className="px-6 py-4 font-medium">Actor</th>
                                <th scope="col" className="px-6 py-4 font-medium">Action Type</th>
                                <th scope="col" className="px-6 py-4 font-medium">Entity ID</th>
                                <th scope="col" className="px-6 py-4 font-medium w-full">Metadata / Changes</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-800">
                            {logs.map((log) => (
                                <tr key={log.event_id} className="hover:bg-zinc-800/50 transition-colors font-mono text-xs">
                                    <td className="px-6 py-4 text-zinc-500">
                                        {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium border ${log.actor.includes('System') || log.actor.includes('Agent')
                                            ? 'bg-blue-900/10 text-blue-400 border-blue-900/30'
                                            : 'bg-zinc-800 text-zinc-300 border-zinc-700'
                                            }`}>
                                            {log.actor}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-zinc-300 font-semibold">{log.action_type}</td>
                                    <td className="px-6 py-4 text-zinc-400">{log.entity_id}</td>
                                    <td className="px-6 py-4 text-zinc-400 whitespace-normal min-w-[300px]">{log.changes}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
