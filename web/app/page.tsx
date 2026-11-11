"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { 
  SignInButton, 
  SignUpButton, 
  UserButton, 
  useUser, 
  useAuth 
} from "@clerk/nextjs";

type Citation = { slug: string; title?: string; excerpt?: string };
type ChatResponse = {
  output: string;
  route?: string;
  ticket_id?: string | null;
  citations?: Citation[];
  detail?: string;
};
type Ticket = {
  id: string;
  route: string;
  status: string;
  query: string;
  summary?: string;
  created_at?: string;
  remote_id?: string | null;
  transcript?: { role: string; content: string }[];
  notes?: { at: string; action: string; body: string }[];
  retrieved_slugs?: string[];
};
type Item = {
  name: string;
  description?: string;
  price: number;
  category?: string;
  stock?: number;
};
type Msg = { role: "human" | "ai" | "system"; text: string; extra?: ChatResponse };
type Filter = "needs" | "all" | "done";

const SESSION_KEY = "nimbus.sessionId";

const STAGE_LABEL: Record<string, string> = {
  load_memory: "Reading conversation",
  retrieve: "Searching knowledge",
  lookup_order: "Checking orders",
  gate: "Routing request",
  generate: "Writing response",
  guardrails: "Validating",
  ticket: "Filing ticket",
  save_memory: "Saving",
};

const ROUTE_LABEL: Record<string, string> = {
  grounded: "Knowledge found",
  refund_request: "Refund request",
  wants_human: "Human requested",
  out_of_scope: "Outside knowledge base",
};

const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  pending_approval: "Pending",
  approved: "Approved",
  denied: "Denied",
  resolved: "Resolved",
};

const ACTION_LABEL: Record<string, string> = {
  approve_refund: "Approved",
  deny_refund: "Denied",
  resolve: "Resolved",
  note: "Note",
};

const PROMPTS = [
  "How do I reset my password?",
  "Where is order #1042?",
  "Can I get a refund after 40 days?",
  "What is the Nimbus extended warranty?",
];

function sessionId() {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

function shortId(id: string) {
  return id.replace(/-/g, "").slice(0, 8);
}

function routeLabel(route: string) {
  return ROUTE_LABEL[route] || route.replaceAll("_", " ");
}

function statusLabel(status: string) {
  return STATUS_LABEL[status] || status.replaceAll("_", " ");
}

function citationLabel(citation: Citation) {
  return citation.title || citation.slug.replaceAll(/[-_]/g, " ");
}

function formatWhen(iso?: string) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function matches(ticket: Ticket, filter: Filter) {
  if (filter === "all") return true;
  if (filter === "done") return ["resolved", "approved", "denied"].includes(ticket.status);
  return ticket.status === "open" || ticket.status === "pending_approval";
}

async function readSse(res: Response, onNode: (node: string) => void): Promise<ChatResponse> {
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No stream");
  const decoder = new TextDecoder();
  let buffer = "";
  let donePayload: ChatResponse | null = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const block of parts) {
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data) continue;
      const parsed = JSON.parse(data);
      if (event === "node") onNode(parsed.node);
      if (event === "error") throw new Error(parsed.detail || "Stream failed");
      if (event === "done") donePayload = parsed;
    }
  }
  if (!donePayload) throw new Error("Stream ended without an answer");
  return donePayload;
}

function Mark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
      <rect width="28" height="28" rx="8" fill="#0c6a82" />
      <path
        d="M7 17.2c0-2 1.5-3.5 3.4-3.8.5-1.9 2.2-3.2 4.3-3.2 2.4 0 4.3 1.7 4.6 3.8 1.3.3 2.2 1.4 2.2 2.8 0 1.6-1.3 2.9-3 2.9H10c-1.7 0-3-1.1-3-2.5z"
        fill="#fff"
      />
    </svg>
  );
}

