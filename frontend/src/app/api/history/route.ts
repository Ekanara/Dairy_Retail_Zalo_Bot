/**
 * Proxy to chat-service (port 8007).
 *
 * GET  /api/history?window_id=<uuid>&limit=20  → fetch top-N messages
 * POST /api/history  { window_id, role, content, metadata? }  → save a message
 */
export const dynamic = "force-dynamic";

const CHAT_SERVICE = "http://localhost:8007";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const upstream = new URL(`${CHAT_SERVICE}/chat/messages`);
  searchParams.forEach((v, k) => upstream.searchParams.set(k, v));

  try {
    const res = await fetch(upstream.toString());
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json({ error: "chat-service unavailable" }, { status: 502 });
  }
}

export async function POST(request: Request) {
  const body = await request.json();

  try {
    const res = await fetch(`${CHAT_SERVICE}/chat/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json({ error: "chat-service unavailable" }, { status: 502 });
  }
}
