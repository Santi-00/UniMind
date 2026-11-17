import { useEffect, useState } from "react";
import { api, json } from "../api";

function Detail({ s, onClose }: { s: any; onClose: () => void }) {
  const [docs, setDocs] = useState<any[]>([]);
  const [lessons, setLessons] = useState<any[]>([]);
  const [tests, setTests] = useState<any[]>([]);
  const [prog, setProg] = useState<any>(null);
  useEffect(() => {
    api(`/documents?subject_id=${s.id}`).then(setDocs); api(`/lessons?subject_id=${s.id}`).then(setLessons);
    api(`/tests?subject_id=${s.id}`).then(setTests); api("/progress").then((r) => setProg(r.find((x: any) => x.id === s.id)));
  }, [s.id]);
  const box = (title: string, items: any[], row: (x: any) => any, empty: string) => (
    <div className="card"><h3 className="mb-2 font-medium">{title} ({items.length})</h3>
      {items.length === 0 ? <p className="text-sm text-slate-500">{empty}</p> : <ul className="space-y-1 text-sm">{items.map(row)}</ul>}</div>);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><button className="btn-ghost" onClick={onClose}>← Tutte le materie</button>
        <h1 className="text-2xl font-semibold" style={{ color: s.color }}>{s.name}</h1></div>
      <p className="text-sm text-slate-500">{s.professor || "Professore non indicato"}{s.exam_date ? ` · Esame: ${new Date(s.exam_date).toLocaleDateString("it-IT")}` : ""}{s.description ? ` · ${s.description}` : ""}</p>
      {prog && <div className="card grid gap-3 text-sm sm:grid-cols-4">
        <div>Preparazione: <b>{prog.preparazione}%</b></div><div>Lezioni studiate: <b>{prog.lezioni_studiate}/{prog.lezioni}</b></div>
        <div>Media test: <b>{prog.media_test ?? "–"}{prog.media_test != null && "%"}</b></div><div>Studio: <b>{Math.floor(prog.minuti_studio / 60)} h {prog.minuti_studio % 60} min</b></div>
        {prog.punti_deboli.length > 0 && <div className="sm:col-span-4">Punti deboli: {prog.punti_deboli.join(", ")}</div>}</div>}
      <div className="grid gap-4 lg:grid-cols-3">
        {box("Materiali", docs, (d) => <li key={d.id}>{d.filename} <span className="text-xs text-slate-500">· {d.status}</span></li>, "Nessun materiale.")}
        {box("Lezioni", lessons, (l) => <li key={l.id}>{l.title} <span className="text-xs text-slate-500">· {l.studied ? "studiata" : "da studiare"}</span></li>, "Nessuna lezione.")}
        {box("Test", tests, (t) => <li key={t.id}>{t.topic || "Tutta la materia"} <span className="text-xs text-slate-500">· {t.last_pct != null ? t.last_pct + "%" : "non svolto"}</span></li>, "Nessun test.")}
      </div>
    </div>);
}

const empty = { name: "", professor: "", description: "", color: "#7c3aed", exam_date: "" };

export default function Subjects() {
  const [list, setList] = useState<any[]>([]);
  const [form, setForm] = useState<any>(empty);
  const [editing, setEditing] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<any>(null);
  const load = () => api("/subjects").then(setList).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault(); setErr("");
    const body = { ...form, exam_date: form.exam_date || null };
    try {
      await api(editing ? `/subjects/${editing}` : "/subjects", json(editing ? "PUT" : "POST", body));
      setForm(empty); setEditing(null); load();
    } catch (e: any) { setErr(e.message); }
  }
  async function remove(s: any) {
    if (!confirm(`Eliminare "${s.name}"? Verranno eliminati anche i suoi materiali.`)) return;
    await api(`/subjects/${s.id}`, { method: "DELETE" }); load();
  }

  if (open) return <Detail s={open} onClose={() => setOpen(null)} />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Le mie materie</h1>
      <form onSubmit={save} className="card grid gap-3 sm:grid-cols-2">
        <div><label className="label">Nome</label><input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div><label className="label">Professore</label><input className="input" value={form.professor || ""} onChange={(e) => setForm({ ...form, professor: e.target.value })} /></div>
        <div className="sm:col-span-2"><label className="label">Descrizione</label><input className="input" value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
        <div><label className="label">Data esame</label><input type="date" className="input" value={form.exam_date || ""} onChange={(e) => setForm({ ...form, exam_date: e.target.value })} /></div>
        <div><label className="label">Colore</label><input type="color" className="h-10 w-full rounded-xl" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} /></div>
        <div className="flex gap-2 sm:col-span-2">
          <button className="btn">{editing ? "Salva modifiche" : "Aggiungi materia"}</button>
          {editing && <button type="button" className="btn-ghost" onClick={() => { setEditing(null); setForm(empty); }}>Annulla</button>}
        </div>
        {err && <p className="text-sm text-red-600 sm:col-span-2">{err}</p>}
      </form>

      {list.length === 0 && <p className="text-sm text-slate-500">Non hai ancora materie. Aggiungi la prima qui sopra.</p>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {list.map((s) => (
          <div key={s.id} className="card" style={{ borderTop: `4px solid ${s.color}` }}>
            <div className="font-medium">{s.name}</div>
            <div className="text-sm text-slate-500">{s.professor || "Professore non indicato"}</div>
            {s.description && <p className="mt-2 text-sm">{s.description}</p>}
            {s.exam_date && <p className="mt-2 text-xs text-slate-500">Esame: {new Date(s.exam_date).toLocaleDateString("it-IT")}</p>}
            <div className="mt-3 flex gap-1">
              <button className="btn-ghost" onClick={() => setOpen(s)}>Apri</button>
              <button className="btn-ghost" onClick={() => { setEditing(s.id); setForm({ ...empty, ...s }); window.scrollTo(0, 0); }}>Modifica</button>
              <button className="btn-ghost text-red-600" onClick={() => remove(s)}>Elimina</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
