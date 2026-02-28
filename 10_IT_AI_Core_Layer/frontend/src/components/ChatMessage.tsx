import { T, useTyping } from "../contexts/OrchestratorContext";
import type { ChatMessage as ChatMsg } from "../contexts/OrchestratorContext";
import type { User } from "../contexts/OrchestratorContext";
import { Tag, AttachmentBubble, FindingsCard } from "./ui";

export function ChatMessage({ msg, isLatest, user }: { msg: ChatMsg; isLatest: boolean; user: User }) {
  const isBot = msg.isBot;
  const textToType = msg.text || "";
  const { displayed } = useTyping(textToType, 12, isBot && isLatest);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: isBot ? "flex-start" : "flex-end", marginBottom: 20, animation: "msg-in 0.25s ease" }}>
      {isBot && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <div style={{ width: 22, height: 22, borderRadius: "50%", background: `${T.gold}18`, border: `1px solid ${T.gold}44`, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ fontSize: 7, color: T.gold, fontFamily: "monospace", fontWeight: 700 }}>CIL</span>
          </div>
          <span style={{ color: T.dim, fontSize: 10, fontFamily: "monospace" }}>Chief of Staff</span>
          {msg.intent && (
            <div style={{ display: "flex", gap: 4 }}>
              <Tag label={msg.intent} color={T.blue} />
              <Tag label={msg.entity || ""} color={T.goldDim} />
              {msg.confidence && <Tag label={`${msg.confidence}%`} color={T.green} />}
            </div>
          )}
        </div>
      )}
      {!isBot && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
          <span style={{ color: T.dim, fontSize: 10, fontFamily: "monospace" }}>{user.name} · {user.role}</span>
          <Tag label={user.access} color={user.access === "SOVEREIGN" ? T.gold : T.blue} />
        </div>
      )}
      <div style={{
        maxWidth: "88%", padding: msg.attachments?.length && !msg.text ? "8px" : "10px 14px",
        borderRadius: isBot ? "3px 12px 12px 12px" : "12px 3px 12px 12px",
        background: isBot ? T.elevated : `${T.gold}15`,
        border: `1px solid ${isBot ? T.border2 : T.gold + "44"}`,
        color: T.text, fontSize: 12, lineHeight: 1.65, fontFamily: "'DM Sans', sans-serif",
      }}>
        {msg.attachments?.map((f, i) => <AttachmentBubble key={i} file={f} />)}
        {msg.text && (
          <div style={{ marginTop: msg.attachments?.length ? 8 : 0 }}>
            {isBot && isLatest ? displayed : msg.text}
            {isBot && isLatest && displayed.length < textToType.length && (
              <span style={{ display: "inline-block", width: 2, height: 12, background: T.gold, marginLeft: 2, animation: "blink 1s infinite", verticalAlign: "middle" }} />
            )}
          </div>
        )}
        {msg.findings && <FindingsCard findings={msg.findings} />}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
        <span style={{ color: T.muted, fontSize: 9, fontFamily: "monospace" }}>{msg.time}</span>
        {isBot && <div style={{ display: "flex", alignItems: "center", gap: 3, color: T.muted, fontSize: 9, fontFamily: "monospace" }}>
          <span style={{ color: T.green }}>✓</span> LEDGER
        </div>}
      </div>
    </div>
  );
}
