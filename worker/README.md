# shadow-gasp-bot Worker — which file is authoritative

**`DEPLOYED_BUNDLE.js` is what actually runs. Deploy that, not `worker.js`.**

## Why there are two files

This Worker has been edited directly in the Cloudflare dashboard, so the
readable source in `worker.js` fell behind production and stayed behind.
Measured 2026-08-30:

| file | lines | last changed | status |
| --- | --- | --- | --- |
| `DEPLOYED_BUNDLE.js` | 1469 | 2026-08-18 (version `250d877f`) | **running in production** |
| `worker.js` | 1186 | 2026-08-14 | stale by ~283 lines / 9 functions |
| `worker.js` @ git HEAD before this | 840 | 2026-08-01 | staler still |

Every function in `worker.js` also exists in the bundle, so the bundle is a
strict superset — nothing readable was lost that the bundle does not also
contain. What *was* lost is the comments: 186 comment lines in `worker.js`,
2 in the bundle. For the 9 dashboard-authored functions, no commented source
exists anywhere; the bundle is all there is.

`DEPLOYED_BUNDLE.js` is a build artifact, not hand-written source — esbuild
output, retrieved with `wrangler init --from-dash shadow-gasp-bot`. It carries
injected `__name`/`__name2` wrappers. The presence of *both* wrapper
generations shows the deployed bundle was itself built from an earlier
downloaded bundle, i.e. the download-edit-redeploy cycle has already happened
at least once.

## The trap this exists to prevent

`wrangler deploy` uploads the local file wholesale. Editing `worker.js` and
deploying it would silently revert every dashboard change since 2026-08-14 —
no error, no warning, and the bot keeps answering. That is the root cause
behind this Worker's repeated unexplained regressions.

## Rules

1. Deploy `DEPLOYED_BUNDLE.js`. Never deploy `worker.js`.
2. Before any deploy, re-download the live bundle and diff it against
   `DEPLOYED_BUNDLE.js`. If they differ, someone edited the dashboard again —
   commit the new live version first, then re-apply your change on top.
3. After deploying, commit the exact bytes you deployed.
4. Prefer editing here and deploying over editing in the dashboard. Every
   dashboard edit re-opens this gap.

`worker.js` is kept only as the last readable source, useful for reading the
pre-2026-08-18 logic with its comments intact. It is not deployable as-is.

## Commands

```sh
# re-download the live bundle to compare against this repo
npx wrangler init --from-dash shadow-gasp-bot --no-delegate-c3 -y

# deploy the bundle in this repo (KV binding PENDING comes from wrangler.toml)
npx wrangler deploy DEPLOYED_BUNDLE.js --name shadow-gasp-bot

# confirm what is live
npx wrangler deployments list --name shadow-gasp-bot
```
