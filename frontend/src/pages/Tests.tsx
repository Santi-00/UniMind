import { useEffect, useState } from "react";
import { api, json } from "../api";
import { MathText } from "./Rich";

const TIPI: Record<string, string> = { multipla: "Risposta multipla", vero_falso: "Vero o falso", aperta: "Risposta aperta", completamento: "Completamento", esercizio: "Esercizio", programmazione: "Programmazione", logica: "Problema logico" };
const COLORE: Record<string, string> = { Ottimo: "text-emerald-600", Buono: "text-emerald-500", Discreto: "text-amber-500", Iniziale: "text-orange-500", Insufficiente: "text-red-600" };

export default function Tests() {
  const [subjects, setSubjects] = useState<any[]>([]);
  const [list, setList] = useState<any[]>([]);
  const [form, setForm] = useState<any>({ subject_id: "", topic: "", n: 5, difficulty: "media", types: ["multipla", "vero_falso", "aperta"] });
  const [test, setTest] = useState<any>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const load = () => api("/tests").then(setList);
  useEffect(() => { load(); api("/subjects").then(setSubjects); }, []);

  async function generate() {
    if (!form.subject_id) { setErr("Scegli una materia."); return; }
    setBusy("gen"); setErr("");
    try {
      const r = await api("/tests/generate", json("POST", { ...form, subject_id: Number(form.subject_id), n: Number(form.n), topic: form.topic || null }));
      await start(r.id); load();
    } catch (e: any) { setErr(e.message); }
    setBusy("");
  }
  async function start(id: number) { setResult(null); setAnswers({}); setErr(""); setTest(await api(`/tests/${id}`)); }
  async function submit() {
    setBusy("sub"); setErr("");
    try { setResult(await api(`/tests/${test.id}/submit`, json("POST", { answers }))); load(); }
    catch (e: any) { setErr(e.message); }
    setBusy("");
  }
  const toggle = (t: string) => setForm({ ...form, types: form.types.includes(t) ? form.types.filter((x: string) => x !== t) : [...form.types, t] });
  const set = (i: number, v: string) => setAnswers({ ...answers, [i]: v });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Test</h1>
      {!test && (
        <>
          <section className="card space-y-3">
            <div className="grid gap-3 sm:grid-cols-4">
              <div><label className="label">Materia</label><select className="input" value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })}><option value="">Scegli…</option>{subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
              <div><label className="label">Argomento (facoltativo)</label><input className="input" value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} /></div>
              <div><label className="label">Numero di domande</label><input type="number" min={1} max={20} className="input" value={form.n} onChange={(e) => setForm({ ...form, n: e.target.value })} /></div>
              <div><label className="label">Difficoltà</label><select className="input" value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value })}>{["facile", "media", "difficile"].map((d) => <option key={d}>{d}</option>)}</select></div>
            </div>
            <div className="flex flex-wrap gap-2">{Object.entries(TIPI).map(([k, v]) => (
              <label key={k} className={`cursor-pointer rounded-full border px-3 py-1 text-sm ${form.types.includes(k) ? "border-brand-500 bg-brand-500/15" : "border-slate-300 dark:border-night-600"}`}>
                <input type="checkbox" className="hidden" checked={form.types.includes(k)} onChange={() => toggle(k)} />{v}</label>))}</div>
            <button className="btn" disabled={!!busy} onClick={generate}>{busy === "gen" ? "Sto creando il test…" : "Crea test"}</button>
            {err && <p className="text-sm text-red-600">{err}</p>}
          </section>
          <section className="space-y-2">
            <h2 className="font-medium">Test creati</h2>
            {list.length === 0 && <p className="text-sm text-slate-500">Nessun test. Creane uno qui sopra.</p>}
            {list.map((t) => (
              <button key={t.id} onClick={() => start(t.id)} className="card flex w-full items-center justify-between !p-4 text-left text-sm">
                <span>{t.subject_name} · {t.topic || "Tutta la materia"} · {t.difficulty}</span>
                <span className="text-slate-500">{t.last_pct != null ? `Ultimo: ${t.last_pct}%` : "Non svolto"}</span>
              </button>))}
          </section>
        </>
      )}

      {test && !result && (
        <section className="space-y-4">
          {test.questions.map((q: any, i: number) => (
            <div key={i} className="card space-y-2">
              <div className="text-xs text-slate-500">Domanda {i + 1} · {TIPI[q.type]}</div>
              <p className="font-medium"><MathText text={q.question} /></p>
              {q.type === "multipla" && q.options.map((o: string, j: number) => {
                const L = "ABCDEF"[j];
                return <label key={j} className="flex items-center gap-2 text-sm"><input type="radio" name={`q${i}`} checked={answers[i] === L} onChange={() => set(i, L)} />{L}) <MathText text={o.replace(/^[A-F][).]\s*/, "")} /></label>;
              })}
              {q.type === "vero_falso" && ["vero", "falso"].map((v) => <label key={v} className="flex items-center gap-2 text-sm capitalize"><input type="radio" name={`q${i}`} checked={answers[i] === v} onChange={() => set(i, v)} />{v}</label>)}
              {!["multipla", "vero_falso"].includes(q.type) && <textarea className={`input h-24 ${q.type === "programmazione" ? "font-mono" : ""}`} value={answers[i] || ""} onChange={(e) => set(i, e.target.value)} />}
            </div>
          ))}
          {err && <p className="text-sm text-red-600">{err}</p>}
          <div className="flex gap-2">
            <button className="btn" disabled={!!busy} onClick={submit}>{busy === "sub" ? "Correzione in corso…" : "Consegna"}</button>
            <button className="btn-ghost" onClick={() => setTest(null)}>Esci senza consegnare</button>
          </div>
        </section>
      )}

      {result && (
        <section className="space-y-4">
          <div className="card text-center">
            <div className={`text-4xl font-semibold ${COLORE[result.level]}`}>{result.score_pct}%</div>
            <div className="mt-1">{result.level} · voto indicativo {result.grade_30}/30</div>
            {result.weak_topics.length > 0 && <p className="mt-2 text-sm text-slate-500">Da ripassare: {result.weak_topics.join(", ")}</p>}
          </div>
          {result.results.map((r: any, i: number) => (
            <div key={i} className="card space-y-1 text-sm" style={{ borderLeft: `4px solid ${r.score >= 0.99 ? "#10b981" : r.score > 0 ? "#f59e0b" : "#ef4444"}` }}>
              <div className="font-medium">{i + 1}. <MathText text={test.questions[i].question} /></div>
              <div>La tua risposta: {r.given || "—"}</div>
              {r.score < 0.99 && <div>Risposta corretta: <MathText text={r.correct_answer} /></div>}
              {r.feedback && <div className="text-slate-600 dark:text-slate-300"><MathText text={r.feedback} /></div>}
              {r.explanation && <div className="text-xs text-slate-500"><MathText text={r.explanation} /></div>}
            </div>))}
          <button className="btn" onClick={() => { setTest(null); setResult(null); }}>Torna ai test</button>
        </section>
      )}
    </div>
  );
}
