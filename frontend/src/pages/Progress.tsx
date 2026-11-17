import { useEffect, useState } from "react";
import { api, json } from "../api";

function Bar({ v, color }: { v: number; color: string }) {
  return <div className="h-2 w-full rounded-full bg-slate-200 dark:bg-night-700"><div className="h-2 rounded-full" style={{ width: `${Math.min(100, v)}%`, background: color }} /></div>;
}

export default function Progress() {
  const [rows, setRows] = useState<any[]>([]);
  const [plans, setPlans] = useState<Record<number, any>>({});
  const [hours, setHours] = useState("2");
  const [minutes, setMinutes] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<Record<number, string>>({});

  const load = async () => {
    const r = await api("/progress"); setRows(r);
    const p: Record<number, any> = {};
    for (const s of r) p[s.id] = await api(`/plans/${s.id}`);
    setPlans(p);
  };
  useEffect(() => { load(); }, []);

  async function plan(s: any, reorganize: boolean) {
    setBusy(s.id); setErr({ ...err, [s.id]: "" });
    try { await api("/plans/generate", json("POST", { subject_id: s.id, hours_per_day: Number(hours), reorganize })); await load(); }
    catch (e: any) { setErr({ ...err, [s.id]: e.message }); }
    setBusy(null);
  }
  async function log(s: any) {
    const m = Number(minutes[s.id]); if (!m) return;
    await api("/progress/session", json("POST", { subject_id: s.id, minutes: m }));
    setMinutes({ ...minutes, [s.id]: "" }); load();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Progressi e piano di studio</h1>
      <p className="max-w-2xl text-sm text-slate-500">La preparazione vale 30% per le lezioni studiate e 70% per la media degli ultimi 5 test. Un argomento letto non conta come assimilato: serve un test.</p>
      {rows.length === 0 && <p className="text-sm text-slate-500">Crea prima una materia in "Le mie materie".</p>}
      {rows.map((s) => (
        <section key={s.id} className="card space-y-4" style={{ borderTop: `4px solid ${s.color}` }}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-medium">{s.name}</h2>
            <span className="text-sm text-slate-500">{s.exam_date ? `Esame: ${new Date(s.exam_date).toLocaleDateString("it-IT")}` : "Data esame non impostata"}</span>
          </div>
          <div><div className="mb-1 flex justify-between text-sm"><span>Preparazione</span><b>{s.preparazione}%</b></div><Bar v={s.preparazione} color={s.color} /></div>
          <div className="grid gap-3 text-sm sm:grid-cols-4">
            <div><b>{s.documenti}</b> materiali caricati</div>
            <div><b>{s.lezioni_studiate}/{s.lezioni}</b> lezioni studiate</div>
            <div>Media test: <b>{s.media_test ?? "–"}{s.media_test != null && "%"}</b></div>
            <div>Tempo di studio: <b>{Math.floor(s.minuti_studio / 60)} h {s.minuti_studio % 60} min</b></div>
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-2">
            <div>Argomenti: {["caricato", "studiato", "verificato", "assimilato"].map((k) => `${s.argomenti[k] || 0} ${k}`).join(" · ")}</div>
            <div className="flex items-end gap-1" aria-label="Andamento dei test">
              {s.andamento.length === 0 ? <span className="text-slate-500">Nessun test svolto.</span> : s.andamento.map((v: number, i: number) => <div key={i} title={`${v}%`} className="w-5 rounded-t bg-brand-500" style={{ height: `${Math.max(4, v * 0.5)}px` }} />)}
            </div>
            <div><b>Punti deboli:</b> {s.punti_deboli.join(", ") || "nessuno rilevato"}</div>
            <div><b>Punti di forza:</b> {s.punti_forti.join(", ") || "ancora nessuno"}</div>
          </div>
          <div className="flex items-end gap-2">
            <div className="w-32"><label className="label">Minuti studiati</label><input type="number" min={1} className="input" value={minutes[s.id] || ""} onChange={(e) => setMinutes({ ...minutes, [s.id]: e.target.value })} /></div>
            <button className="btn-ghost border border-slate-300 dark:border-night-600" onClick={() => log(s)}>Registra</button>
          </div>

          <div className="border-t border-slate-200 pt-4 dark:border-night-700">
            <div className="mb-3 flex flex-wrap items-end gap-2">
              <h3 className="mr-2 font-medium">Piano di studio</h3>
              <div className="w-28"><label className="label">Ore al giorno</label><input type="number" min={0.5} step={0.5} className="input" value={hours} onChange={(e) => setHours(e.target.value)} /></div>
              <button className="btn" disabled={busy === s.id} onClick={() => plan(s, false)}>{busy === s.id ? "Sto pianificando…" : "Crea piano"}</button>
              {plans[s.id]?.plan.length > 0 && <button className="btn-ghost border border-slate-300 dark:border-night-600" disabled={busy === s.id} onClick={() => plan(s, true)}>Riorganizza (sono rimasto indietro)</button>}
            </div>
            {err[s.id] && <p className="mb-2 text-sm text-red-600">{err[s.id]}</p>}
            {plans[s.id]?.plan.length === 0 && !err[s.id] && <p className="text-sm text-slate-500">Nessun piano. Servono data d'esame e almeno una lezione o un documento con capitoli.</p>}
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {plans[s.id]?.plan.map((d: any) => (
                <div key={d.date} className="rounded-xl border border-slate-200 p-3 text-sm dark:border-night-700">
                  <div className="font-medium">{new Date(d.date).toLocaleDateString("it-IT", { weekday: "short", day: "numeric", month: "short" })} <span className="font-normal text-slate-500">· {d.minutes} min</span></div>
                  <ul className="mt-1 list-disc pl-4">{d.activities.map((a: string, i: number) => <li key={i}>{a}</li>)}</ul>
                </div>))}
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
