import { useState, useEffect, useRef } from "react";
import { Send, Sparkles, User } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api";
import { PageHeader, Spinner } from "@/components/kit";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "What's the single most important thing today?",
  "How many months of runway do we really have?",
  "Which decision should I make first and why?",
  "Where is my team over capacity?",
];

export default function AskHelm() {
  const { data: history } = useFetch("/ask/history");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (history?.messages) setMessages(history.messages.map((m) => ({ role: m.role, content: m.content })));
  }, [history]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming]);

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "" }]);
    setStreaming(true);
    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message: q }),
      });
      if (res.status === 403) {
        setMessages((m) => m.slice(0, -2));
        setStreaming(false);
        navigate("/app/billing");
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += decoder.decode(value, { stream: true });
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { role: "assistant", content: acc };
          return copy;
        });
      }
    } catch (e) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: "I couldn't reach my reasoning engine. Please try again." };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] lg:h-[calc(100vh-6rem)]">
      <PageHeader title="Ask Helm" subtitle="Your executive AI chief-of-staff — grounded in your live company data." />

      <div ref={scrollRef} className="flex-1 overflow-y-auto pr-1 space-y-6">
        {messages.length === 0 && (
          <div className="max-w-xl">
            <div className="flex items-center gap-2 mb-4 text-gold">
              <Sparkles className="w-4 h-4" />
              <span className="font-mono text-xs uppercase tracking-[0.2em]">Try asking</span>
            </div>
            <div className="grid sm:grid-cols-2 gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)} data-testid="ask-suggestion"
                  className="text-left rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm text-zinc-300 transition-colors hover:border-gold/30 hover:bg-white/[0.04]">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")} data-testid={`msg-${m.role}`}>
            <div className={cn("w-7 h-7 rounded-md flex items-center justify-center shrink-0 border",
              m.role === "user" ? "bg-white/5 border-white/10" : "bg-gold/15 border-gold/30")}>
              {m.role === "user" ? <User className="w-3.5 h-3.5 text-zinc-400" /> : <span className="font-mono text-gold text-xs">H</span>}
            </div>
            <div className={cn("max-w-[80%] rounded-xl px-4 py-3 text-[15px] leading-relaxed",
              m.role === "user" ? "bg-gold/10 border border-gold/20 text-white" : "bg-[#141417] border border-white/5 text-zinc-200")}>
              {m.content ? <p className="whitespace-pre-wrap">{m.content}</p> : <Spinner className="w-4 h-4" />}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-white/5">
        <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#141417] px-3 py-2 focus-within:border-gold/40 transition-colors">
          <input
            data-testid="ask-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask Helm anything about your company…"
            className="flex-1 bg-transparent text-white text-sm placeholder:text-zinc-600 focus:outline-none py-1.5"
          />
          <button data-testid="ask-send-btn" onClick={() => send()} disabled={streaming || !input.trim()}
            className="w-9 h-9 rounded-lg bg-gold text-black flex items-center justify-center transition-colors hover:bg-gold-hover disabled:opacity-40">
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
