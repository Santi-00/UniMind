import { useEffect, useRef, useState } from "react";
import { api, json } from "../api";
import Rich from "./Rich";

const MODI: Record<string, string> = { spiegazione: "Spiegazione", interrogazione: "Interrogazione", esercizi: "Esercizi" };

export default function Tutor() {
  const [convs, setConvs] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<any[]>([]);
  const [subj, setSubj] = useState("");
  const [mode, setMode] = useState("spiegazione");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const end = useRef<HTMLDivElement>(null);

  const loadConvs = () => api("/tutor/conversations").then(setConvs);
  useEffect(() => { loadConvs(); api("/subjects").then(setSubjects); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function open(id: number) {
    setActive(id); setErr(""); setMsgs(await api(`/tutor/conversations/${id}/messages`));
  }
  async function create() {
    const r = await api("/tutor/conversations", json("POST", { subject_id: subj ? Number(subj) : null, mode }));
    await loadConvs(); open(r.id);
  }
  async function remove(id: number) {
    if (!confirm("Eliminare questa conversazione?")) return;
    await api(`/tutor/conversations/${id}`, { method: "DELETE" });
    if (active === id) { setActive(null); setMsgs([]); }
    loadConvs();
  }

  async function send(content: string, confused = false) {
    if (!active || !content.trim() || busy) return;
    setBusy(true); setErr(""); setInput("");
    setMsgs((m) => [...m, { role: "user", content }, { role: "assistant", content: "", sources: [] }]);
    const patch = (fn: (a: any) => any) => setMsgs((m) => { const c = [...m]; c[c.length - 1] = fn(c[c.length - 1]); return c; });
    try {
      const res = await fetch(`/api/tutor/conversations/${active}/message`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content, confused }),
      });
      if (!res.ok || !res.body) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n"); buf = lines.pop() || "";
        for (const l of lines) {
          if (!l.trim()) continue;
          const e = JSON.parse(l);
          if (e.type === "sources") patch((a) => ({ ...a, sources: e.data }));
          else if (e.type === "token") patch((a) => ({ ...a, content: a.content + e.data }));
          else if (e.type === "error") setErr(e.data);
        }
      }
    } catch (e: any) { setErr(e.message); }
    setBusy(false); loadConvs();
  }

  const lastAssistant = msgs.length > 0 && msgs[msgs.length - 1].role === "assistant" && msgs[msgs.length - 1].content;

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <aside className="space-y-3">
        <div className="card space-y-2 !p-4">
          <h2 className="font-medium">Nuova conversazione</h2>
          <select className="input" value={subj} onChange={(e) => setSubj(e.target.value)}>
            <option value="">Tutte le materie</option>{subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
          <select className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
            {Object.entries(MODI).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <button className="btn w-full justify-center" onClick={create}>Inizia</button>
        </div>
        <div className="space-y-1">
          {convs.length === 0 && <p className="text-sm text-slate-500">Nessuna conversazione. Creane una qui sopra.</p>}
          {convs.map((c) => (
            <div key={c.id} className={`flex items-center rounded-xl px-3 py-2 text-sm ${active === c.id ? "bg-brand-600/15" : "hover:bg-slate-100 dark:hover:bg-night-800"}`}>
              <button className="min-w-0 flex-1 text-left" onClick={() => open(c.id)}>
                <div className="truncate">{c.title || "Nuova conversazione"}</div>
                <div className="text-xs text-slate-500">{c.subject_name || "Tutte le materie"} · {MODI[c.mode]}</div>
              </button>
              <button className="btn-ghost !px-1.5 text-red-600" onClick={() => remove(c.id)} aria-label="Elimina">✕</button>
            </div>
          ))}
        </div>
      </aside>

      <section className="card flex min-h-[70vh] flex-col !p-0">
        {!active ? (
          <p className="m-auto p-8 text-center text-sm text-slate-500">Scegli materia e modalità, poi premi "Inizia" per studiare insieme.</p>
        ) : (
          <>
            <div className="flex-1 space-y-4 overflow-y-auto p-5">
              {msgs.length === 0 && <p className="text-sm text-slate-500">Scrivi una domanda sul tuo materiale. In modalità Interrogazione scrivi "iniziamo".</p>}
              {msgs.map((m, i) => (
                <div key={i} className={m.role === "user" ? "ml-auto max-w-[85%] rounded-2xl bg-brand-600 px-4 py-2 text-sm text-white" : "max-w-[92%] text-sm"}>
                  {m.role === "assistant" && m.content ? <Rich text={m.content} /> : <div className="whitespace-pre-wrap leading-relaxed">{m.content || (busy && i === msgs.length - 1 ? "…" : "")}</div>}
                  {m.role === "assistant" && m.sources?.length > 0 && (
                    <details className="mt-2 text-xs text-slate-500">
                      <summary className="cursor-pointer">Fonti ({m.sources.length})</summary>
                      <ul className="mt-1 space-y-1">{m.sources.map((s: any, j: number) => (
                        <li key={j}><b>[{j + 1}]</b> {s.filename}, pag. {s.page}{s.chapter ? `, ${s.chapter}` : ""}<div className="line-clamp-2 opacity-80">{s.text}</div></li>
                      ))}</ul>
                    </details>
                  )}
                  {m.role === "assistant" && m.content && m.sources?.length === 0 && <p className="mt-1 text-xs text-amber-600">Nessuna fonte trovata nei tuoi documenti.</p>}
                </div>
              ))}
              <div ref={end} />
            </div>
            {err && <p className="border-t border-slate-200 p-3 text-sm text-red-600 dark:border-night-700">{err}</p>}
            <div className="flex gap-2 border-t border-slate-200 p-3 dark:border-night-700">
              <input className="input" placeholder="Scrivi qui…" value={input} disabled={busy}
                onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send(input)} />
              <button className="btn" disabled={busy || !input.trim()} onClick={() => send(input)}>Invia</button>
              <button className="btn-ghost whitespace-nowrap border border-slate-300 dark:border-night-600" disabled={busy || !lastAssistant}
                onClick={() => send("Non ho capito.", true)}>Non ho capito</button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
