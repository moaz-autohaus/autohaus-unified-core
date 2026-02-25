import React, { useState } from 'react';
import { Check, Clock, AlertCircle } from 'lucide-react';

interface Vehicle {
    id: string;
    make: string;
    model: string;
    vin: string;
    price: number;
    status: 'PENDING' | 'LIVE';
    entity: string;
}

const MOCK_INVENTORY: Vehicle[] = [
    { id: 'V-001', make: 'Porsche', model: '911 Carrera T', vin: 'WP0AB2A93RS', price: 128500, status: 'PENDING', entity: 'KAMM_LLC' },
    { id: 'V-002', make: 'BMW', model: 'M4 Competition', vin: 'WBS43AZ0XNC', price: 84000, status: 'LIVE', entity: 'KAMM_LLC' },
    { id: 'V-003', make: 'Ford', model: 'Transit 250', vin: '1FTBR1CM4PK', price: 42000, status: 'LIVE', entity: 'FLUIDITRUCK_LLC' },
];

export function InventoryMatrix() {
    const [vehicles, setVehicles] = useState<Vehicle[]>(MOCK_INVENTORY);
    const [loadingId, setLoadingId] = useState<string | null>(null);

    const handlePromote = async (id: string) => {
        setLoadingId(id);

        // Simulate backend handshake
        // endpoint: POST /api/inventory/promote
        // payload: { vehicle_id: id, actor_id: "UI_Agent" }

        setTimeout(() => {
            setVehicles(prev => prev.map(v =>
                v.id === id ? { ...v, status: 'LIVE' } : v
            ));
            setLoadingId(null);
        }, 1000);
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-semibold text-white tracking-tight mb-1">Inventory Matrix</h2>
                    <p className="text-sm text-zinc-400">The authoritative ledger of physical assets across all entities.</p>
                </div>
                <button className="bg-zinc-800 hover:bg-zinc-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors border border-zinc-700">
                    Sync with CIL
                </button>
            </div>

            <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
                <table className="w-full text-left text-sm whitespace-nowrap">
                    <thead className="bg-zinc-950 text-zinc-400 border-b border-zinc-800">
                        <tr>
                            <th scope="col" className="px-6 py-4 font-medium">Asset</th>
                            <th scope="col" className="px-6 py-4 font-medium">Entity</th>
                            <th scope="col" className="px-6 py-4 font-medium">Price</th>
                            <th scope="col" className="px-6 py-4 font-medium">Status</th>
                            <th scope="col" className="px-6 py-4 font-medium text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800">
                        {vehicles.map((v) => (
                            <tr key={v.id} className="hover:bg-zinc-800/50 transition-colors">
                                <td className="px-6 py-4">
                                    <div className="font-medium text-zinc-100">{v.make} {v.model}</div>
                                    <div className="text-zinc-500 font-mono text-xs mt-1">{v.vin}</div>
                                </td>
                                <td className="px-6 py-4">
                                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-zinc-800 text-zinc-300 border border-zinc-700">
                                        {v.entity}
                                    </span>
                                </td>
                                <td className="px-6 py-4 font-mono text-zinc-300">
                                    ${v.price.toLocaleString()}
                                </td>
                                <td className="px-6 py-4">
                                    {v.status === 'LIVE' ? (
                                        <span className="inline-flex items-center text-green-400 text-xs font-medium">
                                            <Check className="w-3.5 h-3.5 mr-1" /> Live
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center text-amber-400 text-xs font-medium">
                                            <Clock className="w-3.5 h-3.5 mr-1" /> Pending
                                        </span>
                                    )}
                                </td>
                                <td className="px-6 py-4 text-right">
                                    {v.status === 'PENDING' && (
                                        <button
                                            onClick={() => handlePromote(v.id)}
                                            disabled={loadingId === v.id}
                                            className="inline-flex items-center justify-center bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded text-xs font-semibold transition-colors disabled:opacity-50"
                                        >
                                            {loadingId === v.id ? 'Promoting...' : 'Promote to Live'}
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
