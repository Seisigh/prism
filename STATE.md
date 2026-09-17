# PRISM — build state

Read this alongside `BUILD_BRIEF.md` before doing anything else in a new
session. This file is updated after each module, not at the end.

**Current gate:** 0 complete. Gate 1 started (simulator + taste vector built and tested; ranker/calibration/profile-updater wiring not yet).
**Repo:** https://github.com/Seisigh/prism (private)
**Deployment: blocked on the author's action** — see "Deployment" section near the end. Everything needed is prepared and locally verified (Dockerfile builds clean, container runs and serves correctly); it needs an authenticated `flyctl` session, which the agent cannot create.

---

## Done

### Catalog pipeline (`catalog/`)

Real data, not a stub: pulled from the live ABO public S3 bucket
(`amazon-berkeley-objects`), filtered to US/English/branded/imaged
listings (23,231 valid candidates out of ~24.8k US listings), and built
into a 750-item context catalog + 60-item instrumented core.

- `download.py` — fetches all 16 `listings_*.json.gz` shards + `images.csv.gz`, cached under `data/raw/` (gitignored, ~90MB).
- `taxonomy.py` — hand-authored `product_type -> {category, verticals, gender, age_band}` map, built against the *real* distribution of valid US listings (see "ABO coverage reality" below). `infer_gender`/`infer_age_band` refine the default from keyword signal in title/keywords text (e.g. a SHOES listing defaults `gender=womens` per corpus skew, but flips to `mens` when the listing's own keywords say so).
- `brands.py` — invented brand pool (150 names, `value`/`standard`/`premium` tiers, deterministic per item via hash of source item_id) + `strip_known_brand_strings` (removes the item's own ABO brand string + a ~150-entry real-brand denylist, whole-word, case-insensitive) as defense in depth over bullet-point text.
- `titles.py` — titles generated **only** from `product_type` + structured attributes (material/style/pattern/color/dimensions), never from ABO's `item_name` (which is brand-dense — e.g. "Amazon Brand - find. Women's..."). Filters SKU-looking style codes (`Um1530`) out of the descriptor slot; falls back to a scrubbed keyword when there's no color/material/style at all, so a title never silently reduces to a bare noun when better text exists in the listing.
- `descriptions.py` — **no LLM configured in this environment**, so §5.4's "LLM normalization pass" is a deterministic rule-based sentence assembler instead (bullets → template sentences → padded/trimmed to a target character band). Drop-in swap point if an LLM key gets added later — the band contract (`short`/`medium`/`long` char ranges) doesn't change.
- `synth_attributes.py` — §5.6 distributions: log-normal price per category with `.99`/`.95` snapping, beta-skewed ratings (mean ~4.3), Pareto-tailed review counts, 35% anchor-price rate, mostly-in-stock/rarely-out-of-stock.
- `core_sets.py` — 12 near-substitute sets of 5 items each (60 total), one product_type per set (`CHAIR`, `SOFA`, `TABLE`, `LAMP`, `RUG`, `SHOES`, `BOOT`, `PILLOW`, `EARRING`, `PLANTER`, `BACKPACK`, `COFFEE`), one controlled attribute varied per set, rotating through all 5 axes in §5.4 (price / rating_count / description_length / gallery_size / copy_framing).
- `images.py` — main image fetched from `images/original/` (real resolution, for detail/zoom), gallery images from `images/small/` (navigation thumbnails only). **Contain-fit, not cover-crop** — see "decision" below. Resized to grid (480²) / detail (900²) / zoom (1800 max) WebP, saved to `data/thumbs/<item_id>/` (gitignored, ~198MB, not committed).
- `build.py` — orchestrator: `python -m catalog.build` → `data/catalog.json` (gitignored build artifact; server seeds from it). Parallel image fetch (16 workers), idempotent (skips already-resized thumbnails), ~24s on a warm cache / ~170s cold.
- Spot-check (§5.3.3): built a 50-item random contact sheet (`data/spotcheck_*.png`, not committed) and inspected it directly (visible logos on grocery packaging — `amazonbasics`, `365`, `Whole Paws`, `wag` — are exactly the accepted residual case in §5.3: incidental photo, no brand named in text). **Zero items where the product is its branding** (no jerseys, logo mugs, monogram goods) in the sample; none needed dropping.
- `tests/catalog/` — 20 tests, including a build-failing integration scan (`test_no_leaked_brands.py`) that reads the actual `data/catalog.json` and checks every served text field (title, description, brand, bullets, spec values) of all 810 items against the real-brand denylist. All pass.

### Decisions made and why

- **Core (60) is disjoint from context (750), not a labeled subset.** §12 scopes the recommender's candidate generation to "the context catalog," which only makes sense if core is a separate pool. Total unique catalog = 810 items. Both browsable/searchable/logged identically; core additionally gets the §5.7 placement boost.
- **Contain-fit thumbnails, not cover-crop.** First pass used cover-crop and it cut the top/bottom off tall narrow products (a drinking glass lost its rim and base). Switched to fit-within-canvas + white padding — matches "fixed aspect-ratio containers" in §6.5 without ever cropping the product.
- **Gender inferred from listing keywords, not just product_type default.** Initial pass had 0 `mens` items because SHOES/BOOT/SANDAL/etc. all defaulted to `womens` (matches real corpus skew — ABO's US apparel listings for these types skew heavily women's) with no men's split. Added keyword-based override so genuinely men's-labeled listings (10 of them, real corpus count) show up as such rather than being silently absorbed.
- **No LLM for description normalization** (see `descriptions.py` above) — no API key configured in this build environment.

### ABO coverage reality (§5.2 target vs. what the data supports)

ABO is a furniture/home/apparel/grocery/beauty-heavy dataset. §5.2 asks for
"roughly 15-25 items per cell" across 10 interest verticals × gender ×
age-band, and says up front "thin for measurement, correct for context" —
this was clearly anticipated. Actual vertical coverage in the 750-item
context catalog:

```
cooking 88, pets 44, travel 44, fitness 44, gardening 40, music 39,
reading_study 38, outdoors_camping 33, gaming 11, crafts 9
```

`gaming` and `crafts` are thin because ABO genuinely has almost no
inventory there (10 `VIDEO_GAME_ACCESSORIES` + a handful of puzzles/toys
across the whole 24.8k-listing US corpus). Padding these with
near-duplicate filler to hit a number would be worse than an honest gap —
not done. Category coverage is even (43-44 per category, 18 categories)
except `Toys & Games` (14, real supply limit) and `Music` (37).
Gender: 668 unisex / 72 womens / 10 mens (apparel/jewelry types are a
small slice of ABO and skew heavily womens in the source data).

---

## Open items flagged during catalog build (not blockers, logged for follow-up)

1. A handful of titles still read as a bare noun (`"Shoes"`, `"Hat"`,
   `"Luggage"`) when the source listing has no color/material/style *and*
   no usable keywords — rare, cosmetic, not a safety issue.
2. Compound style values like `"Basil-1W501"` (a real descriptor fused to
   a SKU suffix in one field) aren't split — the SKU-code filter only
   catches when the *whole* field value looks like a code. Affects a
   small number of Shoes titles. Cosmetic.
3. `catalog/build.py` calls `iter_candidates()` twice (once inside
   `select.build_catalog()`, once in `build.py` for the image-fetch pass)
   — reparses the 16 shards twice, ~7s wasted per build. Not worth fixing
   given build already runs in <30s warm.

---

## Storefront (`web/`) — done

Every §6 surface built, styled from `web/src/styles/tokens.css` (§6.0 + §6.5
tokens as CSS custom properties, one file), and run through the §6.6
screenshot review loop at 1440 and 768 — minimum two passes each, real
defects found and fixed (not just cosmetic nitpicks). Final screenshots in
`docs/screens/` (20 images: every surface × both breakpoints, plus the
required empty/declined/building profile states).

- Stack: Vite + React 19 + TS, `react-router-dom`, `lucide-react`, hand-written CSS Modules per component (no Tailwind — wanted full control over the dense-commerce aesthetic rather than utility-class defaults). Design direction: instrument-grade dense catalog — left-aligned grids, borders over shadows, tabular numerals, single indigo accent, spectrum strictly confined to the profile panel (confirmed nowhere else in the UI).
- Surfaces: consent gate (split ink/white layout — first version was a generic centered card, rebuilt), persistent banner, header (search + scoped category select + autocomplete + account/wishlist/cart stubs), category nav strip, home (hero carousel + category cards + rails), category page (facets + sort + grid), search (distinct sponsored strip above organic results per §6.0, not just badges mixed into the grid — first version had this wrong), product detail (gallery with hover-zoom + thumbnail strip, buy box, spec table, rating histogram, reviews, two rails), compare view, cart, checkout stub (confirms, charges nothing, clears cart), what-gets-recorded (data dictionary table generated from `web/src/lib/eventSchema.ts`, the same schema the SDK will import — can't drift out of sync), delete-my-data, 404.
- `server/main.py` + `server/catalog_store.py` — FastAPI serving `/api/home`, `/api/category/{c}`, `/api/search`, `/api/autocomplete`, `/api/items/{id}`, `/api/items/{id}/similar`, `/api/items/{id}/also-viewed`, `/api/compare/{set_id}`, static thumbs at `/media/thumbs/`. Rail responses carry `policy_id: "popularity_fallback"` or `"category_price_proximity_fallback"` so this bootstrap ranking can never later be mistaken for Gate 1's trained recommender. `X-Robots-Tag: noindex, nofollow` on every response (defense in depth; the SPA's `<meta name="robots">` is primary).

### Real bugs found and fixed during the review loop (not just polish)

1. **Infinite React re-render loop opening the profile panel** — `SessionContext`'s `setDemo`/`accept`/`decline` callbacks depended on `state`, so their identity churned every render; `ProfilePanel`'s `useEffect(() => setDemo(true), [open, setDemo])` then re-fired every time `setDemo` got a new identity, calling `setDemo(true)` again, forever, until React's "Maximum update depth exceeded". Fixed by making `persist` take a functional updater and giving every derived callback a stable identity (see `web/src/state/SessionContext.tsx`). This would have broken the profile panel for every real visitor — the most serious bug caught this session.
2. Two empty-state "clear filters"/"clear search" buttons were reusing the `<select>` dropdown's CSS class and rendered a stray, non-functional chevron icon.
3. Facet rail kept its fixed 240px desktop width when the layout collapsed to a single column below 900px, leaving a large dead gray gap.
4. Compare view showed "Brand" as a row twice (once as a dedicated row, once again from the spec table, which also carries a Brand key).
5. Spec table dimensions/weight rendered glued to their unit ("31inches") with no space, and using the verbose unit name instead of an abbreviation.
6. Synthetic reviews could repeat the identical sentence back-to-back (`generate_review_texts` sampled with replacement from a 3-5-phrase pool); fixed to sample without replacement per item.
7. Individual review star ratings announced "0 reviews" to screen readers even though `showCount` was false and no count applied.
8. Category nav strip is horizontally scrollable with no visual hint it truncates — added a fade mask.
9. §7.3/COPY §9's reduced-capture notice for touch/narrow viewports was speced but never wired up — added, gated on `(hover: none) and (pointer: coarse) and (max-width: 767px)` so a narrow desktop window doesn't wrongly show it.

### Known non-bugs (investigated, ruled out)

- Screenshot-only "blank" images in `fullPage` captures — native `loading="lazy"` hadn't fired yet at capture time; confirmed via DOM (`img.complete`) that real scroll+wait loads them fine.
- Perceived blue-tinted body text on the consent gate — confirmed via `getComputedStyle` that all three paragraphs are identical `rgb(90,97,110)`; a PNG-compression artifact, not a real color difference.
- Some catalog items show real manufacturer logos on grocery packaging (`amazonbasics`, `365`, `Wag`) — this is the accepted residual case in §5.3 (incidental photo, no brand named in text), not a leak. Verified via the automated `test_no_leaked_brands.py` scan of all 810 items' served text.

## `server/features/` — done (the leakage-critical module)

Pure Python, zero imports from `ingest`/`models`/`recommender` (enforced
by `import-linter`, part of `pyproject.toml`, run via `lint-imports` — see
"features has no upward imports" contract, currently **kept**). 89 tests,
all passing.

- `item_view.py` — the canonical view function (§8). All 6 required fixtures pass (simple open/close, merge-gap, multi-surface tie, tab-blur mid-view, rapid-scroll sub-threshold, mode-assigned-once-at-open), plus extras (below-threshold never opens, gap>=500ms doesn't merge, navigation force-close). Multi-surface attribution: pointer focus at the overlap's start wins; no focus signal falls back to surface depth (`detail > compare > grid > rail`). Mode assignment is injected as a callback (`ModeResolver`) rather than imported, so this module's tests stay free of mode-precedence fixtures and vice versa — see its docstring for why.
- `mode.py` — §4 browsing-mode stratum. `assign_mode` enforces the full precedence (`refind > comparison > directed_search > broad_search > discovery`); `classify_query_tokens` resolves the §4.1 ambiguity flagged at kickoff (model-token regex `/^[a-z]{0,4}-?\d+[a-z0-9-]*$/i`, mirrors `catalog/titles.py`'s SKU heuristic — same judgment, same shape of evidence).
- `window_spec.py` — `WindowSpec` is `[t_start, t_end)`, half-open, `t_end` exclusive so an event *at* the seal is never admitted. `seal_window_for_view` implements §9.1's truncate-at-first-commitment-minus-1000ms rule, clamped so it never produces a negative-length window (collapses to zero length instead — every signal must degrade to `None` there, and does, tested explicitly).
- `signals.py` — all 8 Gate 0 signals (§9.3), each `f(events, window, ctx) -> float | None`, each reading only through `events_in_window` (never `events` directly). Touch `pointer_type` gates the whole motor-signal family off (hover, velocity, curvature, x-flips) per §7.3, tested explicitly.
- `labels.py` — the Tier-1 weak label (§9.1, deliberately session-wide and NOT window-sealed — it's the prediction target, not a feature) and `is_fast_skip` (§9.3 item 8 — "the negative-class definition, not a feature," kept out of `SIGNAL_REGISTRY` on purpose). The fast-skip threshold is a documented placeholder (`FAST_SKIP_THRESHOLD_MS_DEFAULT`) — §9.5 wants it fit from a real exposure distribution, which doesn't exist yet at this point in the build (no simulator, no deployed traffic); flagged here and in the original preflight list as a Gate 1 follow-up, not silently treated as final.
- `resample.py` — §7.3's 60Hz linear-interpolation resampling, tested for cross-rate agreement (two synthetic "browsers" sampling the same motion at ~120Hz and ~30Hz land within 5% of each other post-resample).
- `normalize.py` — `z_score`, the within-(session, mode, surface) half of §4.2's dwell normalization. The "centered within item" half needs cross-session per-item baselines, which is session-store aggregation state that belongs to `server/ingest`, not a pure-function module — not implemented yet, flagged rather than half-built.
- `tests/features/test_leakage.py` — the build-failing audit (§10.8), table-driven over `SIGNAL_REGISTRY`: for every signal, injects "poison" events at and after the seal shaped to swing the output hard (a 999999px pointer jump, a full-page scroll, an hour-long hover) and asserts the output is unchanged. A companion test guards against a vacuous pass (every signal must produce a real, non-None value on the baseline, so "blind to poison" can't be confused with "blind to everything").
- `tests/features/test_invariance.py`, `test_resample.py` — §15 items 7 and 8 (curvature rotation-invariance, z-score scale-invariance, dwell monotonicity, resampling tolerance).

## `sdk/`, `server/ingest/`, event-log viewer, skew test — done

Real, working, end-to-end telemetry, verified against the actual running
app in a real browser (not just unit-tested in isolation) — accepted
consent, browsed categories, opened a detail page, added to cart,
filtered, sorted, and confirmed every single one of §7.2's 25 event types
actually lands in Postgres with the right shape, then confirmed Redis
carries real live session state too. Full pipeline: `web/` → `sdk/` →
WebSocket → `server/ingest` → Postgres (durable log) + Redis (live
state) → `server/features/replay.py` (offline recompute) → the
event-log viewer.

- `sdk/` (`sdk/src/`) — framework-agnostic TS package (§3), aliased into `web/` via a Vite/tsconfig path mapping (`@prism/sdk` → `sdk/src/index.ts`) rather than a build step, since both live in this one repo. `transport.ts` handles the WS connection (250ms flush, `sendBeacon` fallback on `pagehide`, bounded queue that drops the oldest entry under backpressure rather than growing unboundedly — §7.4). `pointerTracker.ts`/`scrollTracker.ts` do rAF-gated, coalesced-event sampling into delta-encoded batches. `itemVisibility.ts` is deliberately naive — raw IntersectionObserver 50%-threshold crossings only, no merge/300ms logic; `server/features/item_view.py` is the one canonical source of truth for real view boundaries (§8), computed offline from this raw stream, never duplicated client-side. `mode.ts` mirrors `server/features/mode.py`'s rules so the SDK can attach `mode` to each envelope in real time (the "online" path the skew test compares against).
- `server/ingest/` — Postgres schema (`sessions`, `events`, idempotent on `event_id` via `ON CONFLICT DO NOTHING`), WebSocket + HTTP (`/api/events`, the `sendBeacon` target) endpoints, `DELETE /api/sessions/{code}` (cascades to events), `GET /api/sessions/by-code/{code}`. `session_state.py` is real, live Redis state (not a stub) — a session-active flag with a rolling 30-minute TTL matching §4.1a's idle-timeout boundary, and a live view counter backing "sessions with <3 views are excluded from normalization fitting," both verified against the real docker-compose Redis.
- `server/features/replay.py` — offline recomputation: raw stored events → canonical views + modes, using the *exact same* `item_view.py`/`mode.py` functions the fixture tests exercise. Backs both the event-log viewer and the skew test. One documented simplification: §7.2 has no persisted event type for "category nav click" (only the SDK's in-memory tracker sees it), so the offline path proxies it with a `page_view` on the `category` surface — right in the common case (arriving via the nav strip), not exhaustive (e.g. browser back). Logged as a real, small skew source rather than assumed away.
- `GET /api/sessions/{id}/views` + `web/src/pages/Admin/SessionViewer.tsx` (`/admin/session`) — **the Gate 0 manual gate tool.** Paste a code or session_id, see the raw event log and the recomputed canonical views/modes side by side. Not part of the polished consumer storefront (no nav link, no §6.6 review pass — it's a diagnostic, not a customer-facing surface) and has no admin auth yet (flagged below).
- `tests/ingest/test_skew.py` — §10.9's skew test: a hand-scripted session exercising all five modes (including the query-expiry-via-category-nav-click edge case) run through `replay.py`, compared against the mode each event claims to have been assigned online. Reports a continuous skew rate (currently 0.0) rather than just asserting a boolean, per the brief.

### Real bugs found while building this against the actual live app (not just unit tests)

1. **jsonb payload roundtrip** — asyncpg doesn't auto-serialize Python dicts for `jsonb` columns; needed an explicit type codec (`set_type_codec` in `db.py`) or every insert threw `TypeError: expected str, got dict`.
2. **A still-open view collapsed to zero duration.** `item_view.py`'s raw-run builder used a run's *own* last sample as its "still open" end time — correct when there's a real closing sample, wrong when there's only one sample (e.g. reading a session's log while an item is still visible, no `view_end` yet), where it collapsed to a zero-length run and silently vanished. Fixed by threading a separate `open_run_horizon` (the latest timestamp observed anywhere in the input) through — kept deliberately distinct from `session_horizon` (only ever set by an explicit caller) so an ordinary visibility-timeout close a few hundred ms before the last observed event doesn't get mislabeled `closed_by: "session_end"`. Caught by testing the event-log viewer against a real live session, not by a unit test — added as a regression fixture (`test_still_open_single_sample_view_extends_to_the_observed_horizon`) afterward.
3. **`rec_impression` double-fired under React StrictMode's dev double-invoke.** Fixed with a dedupe set inside the SDK instance keyed on `(rail_id, slate)`.

### Known gaps, flagged rather than silently skipped

- **No admin auth on `/admin/session`.** Acceptable for now (site isn't deployed publicly yet, whole app is noindex + consent-gated), not acceptable to ship deployed without a real auth wall — needs one before the repo goes public per the kickoff instructions' own privacy gate.
- **§10.11's 90-day retention purge (`purge_expired_sessions`) isn't wired to a scheduler.** No cron/deployment scheduler exists yet at this point in the build.
- **The skew test uses a hand-scripted fixture, not a replayed real session**, because there's no deployed traffic yet to pull a real session from. A live-traffic version is a Gate 1+ follow-up once the site is actually deployed and has sessions to replay.
- **The category-nav-click proxy in `replay.py`** (see above) is a real, documented, non-zero source of online/offline mode skew for the one case it can't see (a category page reached without a nav-strip click).

## Next

`README.md` — **done**, with real screenshots and an honesty section that reflects Gate 0's actual state (no Gate 1+ metrics invented). No profile-panel GIF yet — the panel only has an honest empty state to show until Gate 1's taste vector exists; a fabricated "updating" animation would misrepresent what's built, so it's skipped rather than faked, flagged here instead.

Gate 0's remaining item: deploy to a URL. Then Gates 1–3 (modeling, simulator, recommender, ablation), not started — those are substantial additional ML engineering (LightGBM ranker, a drift-diffusion simulator, LinUCB, an ablation harness) that this session did not reach; flagging that honestly rather than shipping a rushed stub.

**Manual gate status: ready.** `/admin/session` is live and working — paste a session code (shown in the consent-gate footer and site footer) or session_id, see the raw log next to the recomputed canonical views/modes. Confirmed working against real browser sessions during this build.

**Open decision, not the agent's to make:** no `LICENSE` file has been chosen for the repo's own code (separate from the ABO dataset's CC BY-NC 4.0 terms in `NOTICE`). Flagged rather than guessed.

---

## Open questions (none blocking — logged for the record)

See the "Preflight" analysis given to the user at kickoff for the initial
list (token rules for `directed_search`, near-substitute sets not
existing in the context catalog, pointer-focus tie resolution, the
fast-skip bootstrap problem, the skew-test fixture). Nothing new since.

---

## Gate 0 checklist (§10), live status

1. Catalog pipeline (750 + 60, brand-scrubbed, thumbnails) — **done**
2. Storefront serves every §6 surface — **done**, 20 screenshots in `docs/screens/`
3. Consent gate blocks telemetry — **done** — SDK is only ever constructed after `consent === 'accepted'`; "Browse without recording" leaves no SDK instance at all, verified live (declined session shows 0 events)
4. SDK emits every §7.2 event type — **done** — all 25 types confirmed flowing into Postgres via real browser sessions during this build, not just unit-tested
5. Ingest persists idempotently, Redis session state — **done** — idempotency + Redis TTL/view-counter both verified against the real docker-compose services
6. `features/` implements 8 Gate-0 signals — **done**, all reading only through `events_in_window`
7. Item-view fixtures (6 cases) — **done**, 13 tests including all 6 required + a regression case found mid-build
8. Leakage test, build-failing — **done**, table-driven over `SIGNAL_REGISTRY`
9. Skew test — **done**, reports a continuous skew rate (currently 0.0) on a scripted fixture; a live-traffic version is a follow-up once deployed
10. §6.6 review loop, 2 passes/surface, `docs/screens/` — **done** — every surface, real defects found and fixed each pass (see the storefront section above for the list), not just cosmetic tweaks
11. Deployed at a URL — **not started**
12. Consent copy live — **done**, verbatim from `COPY.md`, wired into `ConsentGate.tsx`
13. `README.md` with screenshots/GIF/§14 — **not started**
14. **Manual gate**: author confirms view boundaries/modes by hand against a raw event log — **ready**. `/admin/session` is live; paste a code or session_id to see the raw log next to the recomputed canonical views/modes.

**Blocking Gate 0 completion: only #11 (deploy) remains — README is done. Everything else in Gate 0's DoD is done and verified.**

---

## Catalog pipeline: one more real bug found and fixed

Building the production Docker image (a fresh container, nothing cached)
surfaced a genuine concurrency bug that never showed up locally, because
locally `images.csv.gz` was always already cached from earlier runs:
`catalog/images.py`'s thread pool has every worker thread call
`fetch_images_index()` on first use, and `catalog/download.py`'s
`_download()` had no locking — two threads racing on a cold cache both
saw the destination file missing, both downloaded to the *same* `.part`
temp path, and the loser's rename failed once the winner had already
moved it (`No such file or directory: '.../images.csv.gz.part'`). 15 of
810 items silently lost their images this way on the first clean build.

Fixed at the root in `download.py`: a per-destination-path lock (so
unrelated downloads never block each other) plus a uuid-suffixed temp
filename (so even a second, out-of-process `catalog.build` run can't
collide). Verified by rebuilding the Docker image from scratch twice —
first confirmed the failure, then confirmed `context=750 core=60` with
zero dropped items after the fix.

---

## Gate 1, started: `sim/` and `server/models/taste_vector.py`

Built in the stated order's first two pieces (§11: "Build the simulator
before the ranker... simulator, then calibration against real traces,
then ranker, then profile updater"). The taste vector is technically
listed after the ranker, but it's a small, fully self-contained §11
formula with no ranker dependency, so it was quick to get done and tested
while the simulator's own tests were being fixed — reordering it ahead of
the ranker cost nothing and any Python-level module can be worked in the
order that's actually efficient as long as the *conceptual* dependencies
(simulator's output existing before the ranker can train on it) are
respected, which they are.

- `sim/embedding.py` — item embeddings built from the **real** `data/catalog.json`, not a synthetic stand-in: 7 interpretable dimensions (standardized log-price within category, rating, log review count, on-sale flag, description-length band, gallery size, brand tier), all real catalog attributes. Verified against the actual 810-item catalog.
- `sim/agents.py` — the five archetypes (skimmer, deliberator, price_hunter, image_driven, spec_reader), each with a `taste_vector` (weights over the embedding dims, used only for utility) and a `signal_weighting_vector` (the five families from §11 — attention/motor_conflict/exploration/comparison/availability — the actual Gate 1 DoD recovery target) kept **separate** from the motor/timing parameters that drive the generative process, so archetype recovery from simulated behavior is a real test rather than a tautology.
- `sim/generative.py` — the declared generative process: a drift-diffusion utility accumulator decides *how long* an agent looks at something (`dwell_via_drift_diffusion`), a gaze-then-reach motor model with AR(1)-smoothed perpendicular noise decides *how the cursor gets there* (`reach_trajectory` — smoothed noise is what makes the path curve rather than jitter), and a reading model decides scroll progression with re-read reversals (`reading_scroll`). Curvature, peak velocity, and scroll reversals are never assigned directly anywhere — they emerge from these processes.
- `sim/session.py` — simulates a full session for one archetype against real catalog items, laid out on a synthetic grid, producing `RawEvent`s in the exact shape `server/features/window_spec.py` expects. The simulator's output goes through the *same* `item_view.py`/`signals.py` pipeline real telemetry does — verified directly (`sim.session.simulate_session` → 10 items → 2,884 raw events → 10 canonical views, dwell/commit outcomes tracking utility as expected).
- `server/models/taste_vector.py` — §11's fully-specified update rule (`v_0` = catalog centroid, never the zero vector; `w_i = clip(2p_i - 1, -0.5, 1.0)`, `-0.5` on a fast skip; `eta=0.3`, `lambda=0.067`), with the population-prior gate below 3 scored views built in rather than left for callers to remember. 12 tests: unit norm after 200 arbitrary updates, bounded magnitude under extreme weights, convergence toward a repeatedly-liked direction and away from a repeatedly-disliked one, and the population-prior gate's exact boundary.

### Dwell vs. utility: corrected terminology, real data, and a fast-skip fix

The first version of `tests/sim/test_generative.py` asserted dwell
correlates positively with utility — and failed, including a *negative*
correlation in one case. That's correct drift-diffusion behavior, not a
bug: reaction time in a DDM peaks when drift is near zero and falls off
as |drift| grows in either direction. **I initially mislabeled this
"U-shaped" in this file and in code comments — that's backwards.** A U
dips in the middle and rises at the edges; what the model actually
produces is the opposite: a peak in the middle, falling at both edges —
**∩-shaped** (inverted-U / peaked-at-indifference). Corrected everywhere
it appeared (`tests/sim/test_generative.py`'s test name and docstring,
this file).

The actual curve — mean dwell (ms) binned by decile of injected utility,
generated fresh from `sim/generative.dwell_via_drift_diffusion`, one row
per archetype (the current generative process doesn't yet take `mode` as
an input at all — see the gap noted below, this table is *not* yet a
per-mode breakdown because there is nothing in the code today that would
make it one):

```
decile (mean u)      skimmer   deliberator  price_hunter  image_driven  spec_reader
0  (-2.2ish)            277        2047          679           683         2524
1  (-1.7ish)             363        2674          903           900         3375
2  (-1.2ish)             520        3700         1206          1211         4725
3  (-0.7ish)             865        6141         2012          2420         8798
4  (-0.2ish)            1354       12270         4979          4098        15524   <- near indifference
5  (+0.2ish)             1445       13411         5223          3157        14837   <- near indifference
6  (+0.7ish)              813        6724         1949          1800         7787
7  (+1.2ish)              537        3863         1252          1200         4603
8  (+1.7ish)              371        2594          924           829         3139
9  (+2.2ish)              292        2059          714           690         2610
```

Every single archetype: lowest at both extremes, highest at deciles 4-5
(utility near zero). What's actually monotonic in utility is the
**commitment rate** (which threshold gets hit), not dwell duration — a
separate check (`u=+2.0 → commit_rate=1.00`, `u=-2.0 → commit_rate=0.00`,
smoothly monotonic in between) confirms that's the real interest signal.
This is the simulator concretely reproducing §4.2's own warning ("Do not
assume dwell is positively related to interest in `directed_search`") as
an emergent property of a physically-motivated process, not a rule
anyone hand-coded. Tests fixed to check commitment rate and to
explicitly document the ∩-shape as intentional, not asserted away.

**Gap this surfaced, now resolved by the author's answer:**
`dwell_via_drift_diffusion` originally took `(utility, archetype, rng)`
with no `mode` input at all. The author's ruling: **mode does modulate
the generative process, but only at the process level** — it shifts the
DDM's drift rate and boundary separation (and, for `refind`, its
non-decision time). It must never touch dwell, curvature, or any other
feature directly, which would reintroduce the exact circularity §11's
"parameterize independently of the feature set" rule exists to prevent.

### Per-mode DDM priors — a stated hypothesis, not a tuning knob

Written here **before** implementation, per the author's explicit
instruction, and copied into `sim/mode_priors.py`'s own docstring so the
two can't drift apart. **These are a hypothesis about shopper behavior.
They must not be adjusted later to make a downstream metric look
better** — if a ranker result looks wrong once these are wired in, that
is a signal to stop and raise it, not to retune these numbers until the
metric improves.

| Mode | drift multiplier | boundary multiplier | other | Reasoning |
|---|---|---|---|---|
| `directed_search` | 1.8, **bimodal**: 75% decisive / 25% scaled to 0.12 | 0.7 (lower) | — | Checking a known target is verification, not preference formation — genuine matches resolve fast. The 25% "ambiguous" tail scales drift toward zero **regardless of the item's own utility**, representing a close-but-wrong candidate that's plausible enough to cause hesitation. That tail *is* §4.2's "failure to find": long dwell in directed_search comes from this regime, not from interest — which is exactly why dwell means something different here than in discovery. |
| `broad_search` | 1.2 | 0.85 | — | Between directed_search and discovery on both axes: a category-level goal without a single verified target. |
| `discovery` | 0.7 (lower) | 1.3 (higher) | — | No target to verify against — utility has to be *constructed* from attributes as they're encountered, a noisier, slower-accumulating process, and more evidence is required before committing without a prior target-match signal to lean on. |
| `comparison` | 0.5 | 1.4 (highest) | — | Drift concentrated near zero **by construction**: near-substitute items are deliberately controlled to vary one attribute at a time (`catalog/core_sets.py`), so they're close in utility to begin with; comparison's own low drift multiplier suppresses it further. Highest boundary of any mode → longest dwell, since resolving a close call takes the most accumulated evidence. |
| `refind` | 1.6 | 0.6 (lowest) | non-decision time 80ms (vs. 250ms default) | The evaluation largely already happened on the first view — fast on every axis, including the encoding/motor overhead that's constant across the other modes. |

### Mode emerges from goal + history, not a sampled input

Per the author's explicit instruction, mode is never assigned or sampled
directly anywhere in `sim/session.py`. Instead:

- A simulated session gets an optional `SessionGoal` (`sim/session.py`):
  `target_item_id`, `target_category`, or neither. A goal only ever
  supplies the *fiction* of an active search query — a 3-token synthetic
  query for an item target (guarantees `directed_search` classification
  via §4.1's ≥3-token rule), a single categorical word for a category
  target (guarantees `broad_search`).
- Every view's mode is computed by calling the **exact same**
  `server.features.mode.assign_mode` real ingested sessions are scored
  with — fed the goal's query (if any) and the agent's own accumulating
  `PriorView` history. `refind` and `comparison` are never specially
  cased: they fall out of `assign_mode`'s own precedence rules applied
  to whatever the agent actually did (a real revisit ≥60s later; two
  near-substitute-set items viewed within 120s), exactly as §4.1
  describes for real behavior.
- Added a revisit mechanic (`revisit_prob`, default 0.15): at each step
  the agent has a chance to go back to a previously-viewed item instead
  of a new one — the only path to `refind`, since nothing else in the
  function revisits.
- `tests/sim/test_session.py` (7 tests, all passing against the real
  built catalog) confirms all five modes genuinely emerge from the right
  conditions: a goalless session is pure `discovery`; an item-goal
  session is pure `directed_search`; a category-goal session is pure
  `broad_search`; browsing a near-substitute-heavy pool produces
  `comparison`; a long, slow, revisit-heavy session produces `refind`
  (needed `deliberator` archetype + 60 items to accumulate the required
  60+ real seconds — `skimmer` over 40 fast items never reached the
  refind gap, which is realistic, not a bug: refind genuinely needs that
  much elapsed time). One test statically greps `sim/session.py` for a
  hardcoded `mode = "..."` literal bypassing `assign_mode`, to catch a
  future edit reintroducing directly-sampled mode.

### The real per-mode and per-archetype curves

Generated by actually running `simulate_session` against the real
810-item catalog (Kitchen & Dining items for discovery/search/refind
sessions, the instrumented core's near-substitute sets pooled together
for comparison sessions), pooling ~3,600 views across all five
archetypes and five goal conditions. Two honest caveats before the
numbers: (1) unlike the pure-archetype table above (a uniform synthetic
utility sweep from -2.5 to 2.5), this pools *real* catalog utilities,
which are not uniformly distributed and skew positive for several
archetypes against this catalog slice — so each row's utility range
differs and a strict decile-by-decile ∩ comparison across modes isn't
directly meaningful; (2) pooling five archetypes together per mode means
each decile mixes different archetypes' dynamics. What **is** directly
meaningful and clean is each mode's overall dwell *scale*, which is
exactly what the boundary multipliers control:

```
mode              n     mean dwell   median dwell
comparison       463      4938ms        3750ms   <- highest boundary (1.4)
discovery       1750      3669ms        2600ms   <- boundary 1.3
broad_search     600      1723ms        1200ms   <- boundary 0.85
directed_search  599      2434ms        1100ms   <- lowest boundary (0.7) but see below
refind           170      1332ms         980ms   <- lowest boundary (0.6) + reduced non-decision time
```

Median ordering matches the boundary-multiplier ordering exactly:
comparison > discovery > broad_search > directed_search > refind.
`directed_search`'s *mean* (2434ms) sits above `broad_search`'s despite
a lower boundary — that gap is the bimodal failure-to-find tail showing
up concretely. Isolating just directed_search vs. broad_search
(n=1500 each, mixed archetypes, item-goal vs. category-goal sessions):

```
mode              mean    median    p90    mean/median ratio
directed_search  2261.4   1050.0   5450.0        2.15
broad_search     1720.8   1250.0   3400.0        1.38
```

directed_search's mean/median ratio (2.15) is well above broad_search's
(1.38) — a real-catalog confirmation that a *minority* of directed_search
views run long (the ambiguous-tail regime) while the *typical*
directed_search view resolves faster than a typical broad_search view
(lower median), which is exactly the "failure to find is a tail, not the
typical case" shape the priors were written to produce.

### Fast-skip was unsafe as originally implemented — found and fixed

Consequence of the ∩-shape above: **a short view is ambiguous between a
confident reject and a confident accept** — decile 9 (strong positive,
commit_rate≈1.0) and decile 0 (strong negative, commit_rate≈0.0) have
comparably *short* dwell for every archetype. `server/features/labels.py`'s
`is_fast_skip` originally keyed on duration alone
(`view_duration_ms < threshold_ms`), which — unchecked — would have
put the strongest positives (decided on instantly) into the negative
class right alongside genuine fast rejections, and this function had
**no tests at all**, which is how it went unnoticed.

Fixed: `is_fast_skip` now requires a short exposure **and** no later
commitment **and** no later revisit of that same item in the session —
only a short view that's never returned to and never committed to is
safely a fast skip. New `tests/features/test_labels.py`, 10 tests,
including the exact failure scenario (`test_short_view_later_committed_is_NOT_a_fast_skip`)
and the revisit case, both passing. Also renamed a confusingly-named
constant in `sim/session.py` (`FAST_SKIP_DWELL_FLOOR_MS`, 300ms) that
had nothing to do with the fast-skip *label* concept at all — it was
`item_view.py`'s unrelated 300ms view-qualifying floor under a name that
invited exactly this kind of confusion. Now imports the real constant
(`MIN_QUALIFYING_DURATION_MS`) from `item_view.py` instead of duplicating
the number under a misleading name.

### Confirmed: nothing assumes dwell is monotonic in interest

Checked every place dwell touches the pipeline so far:
- `signals.item_dwell` returns `log1p(duration_s)` — a raw sealed-window
  measurement, not an interest score; it doesn't encode or assume any
  particular relationship to interest, monotonic or otherwise. That
  interpretation work is the ranker's job, not signals.py's.
- `taste_vector.py`'s `weight_from_calibrated_interest` takes `p_i`
  (*calibrated* interest, i.e. a model's output) and `is_fast_skip`
  directly — it never touches raw dwell.
- **No LightGBM ranker exists yet**, so there are no `monotone_constraints`
  to audit today. Recorded here as a binding constraint on that work when
  it starts: **no monotonic constraint on any dwell-derived feature**,
  and no linear-only encoding of dwell as a single scalar proxy for
  interest — dwell needs a representation that can express the ∩-shape
  (e.g. binned/one-hot, or paired with |dwell - session-mode-median| as
  a second feature) if it enters the ranker's feature set as anything
  more than one input among the five family composites, which is where
  §11 actually wants it to live in the first place.

### What's not built yet for Gate 1

- **Calibration against real traces** (§11's stated step 2, before the ranker) — needs the author's own real browsing data, which doesn't exist yet: no deployment, so no real sessions to calibrate `sim/agents.py`'s motor/timing parameters against. Genuinely blocked on deployment + the author actually using the deployed site, not something buildable in isolation.
- **The ranker** (LambdaRank over within-session pairs, five family composites, per-mode calibration) — not started, and now blocked on the mode-conditional-generative-process question above before it can honestly claim per-mode validity. Next piece to build once that's resolved.
- Archetype linear-probe recovery, the negative control at the full-pipeline level (§11's actual DoD items, distinct from the generative-process-level sanity checks already passing in `tests/sim/test_generative.py`), and the profile updater's integration into ingest — all downstream of the ranker.

---

## Gate 2 — noted, not started

`BUILD_BRIEF.md` was replaced with a version adding **§6.7 (admin
console)** and revising Gate 2's bullet list to include it
("Admin console per §6.7: sessions list, session signal table, live
view, event log viewer, signal distributions, new-profile control.
Behind auth."). This is a **Gate 2 deliverable** — not started, per the
author's explicit instruction to just note it here rather than begin it
now. Gate 0's manual-gate event-log viewer (`/admin/session`, already
built) is explicitly called out in §6.7 item 4 as the predecessor this
console's own event-log view builds on ("This is the tool Gate 0's
manual check requires, so it exists before this section is built") —
so that piece is already done and just needs auth + the other four views
wrapped around it when Gate 2 starts.

Also new: **§2.1a**, Windows-specific local environment guidance (Python
3.12 explicitly, not the 3.14 also on PATH; Postgres/Redis in Docker;
PowerShell not bash for anything committed). Already compliant — `.venv`
was created against Python 3.12.10, Postgres/Redis already run via the
existing `docker-compose.yml`, and nothing committed to the repo is a
`.sh` script.

---

## Deployment

**Prepared and locally verified, not yet live** — this needs the
author's own authenticated `flyctl` session and Fly.io account (billing,
Postgres/Redis provisioning), which the agent cannot create.

- `Dockerfile` — multi-stage: builds `sdk/` + `web/` (Node), then a Python stage that installs the backend, bakes the real 810-item catalog in at image-build time (`RUN python -m catalog.build` — needs network access during `docker build`), and serves both the API and the built frontend from one `uvicorn` process (§2's "one FastAPI app, one React app," one process in production too). `server/main.py` now has a production-only static-file + SPA-fallback route (only mounted when `web/dist` exists — dev keeps using Vite's own server).
- **Verified locally**: built the image from a clean cache twice (confirming the download-race fix above), ran the container against the existing docker-compose Postgres/Redis, confirmed `/api/health`, `/api/home`, `/`, and `/favicon.svg` all serve correctly, and confirmed the `noindex` header is present on every response.
- `fly.toml` — app config, `shared-cpu-1x` / 512MB, `auto_stop_machines` so it doesn't run (or cost) anything while idle.

### What the author needs to do (the agent cannot do this part)

```powershell
# flyctl is already installed (winget install --id Fly-io.flyctl)
flyctl auth login          # opens a browser — needs the author's account
flyctl launch --no-deploy  # confirms/adjusts fly.toml, picks a real app name
flyctl postgres create     # managed Postgres — note the connection string
flyctl redis create        # managed Redis (Upstash) — note the connection string
flyctl secrets set DATABASE_URL=... REDIS_URL=...
flyctl deploy
```

Once that's done, the repo can flip from private to public per the
kickoff instructions' condition ("stays private until the synthetic-
content labeling, the consent gate, and noindex are all in place" — all
three are already true; deploying doesn't change that gate, it's just
the last item still open).
