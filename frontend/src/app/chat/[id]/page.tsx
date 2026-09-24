"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import ModelSelector, { type ModelOption } from "@/components/ModelSelector";
import { type Message, type Conversation, getConversation, saveConversation } from "@/lib/conversations";

/* ─────────────────────── Chat-service helpers ─────────────────────── */

async function fetchHistory(windowId: string, limit = 20): Promise<Message[]> {
  try {
    const res = await fetch(`/api/history?window_id=${windowId}&limit=${limit}`);
    if (!res.ok) return [];
    const data = await res.json();
    // chat-service returns newest-first; reverse to show oldest first
    const msgs: Array<{ role: string; content: string }> = (data.messages ?? []).reverse();
    return msgs.map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));
  } catch {
    return [];
  }
}

async function saveMessage(windowId: string, role: "user" | "assistant", content: string) {
  try {
    await fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ window_id: windowId, role, content }),
    });
  } catch {
    // fire-and-forget — don't block the UI
  }
}

/* ─────────────────────── SSE streaming helper ─────────────────────── */

async function streamChat(
  messages: Message[],
  modelId: string,
  onDelta: (delta: string) => void,
): Promise<string> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: "web-user", messages, model_id: modelId }),
  });

  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    // Accumulate chunks — SSE lines may be split across TCP packets
    buffer += decoder.decode(value, { stream: true });

    // Process all complete lines; keep incomplete tail in buffer
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (payload === "[DONE]") break;
      try {
        const parsed = JSON.parse(payload);
        if (parsed.error) throw new Error(parsed.error);
        if (parsed.delta) {
          full += parsed.delta;
          onDelta(full);
        }
      } catch (e) {
        if ((e as Error).message?.startsWith("HTTP") || (e as Error).message?.includes("Cannot reach")) throw e;
        // ignore parse errors from malformed chunks
      }
    }
  }

  // Flush any remaining buffered line
  if (buffer.startsWith("data: ")) {
    const payload = buffer.slice(6).trim();
    if (payload && payload !== "[DONE]") {
      try {
        const parsed = JSON.parse(payload);
        if (parsed.delta) { full += parsed.delta; onDelta(full); }
      } catch {}
    }
  }

  return full;
}

/* ─────────────────────── Icons ─────────────────────────────────────── */

