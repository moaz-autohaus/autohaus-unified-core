import React, { useState, useEffect } from 'react';
import { Terminal, Cpu } from 'lucide-react';

interface TelemetryLog {
    id: string;
    timestamp: string;
    source: string;
    message: string;
    confidence?: number;
    rawJson?: string;
}

const MOCK_TELEMETRY: TelemetryLog[] = [
    {
        id: 'log-1',
        timestamp: new Date().toISOString(),
        source: 'AgenticRouter',
        message: 'Extracting entities from prompt: "Need finance status on KAMM Lane"',
        confidence: 0.98,
        rawJson: '{"intent": "FINANCE", "entities": {"domain": "KAMM_LLC"}}'
    },
    {
        id: 'log-2',
        timestamp: new Date(Date.now() - 5000).toISOString(),
        source: 'VectorVault',
        message: 'Recalled 2 context chunks for query "finance status"',
        confidence: 0.85
    },
    {
        id: 'log-3',
        timestamp: new Date(Date.now() - 15000).toISOString(),
        source: 'IdentityEngine',
        message: '+1 515-555-0102 resolved to UID: PRSN-902A (John Doe)',
        confidence: 0.92
    }
];

export function BrainFeed() {
    const [logs, setLogs] = useState<TelemetryLog[]>(MOCK_TELEMETRY);

    return (
        <div className="h-full flex flex-col space-y-4">
            <div className="flex justify-between items-center shrink-0">
                <div>
                    <h2 className="text-2xl font-semibold text-white tracking-tight mb-1 flex items-center">
                        <Cpu className="w-6 h-6 mr-2 text-zinc-500" /> Brain Feed
                    </h2>
                    <p className="text-sm text-zinc-400">Real-time CIL Telemetry and LLM Reasoning Hooks.</p>
                </div>
            </div>

            <div className="bg-[#0f0f12] rounded-xl border border-zinc-800 flex-1 overflow-hidden flex flex-col font-mono text-sm relative">
                <div className="h-8 bg-zinc-900 border-b border-zinc-800 flex items-center px-4 shrink-0">
                    <Terminal className="w-4 h-4 text-zinc-500 mr-2" />
                    <span className="text-xs text-zinc-400">stdout // autohaus.cil.core</span>
                </div>

                <div className="flex-1 overflow-auto p-4 space-y-4">
                    {logs.map((log) => (
                        <div key={log.id} className="border-l-2 border-zinc-800 pl-3 py-1 hover:border-red-900/50 transition-colors">
                            <div className="flex items-center space-x-3 mb-1">
                                <span className="text-zinc-600 text-xs">
                                    {new Date(log.timestamp).toISOString().split('T')[1].replace('Z', '')}
                                </span>
                                <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                                    {log.source}
                                </span>
                                {log.confidence && (
                                    <span className={`text-xs ${log.confidence > 0.9 ? 'text-green-500' : 'text-amber-500'}`}>
                                        [Conf: {log.confidence.toFixed(2)}]
                                    </span>
                                )}
                            </div>
                            <div className="text-zinc-300">
                                <span className="text-red-500 mr-2">&gt;</span>
                                {log.message}
                            </div>
                            {log.rawJson && (
                                <div className="mt-2 bg-[#0a0a0a] p-2 rounded text-zinc-500 text-xs whitespace-pre-wrap">
                                    {log.rawJson}
                                </div>
                            )}
                        </div>
                    ))}

                    <div className="flex items-center text-zinc-500 mt-6 animate-pulse">
                        <span className="text-red-500 mr-2">&gt;</span>_
                    </div>
                </div>
            </div>
        </div>
    );
}
