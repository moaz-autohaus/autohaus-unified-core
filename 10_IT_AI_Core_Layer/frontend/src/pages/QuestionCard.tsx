import { useState, useEffect } from "react";
import { T, type OpenQuestion, useOrchestrator } from "../contexts/OrchestratorContext";

const ROLE_COLORS: Record<string, string> = {
  SOVEREIGN: T.gold,
  STANDARD: T.blue,
  FIELD: T.green,
};

const SOURCE_LABELS: Record<string, string> = {
  CONFLICT: "Conflicting Claims",
  ASSERTION: "Invalid Assertion",
  IEA: "IEA Mismatch",
  MANUAL: "Manual Escalation",
};

function SlaTimer({ dueAt }: { dueAt: string }) {
  const [remaining, setRemaining] = useState("");
  const [urgent, setUrgent] = useState(false);

  useEffect(() => {
    const tick = () => {
      const diff = new Date(dueAt).getTime() - Date.now();
      if (diff <= 0) {
        setRemaining("OVERDUE");
        setUrgent(true);
        return;
      }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining(`${h}h ${m}m ${s}s`);
      setUrgent(diff < 3600000);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [dueAt]);

  return (
    <span style={{
      fontFamily: "monospace",
      fontSize: 12,
      color: urgent ? T.red : T.textDim,
      fontWeight: urgent ? 700 : 400,
    }}>
      {remaining}
    </span>
  );
}

export function QuestionCard({ q }: { q: OpenQuestion }) {
  const { answerQuestion, deferQuestion } = useOrchestrator();
  const roleColor = ROLE_COLORS[q.owner_role] || T.textDim;
  const resolved = q.status !== "OPEN";

  return (
    <div style={{
      background: T.elevated,
      border: `1px solid ${resolved ? T.muted : roleColor}`,
      borderRadius: 8,
      padding: 14,
      marginBottom: 10,
      opacity: resolved ? 0.5 : 1,
      transition: "opacity 0.3s ease",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{
            background: roleColor,
            color: "#000",
            fontSize: 10,
            fontWeight: 700,
            padding: "2px 8px",
            borderRadius: 4,
            textTransform: "uppercase",
            letterSpacing: 0.5,
          }}>
            {q.owner_role}
          </span>
          <span style={{
            background: T.border2,
            color: T.textDim,
            fontSize: 10,
            padding: "2px 8px",
            borderRadius: 4,
          }}>
            {SOURCE_LABELS[q.source_type] || q.source_type}
          </span>
          {resolved && (
            <span style={{
              background: q.status === "ANSWERED" ? T.green : T.dim,
              color: "#000",
              fontSize: 10,
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 4,
            }}>
              {q.status}
            </span>
          )}
        </div>
        <SlaTimer dueAt={q.due_at} />
      </div>

      <p style={{ color: T.text, fontSize: 13, lineHeight: 1.5, margin: "0 0 10px 0" }}>
        {q.content}
      </p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ color: T.dim, fontSize: 11 }}>
          {q.question_id.slice(0, 8)}… · {new Date(q.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>

        {!resolved && (
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => answerQuestion(q.question_id)}
              style={{
                background: T.green,
                color: "#000",
                border: "none",
                borderRadius: 4,
                padding: "4px 14px",
                fontSize: 11,
                fontWeight: 700,
                cursor: "pointer",
                letterSpacing: 0.3,
              }}
            >
              ANSWER
            </button>
            <button
              onClick={() => deferQuestion(q.question_id)}
              style={{
                background: "transparent",
                color: T.textDim,
                border: `1px solid ${T.border2}`,
                borderRadius: 4,
                padding: "4px 14px",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                letterSpacing: 0.3,
              }}
            >
              DEFER
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function QuestionPanel() {
  const { openQuestions } = useOrchestrator();
  const active = openQuestions.filter(q => q.status === "OPEN");
  const resolved = openQuestions.filter(q => q.status !== "OPEN");

  if (openQuestions.length === 0) return null;

  return (
    <div style={{ padding: "12px 0" }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 10,
        paddingBottom: 8,
        borderBottom: `1px solid ${T.border}`,
      }}>
        <span style={{ color: T.gold, fontSize: 13, fontWeight: 700, letterSpacing: 0.5 }}>
          OPEN QUESTIONS
        </span>
        {active.length > 0 && (
          <span style={{
            background: T.red,
            color: "#fff",
            fontSize: 10,
            fontWeight: 700,
            padding: "1px 6px",
            borderRadius: 8,
            minWidth: 16,
            textAlign: "center",
          }}>
            {active.length}
          </span>
        )}
      </div>
      {active.map(q => <QuestionCard key={q.question_id} q={q} />)}
      {resolved.map(q => <QuestionCard key={q.question_id} q={q} />)}
    </div>
  );
}
