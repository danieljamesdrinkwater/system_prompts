import { streamText } from "ai";
import { providers, type ProviderId } from "@/lib/providers";
import { tools } from "@/lib/tools";
import { systemPrompt } from "@/lib/system-prompt";

export async function POST(req: Request) {
  const { messages, provider = "anthropic" } = await req.json();

  const getModel = providers[provider as ProviderId];
  if (!getModel) {
    return new Response("Invalid provider", { status: 400 });
  }

  const result = streamText({
    model: getModel(),
    system: systemPrompt,
    messages,
    tools,
  });

  return result.toUIMessageStreamResponse();
}
