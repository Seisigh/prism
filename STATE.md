# PRISM — build state

Read this alongside `BUILD_BRIEF.md` before doing anything else in a new
session. This file is updated after each module, not at the end.

**Current gate:** 0 (catalog + storefront done, SDK/ingest/features next)
**Repo:** https://github.com/Seisigh/prism (private)

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

## Next

`sdk/` (browser telemetry package) → `server/ingest` (WS + HTTP, Redis session state, unpacks `pointer_batch`/`scroll_batch` envelopes into the flat `pointer_sample`/`scroll_sample`/`visibility_sample` RawEvents `signals.py` consumes) → skew test (needs ingest to exist first, per the stated build order) → event-log viewer for the manual gate.

---

## Open questions (none blocking — logged for the record)

See the "Preflight" analysis given to the user at kickoff for the initial
list (token rules for `directed_search`, near-substitute sets not
existing in the context catalog, pointer-focus tie resolution, the
fast-skip bootstrap problem, the skew-test fixture). Nothing new since.

---

## Gate 0 checklist (§10), live status

1. Catalog pipeline (750 + 60, brand-scrubbed, thumbnails) — **done**
2. Storefront serves every §6 surface — not started
3. Consent gate blocks telemetry — not started
4. SDK emits every §7.2 event type — not started
5. Ingest persists idempotently, Redis session state — not started
6. `features/` implements 8 Gate-0 signals — not started
7. Item-view fixtures (6 cases) — not started
8. Leakage test, build-failing — not started
9. Skew test — not started
10. §6.6 review loop, 2 passes/surface, `docs/screens/` — not started
11. Deployed at a URL — not started
12. Consent copy live — copy exists verbatim in `COPY.md`, not yet wired into a component
13. `README.md` with screenshots/GIF/§14 — not started
14. **Manual gate**: author confirms view boundaries/modes by hand against a raw event log — blocked on 4-9 existing first; will flag here the moment the event-log viewer is ready.
