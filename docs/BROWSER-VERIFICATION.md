# Browser verification

The Playwright suite checks a **fresh checkout's own** Next.js frontend and
FastAPI backend with synthetic fixture data. It never connects to another
machine's running app, uses a tunnel, changes browser security, connects
customer accounts, calls a model, runs generated agent code, or deploys anything.

## Separate evidence layers

- Backend tests validate contracts, transitions and persistence behavior.
- Vitest/Testing Library validates component state with controlled inputs.
- Playwright exercises rendered browser controls against the real local API.
- Fault-injection tests are named accordingly. Mocked errors/empty responses do
  not prove backend execution. Showcase/Social Studio are local displays;
  Performance's trend is explicitly illustrative.

Component tests do **not** establish browser behavior. This suite was initially
authored in an environment where browser launch/local-page access was blocked.
Its first independent CI execution is required before claiming rendered E2E
passes. The matrix below describes coverage targets, not exhaustive proof.

## Run on a permitted isolated test machine

Use Python 3.12+, Node 22 and a fresh checkout with no customer data or external
connector/model credentials. Install the checked-in requirements and npm lockfile.

```sh
python -m pip install -r backend/requirements.txt
cd frontend
npm ci
npx --no-install playwright install --with-deps chromium
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api npm run build
npm run test:e2e
```

Playwright starts both loopback servers and refuses to reuse existing ones.
The backend test launcher uses a disposable SQLite database and recipe output
directory for every run, leaving existing checkout data untouched.
Chromium's sandbox stays enabled. If browser/local-page access is blocked, stop
and report the restriction; do not disable security, alias the target, or tunnel
around it. `npm run test:e2e:list` discovers tests without starting a browser/server.

The standard public Ubuntu 24.04 Actions job uses its preinstalled stable Chrome
through Playwright's supported `chrome` channel with `chromiumSandbox: true`.
Ubuntu's existing AppArmor profile covers that installed Chrome binary. A
fail-fast launch check aborts the job if Chrome or sandbox support is missing;
it does not change AppArmor, sysctl, browser flags, or system security settings.
The initial downloaded headless-shell run failed before page execution with
`No usable sandbox!`; it is not a UI test pass. Local default discovery still
uses Playwright Chromium; set `AUTOPILOT_BROWSER_CHANNEL=chrome` only on a
permitted machine with an existing supported Chrome installation.

