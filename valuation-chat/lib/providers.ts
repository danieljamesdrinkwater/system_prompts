import { anthropic } from "@ai-sdk/anthropic";
import { openai } from "@ai-sdk/openai";
import { google } from "@ai-sdk/google";

export const providers = {
  anthropic: () => anthropic("claude-sonnet-4-20250514"),
  openai: () => openai("gpt-4o"),
  google: () => google("gemini-2.5-flash-preview-04-17"),
} as const;

export type ProviderId = keyof typeof providers;

export const providerLabels: Record<ProviderId, string> = {
  anthropic: "Claude",
  openai: "GPT-4o",
  google: "Gemini",
};
