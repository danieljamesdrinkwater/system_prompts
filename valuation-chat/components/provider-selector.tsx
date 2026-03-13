"use client";

import type { ProviderId } from "@/lib/providers";
import { providerLabels } from "@/lib/providers";

interface ProviderSelectorProps {
  value: ProviderId;
  onChange: (provider: ProviderId) => void;
}

const providerIds: ProviderId[] = ["anthropic", "openai", "google"];

export function ProviderSelector({ value, onChange }: ProviderSelectorProps) {
  return (
    <div className="flex gap-1 rounded-lg bg-zinc-100 p-1 dark:bg-zinc-800">
      {providerIds.map((id) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
            value === id
              ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
              : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          }`}
        >
          {providerLabels[id]}
        </button>
      ))}
    </div>
  );
}
