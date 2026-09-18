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
boundary rule, the browsing-mode stratum, sealed feature windows, and a
full behavioral signal set — all with a build-failing leakage audit and
an online/offline skew test.

**Gate 1 is closed.** A drift-diffusion behavioral simulator, five
archetypes, a per-mode-conditioned generative process, and a LambdaRank
ranker recover *signal rather than noise* from simulated browsing
behavior — a claim that survived a full retraction and rebuild of its
own evaluation bar and negative control before being trusted. See
["The bar was wrong" below](#the-bar-was-wrong-a-negative-control-that-couldnt-fail-and-what-replaced-both)
for why that sentence is the actual headline of this project so far, not
a recovery number. 181 tests, all green.

**Gates 2–3 (the recommender, the ablation harness, the admin console)
are not yet built.** That's the honest state of the project as of this
commit — see `STATE.md` for exactly what's done, what's open, and why,
kept up to date as the build continues.

## The bar was wrong, a negative control that couldn't fail, and what replaced both

This is the most credible result in the repository, and it isn't a
recovery number. It's a diagnostic sequence, and it's presented here
first because it demonstrates more about whether this project's claims
can be trusted than any single metric would.

**What happened, in order:**

1. Gate 1's original Definition of Done required Spearman ρ > 0.6
   between predicted interest and true utility on held-out simulated
   sessions. Three rounds of real engineering — coupling the simulator's
   motor model to its own decision process, adding signals that could
   read *direction* rather than just magnitude of behavior, fixing a
   real polarity bug — moved that number from 0.074 to 0.099 to 0.011.
2. Bootstrapped confidence intervals on those three numbers showed they
   were not statistically distinguishable from how much a "negative
   control" moved over the same three iterations. Read plainly: **three
   iterations of engineering were steering on a number that couldn't
   tell signal from noise.**
3. Checking the negative control itself found the actual bug: it
   permuted which item a behavior belonged to and then evaluated
   against that *same* permutation — a self-consistent replay under a
   relabeled catalog, not a test that could ever detect leakage. It had
   never been capable of failing.
4. A ceiling analysis (three oracle probes: perfect features against the
   true utility, perfect features against the actual weak label, real
   features against true utility) found the deeper problem: **the 0.6
   bar sat above what the pipeline's own label can support even with a
   perfect model** — a perfect feature against the real commitment
   label tops out around 0.33 per-session ρ. The bar was unreachable,
   not demanding.

**What replaced both:** the fixed-magnitude bar was retracted. Gate 1
now closes on a non-overlap test — the real condition's confidence
interval must not overlap a *corrected* negative control's (predictions
held fixed, only the evaluation target shuffled, so any nonzero result
under the shuffle is leakage by construction) — paired with an
*efficiency* number (achieved performance relative to the measured
ceiling, not against an arbitrary target). Retroactively, all three
historical iterations pass the corrected gate; the pipeline likely had
recoverable signal from very early on, and no tool available at the time
could see it.

**The actual result, at the fixed evaluation settings (625/625
sessions):**

| | achieved | ceiling | efficiency | gate |
|---|---|---|---|---|
| Interest ranking (per-session ρ) | 0.088 [0.059, 0.119] | 0.497 [0.456, 0.535] | 0.178 | pass — CI vs. negative control [-0.032, 0.016] does not overlap |
| Archetype separation (accuracy) | 0.363 [0.326, 0.400] | 0.518 [0.480, 0.555] | 0.513 | pass — CI vs. chance-level control [0.174, 0.238] does not overlap |

Full sequence, every number, and the exact code for the corrected
negative control: `STATE.md`'s "Gate 1 closes" section.

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
  models/    taste vector (Gate 1); profile updater (Gate 2, not yet built)
  recommender/  candidate gen, rerank, ablation (Gate 2, not yet built)
sim/         behavioral simulator: five archetypes, drift-diffusion + motor coupling (Gate 1, done)
eval/        corpus, ranker, signal-weighting recovery, negative control, ceiling probes, diagnostics (Gate 1, done)
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
> **What this does not show yet.** Recommendations, an ablation over the
> behavioral signal families, or anything about real (non-simulated)
> shoppers — the recommender and the ablation harness (BUILD_BRIEF.md
> §12) are not built. There is no latency number to report because there
> is no real-time scoring path deployed yet. This README will be updated
> with those numbers once they exist, not before. The ranker recovery
> numbers above (efficiency 0.178 for interest ranking, 0.513 for
> archetype separation) are the honest, ceiling-relative headline —
> see ["The bar was wrong"](#the-bar-was-wrong-a-negative-control-that-couldnt-fail-and-what-replaced-both)
> for why a fixed target number isn't reported instead. Browsing mode's
> measured contribution to a future ablation will be partly a
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
