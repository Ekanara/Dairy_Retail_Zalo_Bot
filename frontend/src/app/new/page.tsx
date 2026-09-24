"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import ModelSelector, { type ModelOption } from "@/components/ModelSelector";
import { createConversation } from "@/lib/conversations";

const STORAGE_KEY = "selected_model_id";

function AsteriskLogo() {
  return (
    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" aria-hidden>
      {[0, 30, 60, 90, 120, 150].map((deg) => (
        <line
          key={deg}
          x1="12" y1="3" x2="12" y2="21"
          stroke="rgb(191, 96, 69)"
          strokeWidth="2.2"
          strokeLinecap="round"
          transform={`rotate(${deg} 12 12)`}
        />
      ))}
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="currentColor" aria-hidden>
      <path d="M10 4a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 10 4z" />
    </svg>
  );
}

function VoiceIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" strokeLinecap="round" />
      <line x1="12" y1="17" x2="12" y2="22" strokeLinecap="round" />
      <line x1="9" y1="22" x2="15" y2="22" strokeLinecap="round" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg viewBox="0 0 12 12" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CodePillIcon() {
  return <svg viewBox="0 0 256 256" width="14" height="14" fill="currentColor" aria-hidden><path d="M69.12,94.15,28.5,128l40.62,33.85a8,8,0,1,1-10.24,12.29l-48-40a8,8,0,0,1,0-12.29l48-40a8,8,0,0,1,10.24,12.3Zm176,27.7-48-40a8,8,0,1,0-10.24,12.3L227.5,128l-40.62,33.85a8,8,0,1,0,10.24,12.29l48-40a8,8,0,0,0,0-12.29ZM162.73,32.48a8,8,0,0,0-10.25,4.79l-64,176a8,8,0,0,0,4.79,10.26A8.14,8.14,0,0,0,96,224a8,8,0,0,0,7.52-5.27l64-176A8,8,0,0,0,162.73,32.48Z" /></svg>;
}
function LearnPillIcon() {
  return <svg viewBox="0 0 256 256" width="14" height="14" fill="currentColor" aria-hidden><path d="M240,120a48.05,48.05,0,0,0-48-48H152V64a8,8,0,0,0-8-8H64a8,8,0,0,0-8,8V200a8,8,0,0,0,16,0V128h64v8a8,8,0,0,0,8,8h48A48.05,48.05,0,0,0,240,120ZM192,128H152V88h40a32,32,0,0,1,0,64Z" /></svg>;
}
function WritePillIcon() {
  return <svg viewBox="0 0 256 256" width="14" height="14" fill="currentColor" aria-hidden><path d="M224,160a8,8,0,0,1-8,8H152a8,8,0,0,1,0-16h64A8,8,0,0,1,224,160ZM216,96H152a8,8,0,0,0,0,16h64a8,8,0,0,0,0-16ZM64,200H40a8,8,0,0,0,0,16H64a8,8,0,0,0,0-16ZM40,64H216a8,8,0,0,0,0-16H40a8,8,0,0,0,0,16ZM40,128H216a8,8,0,0,0,0-16H40a8,8,0,0,0,0,16Z" /></svg>;
}
function LifePillIcon() {
  return <svg viewBox="0 0 256 256" width="14" height="14" fill="currentColor" aria-hidden><path d="M128,24A104,104,0,1,0,232,128,104.11,104.11,0,0,0,128,24Zm0,192a88,88,0,1,1,88-88A88.1,88.1,0,0,1,128,216Zm56-88a56,56,0,1,1-56-56A56.06,56.06,0,0,1,184,128Zm-16,0a40,40,0,1,0-40,40A40,40,0,0,0,168,128Z" /></svg>;
}
function ClaudeChoiceIcon() {
  return <svg viewBox="0 0 256 256" width="14" height="14" fill="currentColor" aria-hidden><path d="M176,232a8,8,0,0,1-8,8H88a8,8,0,0,1,0-16h80A8,8,0,0,1,176,232Zm40-128a87.55,87.55,0,0,1-33.64,69.21A16.24,16.24,0,0,0,176,186v6a16,16,0,0,1-16,16H96a16,16,0,0,1-16-16v-6a16,16,0,0,0-6.23-12.66A87.59,87.59,0,0,1,40,104.49C39.74,56.83,78.26,17.14,125.88,16A88,88,0,0,1,216,104Z" /></svg>;
}

