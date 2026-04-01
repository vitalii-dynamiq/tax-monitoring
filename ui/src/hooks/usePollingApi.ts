import { useCallback, useEffect, useRef, useState } from "react";

interface UsePollingApiOptions<T> {
  intervalMs: number;
  enabled: boolean;
  stopWhen?: (data: T) => boolean;
}

interface UsePollingApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  isPolling: boolean;
}

export function usePollingApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[],
  options: UsePollingApiOptions<T>,
): UsePollingApiResult<T> {
  const { intervalMs, enabled, stopWhen } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stoppedRef = useRef(false);

  const doFetch = useCallback(() => {
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        setData(result);
        if (stopWhen && stopWhen(result)) {
          stoppedRef.current = true;
          setIsPolling(false);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    stoppedRef.current = false;

    if (!enabled) {
      setIsPolling(false);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Initial fetch
    doFetch();
    setIsPolling(true);

    intervalRef.current = setInterval(() => {
      if (!stoppedRef.current) {
        doFetch();
      }
    }, intervalMs);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setIsPolling(false);
    };
  }, [enabled, intervalMs, doFetch]);

  return { data, loading, error, isPolling };
}