References: [supported channels](https://playwright.dev/docs/browsers#google-chrome--microsoft-edge),
[Ubuntu's installed Chrome profile](https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md),
[runner image software](https://github.com/actions/runner-images/blob/ubuntu24/20261004.327/images/ubuntu/Ubuntu2404-Readme.md).

The standard public Actions job has read-only repository permission, disables
persistent checkout credentials, and uses pinned official setup actions. It has
no secret inputs, persistent caches or deployment steps. Normal runs upload
no artifacts; the explicitly approved one-run exception is described below. Existing CI also uses read-only checkout and disables cache use for PR events;
main-push cache behavior is preserved. Normal recording is off. Reports remain
ephemeral except for the bounded one-run recording; normal CI logs show test results. Do not embed media in logs or substitute another storage service.

## UI coverage matrix

| Route/layer | Planned browser checks | Evidence boundary |
| --- | --- | --- |
| `/` | Heading/navigation, seeded counts, viewport fit | Real dashboard API |
| `/archetypes` | Five workflows; refund pending/resolved/replay; invoice failure/recovery; role filter; quarantine; rollback; loading lock; failure/retry; tab/mode interruption; keyboard tabs | Real API happy paths; explicitly injected failures |
| `/distillation` | Redaction, clearing stale preview, declarations gate, recipe generation, model-change invalidation | Local generated files; no model/provider calls |
| `/deploy` | Create/approve/pause/resume/remove records; slider keyboard limit; failure/refresh gate | Records only; no worker started |
| `/processes` | Graph, discovery refresh, node selection | Deterministic fixture discovery |
| `/objects` | Type filters, object selection, trace | Real synthetic object log |
| `/scores` | Real workflows, keyboard selection, empty/error states | Real scores; injected empty/error fixtures |
| `/channels` | Source names, empty/error states | Seeded records; no account sync |
| `/performance` | Created record visibility, chart disclosure | Real records; illustrative trend |
| `/showcase` | Tabs, slider, fixture disclosure | Local illustrative content |
| `/social-deck` | Themes, rejected clipboard behavior | Local content/capability fault injection |
| Shared | All 11 routes desktop/mobile; named collapsed navigation; keyboard; Back/Forward; overflow; uncaught errors; intercepted HTTP(S) request guard | Chromium only; not blanket network isolation |

Component regressions also cover states difficult to create with ordinary seed
data. Do not mark an unexecuted case as passed. Coverage is bounded by the tests,
browser, viewport, inputs and actual CI result. Inspect failed screenshots only
on a separately approved retention/download path. The one-run recording below
uploads only its video/evidence ZIP, never failure screenshots.

## Optional genuine demo recording

`demo.spec.ts` checks actual API responses and visible controls. It shows an
invoice discrepancy, corrects it, then ingests and approves a synthetic refund,
ending with the same ticket ID visibly resolved. It never synthesizes UI success.

With separately reviewed recording/retention, `AUTOPILOT_RECORD_DEMO=1` enables
Playwright video and short readability holds. Normal workflow runs neither enable recording nor upload files. A supported retention/download path must
be cleared before promising a deliverable. Video is usable only after context
shutdown, retrieval and visual inspection. Captions and owner-supplied audio
can then be edited over genuine footage. The tests do not clone a voice.

## Explicit exclusions

Customer connectors, credentials, webhooks, real refunds/messages/infrastructure;
external models, training, deployment, generated LangGraph execution;
authenticated identity, tenant isolation or legal/data-rights certification;
Safari/Firefox, native apps, screen-reader audit, pixel baselines,
performance/load/security audits, and every possible input/interleaving.
No recording of the blocked parent-cloud instance is attempted.

References: [CI](https://playwright.dev/docs/ci-intro),
[multiple web servers](https://playwright.dev/docs/test-webserver#multiple-web-servers),
[videos](https://playwright.dev/docs/videos).

The HTTP(S) browser route guard is a diagnostic, not a network sandbox. Service
Workers are blocked; it does not prove backend/API-client/WebSocket isolation.
All authored API requests use fixed loopback URLs; no external credentials or
provider calls are configured. Review any future integration tests separately.

## Approved one-shot recording

The owner approved up to US$1 attributable recording storage, one artifact of at
most 5,000,000 bytes including archive overhead, and one-day retention. The sole
exception is this repository's PR #8, browser workflow run number 5, attempt 1.
All later runs and reruns keep recording/upload disabled. This is not a general
storage authorization or an account-wide invoice limit.

The completed demo's video and evidence are packaged into one ZIP. The packager
checks the finished ZIP against the exact byte cap before any upload. Official
upload-artifact v7 uses `archive: false`, so it sends that single ZIP unchanged
rather than adding a wrapper. It uses `retention-days: 1` and does not overwrite
or upload any extra artifacts. Failure at any preceding step prevents upload.
No plan, budget, payment credentials, or security settings are changed. If the
one-shot slot is missed or upload is blocked, stop and report rather than widen
the guard or automatically rerun. Verify retained size/expiry and retrieve the
real footage promptly for visual inspection before claiming a video deliverable.

The first recording attempt passed all 46 browser checks but failed the raw
size gate before upload; no artifact was retained. The authorized replacement
uses short captured holds and adds disclosed caption-reading pauses after
retrieval. It logs exact raw size and can compress with already-installed
FFmpeg only; no installer or security change is used for that fallback.