export default function Page() {
  const { isLoaded, isSignedIn, user } = useUser();
  const { getToken } = useAuth();
  
  const [messages, setMessages] = useState<Msg[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [input, setInput] = useState("");
  const [stage, setStage] = useState("");
  const [busy, setBusy] = useState(false);
  const [knowledgeBusy, setKnowledgeBusy] = useState(false);
  const [filter, setFilter] = useState<Filter>("needs");
  const [online, setOnline] = useState<"checking" | "live" | "offline">("checking");
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState<"customer" | "admin" | "items">("customer");
  const [notice, setNotice] = useState("");
  const [session, setSession] = useState("");
  const [isClient, setIsClient] = useState(false);
  
  const endRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);
  const sending = useRef(false);

  useEffect(() => {
    setIsClient(true);
    const sid = sessionId();
    setSession(sid);
    
    if (isSignedIn) {
      const init = async () => {
        try {
          await Promise.all([loadHistory(sid), loadTickets(), loadItems()]);
          setOnline("live");
        } catch (e) {
          setOnline("offline");
        } finally {
          setReady(true);
        }
      };
      init();
    } else {
      setReady(true);
    }
  }, [isSignedIn]);

  async function loadTickets() {
    const res = await fetch("http://127.0.0.1:8085/api/tickets?all=true");
    if (!res.ok) throw new Error("tickets");
    const rows: Ticket[] = await res.json();
    rows.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    setTickets(rows);
    return rows;
  }

  async function loadItems() {
    const res = await fetch("http://127.0.0.1:8085/api/items");
    if (!res.ok) return;
    setItems(await res.json());
  }

  async function loadHistory(sid: string) {
    const res = await fetch("http://127.0.0.1:8085/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: sid, action: "loadPreviousSession" }),
    });
    if (!res.ok) throw new Error("history");
    const data = await res.json();
    const hist: Msg[] = (data.data || []).map((m: { role: string; content: string }) => ({
      role: m.role === "human" ? "human" : "ai",
      text: m.content,
    }));
    setMessages(hist);
  }

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, stage]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4200);
    return () => clearTimeout(timer);
  }, [notice]);

  async function openTicket(id: string) {
    const res = await fetch(`http://127.0.0.1:8085/api/tickets/${id}`);
    if (!res.ok) {
      setNotice("Could not open ticket.");
      return;
    }
    setSelected(await res.json());
  }

  async function send(text: string) {
    if (sending.current) return;
    sending.current = true;
    setBusy(true);
    setMessages((prev) => [...prev, { role: "human", text }]);
    setInput("");
    if (boxRef.current) boxRef.current.style.height = "auto";
    setStage("load_memory");
    try {
      const res = await fetch("http://127.0.0.1:8085/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: session, chatInput: text }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Nimbus could not answer.");
      }
      const data = await readSse(res, setStage);
      setMessages((prev) => [...prev, { role: "ai", text: data.output || "", extra: data }]);
      setOnline("live");
      await loadTickets();
      if (data.ticket_id) {
        setFilter((current) => (current === "done" ? "needs" : current));
        const ticketRes = await fetch(`/api/tickets/${data.ticket_id}`);
        if (ticketRes.ok) setSelected(await ticketRes.json());
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "system", text: err instanceof Error ? err.message : "Request failed" },
      ]);
    } finally {
      setStage("");
      setBusy(false);
      sending.current = false;
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (text && !busy) send(text);
  }

  async function syncKnowledge() {
    setKnowledgeBusy(true);
    try {
      const res = await fetch("http://127.0.0.1:8085/api/sync", { method: "POST" });
      const data = await res.json();
      setNotice(
        res.ok
          ? `Synced ${data.copied?.length || 0} files. ${data.indexed} sections indexed.`
          : data.detail || "Sync failed."
      );
    } finally {
      setKnowledgeBusy(false);
    }
  }

  async function act(id: string, action: string) {
    const res = await fetch(`http://127.0.0.1:8085/api/tickets/${id}/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setNotice(data.detail || "Could not update ticket.");
      return;
    }
    setSelected(data);
    await loadTickets();
    setNotice(`${id} marked ${statusLabel(data.status).toLowerCase()}.`);
  }

  if (!isClient || !isLoaded) return null;

  if (!isSignedIn) {
    return (
      <div className="empty" style={{ height: "100vh", display: "grid", placeItems: "center" }}>
        <div>
          <Mark />
          <h2 style={{ marginTop: 20 }}>Welcome to Nimbus</h2>
          <p>Please sign in to access customer support.</p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <SignInButton mode="modal">
              <button className="primary">Sign In</button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button>Sign Up</button>
            </SignUpButton>
          </div>
        </div>
      </div>
    );
  }

  const needsCount = tickets.filter((row) => matches(row, "needs")).length;
  const visible = tickets.filter((row) => matches(row, filter));

  return (
    <div className="app" data-mode={mode}>
      <header className="topbar">
        <div className="brand" onClick={() => setMode("customer")} style={{ cursor: "pointer" }}>
          <Mark />
          <div>
            <strong>Nimbus Support</strong>
            <span>Active: {user.firstName || "Customer"}</span>
          </div>
        </div>
        <div className="top-meta">
          <button 
            type="button" 
            className="admin-toggle" 
            onClick={() => setMode(mode === "items" ? "customer" : "items")}
          >
            {mode === "items" ? "Close Store" : "Browse Items"}
          </button>
          <button 
            type="button" 
            className="admin-toggle" 
            onClick={() => setMode(mode === "admin" ? "customer" : "admin")}
          >
            {mode === "admin" ? "Close Desk" : "Open Desk"}
          </button>
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      {mode === "admin" && (
        <aside className="rail">
          <div className="rail-actions">
            <button type="button" onClick={syncKnowledge} disabled={knowledgeBusy}>
              {knowledgeBusy ? "Syncing..." : "Sync Knowledge (Drive/Sheets)"}
            </button>
            <button type="button" disabled={busy} onClick={() => send("I want to talk to a human")}>
              Test Escalation
            </button>
          </div>
          <div className="knowledge">
            <p className="section-label">Help Center Stats</p>
            <p className="hint">Neon DB & Vector Search active.</p>
          </div>
          <p className="policy">
            Administrative mode: manage tickets and sync knowledge base from Google Docs.
          </p>
        </aside>
      )}

      <main className="thread">
        {mode === "items" ? (
          <div className="log">
            <div className="empty">
              <h2>Inventory</h2>
              <p>Items retrieved from Neon PostgreSQL database.</p>
            </div>
            <div className="prompts" style={{ gridTemplateColumns: "1fr" }}>
              {items.map((item, i) => (
                <div key={i} className="bubble" style={{ marginBottom: 12 }}>
                  <strong>{item.name}</strong> — ${item.price}
                  <p style={{ margin: "4px 0", fontSize: 13, color: "var(--muted)" }}>{item.description}</p>
                  <span className="pill">{item.category}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div className="log" aria-live="polite">
              {messages.length === 0 && !stage ? (
                <div className="empty">
                  <div className="avatar nimbus center">N</div>
                  <h2>How can we help you today?</h2>
                  <p>Ask about our services or your account. Nimbus is here to help.</p>
                  <div className="prompts">
                    {PROMPTS.map((prompt) => (
                      <button key={prompt} type="button" disabled={busy} onClick={() => send(prompt)}>
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {messages.map((message, index) => (
                <div key={index} className={`msg ${message.role}`}>
                  <div className={`avatar ${message.role === "human" ? "visitor" : "nimbus"}`} aria-hidden="true">
                    {message.role === "human" ? (user.firstName?.[0] || "C") : "N"}
                  </div>
                  <div>
                    <div className="bubble">
                      {message.text}
                      {message.extra?.citations?.length ? (
                        <div className="sources">
                          {message.extra.citations.map((citation) => (
                            <span key={citation.slug} className="source" title={citation.excerpt || citation.slug}>
                              {citationLabel(citation)}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
              {stage ? (
                <div className="msg ai typing">
                  <div className="avatar nimbus" aria-hidden="true">N</div>
                  <div className="bubble">
                    {STAGE_LABEL[stage] || "Thinking..."}
                    <span className="caret"><i></i><i></i><i></i></span>
                  </div>
                </div>
              ) : null}
              <div ref={endRef} />
            </div>
            <form className="composer" onSubmit={onSubmit}>
              <div className="composer-inner">
                <textarea
                  ref={boxRef}
                  rows={1}
                  value={input}
                  placeholder="Ask anything..."
                  onChange={(e) => {
                    setInput(e.target.value);
                    e.target.style.height = "auto";
                    e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      const text = input.trim();
                      if (text && !busy) send(text);
                    }
                  }}
                />
                <button className="primary send-btn" type="submit" disabled={busy || !input.trim()}>
                  {busy ? <span className="caret"><i></i><i></i><i></i></span> : "↑"}
                </button>
              </div>
            </form>
          </>
        )}
      </main>

      {mode === "admin" && (
        <section className="queue">
          {selected ? (
            <div className="detail">
              <button onClick={() => setSelected(null)}>← Inbox</button>
              <h2>{selected.id}</h2>
              <span className={`pill ${selected.status}`}>{statusLabel(selected.status)}</span>
              <p>{selected.query}</p>
              <div className="actions">
                <button onClick={() => act(selected.id, "resolve")}>Resolve</button>
              </div>
            </div>
          ) : (
            <div className="ticket-list">
              <h2>Open Tickets</h2>
              {visible.map((t) => (
                <button key={t.id} className="ticket" onClick={() => openTicket(t.id)}>
                  <strong>{t.id}</strong> — {t.query}
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {notice ? <div className="toast">{notice}</div> : null}
    </div>
  );
}
