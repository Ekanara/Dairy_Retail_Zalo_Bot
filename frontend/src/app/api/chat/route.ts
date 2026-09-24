import { getDefaultModel, getModel } from "@/lib/models";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = await request.json();

  // model_id sent by the client; fall back to the first model in config
  const model =
    (body.model_id ? getModel(body.model_id) : null) ?? getDefaultModel();

  // Strip model_id before forwarding — upstream doesn't know about it
  const { model_id: _ignored, ...upstream_body } = body;

  let res: Response;
  try {
    res = await fetch(model.api_url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(upstream_body),
    });
  } catch {
    return new Response(
      'data: {"error":"Cannot reach AI service: ' + model.name + '"}\ndata: [DONE]\n\n',
      { status: 502, headers: { "Content-Type": "text/event-stream" } }
    );
  }

  if (!res.ok) {
    const text = await res.text();
    return new Response(
      `data: {"error":"${text.slice(0, 200)}"}\ndata: [DONE]\n\n`,
      { status: res.status, headers: { "Content-Type": "text/event-stream" } }
    );
  }

  return new Response(res.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
