"use client";

import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { CriticalAlerts, StatusCard } from "@/components/status-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { AssessResult } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  text: string;
  error?: boolean;
}

const SUGGESTIONS = ["How am I doing today?", "Run a check for me", "What does my last result mean?"];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "Hi! I can check your latest readings and explain your results. How are you feeling today?" },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [result, setResult] = useState<AssessResult | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Braces matter: scrollIntoView can return a Promise, which must not be returned to React.
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: message }]);
    setBusy(true);
    try {
      const r = await api.chat(message, conversationId);
      setConversationId(r.conversation_id);
      if (r.latest_result) setResult(r.latest_result);
      setMessages((m) => [...m, { role: "assistant", text: r.reply, error: r.error }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: e instanceof Error ? e.message : "The assistant is not available.", error: true },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <Card className="flex h-[70vh] flex-col py-0 hover:border-border hover:shadow-sm">
        <CardContent className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
          {messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                "flex animate-message-in items-end gap-2",
                m.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              {m.role === "assistant" && <BrandMark className="mb-0.5 size-6" />}
              <div
                className={cn(
                  "max-w-[80%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm",
                  m.role === "user"
                    ? "rounded-br-sm bg-primary text-primary-foreground"
                    : "rounded-bl-sm bg-muted",
                  m.error && "border-[#fecaca] bg-[#fee2e2] text-[#991b1b]",
                )}
              >
                {m.text}
              </div>
            </div>
          ))}
          {busy && <TypingIndicator />}
          <div ref={endRef} />
        </CardContent>
        <div className="border-t p-3">
          {messages.length === 1 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <Button
                  key={s}
                  variant="outline"
                  size="sm"
                  onClick={() => send(s)}
                  className="animate-message-in hover:-translate-y-0.5"
                  style={{ animationDelay: `${150 + SUGGESTIONS.indexOf(s) * 80}ms` }}
                >
                  {s}
                </Button>
              ))}
            </div>
          )}
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Type your message"
              rows={1}
              className="min-h-9 resize-none"
              aria-label="Message"
            />
            <Button
              type="submit"
              size="icon"
              disabled={busy || !input.trim()}
              aria-label="Send"
              className="size-9 hover:scale-105 active:scale-95"
            >
              <Send className="size-4" />
            </Button>
          </form>
        </div>
      </Card>

      <aside className="space-y-4">
        {result ? (
          <div key={result.assessed_at} className="animate-message-in space-y-4">
            <CriticalAlerts notice={result.critical_notice} alerts={result.alerts} />
            <StatusCard result={result} />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Your latest result will appear here when the assistant runs a check.</p>
        )}
      </aside>
    </div>
  );
}

/** WhatsApp-style "typing" bubble shown while the assistant works. */
function TypingIndicator() {
  return (
    <div className="flex animate-message-in items-end gap-2" role="status">
      <BrandMark className="mb-0.5 size-6" />
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm bg-muted px-3.5 py-3">
        {["bg-primary", "bg-secondary", "bg-tertiary"].map((color, i) => (
          <span
            key={color}
            className={cn("size-1.5 animate-typing-dot rounded-full", color)}
            style={{ animationDelay: `${i * 0.18}s` }}
          />
        ))}
        <span className="sr-only">The assistant is checking…</span>
      </div>
    </div>
  );
}
