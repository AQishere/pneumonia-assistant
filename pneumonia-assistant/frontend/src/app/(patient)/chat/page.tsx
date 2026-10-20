"use client";

import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

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
      <Card className="flex h-[70vh] flex-col py-0">
        <CardContent className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
          {messages.map((m, i) => (
            <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
              <div
                className={cn(
                  "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm",
                  m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted",
                  m.error && "bg-destructive/10 text-destructive",
                )}
              >
                {m.text}
              </div>
            </div>
          ))}
          {busy && <p className="text-sm text-muted-foreground">The assistant is checking…</p>}
          <div ref={endRef} />
        </CardContent>
        <div className="border-t p-3">
          {messages.length === 1 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <Button key={s} variant="outline" size="sm" onClick={() => send(s)}>
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
              className="min-h-10 resize-none"
              aria-label="Message"
            />
            <Button type="submit" disabled={busy || !input.trim()} aria-label="Send">
              <Send className="size-4" />
            </Button>
          </form>
        </div>
      </Card>

      <aside className="space-y-4">
        {result ? (
          <>
            <CriticalAlerts notice={result.critical_notice} alerts={result.alerts} />
            <StatusCard result={result} />
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Your latest result will appear here when the assistant runs a check.</p>
        )}
      </aside>
    </div>
  );
}
