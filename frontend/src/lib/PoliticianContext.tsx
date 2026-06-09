import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getPoliticians, type Politician } from "./api";

interface Ctx {
  politicians: Politician[];
  selected: Politician | null;
  setSelectedId: (id: number) => void;
  loading: boolean;
  error: string | null;
}

const PoliticianCtx = createContext<Ctx>({
  politicians: [],
  selected: null,
  setSelectedId: () => {},
  loading: true,
  error: null,
});

export function PoliticianProvider({ children }: { children: ReactNode }) {
  const [politicians, setPoliticians] = useState<Politician[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPoliticians()
      .then((ps) => {
        setPoliticians(ps);
        if (ps.length) setSelectedId(ps[0].id);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const selected = politicians.find((p) => p.id === selectedId) ?? null;

  return (
    <PoliticianCtx.Provider value={{ politicians, selected, setSelectedId, loading, error }}>
      {children}
    </PoliticianCtx.Provider>
  );
}

export const usePolitician = () => useContext(PoliticianCtx);
