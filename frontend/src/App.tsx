import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./layout/Sidebar";
import { getHealth, type HealthResponse } from "./lib/api";
import { PoliticianProvider, usePolitician } from "./lib/PoliticianContext";

function PoliticianSelector() {
  const { politicians, selected, setSelectedId } = usePolitician();
  if (!politicians.length) return <span className="text-xs text-mocha">no accounts</span>;
  return (
    <select
      className="glass-soft rounded-lg px-3 py-1.5 text-sm font-medium text-ink outline-none"
      value={selected?.id ?? ""}
      onChange={(e) => setSelectedId(Number(e.target.value))}
    >
      {politicians.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name} · {p.constituency ?? "—"}
        </option>
      ))}
    </select>
  );
}

function TopBar() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [reachable, setReachable] = useState(true);

  useEffect(() => {
    getHealth()
      .then((h) => {
        setHealth(h);
        setReachable(true);
      })
      .catch(() => setReachable(false));
  }, []);

  const status = !reachable ? "api unreachable" : (health?.status ?? "…");
  const dot = status === "ok" ? "bg-green-500" : status === "…" ? "bg-mocha/50" : "bg-amber-500";

  return (
    <header className="glass sheen mx-3 mt-3 flex items-center justify-between rounded-2xl px-5 py-3">
      <PoliticianSelector />
      <div className="flex items-center gap-2 text-xs font-medium text-coffee/80">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        backend: {status}
      </div>
    </header>
  );
}

export function App() {
  return (
    <PoliticianProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex min-h-screen flex-1 flex-col">
          <TopBar />
          <main className="p-5">
            <Outlet />
          </main>
        </div>
      </div>
    </PoliticianProvider>
  );
}
