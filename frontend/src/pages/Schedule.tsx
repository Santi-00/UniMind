import { useEffect, useState } from "react";
import { api, json, GIORNI } from "../api";

const empty = { subject_id: "", professor: "", weekday: 0, start_time: "09:00", end_time: "10:00", room: "", kind: "Lezione", reminder_minutes: 15 };

export default function Schedule() {
  const [events, setEvents] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [form, setForm] = useState<any>(empty);
  const [editing, setEditing] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const load = () => api("/schedule").then(setEvents);
  useEffect(() => { load(); api("/subjects").then(setSubjects); }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault(); setErr("");
    const body = { ...form, subject_id: form.subject_id ? Number(form.subject_id) : null, weekday: Number(form.weekday), reminder_minutes: Number(form.reminder_minutes) };
    try {
      await api(editing ? `/schedule/${editing}` : "/schedule", json(editing ? "PUT" : "POST", body));
      setForm(empty); setEditing(null); load();
    } catch (e: any) { setErr(e.message); }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Orario settimanale</h1>
      <form onSubmit={save} className="card grid gap-3 sm:grid-cols-3">
        <div><label className="label">Materia</label>
          <select className="input" value={form.subject_id ?? ""} onChange={(e) => setForm({ ...form, subject_id: e.target.value })}>
            <option value="">—</option>{subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select></div>
        <div><label className="label">Giorno</label>
          <select className="input" value={form.weekday} onChange={(e) => setForm({ ...form, weekday: e.target.value })}>
            {GIORNI.map((g, i) => <option key={g} value={i}>{g}</option>)}
          </select></div>
        <div><label className="label">Professore</label><input className="input" value={form.professor || ""} onChange={(e) => setForm({ ...form, professor: e.target.value })} /></div>
        <div><label className="label">Inizio</label><input type="time" className="input" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} /></div>
        <div><label className="label">Fine</label><input type="time" className="input" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} /></div>
        <div><label className="label">Aula</label><input className="input" value={form.room || ""} onChange={(e) => setForm({ ...form, room: e.target.value })} /></div>
        <div><label className="label">Tipo</label>
          <select className="input" value={form.kind || ""} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            {["Lezione", "Laboratorio", "Esercitazione", "Ricevimento"].map((k) => <option key={k}>{k}</option>)}
          </select></div>
        <div><label className="label">Promemoria (minuti prima)</label><input type="number" min={0} className="input" value={form.reminder_minutes} onChange={(e) => setForm({ ...form, reminder_minutes: e.target.value })} /></div>
        <div className="flex items-end gap-2">
          <button className="btn">{editing ? "Salva evento" : "Aggiungi evento"}</button>
          {editing && <button type="button" className="btn-ghost" onClick={() => { setEditing(null); setForm(empty); }}>Annulla</button>}
        </div>
        {err && <p className="text-sm text-red-600 sm:col-span-3">{err}</p>}
      </form>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {GIORNI.map((g, i) => (
          <section key={g} className="card">
            <h2 className="mb-2 font-medium">{g}</h2>
            {events.filter((e) => e.weekday === i).length === 0 && <p className="text-sm text-slate-500">Nessuna lezione.</p>}
            <ul className="space-y-2">
              {events.filter((e) => e.weekday === i).map((e) => (
                <li key={e.id} className="rounded-xl border border-slate-200 p-3 text-sm dark:border-night-700" style={{ borderLeft: `4px solid ${e.subject_color || "#7c3aed"}` }}>
                  <div className="font-medium">{e.subject_name || e.kind}</div>
                  <div className="text-slate-500">{e.start_time}–{e.end_time}{e.room ? ` · Aula ${e.room}` : ""}{e.professor ? ` · ${e.professor}` : ""}</div>
                  <div className="mt-1 flex gap-1">
                    <button className="btn-ghost" onClick={() => { setEditing(e.id); setForm({ ...e, subject_id: e.subject_id ?? "" }); window.scrollTo(0, 0); }}>Modifica</button>
                    <button className="btn-ghost" onClick={async () => { await api(`/schedule/${e.id}/duplicate`, { method: "POST" }); load(); }}>Duplica</button>
                    <button className="btn-ghost text-red-600" onClick={async () => { await api(`/schedule/${e.id}`, { method: "DELETE" }); load(); }}>Elimina</button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
