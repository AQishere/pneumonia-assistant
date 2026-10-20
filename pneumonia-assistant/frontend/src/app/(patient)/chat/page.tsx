"use client";

import { ArrowUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { PageHeader } from "@/components/app-shell";
import { BrandMark } from "@/components/brand-mark";
import { CriticalAlerts, StatusCard } from "@/components/status-card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { VITAL_INFO, VITALS } from "@/lib/bands";
import type { AssessResult, AssessmentRow, PatientStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  text: string;
  error?: boolean;
}

const SUGGESTIONS = ["How am I doing today?", "Run a check for me", "What does my last result mean?"];

export default function ChatPage() {
  const { me } = useAuth();
  const id = me!.uid!;
  const [status, setStatus] = useState<PatientStatus | null>(null);
  const [latest, setLatest] = useState<AssessmentRow | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "Hi! I can check your latest readings and explain your results. How are you feeling today?" },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [result, setResult] = useState<AssessResult | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // The side panel: latest result and readings, refreshed whenever the assistant runs a check.
  useEffect(() => {
    Promise.all([api.status(id), api.assessments(id, 1)])
      .then(([s, a]) => {
        setStatus(s);
        setLatest(a.assessments[0] ?? null);
      })
      .catch(() => {});
  }, [id, result]);

  useEffect(() => {
    // Scroll the message list only: scrollIntoView would also scroll the page and hide the header on phones.
    const list = listRef.current;
    list?.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
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
    <>
      <PageHeader title="Assistant" />
      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_400px]">
        <div
          className="flex h-[calc(100dvh-13rem)] min-h-[26rem] flex-col overflow-hidden rounded-2xl surface lg:h-[calc(100dvh-15rem)]"
        >
          <div className="flex items-center gap-3 border-b border-black/5 px-5 py-3">
            <span className="flex size-10 items-center justify-center rounded-lg border bg-card">
              <BrandMark className="size-8" />
            </span>
            <div className="leading-tight">
              <p className="font-semibold">Pneumonia Assistant</p>
              <p className="text-[13px] text-muted-foreground">{busy ? "typing…" : "Online"}</p>
            </div>
          </div>
          <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto px-4 py-5 lg:px-6" aria-live="polite">
            {messages.map((m, i) => (
              <div
                key={i}
                className={cn("flex animate-message-in items-end gap-2", m.role === "user" ? "justify-end" : "justify-start")}
              >
                {m.role === "assistant" && <ChatAvatar />}
                <div
                  className={cn(
                    "max-w-[75%] rounded-2xl px-4 py-2 text-sm leading-relaxed whitespace-pre-wrap",
                    m.role === "user" ? "rounded-br-md bg-primary text-white" : "rounded-bl-md bg-muted text-foreground",
                    m.error && "bg-[#dc2626]/10 text-[#b91c1c]",
                  )}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {busy && <TypingIndicator />}
          </div>
          <div className="border-t border-black/5 p-3">
            {messages.length === 1 && (
              <div className="mb-2.5 flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <Button
                    key={s}
                    variant="outline"
                    size="sm"
                    onClick={() => send(s)}
                    className="animate-message-in"
                    style={{ animationDelay: `${150 + SUGGESTIONS.indexOf(s) * 80}ms` }}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            )}
            <form
              className="flex items-end gap-2 rounded-lg border border-input bg-card py-1 pr-1 pl-1 shadow-xs focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/20"
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
                placeholder="Message"
                rows={1}
                className="max-h-32 min-h-9 resize-none border-0 bg-transparent py-1.5 focus-visible:border-0 focus-visible:bg-transparent focus-visible:ring-0"
                aria-label="Message"
              />
              <Button
                type="submit"
                size="icon"
                disabled={busy || !input.trim()}
                aria-label="Send"
                className="size-8 hover:scale-105 active:scale-95"
              >
                <ArrowUp className="size-[18px]" strokeWidth={2.5} />
              </Button>
            </form>
          </div>
        </div>

        <aside className="space-y-4">
          {result ? (
            <div key={result.assessed_at} className="animate-message-in space-y-4">
              <CriticalAlerts notice={result.critical_notice} alerts={result.alerts} compact />
              <StatusCard result={result} alertActive={result.alerts.length > 0} compact />
            </div>
          ) : (
            status && (
              <>
                <CriticalAlerts notice={status.critical_notice} alerts={status.alerts} compact />
                <StatusCard band={latest?.band} at={latest?.created_at} alertActive={status.alerts.length > 0} compact />
              </>
            )
          )}
          {status && (
            <div className="animate-rise rounded-2xl surface px-4 pt-4 pb-1">
              <h2 className="pb-1 text-[15px] font-semibold">Latest readings</h2>
              <ul className="divide-y">
                {VITALS.map((v) => {
                  const info = VITAL_INFO[v];
                  const r = status.latest_readings[v];
                  return (
                    <li key={v} className="flex items-center gap-3 py-2.5">
                      <info.icon className="size-4 shrink-0" style={{ color: info.color }} />
                      <span className="flex-1 text-sm">{info.label}</span>
                      <span className="text-sm font-semibold tabular-nums">
                        {r ? r.value.toFixed(info.digits) : "—"}
                        <span className="ml-1 text-xs font-normal text-muted-foreground">{info.unit}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}

/** The logo in a small white circle, next to the assistant's messages. */
function ChatAvatar() {
  return (
    <span className="mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
      <BrandMark className="size-6" />
    </span>
  );
}

/** iMessage-style "typing" bubble shown while the assistant works. */
function TypingIndicator() {
  return (
    <div className="flex animate-message-in items-end gap-2" role="status">
      <ChatAvatar />
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-md bg-muted px-4 py-3.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-2 animate-typing-dot rounded-full bg-[#64748b]"
            style={{ animationDelay: `${i * 0.18}s` }}
          />
        ))}
        <span className="sr-only">The assistant is checking…</span>
      </div>
    </div>
  );
}
