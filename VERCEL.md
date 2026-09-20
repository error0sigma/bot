# Vercel deployment

This repository can be deployed to Vercel as a Python serverless API. It is suitable for bounded, on-demand discovery requests and a periodic cron trigger.

## Important limitation

Vercel function instances are ephemeral. SQLite files and `/tmp` data do not persist between invocations. The Vercel adapter therefore creates a request-scoped database and returns the snapshot in the response. For durable history, configure `DISCOVERY_SHEETS_WEBHOOK_URL` or replace the storage adapter with an external database/object store.

## Deploy without a local machine

1. Open [Vercel](https://vercel.com/) and sign in with GitHub.
2. Click **Add New → Project**, import `error0sigma/bot`, and select the `main` branch.
3. Vercel should detect `vercel.json`; leave the framework preset as **Other**.
4. Add environment variables under **Settings → Environment Variables**:
   - `CRON_SECRET`: random secret used to protect `/api/cron` and discovery requests.
   - `DISCOVERY_QUERY`: default query for the scheduled job.
   - `GITHUB_TOKEN`: optional GitHub token for API quota.
   - `ENABLE_GITHUB=1` or `0`.
   - `SEARCH_API_URL` and `SEARCH_API_KEY`: optional generic search provider.
   - `DISCOVERY_SHEETS_WEBHOOK_URL`: optional JSON webhook/Google Apps Script endpoint.
   - Optional limits: `DISCOVERY_MAX_DEPTH`, `DISCOVERY_MAX_SOURCES`, `DISCOVERY_MAX_RUNTIME`, `DISCOVERY_CONFIDENCE`.
5. Click **Deploy**.

## Use the API

Replace `YOUR-APP.vercel.app` with the deployment URL:

```bash
curl https://YOUR-APP.vercel.app/api/health
curl -G 'https://YOUR-APP.vercel.app/api/discover' \
  --data-urlencode 'query=Ivan Ivanov' \
  -H 'Authorization: Bearer YOUR_CRON_SECRET'
```

The endpoint returns `entity_id`, execution statistics, and a schema-versioned graph snapshot as JSON. The cron endpoint uses `DISCOVERY_QUERY`:

```text
GET /api/cron
Authorization: Bearer YOUR_CRON_SECRET
```

`vercel.json` schedules it every six hours. Verify the effective cron schedule and plan limits in the Vercel dashboard; scheduled jobs and quotas depend on the current Vercel plan.

## Free option recommendation

For no-cost hosted execution, use GitHub Actions for the durable scheduled worker and Vercel only as the API/demo frontend. Vercel alone is not a durable database or an always-running worker. Do not commit secrets to Git; configure them in Vercel.

The system is intended only for lawful public-source research and does not bypass authentication, paywalls, CAPTCHAs, robots exclusions, or provider terms.
