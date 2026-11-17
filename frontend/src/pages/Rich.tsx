// Renderer per lezioni, chat e test: titoli, elenchi, grassetto, codice e FORMULE LaTeX (KaTeX, funziona offline).
import katex from "katex";

function renderTex(src: string, display: boolean): string {
  try {
    return katex.renderToString(src, { displayMode: display, throwOnError: false, strict: "ignore" });
  } catch {
    return "";
  }
}

function M({ src, display }: { src: string; display?: boolean }) {
  const html = renderTex(src, !!display);
  if (!html) return <code>{src}</code>;
  return <span className={display ? "block overflow-x-auto py-1" : ""} dangerouslySetInnerHTML={{ __html: html }} />;
}

const MATH = /(\$[^$\n]+?\$|\\\([^\n]+?\\\))/g;

const boldParts = (t: string, k: string) =>
  t.split(/(\*\*[^*]+\*\*)/g).map((p, i) => (p.startsWith("**") && p.endsWith("**") && p.length > 4 ? <b key={`${k}b${i}`}>{p.slice(2, -2)}</b> : p));

function withMath(text: string, k: string) {
  return text.split(MATH).map((p, i) => {
    if (i % 2 === 1) return <M key={`${k}m${i}`} src={p.startsWith("$") ? p.slice(1, -1) : p.slice(2, -2)} />;
    return <span key={`${k}t${i}`}>{boldParts(p, `${k}${i}`)}</span>;
  });
}

// Testo breve con formule in linea (domande di test, feedback)
export function MathText({ text }: { text: string }) {
  return <>{withMath(text || "", "x")}</>;
}

export default function Rich({ text }: { text: string }) {
  const norm = (text || "").replace(/\\\[([\s\S]+?)\\\]/g, (_m, g) => `$$${g}$$`);
  const out: JSX.Element[] = [];
  norm.split(/(\$\$[\s\S]+?\$\$)/g).forEach((chunk, ci) => {
    if (ci % 2 === 1) {
      out.push(<div key={`d${ci}`}><M src={chunk.slice(2, -2).trim()} display /></div>);
      return;
    }
    let code: string[] | null = null;
    chunk.split("\n").forEach((l, i) => {
      const k = `${ci}_${i}`;
      if (l.trim().startsWith("```")) {
        if (code) { out.push(<pre key={k} className="my-2 overflow-x-auto rounded-xl bg-slate-900/85 p-3 text-xs text-slate-100">{code.join("\n")}</pre>); code = null; }
        else code = [];
        return;
      }
      if (code) { code.push(l); return; }
      if (l.startsWith("# ")) out.push(<h1 key={k} className="mb-2 text-2xl font-semibold">{withMath(l.slice(2), k)}</h1>);
      else if (l.startsWith("## ")) out.push(<h2 key={k} className="mb-1 mt-5 text-lg font-semibold text-brand-600 dark:text-brand-400">{withMath(l.slice(3), k)}</h2>);
      else if (l.startsWith("### ")) out.push(<h3 key={k} className="mt-3 font-medium">{withMath(l.slice(4), k)}</h3>);
      else if (/^\s*[-*] /.test(l)) out.push(<li key={k} className="ml-5 list-disc text-sm leading-relaxed">{withMath(l.replace(/^\s*[-*] /, ""), k)}</li>);
      else if (l.startsWith("Approfondimento AI:")) out.push(<p key={k} className="my-2 rounded-xl border-l-4 border-brand-500 bg-brand-500/10 px-3 py-2 text-sm leading-relaxed">{withMath(l, k)}</p>);
      else if (l.trim()) out.push(<p key={k} className="my-1.5 text-sm leading-relaxed">{withMath(l, k)}</p>);
    });
    if (code) out.push(<pre key={`c${ci}`} className="my-2 overflow-x-auto rounded-xl bg-slate-900/85 p-3 text-xs text-slate-100">{(code as string[]).join("\n")}</pre>);
  });
  return <div>{out}</div>;
}
