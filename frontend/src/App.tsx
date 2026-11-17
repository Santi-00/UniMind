import { useEffect, useState } from "react";
import Dashboard from "./pages/Dashboard";
import Subjects from "./pages/Subjects";
import Schedule from "./pages/Schedule";
import Documents from "./pages/Documents";
import Study from "./pages/Study";
import Lessons from "./pages/Lessons";
import Tutor from "./pages/Tutor";
import Tests from "./pages/Tests";
import Progress from "./pages/Progress";
import Settings from "./pages/Settings";
import { api, json } from "./api";

const PAGES = [
  { id: "dashboard", label: "Dashboard" },
  { id: "materie", label: "Le mie materie" },
  { id: "orario", label: "Orario" },
  { id: "documenti", label: "Materiali" },
  { id: "studio", label: "Studio in sequenza" },
  { id: "lezioni", label: "Lezioni" },
  { id: "tutor", label: "Studiamo insieme" },
  { id: "test", label: "Test" },
  { id: "progressi", label: "Progressi e piano" },
  { id: "impostazioni", label: "Impostazioni" },
];

export default function App() {
  const [page, setPage] = useState(location.hash.slice(1) || "dashboard");
  const [dark, setDark] = useState(localStorage.getItem("theme") !== "light");
  const [needName, setNeedName] = useState(false);
  const [name, setName] = useState("");

  useEffect(() => { document.documentElement.classList.toggle("dark", dark); localStorage.setItem("theme", dark ? "dark" : "light"); }, [dark]);
  useEffect(() => { location.hash = page; }, [page]);
  useEffect(() => { api("/profile").then((p) => setNeedName(!p.name)).catch(() => {}); }, []);

  // Promemoria locali (Notification API del browser)
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
    const fired = new Set<string>();
    const tick = async () => {
      if (!("Notification" in window) || Notification.permission !== "granted") return;
      try {
        const events = await api("/schedule");
        const now = new Date();
        const wd = (now.getDay() + 6) % 7;
        for (const e of events) {
          if (e.weekday !== wd) continue;
          const [h, m] = e.start_time.split(":").map(Number);
          const start = new Date(now); start.setHours(h, m, 0, 0);
          const diff = Math.round((start.getTime() - now.getTime()) / 60000);
          const key = `${e.id}-${now.toDateString()}`;
          if (diff === e.reminder_minutes && !fired.has(key)) {
            fired.add(key);
            new Notification(`Tra ${diff} minuti inizia ${e.subject_name || "la lezione"}`, { body: e.room ? `Aula ${e.room}` : "" });
          }
        }
      } catch {}
    };
    const id = setInterval(tick, 60000);
    return () => clearInterval(id);
  }, []);

  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await api("/profile", json("PUT", { name, info: "" }));
    setNeedName(false); setPage("dashboard"); location.reload();
  }

  return (
    <div className="flex min-h-screen">
      <aside className="glass sticky top-0 hidden h-screen w-64 shrink-0 flex-col rounded-none border-y-0 border-l-0 p-4 md:flex">
        <div className="mb-6 px-2">
          <div className="bg-gradient-to-r from-brand-500 to-sky-400 bg-clip-text text-xl font-bold tracking-tight text-transparent">UNIMIND</div>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Meno disordine. Più conoscenza.</p>
        </div>
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {PAGES.map((p) => (
            <button key={p.id} onClick={() => setPage(p.id)}
              className={`rounded-xl px-3 py-2 text-left text-sm transition ${page === p.id ? "bg-gradient-to-r from-brand-600 to-indigo-500 text-white shadow-lg shadow-brand-600/30" : "text-slate-600 hover:bg-white/60 dark:text-slate-300 dark:hover:bg-white/10"}`}>
              {p.label}
            </button>
          ))}
        </nav>
        <button className="btn-ghost justify-center" onClick={() => setDark(!dark)}>{dark ? "Tema chiaro" : "Tema scuro"}</button>
      </aside>

      <main className="min-w-0 flex-1 p-4 md:p-8">
        <div className="mb-4 flex gap-1 overflow-x-auto md:hidden">
          {PAGES.map((p) => (
            <button key={p.id} onClick={() => setPage(p.id)} className={`glass whitespace-nowrap rounded-lg px-3 py-1.5 text-sm ${page === p.id ? "!bg-brand-600 text-white" : ""}`}>{p.label}</button>
          ))}
        </div>
        {page === "dashboard" && <Dashboard go={setPage} />}
        {page === "materie" && <Subjects />}
        {page === "orario" && <Schedule />}
        {page === "documenti" && <Documents />}
        {page === "studio" && <Study go={setPage} />}
        {page === "lezioni" && <Lessons />}
        {page === "tutor" && <Tutor />}
        {page === "test" && <Tests />}
        {page === "progressi" && <Progress />}
        {page === "impostazioni" && <Settings />}
      </main>

      {needName && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <form onSubmit={saveName} className="card w-full max-w-sm space-y-3">
            <h2 className="text-lg font-semibold">Benvenuto in UniMind</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Come ti chiami? Il nome resta solo sul tuo computer.</p>
            <input className="input" autoFocus required maxLength={60} placeholder="Il tuo nome" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn w-full justify-center">Inizia</button>
          </form>
        </div>
      )}
    </div>
  );
}
