"use client";

import { FormEvent, useEffect, useState } from "react";

type Citation = { slug: string };
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
  transcript?: { role: string; content: string }[];
  notes?: { at: string; action: string; body: string }[];
};
type Msg = { role: "human" | "ai"; text: string; extra?: ChatResponse };

const SESSION_KEY = "nimbus.sessionId";

function sessionId() {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

async function readSse(
  res: Response,
  onNode: (node: string) => void
): Promise<ChatResponse> {
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

export default function Page() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [input, setInput] = useState("");
  const [stage, setStage] = useState("");

  async function loadTickets() {
    const res = await fetch("/api/tickets?all=true");
    if (res.ok) setTickets(await res.json());
  }

  async function loadHistory() {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: sessionId(), action: "loadPreviousSession" }),
    });
    const data = await res.json();
    const hist: Msg[] = (data.data || []).map((m: { role: string; content: string }) => ({
      role: m.role === "human" ? "human" : "ai",
      text: m.content,
    }));
    setMessages(hist);
  }

  useEffect(() => {
    loadHistory();
    loadTickets();
  }, []);

  async function send(text: string) {
    setMessages((prev) => [...prev, { role: "human", text }]);
    setInput("");
    setStage("load_memory");
    try {
      const res = await fetch("/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: sessionId(), chatInput: text }),
      });
      const data = await readSse(res, setStage);
      setMessages((prev) => [...prev, { role: "ai", text: data.output || "", extra: data }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: err instanceof Error ? err.message : "Request failed" },
      ]);
    }
    setStage("");
    loadTickets();
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (text) send(text);
  }

  async function onFile(file: File) {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/ingest", { method: "POST", body });
    const data = await res.json();
    setMessages((prev) => [
      ...prev,
      {
        role: "ai",
        text: res.ok
          ? `Indexed ${data.indexed} chunks from ${data.file}.`
          : data.detail || "Ingest failed",
      },
    ]);
  }

  async function syncConnectors() {
    const res = await fetch("/api/sync", { method: "POST" });
    const data = await res.json();
    setMessages((prev) => [
      ...prev,
      {
        role: "ai",
        text: res.ok
          ? `Synced ${data.copied?.length || 0} connector files, indexed ${data.indexed} chunks.`
          : data.detail || "Sync failed",
      },
    ]);
  }

  async function openTicket(id: string) {
    const res = await fetch(`/api/tickets/${id}`);
    if (res.ok) setSelected(await res.json());
  }

  async function act(id: string, action: string) {
    const res = await fetch(`/api/tickets/${id}/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (res.ok) {
      setSelected(await res.json());
      loadTickets();
    }
  }

  return (
    <div className="shell">
      <aside>
        <p className="brand">Nimbus</p>
        <p className="sub">
          Support desk. Answers only from the help center. Refunds wait for a
          human — the agent cannot send money.
        </p>
        <div className="row">
          <button type="button" onClick={() => send("I want to talk to a human")}>
            Talk to a human
          </button>
          <button
            type="button"
            onClick={() => {
              localStorage.removeItem(SESSION_KEY);
              setMessages([]);
              loadHistory();
            }}
          >
            New session
          </button>
        </div>
        <p className="sub" style={{ marginTop: 20 }}>
          Knowledge connectors
        </p>
        <div className="row">
          <button type="button" onClick={syncConnectors}>
            Sync Drive / Sheets
          </button>
        </div>
        <input
          type="file"
          accept=".md,.csv,.pdf"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onFile(file);
          }}
        />
        {stage ? <p className="stage">Running {stage}…</p> : null}
      </aside>
      <main>
        <div className="log">
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.text}
              {m.extra?.citations?.length ? (
                <div className="chips">
                  {m.extra.citations.map((c) => (
                    <span key={c.slug} className="chip">
                      {c.slug}
                    </span>
                  ))}
                </div>
              ) : null}
              {m.extra?.route ? (
                <div className="meta">
                  {[m.extra.route, m.extra.ticket_id].filter(Boolean).join(" · ")}
                </div>
              ) : null}
            </div>
          ))}
        </div>
        <form className="composer" onSubmit={onSubmit}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about passwords, refunds, warranty, or order #1042"
          />
          <button className="primary" type="submit">
            Send
          </button>
        </form>
      </main>
      <section className="inbox">
        <h2>Ticket inbox</h2>
        {tickets.length === 0 ? (
          <p className="sub">No tickets.</p>
        ) : (
          tickets
            .slice()
            .reverse()
            .map((row) => (
              <button
                key={row.id}
                type="button"
                className={`ticket ${selected?.id === row.id ? "active" : ""}`}
                onClick={() => openTicket(row.id)}
              >
                <strong>{row.id}</strong>
                <span>
                  {row.route} · {row.status}
                </span>
                <div>{row.query}</div>
              </button>
            ))
        )}
        {selected ? (
          <div className="detail">
            <h2>{selected.id}</h2>
            <p className="sub">{selected.summary}</p>
            {(selected.transcript || []).map((turn, i) => (
              <div key={i} className="turn">
                <span>{turn.role}</span>
                {turn.content}
              </div>
            ))}
            {(selected.notes || []).map((note, i) => (
              <div key={i} className="note">
                {note.action}: {note.body}
              </div>
            ))}
            <div className="row">
              {selected.route === "refund_request" &&
              selected.status === "pending_approval" ? (
                <>
                  <button type="button" className="primary" onClick={() => act(selected.id, "approve_refund")}>
                    Approve refund
                  </button>
                  <button type="button" onClick={() => act(selected.id, "deny_refund")}>
                    Deny
                  </button>
                </>
              ) : null}
              {selected.status === "open" || selected.status === "pending_approval" ? (
                <button type="button" onClick={() => act(selected.id, "resolve")}>
                  Resolve
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