const pills = [
  { label: "Code", icon: <CodePillIcon /> },
  { label: "Learn", icon: <LearnPillIcon /> },
  { label: "Write", icon: <WritePillIcon /> },
  { label: "Life stuff", icon: <LifePillIcon /> },
  { label: "Claude's choice", icon: <ClaudeChoiceIcon /> },
];

export default function NewPage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("milk-sell-bot-1");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) setSelectedModelId(saved);
  }, []);

  function submit(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return;
    const conv = createConversation(trimmed);
    router.push(`/chat/${conv.id}?first=${encodeURIComponent(trimmed)}&model=${selectedModelId}`);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(text);
    }
  }

  function handlePill(label: string) {
    setText(label);
    textareaRef.current?.focus();
  }

  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="flex-1 flex flex-col items-center justify-center" style={{ paddingLeft: 49 }}>
        <div className="flex flex-col items-center gap-7 w-full" style={{ maxWidth: 672 }}>
          {/* Greeting */}
          <div className="flex items-center gap-2">
            <AsteriskLogo />
            <span style={{ fontFamily: '"Anthropic Serif", Georgia, "Times New Roman", serif', fontSize: 32, fontWeight: 500, color: "rgb(20,20,19)", lineHeight: 1.2 }}>
              Good evening, Nguyễn Nhật Trường
            </span>
          </div>

          {/* Input box */}
          <div
            className="w-full flex flex-col cursor-text"
            style={{ backgroundColor: "#fff", borderRadius: 20, boxShadow: "rgba(0,0,0,0.075) 0px 4px 20px 0px, rgba(31,30,29,0.3) 0px 0px 0px 0.5px", border: "1px solid transparent", minHeight: 120, padding: "12px 16px 10px" }}
            onClick={() => textareaRef.current?.focus()}
          >
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="How can I help you today?"
              rows={1}
              style={{ fontSize: 16, color: "rgb(20,20,19)", fontFamily: '"Anthropic Sans", system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif', lineHeight: "22.4px", resize: "none", outline: "none", border: "none", background: "transparent", width: "100%", minHeight: 44 }}
              className="placeholder:text-[rgb(115,114,108)]"
            />
            <div className="flex items-center justify-between mt-auto pt-2">
              <button aria-label="Attach files" style={{ width: 30, height: 30, borderRadius: 8, color: "rgb(115,114,108)", border: "1px solid rgba(31,30,29,0.15)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", backgroundColor: "transparent" }} className="hover:bg-[rgba(31,30,29,0.06)] transition-colors">
                <PlusIcon />
              </button>
              <div className="flex items-center gap-2">
                <ModelSelector
                  selectedId={selectedModelId}
                  onChange={(m: ModelOption) => setSelectedModelId(m.id)}
                />
                <button
                  aria-label="Send"
                  onClick={() => submit(text)}
                  disabled={!text.trim()}
                  style={{ width: 30, height: 30, borderRadius: 8, color: text.trim() ? "rgb(20,20,19)" : "rgb(115,114,108)", border: "none", display: "flex", alignItems: "center", justifyContent: "center", cursor: text.trim() ? "pointer" : "default", backgroundColor: "transparent" }}
                  className="hover:bg-[rgba(31,30,29,0.06)] transition-colors"
                >
                  <VoiceIcon />
                </button>
              </div>
            </div>
          </div>

          {/* Pills */}
          <div className="flex items-center gap-2 flex-wrap justify-center">
            {pills.map((pill) => (
              <button key={pill.label} onClick={() => handlePill(pill.label)} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, color: "rgb(61,61,58)", padding: "5px 12px", borderRadius: 8, border: "1px solid rgba(31,30,29,0.15)", backgroundColor: "rgb(250,249,245)", cursor: "pointer", fontFamily: '"Anthropic Sans", system-ui, sans-serif', lineHeight: "20px", height: 32 }} className="hover:bg-[rgba(31,30,29,0.06)] transition-colors">
                {pill.icon}{pill.label}
              </button>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
