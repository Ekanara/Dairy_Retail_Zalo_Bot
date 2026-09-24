"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/* ── Icon primitives ─────────────────────────────────────── */

function ClaudeAsterisk() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden>
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

function SidebarToggleIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="currentColor" aria-hidden>
      <path d="M16.5 4A1.5 1.5 0 0 1 18 5.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 2 14.5v-9A1.5 1.5 0 0 1 3.5 4zM7 15h9.5a.5.5 0 0 0 .5-.5v-9a.5.5 0 0 0-.5-.5H7zM3.5 5a.5.5 0 0 0-.5.5v9a.5.5 0 0 0 .5.5H6V5z" />
    </svg>
  );
}

function NewChatIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="currentColor" aria-hidden>
      <path d="M10 3a.75.75 0 0 1 .75.75v5.5h5.5a.75.75 0 0 1 .077 1.496l-.077.004h-5.5v5.5a.75.75 0 0 1-1.5 0v-5.5h-5.5a.75.75 0 0 1 0-1.5h5.5v-5.5A.75.75 0 0 1 10 3" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <circle cx="8.5" cy="8.5" r="5.5" />
      <path d="M15 15l-3-3" strokeLinecap="round" />
    </svg>
  );
}

function StarIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M10 2l2.09 4.26L17 7.27l-3.5 3.41.83 4.82L10 13.27l-4.33 2.23.83-4.82L3 7.27l4.91-.71L10 2z" strokeLinejoin="round" />
    </svg>
  );
}

function ChatsIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M4 4h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H6l-3 2V5a1 1 0 0 1 1-1z" strokeLinejoin="round" />
    </svg>
  );
}

function ProjectsIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M3 6a1 1 0 0 1 1-1h4l2 2h6a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6z" strokeLinejoin="round" />
    </svg>
  );
}

function IntegrationsIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <rect x="3" y="3" width="5" height="5" rx="1" />
      <rect x="12" y="3" width="5" height="5" rx="1" />
      <rect x="3" y="12" width="5" height="5" rx="1" />
      <rect x="12" y="12" width="5" height="5" rx="1" />
    </svg>
  );
}

function CodeIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M7 6L3 10l4 4M13 6l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M10 3v9M6.5 8.5L10 12l3.5-3.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 15h12" strokeLinecap="round" />
    </svg>
  );
}

/* ── Sidebar component ───────────────────────────────────── */

type NavItem = {
  label: string;
  href: string;
  icon: React.ReactNode;
};

const topNav: NavItem[] = [
  { label: "Open sidebar", href: "#", icon: <SidebarToggleIcon /> },
  { label: "New chat", href: "/new", icon: <NewChatIcon /> },
  { label: "Search", href: "#", icon: <SearchIcon /> },
  { label: "Starred", href: "#", icon: <StarIcon /> },
  { label: "Recents", href: "/recents", icon: <ChatsIcon /> },
  { label: "Projects", href: "#", icon: <ProjectsIcon /> },
  { label: "Integrations", href: "#", icon: <IntegrationsIcon /> },
  { label: "Code", href: "#", icon: <CodeIcon /> },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <nav
      style={{
        width: 49,
        borderRight: "1px solid rgba(31, 30, 29, 0.15)",
        backgroundColor: "rgb(250, 249, 245)",
      }}
      className="fixed left-0 top-0 h-screen flex flex-col z-50 overflow-hidden"
    >
      {/* Logo */}
      <div className="flex items-center justify-center h-12 shrink-0">
        <Link href="/new" aria-label="Home" className="flex items-center justify-center opacity-90 hover:opacity-100 transition-opacity">
          <ClaudeAsterisk />
        </Link>
      </div>

      {/* Top icons */}
      <div className="flex flex-col items-center gap-0.5 px-1.5 flex-1">
        {topNav.map((item) => {
          const isActive =
            (item.href === "/new" && pathname === "/new") ||
            (item.href === "/recents" && pathname === "/recents");
          return (
            <Link
              key={item.label}
              href={item.href}
              aria-label={item.label}
              title={item.label}
              style={{
                color: isActive ? "rgb(20, 20, 19)" : "rgb(115, 114, 108)",
                backgroundColor: isActive ? "rgba(31, 30, 29, 0.08)" : "transparent",
                borderRadius: 8,
                width: 32,
                height: 32,
              }}
              className="flex items-center justify-center hover:bg-[rgba(31,30,29,0.06)] hover:text-[rgb(20,20,19)] transition-colors shrink-0"
            >
              {item.icon}
            </Link>
          );
        })}
      </div>

      {/* Bottom: update indicator + avatar */}
      <div className="flex flex-col items-center gap-2 pb-3 shrink-0">
        <button
          aria-label="Updates"
          style={{ color: "rgb(115, 114, 108)", borderRadius: 8, width: 32, height: 32 }}
          className="flex items-center justify-center relative hover:bg-[rgba(31,30,29,0.06)] hover:text-[rgb(20,20,19)] transition-colors"
        >
          <DownloadIcon />
          <span
            className="absolute top-1 right-1 w-2 h-2 rounded-full bg-blue-500"
            style={{ top: 6, right: 6 }}
          />
        </button>
        <button
          aria-label="User menu"
          style={{
            width: 28,
            height: 28,
            borderRadius: "50%",
            backgroundColor: "rgb(61, 61, 58)",
            color: "#fff",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: "0.02em",
          }}
          className="flex items-center justify-center shrink-0"
        >
          NN
        </button>
      </div>
    </nav>
  );
}
