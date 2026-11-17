import { useEffect, useState } from "react";
import { api, json } from "../api";

const fmtSize = (b: number) => (b > 1e6 ? (b / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1e3)) + " KB");

export default function Settings() {
  const [st, setSt] = useState<any>(null);
  const [hw, setHw] = useState<any>(null);
  const [priv, setPriv] = useState<any>(null);
  const [form, setForm] = useState({ ollama_url: "", llm_model: "", embedding_model: "" });
  const [test, setTest] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [profile, setProfile] = useState({ name: "", info: "" });
  const [profSaved, setProfSaved] = useState(false);
  const [backups, setBackups] = useState<any[]>([]);
  const [bmsg, setBmsg] = useState("");
  const [berr, setBerr] = useState("");
  const [bbusy, setBbusy] = useState(false);

  const load = () => api("/ai/status").then((s) => { setSt(s); setForm({ ollama_url: s.url, llm_model: s.llm_model, embedding_model: s.embedding_model }); });
  const loadBackups = () => api("/backup").then(setBackups).catch(() => {});
  useEffect(() => { load(); loadBackups(); api("/ai/hardware").then(setHw); api("/privacy").then(setPriv); api("/profile").then(setProfile); }, []);

  async function save() { await api("/ai/settings", json("PUT", form)); setSaved(true); setTimeout(() => setSaved(false), 2000); load(); }
  async function runTest() {
    setBusy(true); setTest("");
    try { const r = await api("/ai/test", json("POST", {})); setTest("Risposta del modello: " + r.response); }
    catch (e: any) { setTest("Errore: " + e.message); }
    setBusy(false); load();
  }
  async function saveProfile() { await api("/profile", json("PUT", profile)); setProfSaved(true); setTimeout(() => setProfSaved(false), 2000); }

  async function backupNow() {
    setBbusy(true); setBerr(""); setBmsg("");
    try { await api("/backup", { method: "POST" }); setBmsg("Backup creato."); loadBackups(); } catch (e: any) { setBerr(e.message); }
    setBbusy(false);
  }
  async function restore(call: () => Promise<any>) {
    if (!confirm("Ripristinare questo backup? I dati attuali verranno sostituiti (prima ne viene salvata una copia di sicurezza).")) return;
    setBbusy(true); setBerr(""); setBmsg("");
    try {
      const r = await call();
      setBmsg(`Ripristino completato (${r.restored_files} file). Copia di sicurezza: ${r.safety_backup}. Vai in Materiali e premi "Indicizza tutto" per ricostruire la ricerca. Ricarico la pagina…`);
      loadBackups(); setTimeout(() => location.reload(), 4000);
    } catch (e: any) { setBerr(e.message); }
    setBbusy(false);
  }
  async function removeBackup(name: string) {
    if (!confirm(`Eliminare ${name}?`)) return;
    await api(`/backup/${name}`, { method: "DELETE" }); loadBackups();
  }
  function uploadRestore(f: File) {
    restore(() => { const fd = new FormData(); fd.append("file", f); return api("/backup-restore-upload", { method: "POST", body: fd }); });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Impostazioni</h1>

      <section className="card space-y-3">
        <h2 className="font-medium">Configurazione intelligenza artificiale</h2>
        <div className="flex items-center gap-2">
          <span className={`h-3 w-3 rounded-full ${st?.online ? "bg-emerald-500" : "bg-red-500"}`} />
          <span className="font-medium">{st ? (st.online ? "Ollama è attivo" : "Ollama non è raggiungibile") : "Controllo in corso…"}</span>
          <button className="btn-ghost ml-auto" onClick={load}>Aggiorna</button>
        </div>
        {st && !st.online && <p className="text-sm text-slate-600 dark:text-slate-300">{st.help}<br /><span className="text-xs text-slate-500">{st.error}</span></p>}
        {st?.online && <p className="text-sm text-slate-500">Risposta in {st.latency_ms} ms{st.avg_response_s ? ` · tempo medio generazione ${st.avg_response_s} s` : ""}</p>}
        <div className="grid gap-3 sm:grid-cols-3">
          <div><label className="label">Indirizzo Ollama</label><input className="input" value={form.ollama_url} onChange={(e) => setForm({ ...form, ollama_url: e.target.value })} /></div>
          <div><label className="label">Modello linguistico</label>
            <select className="input" value={form.llm_model} onChange={(e) => setForm({ ...form, llm_model: e.target.value })}>
              <option value="">Scegli un modello</option>{st?.models?.map((m: string) => <option key={m}>{m}</option>)}</select></div>
          <div><label className="label">Modello embedding</label>
            <select className="input" value={form.embedding_model} onChange={(e) => setForm({ ...form, embedding_model: e.target.value })}>
              <option value="">Scegli un modello</option>{st?.models?.map((m: string) => <option key={m}>{m}</option>)}</select></div>
        </div>
        {st?.online && st.models.length === 0 && <p className="text-sm text-amber-600">Nessun modello installato. Esempio: <code>ollama pull qwen2.5:3b</code> e <code>ollama pull nomic-embed-text</code> (nulla viene scaricato senza il tuo comando).</p>}
        <div className="flex items-center gap-2">
          <button className="btn" onClick={save}>Salva</button>
          <button className="btn-ghost" disabled={busy} onClick={runTest}>{busy ? "Test in corso…" : "Testa la connessione"}</button>
          {saved && <span className="text-sm text-emerald-500">Salvato</span>}
        </div>
        {test && <p className="text-sm">{test}</p>}
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Profilo</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div><label className="label">Nome</label><input className="input" maxLength={60} value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} /></div>
          <div><label className="label">Note personali (facoltative)</label><input className="input" maxLength={500} value={profile.info} onChange={(e) => setProfile({ ...profile, info: e.target.value })} /></div>
        </div>
        <div className="flex items-center gap-2"><button className="btn" onClick={saveProfile}>Salva profilo</button>{profSaved && <span className="text-sm text-emerald-500">Salvato</span>}</div>
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Backup e dati</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">Un backup automatico viene creato ogni giorno all'avvio (ne restano 7). Contiene database e documenti. L'indice di ricerca non è incluso: dopo un ripristino va ricostruito con "Indicizza tutto".</p>
        <div className="flex flex-wrap gap-2">
          <button className="btn" disabled={bbusy} onClick={backupNow}>Crea backup ora</button>
          <a className="btn-ghost border border-white/60 dark:border-white/15" href="/api/export">Esporta dati (JSON + lezioni .md)</a>
          <label className="btn-ghost cursor-pointer border border-white/60 dark:border-white/15">Ripristina da file…
            <input type="file" accept=".zip" hidden onChange={(e) => e.target.files?.[0] && uploadRestore(e.target.files[0])} /></label>
        </div>
        {bmsg && <p className="text-sm text-emerald-500">{bmsg}</p>}
        {berr && <p className="text-sm text-red-500">{berr}</p>}
        {backups.length === 0 ? <p className="text-sm text-slate-500">Nessun backup ancora.</p> : (
          <ul className="space-y-1 text-sm">{backups.map((b) => (
            <li key={b.name} className="flex flex-wrap items-center gap-2 rounded-xl px-2 py-1 hover:bg-white/40 dark:hover:bg-white/5">
              <span className="min-w-0 flex-1 truncate">{b.created.replace("T", " ")} · {b.kind.replace(/_/g, " ")} · {fmtSize(b.size_bytes)}</span>
              <a className="btn-ghost" href={`/api/backup/${b.name}/download`}>Scarica</a>
              <button className="btn-ghost" disabled={bbusy} onClick={() => restore(() => api(`/backup/${b.name}/restore`, { method: "POST" }))}>Ripristina</button>
              <button className="btn-ghost text-red-500" onClick={() => removeBackup(b.name)}>Elimina</button>
            </li>))}</ul>)}
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="card text-sm"><h2 className="mb-2 font-medium">Il tuo computer</h2>
          {hw && <ul className="space-y-1"><li>CPU: {hw.cpu_cores} core</li>{hw.ram_total_gb && <li>RAM: {hw.ram_available_gb} GB liberi su {hw.ram_total_gb} GB</li>}{hw.suggerimento && <li>Consigliati: {hw.suggerimento}</li>}<li className="text-xs text-slate-500">{hw.gpu_note}</li></ul>}</section>
        <section className="card text-sm"><h2 className="mb-2 font-medium">Privacy: dove sono i tuoi dati</h2>
          {priv && <ul className="space-y-1 break-all"><li>Database: {priv.database}</li><li>Documenti: {priv.documenti}</li><li>Vettori: {priv.vettori}</li><li>Backup: {priv.backup}</li><li>Log: {priv.log}</li><li className="pt-1 text-xs text-slate-500">{priv.nota}</li></ul>}</section>
      </div>
    </div>
  );
}
