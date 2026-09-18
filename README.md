# PRISM

An instrumented storefront that infers browsing interest from behavioral
signals in real time. A research prototype, not a real store — see
[Honesty section](#honesty-section) below before anything else.

![Home](docs/screens/home-1440.png)

## What this is, right now

**Gate 0 is complete.** A 750-item context catalog + 60-item instrumented
core, sourced from [Amazon Berkeley Objects](https://registry.opendata.aws/amazon-berkeley-objects/)
with every brand string scrubbed from served text; a full storefront IA
(home, category, search, detail, compare, cart, checkout stub); a
consent-gated browser telemetry SDK emitting all 25 event types over
WebSocket; idempotent ingest into Postgres with live session state in
Redis; a `features/` library implementing the canonical item-view
boundary rule, the browsing-mode stratum, sealed feature windows, and the
eight Gate 0 signals — all with a build-failing leakage audit and an
online/offline skew test. 98 tests, all green.

**Gates 1–3 (the ranker, the simulator, the recommender, the ablation
harness) are not yet built.** That's the honest state of the project as
of this commit — see `STATE.md` for exactly what's done, what's open, and
why, kept up to date as the build continues.

## Screens

| | |
|---|---|
| Consent gate | ![Consent](docs/screens/consent-1440.png) |
| Category | ![Category](docs/screens/category-1440.png) |
| Search | ![Search](docs/screens/search-1440.png) |
| Product detail | ![Detail](docs/screens/detail-1440.png) |
| Compare | ![Compare](docs/screens/compare-1440.png) |

More surfaces, empty/loading states, and the 768px layouts are in
[`docs/screens/`](docs/screens/).

## Architecture

```
catalog/     ABO ingest, brand masking, synthetic attributes, thumbnails
sdk/         browser telemetry (TypeScript, framework-agnostic)
web/         React storefront
server/
  ingest/    WebSocket + HTTP endpoints, Postgres + Redis
  features/  window-spec'd signal functions — the leakage-critical module
  models/    ranker + profile updater (Gate 1, not yet built)
  recommender/  candidate gen, rerank, ablation (Gate 2, not yet built)
sim/         behavioral simulator (Gate 1, not yet built)
eval/        replay, recovery metrics, ablation reports (Gate 2, not yet built)
tests/
```

`server/features/` imports nothing from `ingest`, `models`, or
`recommender` — enforced by `import-linter`, not just convention (see
`pyproject.toml`).

The single most load-bearing piece of the whole project is
`server/features/item_view.py`: one function, unit-tested against six
required hand-built visibility timelines, that decides what counts as a
"view" and therefore everything downstream measures. Next to it,
`server/features/mode.py` implements the browsing-mode stratum — the
brief's central modeling claim that dwell time means opposite things in
directed search versus discovery browsing, so mode is a stratum you
calibrate and report separately per §4, never a pooled feature column.

## Running it locally

```powershell
# Postgres + Redis
docker compose up -d

# Python backend
uv venv .venv
uv pip install -e ".[dev]"
.venv\Scripts\python.exe -m uvicorn server.main:app --port 8000

# Catalog (first run only — pulls from the public ABO S3 bucket, ~90MB
# metadata + ~200MB of resized thumbnails, both gitignored)
.venv\Scripts\python.exe -m catalog.build

# Frontend
cd web
npm install
npm run dev
```

Copy `.env.example` to `.env` first — the defaults already match
`docker-compose.yml`.

### Tests

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q
```

### The manual gate

Gate 0's Definition of Done includes one check that's the author's to do,
not the agent's: browse a session, open the raw event log, and confirm
by hand that view boundaries and modes match what actually happened. The
tool for that is live at `/admin/session` — paste the session code shown
in the site footer, or a session_id, to see the raw event log next to
the offline-recomputed canonical views and modes side by side.

## Honesty section

> **What this shows.** A real-time pipeline from raw browsing behavior to
> a durable, idempotent event log, over a 750-item catalog with a full
> e-commerce IA. Browsing mode is modeled as a stratum from the start,
> because dwell time means opposite things in directed search and in
> discovery browsing. The canonical item-view boundary rule, the sealed
> feature windows, and the leakage audit are built and tested before any
> model exists to leak into — that ordering is deliberate.
>
> **What this does not show yet.** Calibrated interest estimates,
> recommendations, or anything about behavioral archetypes — the ranker,
> the simulator, and the recommender (BUILD_BRIEF.md §§11–13) are not
> built. There is no latency number to report because there is no
> real-time scoring path yet. This README will be updated with those
> numbers once they exist, not before. Once a ranker ablation exists:
> browsing mode's measured contribution to it will be partly a
> consequence of how the simulator itself was parameterized (see
> `STATE.md`'s per-mode DDM priors) — those per-mode priors are stated
> modeling assumptions about shopper behavior, not measured facts, so an
> ablation result attributing signal to mode should be read as "the
> simulator's stated hypothesis about mode was recoverable," not as
> independent evidence that the hypothesis is true of real shoppers. The
> simulator also assumes motor output (cursor trajectories, scroll
> pacing) is coupled to the evolving decision state as it accumulates,
> not independent of it, per the mouse-tracking literature (Leontyev &
> Yamauchi 2021, §16) — that assumption is what makes recovering interest
> from behavior possible at all. It is an assumption the simulator is
> built on, not a finding this project has demonstrated. Two directional
> motor signals were added only after diagnosing that the original
> eighteen-signal set — despite the coupling above making direction
> mechanistically real in the simulated data — measured only the
> magnitude and shape of behavior (how long, how fast, how curved) and
> nothing about *which* of two on-screen destinations a trajectory leaned
> toward; see STATE.md for the finding in full, including that the two
> new signals individually correlate with the outcome far more than
> anything else measured so far.
>
> **Fabricated content.** Product images derive from Amazon Berkeley
> Objects under CC BY-NC 4.0 and some show manufacturer logos on
> packaging — that's an accepted, licensed residual case (see `NOTICE`
> and `BUILD_BRIEF.md` §5.3), not an oversight. All brand names in the
> listing text are invented; prices, ratings and reviews are generated
> and labeled as such in the interface. Nothing here describes a real
> product, and this site is not affiliated with any retailer and copies
> no retailer's identity.
>
> **On inferring intent from motor behavior.** Cursor position is a weak
> proxy for attention: inactive over half the time, lagging gaze by
> roughly 700ms, with large individual variation. Mouse dynamics are also
> re-identifiable, which is why telemetry here is consent-gated,
> pseudonymous and deleted after 90 days (and on request — see
> `/delete-my-data`).

## License

No `LICENSE` file has been chosen yet for this repository's own code —
that's the author's call to make, not the agent's, and is flagged as an
open item in `STATE.md`. `NOTICE` has the full ABO attribution and the
dataset's CC BY-NC 4.0 terms, which apply to the catalog imagery/metadata
only, never to the code.
