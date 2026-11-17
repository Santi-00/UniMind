import { useEffect, useRef, useState } from "react";
import { api, json } from "../api";

const BADGE: Record<string, string> = {
  caricato: "bg-slate-200 text-slate-700 dark:bg-night-700 dark:text-slate-200",
  "in elaborazione": "bg-amber-100 text-amber-800",
  analizzato: "bg-emerald-100 text-emerald-800",
  errore: "bg-red-100 text-red-800",
};
const fmt = (b: number) => (b > 1e6 ? (b / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1e3)) + " KB");

export default function Documents() {
  const [docs, setDocs] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [subj, setSubj] = useState("");
  const [filter, setFilter] = useState({ subject_id: "", status: "", q: "", sort: "recenti" });
  const [msg, setMsg] = useState("");
  const [info, setInfo] = useState("");
  const [rag, setRag] = useState<any>(null);
  const [working, setWorking] = useState<number | null>(null);
  const [watch, setWatch] = useState(0);
  const loadRag = () => api("/rag/status").then(setRag).catch(() => {});
  useEffect(() => { loadRag(); }, []);
  useEffect(() => {
    if (!rag?.in_corso && watch <= 0) return;
    const t = setInterval(() => { loadRag(); load(); setWatch((w) => w - 1); }, 2000);
    return () => clearInterval(t);
  }, [rag?.in_corso, watch > 0]);
  async function runIndex(documentId?: number) {
    setMsg(""); setInfo("");
    try { await api("/rag/index" + (documentId ? `?document_id=${documentId}` : ""), { method: "POST" }); setInfo("Indicizzazione avviata…"); setWatch(8); }
    catch (e: any) { setMsg(e.message); }
    loadRag();
  }
  async function analyze(d: any) {
    setWorking(d.id); setMsg(""); setInfo("");
    try {
      const ch = await api(`/rag/analyze/${d.id}`, { method: "POST" });
      setInfo(`Capitoli di "${d.filename}": ` + ch.map((c: any) => `${c.title} (pag. ${c.page_start})`).join(" · ") + ". Reindicizza il documento per usarli nelle fonti.");
      load();
    } catch (e: any) { setMsg(e.message); }
    setWorking(null);
  }
  const [preview, setPreview] = useState<any>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const load = () => {
    const p = new URLSearchParams(Object.entries(filter).filter(([, v]) => v) as [string, string][]);
    api("/documents?" + p).then(setDocs).catch((e) => setMsg(e.message));
  };
  useEffect(() => { api("/subjects").then(setSubjects); }, []);
  useEffect(load, [filter]);
  useEffect(() => {
    if (!docs.some((d) => d.status === "caricato" || d.status === "in elaborazione")) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [docs]);

  async function upload(files: FileList | File[]) {
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f));
    if (subj) fd.append("subject_id", subj);
    try {
      const r = await api("/documents", { method: "POST", body: fd });
      setMsg(r.rejected.length ? r.rejected.map((x: any) => `${x.filename}: ${x.motivo}`).join(" ") : "");
      load();
    } catch (e: any) { setMsg(e.message); }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Materiali</h1>

      <div className="card space-y-3">
        <div className="max-w-xs"><label className="label">Associa alla materia</label>
          <select className="input" value={subj} onChange={(e) => setSubj(e.target.value)}>
            <option value="">Nessuna</option>{subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select></div>
        <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
          onClick={() => input.current?.click()}
          className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center text-sm transition ${drag ? "border-brand-500 bg-brand-500/10" : "border-slate-300 dark:border-night-600"}`}>
          Trascina qui i file o clicca per sceglierli<br /><span className="text-xs text-slate-500">PDF, PPTX, DOCX, TXT, JPG, PNG</span>
          <input ref={input} type="file" multiple hidden accept=".pdf,.ppt,.pptx,.doc,.docx,.txt,.jpg,.jpeg,.png" onChange={(e) => e.target.files && upload(e.target.files)} />
        </div>
        {msg && <p className="text-sm text-red-600">{msg}</p>}
        {info && <p className="text-sm text-emerald-700 dark:text-emerald-400">{info}</p>}
        {rag && (
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
            <span>Ricerca nei documenti: {rag.chunks_indicizzati}/{rag.chunks_totali} sezioni indicizzate{rag.embedding_model ? "" : " (scegli prima un modello embedding nelle Impostazioni)"}</span>
            <button className="btn-ghost border border-slate-300 dark:border-night-600" disabled={rag.in_corso} onClick={() => runIndex()}>{rag.in_corso ? "Indicizzazione in corso…" : "Indicizza tutto"}</button>
            {rag.ultimo_errore && <span className="text-red-600">{rag.ultimo_errore}</span>}
          </div>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        <input className="input" placeholder="Cerca nel nome o nel testo" value={filter.q} onChange={(e) => setFilter({ ...filter, q: e.target.value })} />
        <select className="input" value={filter.subject_id} onChange={(e) => setFilter({ ...filter, subject_id: e.target.value })}>
          <option value="">Tutte le materie</option>{subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <select className="input" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
          <option value="">Tutti gli stati</option>{Object.keys(BADGE).map((s) => <option key={s}>{s}</option>)}</select>
        <select className="input" value={filter.sort} onChange={(e) => setFilter({ ...filter, sort: e.target.value })}>
          <option value="recenti">Più recenti</option><option value="nome">Nome</option><option value="dimensione">Dimensione</option></select>
      </div>

      {docs.length === 0 && <p className="text-sm text-slate-500">Nessun materiale. Carica il primo file qui sopra.</p>}
      <div className="space-y-2">
        {docs.map((d) => (
          <div key={d.id} className="card flex flex-wrap items-center gap-3 !p-4">
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{d.filename}</div>
              <div className="text-xs text-slate-500">{d.subject_name || "Senza materia"} · {fmt(d.size_bytes)}{d.n_chunks ? ` · ${d.n_chunks} sezioni` : ""}</div>
              {d.error && <div className="mt-1 text-xs text-red-600">{d.error}</div>}
            </div>
            <select className="input !w-auto !py-1 text-xs" aria-label="Materia del documento" value={d.subject_id ?? ""}
              onChange={async (e) => { if (!e.target.value) return; await api(`/documents/${d.id}`, json("PATCH", { subject_id: Number(e.target.value) })); load(); loadRag(); setInfo("Materia cambiata: premi Indicizza per aggiornare la ricerca."); }}>
              <option value="">Senza materia</option>{subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <span className={`rounded-full px-2.5 py-0.5 text-xs ${BADGE[d.status]}`}>{d.status}</span>
            <div className="flex gap-1">
              <button className="btn-ghost" disabled={d.status !== "analizzato"} onClick={async () => setPreview({ d, rows: await api(`/documents/${d.id}/preview`) })}>Anteprima</button>
              <a className="btn-ghost" href={`/api/documents/${d.id}/download`}>Scarica</a>
              {d.status === "analizzato" && <button className="btn-ghost" disabled={rag?.in_corso} onClick={() => runIndex(d.id)}>{d.n_chunks > 0 && d.n_indexed >= d.n_chunks ? "Reindicizza" : "Indicizza"}</button>}
              {d.status === "analizzato" && <button className="btn-ghost" disabled={working === d.id} onClick={() => analyze(d)}>{working === d.id ? "Analisi…" : "Capitoli"}</button>}
              {d.status === "errore" && <button className="btn-ghost" onClick={async () => { await api(`/documents/${d.id}/reprocess`, { method: "POST" }); load(); }}>Riprova</button>}
              <button className="btn-ghost text-red-600" onClick={async () => { if (confirm(`Eliminare "${d.filename}"?`)) { await api(`/documents/${d.id}`, { method: "DELETE" }); load(); } }}>Elimina</button>
            </div>
          </div>
        ))}
      </div>

      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setPreview(null)}>
          <div className="card max-h-[80vh] w-full max-w-2xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex justify-between"><h2 className="font-medium">{preview.d.filename}</h2><button className="btn-ghost" onClick={() => setPreview(null)}>Chiudi</button></div>
            {preview.rows.map((r: any, i: number) => <p key={i} className="mb-3 whitespace-pre-wrap text-sm"><span className="text-xs text-slate-500">Pag./slide {r.page}</span><br />{r.text}</p>)}
          </div>
        </div>
      )}
    </div>
  );
}