function AsteriskLogo({ size = 20 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" aria-hidden>
      {[0, 30, 60, 90, 120, 150].map((deg) => (
        <line key={deg} x1="12" y1="3" x2="12" y2="21" stroke="rgb(191,96,69)" strokeWidth="2.2" strokeLinecap="round" transform={`rotate(${deg} 12 12)`} />
      ))}
    </svg>
  );
}
function PlusIcon() { return <svg viewBox="0 0 20 20" width="16" height="16" fill="currentColor"><path d="M10 4a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 10 4z" /></svg>; }
function SendIcon() { return <svg viewBox="0 0 20 20" width="16" height="16" fill="currentColor"><path d="M10.894 2.553a1 1 0 0 0-1.788 0l-7 14a1 1 0 0 0 1.169 1.409l5-1.429A1 1 0 0 0 9 15.571V11a1 1 0 1 1 2 0v4.571a1 1 0 0 0 .725.962l5 1.428a1 1 0 0 0 1.17-1.408l-7-14z" /></svg>; }
function ChevronDownSmIcon() { return <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" /></svg>; }
function CopyIcon() { return <svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="7" y="7" width="10" height="10" rx="2" /><path d="M3 13V4a1 1 0 0 1 1-1h9" strokeLinecap="round" /></svg>; }
function ThumbUpIcon() { return <svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M7 10l2-5a2 2 0 0 1 2 2V8h3a1 1 0 0 1 1 1.33l-2 5A1 1 0 0 1 12 15H8a1 1 0 0 1-1-1v-4zM4 15h2V10H4v5z" strokeLinejoin="round" /></svg>; }
function ThumbDownIcon() { return <svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M13 10l-2 5a2 2 0 0 1-2-2V12H6a1 1 0 0 1-1-1.33l2-5A1 1 0 0 1 8 5h4a1 1 0 0 1 1 1v4zM16 5h-2v5h2V5z" strokeLinejoin="round" /></svg>; }
function RefreshIcon() { return <svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 4v5h5M16 16v-5h-5" strokeLinecap="round" strokeLinejoin="round" /><path d="M20.49 9A9 9 0 0 0 5.64 5.64L4 4m-.49 7A9 9 0 0 0 14.36 14.36L16 16" strokeLinecap="round" /></svg>; }

/* ─────────────────────── Message bubbles ────────────────────────────── */

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end mb-6">
      <div style={{ maxWidth: "70%", backgroundColor: "rgba(31,30,29,0.06)", borderRadius: 18, padding: "10px 16px", fontSize: 15, color: "rgb(20,20,19)", fontFamily: '"Anthropic Sans", system-ui, sans-serif', lineHeight: "22px", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {content}
      </div>
    </div>
  );
}

function AssistantMessage({ content, streaming }: { content: string; streaming?: boolean }) {
  const [copied, setCopied] = useState(false);
  function copy() { navigator.clipboard.writeText(content); setCopied(true); setTimeout(() => setCopied(false), 1500); }
  return (
    <div className="mb-8">
      <div style={{ fontSize: 15, color: "rgb(20,20,19)", fontFamily: '"Anthropic Serif", Georgia, "Times New Roman", serif', lineHeight: "26px", whiteSpace: "pre-wrap", wordBreak: "break-word", maxWidth: 620 }}>
        {content}
        {streaming && <span className="inline-block w-2 h-4 bg-[rgb(20,20,19)] ml-0.5 animate-pulse" style={{ verticalAlign: "middle" }} />}
      </div>
      {!streaming && content && (
        <div className="flex items-center gap-1 mt-2">
          {[
            { icon: <CopyIcon />, label: copied ? "Copied!" : "Copy", action: copy },
            { icon: <ThumbUpIcon />, label: "Good response", action: () => {} },
            { icon: <ThumbDownIcon />, label: "Bad response", action: () => {} },
            { icon: <RefreshIcon />, label: "Regenerate", action: () => {} },
          ].map((btn) => (
            <button key={btn.label} onClick={btn.action} title={btn.label} style={{ width: 28, height: 28, borderRadius: 6, border: "none", background: "transparent", color: "rgb(115,114,108)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }} className="hover:bg-[rgba(31,30,29,0.06)] hover:text-[rgb(61,61,58)] transition-colors">
              {btn.icon}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Thinking() {
  return (
    <div className="mb-6 flex items-center gap-2">
      <div className="animate-spin" style={{ animationDuration: "2s" }}><AsteriskLogo size={18} /></div>
    </div>
  );
}

/* ─────────────────────── Page ───────────────────────────────────────── */

export default function ChatPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const id = params.id as string;

  const [conv, setConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [selectedModelId, setSelectedModelId] = useState(() =>
    typeof window !== "undefined" ? (localStorage.getItem("selected_model_id") ?? "milk-sell-bot-1") : "milk-sell-bot-1"
  );

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const initialized = useRef(false);

  /* ── Load history from chat-service (top 20), fall back to localStorage ── */
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const modelFromUrl = searchParams.get("model");
    if (modelFromUrl) {
      setSelectedModelId(modelFromUrl);
      localStorage.setItem("selected_model_id", modelFromUrl);
    }

    let conversation = getConversation(id);
    if (!conversation) {
      conversation = { id, title: "New chat", messages: [], createdAt: Date.now(), updatedAt: Date.now() };
      saveConversation(conversation);
    }
    setConv(conversation);

    // Try to load from chat-service first
    fetchHistory(id, 20).then((remoteMessages) => {
      const msgs = remoteMessages.length > 0 ? remoteMessages : conversation!.messages;
      setMessages(msgs);
      setLoadingHistory(false);

      // First message from /new
      const firstMsg = searchParams.get("first");
      if (firstMsg && msgs.length === 0) {
        doSend(firstMsg, msgs, conversation!);
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  /* ── Auto-scroll ── */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  /* ── Auto-resize textarea ── */
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, [input]);

  /* ── Core send function ── */
  const doSend = useCallback(async (text: string, currentMessages: Message[], currentConv: Conversation) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    const userMsg: Message = { role: "user", content: trimmed };
    const updatedMessages = [...currentMessages, userMsg];

    setMessages(updatedMessages);
    setInput("");
    setStreaming(true);
    setStreamingContent("");

    // Persist user message to localStorage
    const updatedConv = {
      ...currentConv,
      messages: updatedMessages,
      title: currentConv.title === "New chat" ? trimmed.slice(0, 80) : currentConv.title,
      updatedAt: Date.now(),
    };
    setConv(updatedConv);
    saveConversation(updatedConv);

    // Save user message to chat-service (fire-and-forget)
    saveMessage(id, "user", trimmed);

    let aiContent = "";
    try {
      aiContent = await streamChat(
        updatedMessages,
        selectedModelId,
        (partial) => setStreamingContent(partial),
      );
    } catch (err) {
      aiContent = `Sorry, something went wrong: ${(err as Error).message}`;
    }

    const assistantMsg: Message = { role: "assistant", content: aiContent };
    const finalMessages = [...updatedMessages, assistantMsg];

    setMessages(finalMessages);
    setStreamingContent("");
    setStreaming(false);

    // Save assistant message to chat-service (top 20 maintained by service)
    saveMessage(id, "assistant", aiContent);

    // Persist to localStorage
    setConv((prev) => {
      const updated = { ...(prev ?? updatedConv), messages: finalMessages, updatedAt: Date.now() };
      saveConversation(updated);
      return updated;
    });
  }, [id, selectedModelId]);

  function handleSend() {
    if (!input.trim() || streaming || loadingHistory) return;
    doSend(input, messages, conv ?? { id, title: "New chat", messages: [], createdAt: Date.now(), updatedAt: Date.now() });
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }

  const title = conv?.title || "New chat";

  return (
    <div className="flex h-full">
      <Sidebar />

      <div className="flex flex-col flex-1 overflow-hidden" style={{ paddingLeft: 49 }}>
        {/* Top bar */}
        <div style={{ height: 48, borderBottom: "1px solid rgba(31,30,29,0.1)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 20px", flexShrink: 0, backgroundColor: "rgb(250,249,245)" }}>
          <button style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 500, color: "rgb(61,61,58)", background: "none", border: "none", cursor: "pointer", fontFamily: '"Anthropic Sans", system-ui, sans-serif', borderRadius: 6, padding: "4px 8px" }} className="hover:bg-[rgba(31,30,29,0.06)] transition-colors">
            {title.slice(0, 40)}{title.length > 40 ? "…" : ""}
            <ChevronDownSmIcon />
          </button>
          <button style={{ fontSize: 13, fontWeight: 500, color: "rgb(61,61,58)", background: "none", border: "1px solid rgba(31,30,29,0.2)", cursor: "pointer", fontFamily: '"Anthropic Sans", system-ui, sans-serif', borderRadius: 6, padding: "4px 14px" }} className="hover:bg-[rgba(31,30,29,0.06)] transition-colors">
            Share
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto" style={{ padding: "32px 0" }}>
          <div style={{ maxWidth: 680, margin: "0 auto", padding: "0 24px" }}>
            {loadingHistory && messages.length === 0 && (
              <div className="flex justify-center py-12">
                <div className="animate-spin" style={{ animationDuration: "2s" }}><AsteriskLogo size={24} /></div>
              </div>
            )}
            {messages.map((msg, i) =>
              msg.role === "user"
                ? <UserBubble key={i} content={msg.content} />
                : <AssistantMessage key={i} content={msg.content} />
            )}
            {streaming && streamingContent === "" && <Thinking />}
            {streaming && streamingContent !== "" && <AssistantMessage content={streamingContent} streaming />}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input */}
        <div style={{ padding: "0 24px 16px", flexShrink: 0, maxWidth: 728, width: "100%", margin: "0 auto" }}>
          <div style={{ backgroundColor: "#fff", borderRadius: 20, boxShadow: "rgba(0,0,0,0.075) 0px 4px 20px 0px, rgba(31,30,29,0.3) 0px 0px 0px 0.5px", border: "1px solid transparent", padding: "12px 16px 10px" }} onClick={() => textareaRef.current?.focus()}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Reply..."
              disabled={streaming || loadingHistory}
              rows={1}
              style={{ fontSize: 16, color: "rgb(20,20,19)", fontFamily: '"Anthropic Sans", system-ui, sans-serif', lineHeight: "22.4px", resize: "none", outline: "none", border: "none", background: "transparent", width: "100%", minHeight: 22, maxHeight: 200, overflow: "auto" }}
              className="placeholder:text-[rgb(115,114,108)]"
            />
            <div className="flex items-center justify-between mt-2 pt-1">
              <button aria-label="Attach" style={{ width: 30, height: 30, borderRadius: 8, color: "rgb(115,114,108)", border: "1px solid rgba(31,30,29,0.15)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", backgroundColor: "transparent" }} className="hover:bg-[rgba(31,30,29,0.06)] transition-colors">
                <PlusIcon />
              </button>
              <div className="flex items-center gap-2">
                <ModelSelector
                  selectedId={selectedModelId}
                  onChange={(m: ModelOption) => setSelectedModelId(m.id)}
                />
                <button
                  aria-label="Send message"
                  onClick={handleSend}
                  disabled={!input.trim() || streaming || loadingHistory}
                  style={{ width: 30, height: 30, borderRadius: 8, border: "none", display: "flex", alignItems: "center", justifyContent: "center", cursor: input.trim() && !streaming ? "pointer" : "default", backgroundColor: input.trim() && !streaming ? "rgb(20,20,19)" : "rgba(31,30,29,0.1)", color: input.trim() && !streaming ? "#fff" : "rgb(115,114,108)", transition: "all 0.15s" }}
                >
                  <SendIcon />
                </button>
              </div>
            </div>
          </div>
          <p style={{ textAlign: "center", fontSize: 12, color: "rgb(115,114,108)", marginTop: 8, fontFamily: '"Anthropic Sans", system-ui, sans-serif' }}>
            Claude is AI and can make mistakes. Please double-check responses.
          </p>
        </div>
      </div>
    </div>
  );
}
