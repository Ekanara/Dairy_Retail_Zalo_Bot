import { getModels } from "@/lib/models";

export const dynamic = "force-dynamic";

export async function GET() {
  const models = getModels();
  return Response.json(models);
}
