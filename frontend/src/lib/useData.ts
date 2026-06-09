import { useEffect, useState } from "react";

// Fetch helper that re-runs when the dependency (e.g. politician id) changes.
export function useData<T>(fetcher: () => Promise<T>, dep: unknown): {
  data: T | null;
  loading: boolean;
  error: string | null;
} {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Don't fetch until the dependency (e.g. politician id) is available.
    if (dep === null || dep === undefined) {
      setLoading(false);
      setData(null);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    fetcher()
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dep]);

  return { data, loading, error };
}
