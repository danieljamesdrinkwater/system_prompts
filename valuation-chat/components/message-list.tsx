import type { UIMessage } from "ai";
import { MessageBubble } from "./message-bubble";

interface MessageListProps {
  messages: UIMessage[];
  isLoading: boolean;
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {isLoading && messages[messages.length - 1]?.role === "user" && (
        <div className="flex gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-sm font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            AI
          </div>
          <div className="rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm dark:bg-zinc-800">
            <div className="flex gap-1">
              <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-400 [animation-delay:0ms]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-400 [animation-delay:150ms]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-400 [animation-delay:300ms]" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
