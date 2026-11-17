import { useEffect, useRef, useState } from "react";
import { api, json } from "../api";
import Rich from "./Rich";

export default function Study({ go }: { go: (p: string) => void }) {
  const [docs, setDocs] = useState<any[]>([]);
  const [docId, setDocId] = useState("");
  const [data, setData] = useState<any>(null);
  const [lesson, setLesson] = useState<any>(null);
  const [busy, setBusy] = useState<string>("");
  const [err, setErr] = useState("");
  const timer = useRef<any>(null);

  useEffect(() => { api("/documents?status=analizzato").then(setDocs); return () => clearInterval(timer.current); }, []);

  const load = async (id = docId) => { if (!id) return; const r = await api(`/study/${id}`); setData(r); return r; };
  useEffect(() => { setData(null); setLesson(null); setErr(""); if (docId) load(docId); }, [docId]);

  // aggiorna da solo finché le lezioni vengono generate in background
  useEffect(() => {
    clearInterval(timer.current);
    if (data?.job?.running) timer.current = setInterval(() => load(), 3000);
    return () => clearInterval(timer.current);
  }, [data?.job?.running, docId]);

  async function run(label: string, fn: () => Promise<any>) {
    setBusy(label); setErr("");
    try { await fn(); await load(); } catch (e: any) { setErr(e.message); }
    setBusy("");
  }
  const analyze = () => run("analyze", () => api(`/rag/analyze/${docId}`, { method: "POST" }));
  const genAll = () => run("all", () => api(`/study/${docId}/generate-all`, { method: "POST" }));
  const genOne = (c: any) => run("c" + c.id, async () => { const r = await api(`/study/chapter/${c.id}/generate`, { method: "POST" }); await open(r.lesson_id); });
  async function open(id: number) { setLesson(await api(`/lessons/${id}`)); }

  async function toggleStudied() {
    await api(`/lessons/${lesson.id}/studied?studied=${!lesson.studied}`, { method: "POST" });
    setLesson({ ...lesson, studied: lesson.studied ? 0 : 1 }); load();
  }
  const nextLesson = () => data?.chapters.find((c: any) => c.lesson_id && !c.studied && c.lesson_id !== lesson?.id);

  const chapters: any[] = data?.chapters || [];
  const done = chapters.filter((c) => c.studied).length;
  const job = data?.job;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Studio in sequenza</h1>
      <p className="max-w-2xl text-sm text-slate-500 dark:text-slate-400">Scegli un documento: UniMind lo divide in capitoli e scrive una lezione per ciascuno. Poi li studi uno dopo l'altro.</p>

      <section className="card max-w-xl">
        <label className="label">Documento</label>
        <select className="input" value={docId} onChange={(e) => setDocId(e.target.value)}>
          <option value="">Scegli un documento…</option>{docs.map((d) => <option key={d.id} value={d.id}>{d.filename}{d.subject_name ? ` · ${d.subject_name}` : ""}</option>)}
        </select>
        {docs.length === 0 && <p className="mt-2 text-sm text-slate-500">Nessun documento analizzato. Caricane uno in <button className="underline" onClick={() => go("documenti")}>Materiali</button>.</p>}
      </section>

      {err && <p className="text-sm text-red-500">{err}</p>}

      {data && chapters.length === 0 && (
        <section className="card max-w-xl space-y-2">
          <p className="text-sm">Questo documento non ha ancora i capitoli. L'AI li riconosce leggendo il testo (può richiedere un minuto).</p>
          <button className="btn" disabled={!!busy} onClick={analyze}>{busy === "analyze" ? "Sto leggendo il documento…" : "Riconosci capitoli"}</button>
        </section>
      )}

      {data && chapters.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
          <aside className="space-y-3">
            <div className="card space-y-2 !p-4">
              <div className="flex justify-between text-sm"><span>Lezioni studiate</span><b>{done}/{chapters.length}</b></div>
              <div className="h-2 rounded-full bg-slate-300/50 dark:bg-white/10"><div className="h-2 rounded-full bg-gradient-to-r from-brand-600 to-sky-400" style={{ width: `${(done / chapters.length) * 100}%` }} /></div>
              <button className="btn w-full justify-center" disabled={!!busy || job?.running || chapters.every((c) => c.lesson_id)} onClick={genAll}>
                {job?.running ? `Genero ${job.done}/${job.total}…` : "Genera tutte le lezioni mancanti"}</button>
              {job?.running && job.current && <p className="text-xs text-slate-500">In corso: {job.current}. Puoi leggere intanto le lezioni già pronte.</p>}
              {job?.error && <p className="text-xs text-red-500">{job.error}</p>}
              <button className="btn-ghost w-full justify-center" disabled={!!busy} onClick={() => { if (confirm("Rifare il riconoscimento dei capitoli? Le lezioni già collegate restano ma potrebbero non corrispondere ai nuovi capitoli.")) analyze(); }}>Rifai i capitoli</button>
            </div>
            <ol className="space-y-1">
              {chapters.map((c) => (
                <li key={c.id} className={`glass rounded-xl p-3 text-sm ${lesson && lesson.chapter_id === c.id ? "!border-brand-500" : ""}`}>
                  <div className="font-medium">{c.position}. {c.title}</div>
                  <div className="mb-1 text-xs text-slate-500">Pag. {c.page_start}–{c.page_end} · {c.studied ? "Studiata" : c.lesson_id ? "Da studiare" : "Lezione da generare"}</div>
                  {c.lesson_id
                    ? <button className="btn-ghost !px-1" onClick={() => open(c.lesson_id)}>Leggi</button>
                    : <button className="btn-ghost !px-1" disabled={!!busy || job?.running} onClick={() => genOne(c)}>{busy === "c" + c.id ? "Scrivo la lezione…" : "Genera lezione"}</button>}
                </li>))}
            </ol>
          </aside>

          <section className="card min-h-[40vh]">
            {!lesson ? <p className="text-sm text-slate-500">Seleziona un capitolo per leggere la sua lezione.</p> : (
              <>
                <div className="mb-4 flex flex-wrap gap-1">
                  <button className="btn" onClick={toggleStudied}>{lesson.studied ? "Segna da studiare" : "Segna come studiata"}</button>
                  {nextLesson() && <button className="btn-ghost border border-white/60 dark:border-white/15" onClick={() => open(nextLesson().lesson_id)}>Prossima lezione →</button>}
                </div>
                <Rich text={lesson.content} />
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
