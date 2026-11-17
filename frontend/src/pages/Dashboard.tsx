import { useEffect, useState } from "react";
import { api, json, GIORNI } from "../api";

export default function Dashboard({ go }: { go: (p: string) => void }) {
  const [d, setD] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [ai, setAi] = useState<any>(null);
  const [advice, setAdvice] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const now = new Date();
  const wd = (now.getDay() + 6) % 7;
  const hhmm = now.toTimeString().slice(0, 5);

  useEffect(() => {
    api("/dashboard").then(setD).catch(() => {});
    api("/schedule").then(setEvents).catch(() => {});
    api("/ai/status").then(setAi).catch(() => {});
  }, []);

  const today = events.filter((e) => e.weekday === wd);
  const next = today.find((e) => e.start_time >= hhmm);

  async function suggest() {
    setBusy(true); setErr(""); setAdvice("");
    const prep = d.preparazione.map((p: any) => `${p.name}: preparazione ${p.preparazione}%`).join("; ");
    const ctx = `Materie: ${d.materie}. Documenti caricati: ${d.documenti}. Lezioni generate: ${d.lezioni}. Test svolti: ${d.test}. ${prep ? prep + ". " : ""}` +
      `Esami: ${d.esami.map((e: any) => `${e.name} il ${e.exam_date}`).join("; ") || "nessuno"}. ` +
      `Lezioni universitarie di oggi: ${today.map((e) => `${e.subject_name} alle ${e.start_time}`).join("; ") || "nessuna"}.`;
    try {
      const r = await api("/ai/test", json("POST", { prompt: `Sei un tutor universitario. In base a questi dati dello studente, suggerisci in italiano cosa studiare oggi, in massimo 5 punti brevi.\n${ctx}` }));
      setAdvice(r.response);
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  }

  const stat = (label: string, v: any) => (
    <div className="card"><div className="text-3xl font-semibold">{v ?? "–"}</div><div className="mt-1 text-sm text-slate-500 dark:text-slate-400">{label}</div></div>
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Ciao{d?.nome ? `, ${d.nome}` : ""}!</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">{GIORNI[wd]} {now.toLocaleDateString("it-IT", { day: "numeric", month: "long", year: "numeric" })}</p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stat("Materie attive", d?.materie)}{stat("Materiali caricati", d?.documenti)}{stat("Lezioni generate", d?.lezioni)}{stat("Test svolti", d?.test)}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card lg:col-span-2">
          <h2 className="mb-3 font-medium">Il tuo assistente AI</h2>
          {ai && !ai.online && <p className="mb-3 rounded-xl bg-amber-500/15 p-3 text-sm text-amber-700 dark:text-amber-200">{ai.help} <button className="underline" onClick={() => go("impostazioni")}>Apri le impostazioni</button></p>}
          <button className="btn" disabled={busy || !d} onClick={suggest}>{busy ? "Sto pensando…" : "Cosa studio oggi?"}</button>
          {err && <p className="mt-3 text-sm text-red-500">{err}</p>}
          {advice && <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{advice}</p>}
        </section>

        <section className="card">
          <h2 className="mb-3 font-medium">Oggi</h2>
          {next && <p className="mb-2 text-sm">Prossima lezione: <b>{next.subject_name || "Lezione"}</b> alle {next.start_time}</p>}
          {today.length === 0 && <p className="text-sm text-slate-500">Nessuna lezione oggi. <button className="underline" onClick={() => go("orario")}>Aggiungi l'orario</button></p>}
          <ul className="space-y-2">{today.map((e) => (
            <li key={e.id} className="flex items-center gap-2 text-sm"><span className="h-2.5 w-2.5 rounded-full" style={{ background: e.subject_color || "#7c3aed" }} />{e.start_time}–{e.end_time} {e.subject_name}</li>
          ))}</ul>
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-3 font-medium">Preparazione</h2>
          {!d?.preparazione?.length && <p className="text-sm text-slate-500">Crea una materia per iniziare. <button className="underline" onClick={() => go("materie")}>Le mie materie</button></p>}
          <div className="space-y-3">{d?.preparazione?.map((p: any) => (
            <div key={p.id}>
              <div className="mb-1 flex justify-between text-sm"><span>{p.name}</span><b>{p.preparazione}%</b></div>
              <div className="h-2 rounded-full bg-slate-300/50 dark:bg-white/10"><div className="h-2 rounded-full" style={{ width: `${Math.min(100, p.preparazione)}%`, background: p.color }} /></div>
            </div>))}</div>
        </section>

        <section className="card">
          <h2 className="mb-3 font-medium">Ultimi test e prossimi esami</h2>
          {d?.ultimi_test?.length ? <ul className="mb-3 space-y-1 text-sm">{d.ultimi_test.map((t: any, i: number) => (
            <li key={i} className="flex justify-between"><span>{t.subject_name} · {t.topic || "Generale"}</span><b>{t.score_pct}% · {t.grade_30}/30</b></li>))}</ul>
            : <p className="mb-3 text-sm text-slate-500">Nessun test svolto.</p>}
          {d?.esami?.length ? <ul className="space-y-1 border-t border-white/40 pt-3 text-sm dark:border-white/10">{d.esami.map((e: any) => <li key={e.name}>{e.name} — {new Date(e.exam_date).toLocaleDateString("it-IT")}</li>)}</ul>
            : <p className="border-t border-white/40 pt-3 text-sm text-slate-500 dark:border-white/10">Nessun esame in programma.</p>}
        </section>
      </div>
    </div>
  );
}
