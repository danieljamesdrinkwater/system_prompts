import type { UIMessage } from "ai";
import { ValuationCard } from "./valuation-card";

interface MessageBubbleProps {
  message: UIMessage;
}

function parseValuationBlocks(text: string) {
  const parts: { type: "text" | "valuation"; content: string }[] = [];
  const regex = /:::valuation\n([\s\S]*?):::/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", content: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: "valuation", content: match[1].trim() });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push({ type: "text", content: text.slice(lastIndex) });
  }

  return parts.length > 0 ? parts : [{ type: "text" as const, content: text }];
}

function renderMarkdown(text: string) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br />");
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  // Extract images and text from message parts
  const images: string[] = [];
  const textParts: string[] = [];

  for (const part of message.parts) {
    if (part.type === "file" && part.mediaType.startsWith("image/")) {
      images.push(part.url);
    } else if (part.type === "text") {
      textParts.push(part.text);
    }
  }

  const textContent = textParts.join("");

  if (!textContent && images.length === 0) return null;

  const valuationParts = isUser
    ? [{ type: "text" as const, content: textContent }]
    : parseValuationBlocks(textContent);

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-medium ${
          isUser
            ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
            : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
        }`}
      >
        {isUser ? "You" : "AI"}
      </div>

      {/* Content */}
      <div className={`max-w-[80%] space-y-2 ${isUser ? "items-end" : ""}`}>
        {/* Images */}
        {images.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {images.map((src, i) => (
              <img
                key={i}
                src={src}
                alt="Uploaded item"
                className="max-h-64 rounded-xl object-cover"
              />
            ))}
          </div>
        )}

        {/* Text / Valuation */}
        {valuationParts.map((part, i) =>
          part.type === "valuation" ? (
            <ValuationCard key={i} content={part.content} />
          ) : part.content.trim() ? (
            <div
              key={i}
              className={`rounded-2xl px-4 py-3 shadow-sm ${
                isUser
                  ? "rounded-tr-sm bg-blue-600 text-white"
                  : "rounded-tl-sm bg-white text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
              }`}
              dangerouslySetInnerHTML={{ __html: renderMarkdown(part.content) }}
            />
          ) : null
        )}
      </div>
    </div>
  );
}
