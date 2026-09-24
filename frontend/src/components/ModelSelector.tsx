"use client";

import { useEffect, useRef, useState } from "react";

export type ModelOption = {
  id: string;
  name: string;
  description?: string;
  api_url: string;
};

/* ── Icons ───────────────────────────────────────────────── */
function ChevronDownIcon() {
  return (
    <svg viewBox="0 0 12 12" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M3 8l3.5 3.5L13 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ModelIcon() {
  return (
    <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 6v4l2.5 2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ── Props ───────────────────────────────────────────────── */
type Props = {
  selectedId: string;
  onChange: (model: ModelOption) => void;
};

const STORAGE_KEY = "selected_model_id";

/* ── Component ───────────────────────────────────────────── */
export default function ModelSelector({ selectedId, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<ModelOption[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  /* Load models from API */
  useEffect(() => {
    fetch("/api/models")
      .then((r) => r.json())
      .then((data: ModelOption[]) => setModels(data))
      .catch(() => {});
  }, []);

  /* Close on outside click */
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selected = models.find((m) => m.id === selectedId) ?? models[0];

  function select(model: ModelOption) {
    localStorage.setItem(STORAGE_KEY, model.id);
    onChange(model);
    setOpen(false);
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 5,
          fontSize: 13,
          color: "rgb(115, 114, 108)",
          padding: "4px 8px",
          borderRadius: 6,
          border: "none",
          backgroundColor: open ? "rgba(31,30,29,0.08)" : "transparent",
          cursor: "pointer",
          fontFamily: '"Anthropic Sans", system-ui, sans-serif',
          whiteSpace: "nowrap",
          maxWidth: 180,
        }}
        className="hover:bg-[rgba(31,30,29,0.06)] transition-colors"
      >
        <ModelIcon />
        <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
          {selected?.name ?? "Select model"}
        </span>
        <ChevronDownIcon />
      </button>

      {/* Dropdown */}
      {open && models.length > 0 && (
        <div
          style={{
            position: "absolute",
            bottom: "calc(100% + 8px)",
            right: 0,
            minWidth: 260,
            backgroundColor: "#fff",
            borderRadius: 12,
            boxShadow: "0 4px 24px rgba(0,0,0,0.12), 0 0 0 1px rgba(31,30,29,0.1)",
            overflow: "hidden",
            zIndex: 100,
          }}
        >
          <div style={{ padding: "6px 10px 4px", fontSize: 11, fontWeight: 600, color: "rgb(115,114,108)", textTransform: "uppercase", letterSpacing: "0.06em", fontFamily: '"Anthropic Sans", system-ui, sans-serif' }}>
            Models
          </div>

          {models.map((model) => {
            const active = model.id === selected?.id;
            return (
              <button
                key={model.id}
                onClick={() => select(model)}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: 12,
                  width: "100%",
                  padding: "10px 14px",
                  border: "none",
                  background: active ? "rgba(31,30,29,0.05)" : "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                }}
                className="hover:bg-[rgba(31,30,29,0.04)] transition-colors"
              >
                <div>
                  <div style={{ fontSize: 14, fontWeight: active ? 500 : 400, color: "rgb(20,20,19)", fontFamily: '"Anthropic Sans", system-ui, sans-serif', lineHeight: "20px" }}>
                    {model.name}
                  </div>
                  {model.description && (
                    <div style={{ fontSize: 12, color: "rgb(115,114,108)", fontFamily: '"Anthropic Sans", system-ui, sans-serif', marginTop: 2, lineHeight: "16px" }}>
                      {model.description}
                    </div>
                  )}
                </div>
                {active && (
                  <span style={{ color: "rgb(61,61,58)", flexShrink: 0, marginTop: 2 }}>
                    <CheckIcon />
                  </span>
                )}
              </button>
            );
          })}

          <div style={{ borderTop: "1px solid rgba(31,30,29,0.08)", padding: "8px 14px" }}>
            <p style={{ fontSize: 11, color: "rgb(115,114,108)", margin: 0, fontFamily: '"Anthropic Sans", system-ui, sans-serif', lineHeight: "16px" }}>
              Edit <code style={{ fontFamily: "monospace", background: "rgba(31,30,29,0.06)", padding: "1px 4px", borderRadius: 3 }}>config/models.yaml</code> to add more models.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
