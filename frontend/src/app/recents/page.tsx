"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import { type Conversation, getConversations, formatRelativeTime } from "@/lib/conversations";

function PlusIcon() {
  return <svg viewBox="0 0 20 20" width="14" height="14" fill="currentColor" aria-hidden><path d="M10 4a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 10 4z" /></svg>;
}

function SearchIcon() {
  return <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden><circle cx="8.5" cy="8.5" r="5.5" /><path d="M15 15l-3-3" strokeLinecap="round" /></svg>;
}

export default function RecentsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    setConversations(getConversations());
  }, []);

  const filtered = conversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="flex-1 overflow-y-auto" style={{ paddingLeft: 49 }}>
        <div className="mx-auto" style={{ maxWidth: 960, padding: "32px 32px 64px" }}>
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h1 style={{ fontFamily: '"Anthropic Serif", Georgia, "Times New Roman", serif', fontSize: 24, fontWeight: 500, color: "rgb(61,61,58)", lineHeight: "31.2px", margin: 0 }}>
              Chats
            </h1>
            <Link href="/new" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 500, color: "rgb(250,249,245)", backgroundColor: "rgb(20,20,19)", padding: "7px 14px", borderRadius: 8, textDecoration: "none", fontFamily: '"Anthropic Sans", system-ui, sans-serif' }} className="hover:opacity-90 transition-opacity">
              <PlusIcon /> New chat
            </Link>
          </div>

          {/* Search */}
          <div className="relative mb-4">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "rgb(115,114,108)" }}>
              <SearchIcon />
            </span>
            <input
              type="search"
              placeholder="Search your chats..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: "100%", height: 44, paddingLeft: 38, paddingRight: 16, fontSize: 15, color: "rgb(20,20,19)", backgroundColor: "#fff", border: "1.5px solid rgba(31,30,29,0.2)", borderRadius: 10, outline: "none", fontFamily: '"Anthropic Sans", system-ui, sans-serif' }}
              className="focus:border-blue-400 focus:shadow-[0_0_0_3px_rgba(120,187,241,0.2)] transition-all"
            />
          </div>

          {/* Sub-header */}
          <div className="flex items-center gap-3 mb-2">
            <span style={{ fontSize: 14, color: "rgb(115,114,108)", fontFamily: '"Anthropic Sans", system-ui, sans-serif' }}>
              Your chats with Claude
            </span>
            <button style={{ fontSize: 14, color: "rgb(91,145,209)", background: "none", border: "none", cursor: "pointer", padding: 0, fontFamily: '"Anthropic Sans", system-ui, sans-serif' }}>
              Select
            </button>
          </div>

          {/* List */}
          {filtered.length === 0 ? (
            <div style={{ textAlign: "center", padding: "48px 0", color: "rgb(115,114,108)", fontSize: 15, fontFamily: '"Anthropic Sans", system-ui, sans-serif' }}>
              {search ? "No chats match your search." : "No conversations yet. Start a new chat!"}
            </div>
          ) : (
            <div style={{ border: "1px solid rgba(31,30,29,0.12)", borderRadius: 10, overflow: "hidden", backgroundColor: "#fff" }}>
              {filtered.map((conv, idx) => (
                <Link
                  key={conv.id}
                  href={`/chat/${conv.id}`}
                  style={{ display: "block", padding: "12px 16px", borderBottom: idx < filtered.length - 1 ? "1px solid rgba(31,30,29,0.08)" : "none", textDecoration: "none", backgroundColor: "transparent" }}
                  className="hover:bg-[rgba(31,30,29,0.03)] transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span style={{ fontSize: 15, fontWeight: 430, color: "rgb(20,20,19)", fontFamily: '"Anthropic Sans", system-ui, sans-serif', lineHeight: "22px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {conv.title || "Untitled chat"}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, color: "rgb(115,114,108)", marginTop: 2, fontFamily: '"Anthropic Sans", system-ui, sans-serif' }}>
                    Last message {formatRelativeTime(conv.updatedAt)}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
