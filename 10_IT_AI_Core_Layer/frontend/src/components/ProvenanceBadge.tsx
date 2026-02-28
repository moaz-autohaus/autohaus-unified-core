/**
 * ProvenanceBadge — Phase 9, Task 1
 * Displays the data authority level of a field/entity.
 * Authority hierarchy: SOVEREIGN > VERIFIED > AUTO_ENRICHED > EXTRACTED > PROPOSED > UNVERIFIED
 */
import { Crown, ShieldCheck, Shield, FileText, Eye, HelpCircle } from 'lucide-react';

export type AuthorityLevel =
    | 'SOVEREIGN'
    | 'VERIFIED'
    | 'AUTO_ENRICHED'
    | 'EXTRACTED'
    | 'PROPOSED'
    | 'UNVERIFIED';

interface ProvenanceBadgeProps {
    authority_level: AuthorityLevel;
    source_type?: string;   // e.g. "NHTSA", "State Registry"
    corroboration_count?: number;
    showLabel?: boolean;
}

const CONFIGS: Record<
    AuthorityLevel,
    { icon: React.ComponentType<{ className?: string }>; label: string; colorClass: string; bgClass: string; pulse: boolean }
> = {
    SOVEREIGN: {
        icon: Crown,
        label: 'Sovereign',
        colorClass: 'text-yellow-400',
        bgClass: 'bg-yellow-400/10 border-yellow-400/30',
        pulse: false,
    },
    VERIFIED: {
        icon: ShieldCheck,
        label: 'Verified',
        colorClass: 'text-green-400',
        bgClass: 'bg-green-400/10 border-green-400/30',
        pulse: false,
    },
    AUTO_ENRICHED: {
        icon: Shield,
        label: 'Auto-Enriched',
        colorClass: 'text-blue-400',
        bgClass: 'bg-blue-400/10 border-blue-400/30',
        pulse: false,
    },
    EXTRACTED: {
        icon: FileText,
        label: 'Extracted',
        colorClass: 'text-purple-400',
        bgClass: 'bg-purple-400/10 border-purple-400/30',
        pulse: false,
    },
    PROPOSED: {
        icon: Eye,
        label: 'Proposed',
        colorClass: 'text-yellow-300',
        bgClass: 'bg-yellow-300/10 border-yellow-300/30',
        pulse: true,
    },
    UNVERIFIED: {
        icon: HelpCircle,
        label: 'Unverified',
        colorClass: 'text-zinc-500',
        bgClass: 'bg-zinc-500/10 border-zinc-500/20',
        pulse: false,
    },
};

export function ProvenanceBadge({
    authority_level,
    source_type,
    corroboration_count,
    showLabel = false,
}: ProvenanceBadgeProps) {
    const config = CONFIGS[authority_level] ?? CONFIGS.UNVERIFIED;
    const Icon = config.icon;

    const tooltip = source_type
        ? `Verified by ${source_type}${corroboration_count !== undefined ? ` · ${corroboration_count} corroborations` : ''}`
        : `${config.label}${corroboration_count !== undefined ? ` · ${corroboration_count} corroborations` : ''}`;

    return (
        <span
            title={tooltip}
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md border text-[10px] font-semibold uppercase tracking-wider cursor-default select-none
                ${config.colorClass} ${config.bgClass}`}
        >
            <Icon className={`w-3 h-3 flex-shrink-0 ${config.pulse ? 'animate-pulse' : ''}`} />
            {showLabel && <span>{config.label}</span>}
        </span>
    );
}

/**
 * ProvenanceField — wraps a value with a ProvenanceBadge inline.
 * Usage: <ProvenanceField value="WP0AB2A93RS" authority_level="VERIFIED" />
 */
interface ProvenanceFieldProps {
    value: string | number;
    authority_level: AuthorityLevel;
    source_type?: string;
    corroboration_count?: number;
    className?: string;
}

export function ProvenanceField({
    value,
    authority_level,
    source_type,
    corroboration_count,
    className = '',
}: ProvenanceFieldProps) {
    return (
        <span className={`inline-flex items-center gap-1.5 ${className}`}>
            <span>{value}</span>
            <ProvenanceBadge
                authority_level={authority_level}
                source_type={source_type}
                corroboration_count={corroboration_count}
            />
        </span>
    );
}
