import { useEffect, useState } from "react";
import { api, json } from "../api";
import Rich from "./Rich";

export default function Lessons() {
  const [subjects, setSubjects] = useState<any[]>([]);
  const [docs, setDocs] = useState<any[]>([]);
  const [lessons, setLessons] = useState<any[]>([]);
  const [form, setForm] = useState({ subject_id: "", document_id: "", topic: "" });
  const [busy, setBusy] = useState<string>("");
  const [err, setErr] = useState("");
  const [cur, setCur] = useState<any>(null);
  const [edit, setEdit] = useState(false);
  const [speaking, setSpeaking] = useState(false);

  const load = () => api("/lessons").then(setLessons);
  useEffect(() => { load(); api("/subjects").then(setSubjects); api("/documents?status=analizzato").then(setDocs); }, []);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  async function generate() {
    if (!form.subject_id) { setErr("Scegli una materia."); return; }
    setBusy("generate"); setErr("");
    try {
      const r = await api("/lessons/generate", json("POST", { subject_id: Number(form.subject_id), document_id: form.document_id ? Number(form.document_id) : null, topic: form.topic || null }));
      await load(); await open(r.id);
    } catch (e: any) { setErr(e.message); }
    setBusy("");
  }
  async function open(id: number) { setCur(await api(`/lessons/${id}`)); setEdit(false); stop(); }
  async function save() {
    await api(`/lessons/${cur.id}`, json("PUT", { title: cur.title, content: cur.content, notes: cur.notes || "" }));
    setEdit(false); load();
  }
  async function studied() {
    await api(`/lessons/${cur.id}/studied?studied=${!cur.studied}`, { method: "POST" });
    setCur({ ...cur, studied: cur.studied ? 0 : 1 }); load();
  }
  async function regen() {
    if (!confirm("Rigenerare la lezione? Il testo attuale verrà sostituito (gli appunti restano).")) return;
    setBusy("regen"); setErr("");
    try { await api(`/lessons/${cur.id}/regenerate`, { method: "POST" }); await open(cur.id); load(); }
    catch (e: any) { setErr(e.message); }
    setBusy("");
  }
  async function remove() {
    if (!confirm("Eliminare la lezione?")) return;
    await api(`/lessons/${cur.id}`, { method: "DELETE" }); setCur(null); load();
  }
  const stop = () => { window.speechSynthesis?.cancel(); setSpeaking(false); };
  function speak() {
    if (!("speechSynthesis" in window)) { setErr("La sintesi vocale non è disponibile in questo browser."); return; }
    if (speaking) { stop(); return; }
    const u = new SpeechSynthesisUtterance(cur.content.replace(/\$\$[\s\S]+?\$\$|\$[^$\n]+\$/g, " formula ").replace(/[#*`]/g, ""));
    u.lang = "it-IT"; u.onend = () => setSpeaking(false);
    window.speechSynthesis.speak(u); setSpeaking(true);
  }

  const subjDocs = docs.filter((d) => !form.subject_id || String(d.subject_id) === form.subject_id);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Lezioni</h1>
      <section className="card grid gap-3 sm:grid-cols-4">
        <div><label className="label">Materia</label>
          <select className="input" value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value, document_id: "" })}>
            <option value="">Scegli…</option>{subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
        <div><label className="label">Documento (facoltativo)</label>
          <select className="input" value={form.document_id} onChange={(e) => setForm({ ...form, document_id: e.target.value })}>
            <option value="">Tutta la materia</option>{subjDocs.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}</select></div>
        <div><label className="label">Argomento (facoltativo)</label><input className="input" value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} placeholder="es. Cicli for e while" /></div>
        <div className="flex items-end"><button className="btn w-full justify-center" disabled={!!busy} onClick={generate}>{busy === "generate" ? "Sto scrivendo la lezione…" : "Genera lezione"}</button></div>
        {err && <p className="text-sm text-red-600 sm:col-span-4">{err}</p>}
      </section>

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-1">
          {lessons.length === 0 && <p className="text-sm text-slate-500">Nessuna lezione. Generane una qui sopra.</p>}
          {lessons.map((l) => (
            <button key={l.id} onClick={() => open(l.id)} className={`w-full rounded-xl px-3 py-2 text-left text-sm ${cur?.id === l.id ? "bg-brand-600/15" : "hover:bg-slate-100 dark:hover:bg-night-800"}`}>
              <div className="truncate">{l.title}</div>
              <div className="text-xs text-slate-500">{l.subject_name} · {l.studied ? "Studiata" : "Da studiare"}</div>
            </button>
          ))}
        </aside>
        <section className="card min-h-[40vh]">
          {!cur ? <p className="text-sm text-slate-500">Seleziona una lezione per leggerla.</p> : (
            <>
              <div className="mb-4 flex flex-wrap gap-1">
                <button className="btn" onClick={studied}>{cur.studied ? "Segna da studiare" : "Segna come studiata"}</button>
                <button className="btn-ghost" onClick={() => (edit ? save() : setEdit(true))}>{edit ? "Salva" : "Modifica"}</button>
                <button className="btn-ghost" onClick={speak}>{speaking ? "Ferma audio" : "Ascolta"}</button>
                <button className="btn-ghost" disabled={!!busy} onClick={regen}>{busy === "regen" ? "Rigenero…" : "Rigenera"}</button>
                <button className="btn-ghost text-red-600" onClick={remove}>Elimina</button>
              </div>
              {edit ? <textarea className="input h-[50vh] font-mono" value={cur.content} onChange={(e) => setCur({ ...cur, content: e.target.value })} /> : <Rich text={cur.content} />}
              <div className="mt-6"><label className="label">Appunti personali</label>
                <textarea className="input h-28" value={cur.notes || ""} onChange={(e) => setCur({ ...cur, notes: e.target.value })} />
                <button className="btn-ghost mt-1 border border-slate-300 dark:border-night-600" onClick={save}>Salva appunti</button></div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
