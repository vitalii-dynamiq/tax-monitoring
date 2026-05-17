import { useEffect, useState } from "react";
import { api, type MonitoringJob } from "../lib/api";

// Session-wide cache so a page rendering many Provenance panels only fetches
// each distinct run once. Cleared when the page reloads.
const cache = new Map<number, MonitoringJob>();
const inflight = new Map<number, Promise<MonitoringJob>>();
const subscribers = new Map<number, Set<(j: MonitoringJob) => void>>();

function notify(id: number, job: MonitoringJob) {
  const subs = subscribers.get(id);
  if (subs) for (const fn of subs) fn(job);
}

async function fetchOnce(id: number): Promise<MonitoringJob> {
  if (cache.has(id)) return cache.get(id)!;
  if (inflight.has(id)) return inflight.get(id)!;
  const p = api.monitoring.getJob(id).then((j) => {
    cache.set(id, j);
    inflight.delete(id);
    notify(id, j);
    return j;
  });
  inflight.set(id, p);
  return p;
}

/** Returns the MonitoringJob for the given id, fetching once and caching. */
export function useRunMeta(id: number | null | undefined): MonitoringJob | null {
  const [job, setJob] = useState<MonitoringJob | null>(
    id ? cache.get(id) ?? null : null
  );

  useEffect(() => {
    if (!id) {
      setJob(null);
      return;
    }
    const cached = cache.get(id);
    if (cached) {
      setJob(cached);
      return;
    }

    let cancelled = false;
    const subs = subscribers.get(id) ?? new Set();
    const handler = (j: MonitoringJob) => {
      if (!cancelled) setJob(j);
    };
    subs.add(handler);
    subscribers.set(id, subs);

    fetchOnce(id).catch(() => {
      /* ignore — keep job null on error */
    });

    return () => {
      cancelled = true;
      subs.delete(handler);
    };
  }, [id]);

  return job;
}
