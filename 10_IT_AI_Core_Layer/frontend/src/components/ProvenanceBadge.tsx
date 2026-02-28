import { useState } from "react";
import { Crown, ShieldCheck, Shield, FileText, Eye, HelpCircle } from "lucide-react";
import { T } from "../tokens";

export type AuthorityLevel = "SOVEREIGN" | "VERIFIED" | "AUTO_ENRICHED" | "EXTRACTED" | "PROPOSED" | "UNVERIFIED";

interface ProvenanceBadgeProps {
  authority: AuthorityLevel;
  sourceType?: string;
  corroborationCount?: number;
  size?: number;
}

const BADGE_CONFIG: Record<AuthorityLevel, { color: string; label: string; Icon: typeof Crown }> = {
  SOVEREIGN: { color: T.gold, label: "Sovereign Override", Icon: Crown },
  VERIFIED: { color: T.green, label: "Verified", Icon: ShieldCheck },
  AUTO_ENRICHED: { color: T.blue, label: "Auto-Enriched", Icon: Shield },
  EXTRACTED: { color: T.purple, label: "AI Extracted", Icon: FileText },
  PROPOSED: { color: "#eab308", label: "Proposed", Icon: Eye },
  UNVERIFIED: { color: T.dim, label: "Unverified", Icon: HelpCircle },
};

export function ProvenanceBadge({ authority, sourceType, corroborationCount, size = 14 }: ProvenanceBadgeProps) {
  const [hover, setHover] = useState(false);
  const config = BADGE_CONFIG[authority] || BADGE_CONFIG.UNVERIFIED;
  const Icon = config.Icon;

  const tooltipText = authority === "AUTO_ENRICHED" && sourceType
    ? `Verified by ${sourceType}`
    : corroborationCount && corroborationCount > 1
    ? `${config.label} · ${corroborationCount} sources`
    : config.label;

  return (
    <span
      style={{ position: "relative", display: "inline-flex", alignItems: "center", cursor: "default" }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <span style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        animation: authority === "PROPOSED" ? "pulse-dot 2s infinite" : undefined,
      }}>
        <Icon size={size} color={config.color} strokeWidth={2.2} />
      </span>

      {corroborationCount !== undefined && corroborationCount > 0 && (
        <span style={{
          position: "absolute", top: -4, right: -6,
          background: config.color, color: "#000", fontSize: 7,
          fontFamily: "monospace", fontWeight: 800, borderRadius: "50%",
          width: 12, height: 12, display: "flex", alignItems: "center", justifyContent: "center",
          lineHeight: 1,
        }}>
          {corroborationCount}
        </span>
      )}

      {hover && (
        <span style={{
          position: "absolute", bottom: "calc(100% + 6px)", left: "50%", transform: "translateX(-50%)",
          background: T.elevated, border: `1px solid ${T.border2}`, borderRadius: 4,
          padding: "3px 8px", whiteSpace: "nowrap",
          color: config.color, fontSize: 9, fontFamily: "monospace", fontWeight: 600,
          letterSpacing: "0.04em", zIndex: 1000, pointerEvents: "none",
          boxShadow: `0 4px 12px rgba(0,0,0,0.5)`,
        }}>
          {tooltipText}
        </span>
      )}
    </span>
  );
}

export function ProvenanceField({ label, value, authority, sourceType, corroborationCount }: {
  label: string;
  value: string;
  authority: AuthorityLevel;
  sourceType?: string;
  corroborationCount?: number;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "4px 0" }}>
      <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ color: T.text, fontSize: 10, fontFamily: "monospace" }}>{value}</span>
        <ProvenanceBadge authority={authority} sourceType={sourceType} corroborationCount={corroborationCount} />
      </div>
    </div>
  );
}
