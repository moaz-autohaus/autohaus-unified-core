import { T } from "../contexts/OrchestratorContext";
import { useOrchestrator } from "../contexts/OrchestratorContext";
import { StatusBar, PrimitivesBar } from "../components/StatusBar";
import { QuickCommands, StagedAttachments, Processing, AmbientLog } from "../components/ui";
import { ChatMessage } from "../components/ChatMessage";
import { FinancePlate, TwinPlate, AnomalyPlate, CollisionPlate, InventoryPlate, LogisticPlate, EmptyPlate } from "../components/plates";

export function CommandCenter({ onNavigate }: { onNavigate?: (v: string) => void }) {
  const {
    user, setUser, messages, input, setInput,
    plate, setPlate, processing, mode, setMode,
    wsState, anomalyCount, stagedFiles,
    dragOver, setDragOver, sendMessage, stageFiles,
    removeStaged, handleDrop, handleResolve, handleAnomalyDecision,
    chatRef, fileInputRef,
  } = useOrchestrator();

  const handleSend = () => sendMessage(input, stagedFiles);
  const canSend = (input.trim().length > 0 || stagedFiles.length > 0) && !processing;
  const fieldMode = mode === "FIELD" || user.role === "Logistics";

  const plateMap: Record<string, React.ReactNode> = {
    FINANCE:   <FinancePlate onClose={() => setPlate(null)} />,
    TWIN:      <TwinPlate onClose={() => setPlate(null)} />,
    ANOMALY:   <AnomalyPlate onClose={() => setPlate(null)} onDecision={handleAnomalyDecision} />,
    COLLISION: <CollisionPlate onClose={() => setPlate(null)} onResolve={handleResolve} />,
    INVENTORY: <InventoryPlate onClose={() => setPlate(null)} />,
    LOGISTICS: <LogisticPlate onClose={() => setPlate(null)} />,
  };

  return (
    <div
      style={{ display: "flex", flexDirection: "column", height: "100vh", width: "100%", background: dragOver ? `${T.gold}08` : T.bg, fontFamily: "'DM Sans', sans-serif", color: T.text, overflow: "hidden", transition: "background 0.2s" }}
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOver(false); }}
      onDrop={handleDrop}
    >

      {dragOver && (
        <div style={{ position: "fixed", inset: 0, zIndex: 9999, background: `${T.bg}cc`, backdropFilter: "blur(4px)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, pointerEvents: "none", border: `2px dashed ${T.gold}55` }}>
          <div style={{ width: 64, height: 64, borderRadius: 16, border: `2px solid ${T.gold}88`, display: "flex", alignItems: "center", justifyContent: "center", background: `${T.gold}10` }}>
            <span style={{ fontSize: 28 }}>⬆</span>
          </div>
          <p style={{ color: T.gold, fontFamily: "monospace", fontWeight: 700, fontSize: 14, letterSpacing: "0.1em" }}>DROP TO INGEST</p>
          <p style={{ color: T.goldDim, fontFamily: "monospace", fontSize: 10 }}>Intelligence Layer will analyze via Gemini</p>
        </div>
      )}

      <input ref={fileInputRef} type="file" multiple accept="image/*,video/*,.pdf,.doc,.docx,.xlsx,.csv" style={{ display: "none" }}
        onChange={e => { if (e.target.files?.length) stageFiles(e.target.files); e.target.value = ""; }} />

      <StatusBar user={user} wsState={wsState} anomalyCount={anomalyCount} mode={mode} onUserChange={setUser} onModeChange={setMode} />

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        <div style={{ width: plate ? (fieldMode ? "100%" : "40%") : "56%", display: "flex", flexDirection: "column", borderRight: `1px solid ${T.border}`, transition: "width 0.35s cubic-bezier(0.4,0,0.2,1)", minWidth: 300 }}>

          <QuickCommands onSend={(cmd) => sendMessage(cmd)} user={user} onNavigate={onNavigate} />

          <div ref={chatRef} style={{ flex: 1, overflowY: "auto", padding: "20px 18px" }}>
            {mode === "AMBIENT" ? (
              <AmbientLog />
            ) : (
              <>
                {messages.map((msg, i) => (
                  <ChatMessage key={msg.id} msg={msg} isLatest={i === messages.length - 1 && msg.isBot} user={user} />
                ))}
                {processing && <Processing hasMedia={stagedFiles.length > 0} />}
              </>
            )}
          </div>

          <StagedAttachments files={stagedFiles} onRemove={removeStaged} />

          <div style={{ padding: "10px 16px 14px", borderTop: stagedFiles.length ? "none" : `1px solid ${T.border}`, background: T.surface, display: "flex", gap: 8, alignItems: "flex-end" }}>
            <button onClick={() => fileInputRef.current?.click()} title="Attach file or photo"
              style={{ width: 36, height: 36, background: "transparent", border: `1px solid ${T.border2}`, borderRadius: 8, color: T.dim, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 16, transition: "all 0.15s" }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = T.gold; e.currentTarget.style.color = T.gold; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = T.border2; e.currentTarget.style.color = T.dim; }}>
              ⊕
            </button>
            <div style={{ flex: 1, position: "relative" }}>
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                placeholder={stagedFiles.length ? `Add context for ${stagedFiles.length} file${stagedFiles.length > 1 ? "s" : ""}, or send now...` : `Command the CIL, ${user.name}...`}
                rows={1}
                style={{
                  width: "100%", background: T.elevated, border: `1px solid ${T.border2}`,
                  borderRadius: 8, padding: "10px 12px", color: T.text, fontSize: 12,
                  fontFamily: "monospace", outline: "none", resize: "none",
                  lineHeight: 1.5, boxSizing: "border-box", transition: "border-color 0.15s",
                }}
                onFocus={e => e.target.style.borderColor = T.gold + "66"}
                onBlur={e => e.target.style.borderColor = T.border2}
              />
            </div>
            <button onClick={handleSend} disabled={!canSend} style={{
              width: 38, height: 38,
              background: canSend ? (stagedFiles.length ? `${T.gold}25` : `${T.gold}18`) : T.elevated,
              border: `1px solid ${canSend ? T.gold + "66" : T.border}`,
              color: canSend ? T.gold : T.dim, borderRadius: 8,
              cursor: canSend ? "pointer" : "not-allowed",
              fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all 0.2s", flexShrink: 0
            }}>→</button>
          </div>
        </div>

        {(!fieldMode || !plate) && (
          <div style={{ flex: 1, background: T.surface, overflow: "hidden", position: "relative", display: "flex", flexDirection: "column" }}>
            {!plate && (
              <div style={{ position: "absolute", top: 14, right: 16, display: "flex", alignItems: "center", gap: 6, zIndex: 10 }}>
                <div style={{ width: 4, height: 4, borderRadius: "50%", background: T.muted }} />
                <span style={{ color: T.muted, fontSize: 9, fontFamily: "monospace", letterSpacing: "0.1em" }}>JIT HYDRATION CANVAS · AWAITING MOUNT_PLATE</span>
              </div>
            )}
            {plate ? (
              <div style={{ flex: 1, overflow: "hidden", animation: "plate-in 0.3s cubic-bezier(0.4,0,0.2,1)" }}>
                {plateMap[plate]}
              </div>
            ) : (
              <EmptyPlate />
            )}
          </div>
        )}

        {fieldMode && plate && (
          <div style={{ position: "fixed", inset: 0, background: T.bg, zIndex: 200, display: "flex", flexDirection: "column", animation: "plate-in 0.3s ease" }}>
            <div style={{ flex: 1, overflow: "hidden" }}>{plateMap[plate]}</div>
            <button onClick={() => setPlate(null)} style={{ margin: 16, padding: 12, background: T.elevated, border: `1px solid ${T.border2}`, color: T.textDim, borderRadius: 8, fontFamily: "monospace", fontSize: 12, cursor: "pointer" }}>← BACK TO CONVERSATION</button>
          </div>
        )}
      </div>

      <PrimitivesBar />

    </div>
  );
}
