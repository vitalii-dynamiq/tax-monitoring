"""
Bulk discovery: run sub-jurisdiction discovery for countries via the API.

Usage:
    python -m scripts.run_bulk_discovery --countries CA,IN,CH
    python -m scripts.run_bulk_discovery --all --batch-size 5 --delay 10
    python -m scripts.run_bulk_discovery --retry-failed
"""

import argparse
import asyncio
import sys
import time

import httpx


class DiscoveryRunner:
    def __init__(self, api_base: str, api_key: str):
        self.api_base = api_base
        self.headers = {"X-API-Key": api_key}

    def url(self, path: str) -> str:
        return f"{self.api_base}{path}"

    async def get_countries_needing_discovery(self, client: httpx.AsyncClient) -> list[str]:
        resp = await client.get(self.url("/v1/jurisdictions"), params={"limit": "500"})
        resp.raise_for_status()
        all_j = resp.json()
        countries = [
            j for j in all_j
            if j["jurisdiction_type"] == "country" and j["code"] != "TEST-PERSIST"
        ]
        child_roots = {j["path"].split(".")[0] for j in all_j if j["jurisdiction_type"] != "country"}
        return sorted(c["code"] for c in countries if c["code"] not in child_roots)

    async def get_failed_countries(self, client: httpx.AsyncClient) -> list[str]:
        resp = await client.get(
            self.url("/v1/monitoring/discovery/jobs"),
            params={"status": "failed", "limit": "500"},
        )
        resp.raise_for_status()
        return sorted({j["jurisdiction_code"] for j in resp.json() if j.get("jurisdiction_code")})

    async def trigger(self, client: httpx.AsyncClient, code: str) -> int | None:
        try:
            resp = await client.post(self.url(f"/v1/monitoring/discovery/{code}/run"))
            if resp.status_code == 202:
                return resp.json()["id"]
            elif resp.status_code == 409:
                print(f"    {code}: skipped (job already running)")
            elif resp.status_code == 503:
                print(f"    {code}: skipped (AI not configured)")
            else:
                print(f"    {code}: error {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            print(f"    {code}: request failed - {e}")
        return None

    async def poll(self, client: httpx.AsyncClient, job_id: int, code: str, timeout: int) -> dict:
        start = time.monotonic()
        last_status = ""
        while time.monotonic() - start < timeout:
            try:
                resp = await client.get(self.url(f"/v1/monitoring/jobs/{job_id}"))
                job = resp.json()
                status = job.get("status", "unknown")
                if status != last_status:
                    print(f"    {code} (job {job_id}): {status} [{int(time.monotonic() - start)}s]")
                    last_status = status
                if status in ("completed", "failed", "cancelled"):
                    return job
            except Exception as e:
                print(f"    {code}: poll error - {e}")
            await asyncio.sleep(10)
        return {"status": "timeout", "error_message": f"Timed out after {timeout}s"}

    async def run_batch(self, client: httpx.AsyncClient, codes: list[str], timeout: int) -> dict[str, dict]:
        jobs = {}
        for code in codes:
            job_id = await self.trigger(client, code)
            if job_id:
                jobs[code] = job_id
        if not jobs:
            return {}

        async def poll_one(c, jid):
            return c, await self.poll(client, jid, c, timeout)

        results = await asyncio.gather(*[poll_one(c, j) for c, j in jobs.items()])
        return dict(results)

    async def run(self, countries: list[str], batch_size: int, delay: int, timeout: int):
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            try:
                h = (await client.get(self.url("/health"))).json()
                print(f"API: {h.get('status')} | DB: {h.get('database')} | AI: {h.get('ai_configured')}")
                if not h.get("ai_configured"):
                    print("ERROR: ANTHROPIC_API_KEY not configured.")
                    return
            except Exception as e:
                print(f"ERROR: Cannot reach API: {e}")
                return

            batches = [countries[i:i + batch_size] for i in range(0, len(countries), batch_size)]
            print(f"\nPlan: {len(countries)} countries in {len(batches)} batches of {batch_size}")
            print(f"Countries: {', '.join(countries)}\n")

            success = failed = total_discovered = 0
            failed_list = []
            t0 = time.monotonic()

            for i, batch in enumerate(batches):
                print(f"[Batch {i+1}/{len(batches)}] {', '.join(batch)}")
                results = await self.run_batch(client, batch, timeout)

                for code, result in results.items():
                    status = result.get("status")
                    summary = result.get("result_summary") or {}
                    if status == "completed":
                        success += 1
                        created = summary.get("jurisdictions_created", result.get("changes_detected", 0))
                        total_discovered += created
                        print(f"  >> {code}: {created} sub-jurisdictions created")
                    else:
                        failed += 1
                        failed_list.append(code)
                        print(f"  >> {code}: FAILED - {result.get('error_message', '?')[:100]}")

                if i < len(batches) - 1:
                    print(f"  (waiting {delay}s...)\n")
                    await asyncio.sleep(delay)

            elapsed = int(time.monotonic() - t0)
            print(f"\n{'='*60}")
            print(f"DONE in {elapsed}s | OK: {success} | FAIL: {failed} | Discovered: {total_discovered}")
            if failed_list:
                print(f"Failed: {', '.join(failed_list)}")
                print(f"Re-run: python -m scripts.run_bulk_discovery --countries {','.join(failed_list)}")
            print(f"{'='*60}")


def main():
    p = argparse.ArgumentParser(description="Bulk jurisdiction discovery")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--countries", help="Comma-separated codes")
    g.add_argument("--all", action="store_true", help="All countries needing discovery")
    g.add_argument("--retry-failed", action="store_true", help="Re-run failed jobs")
    p.add_argument("--batch-size", type=int, default=3)
    p.add_argument("--delay", type=int, default=10)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--api-url", default="http://localhost:8001")
    p.add_argument("--api-key", default="dev-api-key-change-me")
    args = p.parse_args()

    runner = DiscoveryRunner(args.api_url, args.api_key)

    async def resolve_and_run():
        async with httpx.AsyncClient(headers=runner.headers, timeout=30) as client:
            if args.countries:
                codes = [c.strip().upper() for c in args.countries.split(",")]
            elif args.retry_failed:
                codes = await runner.get_failed_countries(client)
                if not codes:
                    print("No failed jobs found.")
                    return
            else:
                codes = await runner.get_countries_needing_discovery(client)
                if not codes:
                    print("All countries already have sub-jurisdictions!")
                    return
        await runner.run(codes, args.batch_size, args.delay, args.timeout)

    asyncio.run(resolve_and_run())


if __name__ == "__main__":
    main()
