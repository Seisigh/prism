# BUILD BRIEF — PRISM

An instrumented storefront that infers browsing interest in real time.

**Codename:** `prism` (store brand and repo name — change freely, but change it everywhere at once)
**Supersedes:** design spec rev 2, 2026-09-12
**Audience:** the coding agent building this, and the author reviewing it

---

## 0. How to use this brief

Build in gate order. **Do not start a gate until the previous gate's Definition of Done is fully green.** The early modules are load-bearing: if the item-view boundary rule or the sealed feature window is wrong, the ranker trains on garbage, the simulator gets calibrated to garbage, and the ablation table ranks garbage. Those failures are silent and they surface six modules later.

When something in this brief is ambiguous, stop and ask rather than guessing. When something here is wrong, say so rather than implementing it.

---

## 1. What this is

A storefront that records how a visitor browses — pointer motion, scroll, hover, navigation — converts that into calibrated per-item interest estimates in real time, maintains a two-part visitor profile as vectors, and drives recommendations from it. A side panel can show the visitor their own profile forming.

There are **no research participants**. The author is the main subject; a handful of invited visitors may use the deployed demo. The evaluation substrate is a **simulator** whose agents have known preferences, calibrated against the author's own real traces.

### Non-negotiables

These are correctness constraints, not preferences. Violating any of them invalidates the project.

1. **No trade dress.** Copy e-commerce information architecture and interaction patterns freely. Copy no real retailer's wordmark, logo, color identity, typeface, or program names. `prism` has its own name, logo and palette.
2. **No real brand names in any served text.** Every brand string in titles, descriptions, specs and metadata is replaced with an invented label. This applies to text, not to incidental logos visible in source photographs — see §5.3 for why that distinction is the whole of it.
3. **Synthetic content is labeled in the UI.** Prices, ratings, reviews and stock are fabricated and every review block carries a visible marker saying so. A persistent site banner states the same.
4. **`robots: noindex, nofollow`** on every page.
5. **Consent before telemetry.** No event is recorded until the visitor accepts. Random session ID only, no accounts, no PII, IP not stored. 90-day retention, and a delete endpoint keyed on session ID that is shown to the visitor.
6. **Never use the word "anonymous."** The correct word is "pseudonymous."
7. **`demo` sessions are excluded from all training and evaluation** at the query level, not by convention.
8. **No claim about humans in general** appears in the README, the UI, or any output.

---

## 2. Stack

- Backend: **Python 3.12**, FastAPI, WebSockets
- Frontend: React + TypeScript, Vite
- Data: Postgres (events, catalog), Redis (live session state), Parquet (training dumps)
- Models: LightGBM, scikit-learn, numpy. Exact cosine over a numpy matrix for similarity — the catalog is small enough that ANN would be slower and would read as cargo cult.
- Tests: pytest, Playwright
- Icons: Lucide. Never emoji as UI icons.
- No ORM heroics. No microservices. One FastAPI app, one React app.

### 2.1 Deployment

Target Fly.io or Railway. Both host a Python process, managed Postgres and managed Redis on one account, and both support WebSockets, which rules out the static hosts. Deploy from Gate 0 onward so the site is always live somewhere; do not leave deployment to the end, because that is where week-long surprises live.

### 2.1a Local environment — Windows, read before running anything

The development machine is Windows, not Linux or macOS. Three consequences:

- **Use Python 3.12 explicitly.** Python 3.14 is also installed and is the default `python` on PATH. Do not use it: LightGBM, scikit-learn and pyarrow have no prebuilt wheels for 3.14, so pip will attempt source builds that need a C++ toolchain. Create the environment with `py -3.12 -m venv .venv` and activate with `.\.venv\Scripts\Activate.ps1`. Every Python command in this project runs inside that venv.
- **Postgres and Redis run in Docker**, via the `docker-compose.yml` already in the repo. Redis has no supported native Windows build. Connection strings are in `.env.example` and already match the compose file. Start services with `docker compose up -d`.
- **Shell is PowerShell, not bash.** Write scripts as `.ps1` or, better, as Python so they are portable. Do not assume `&&` chaining, `rm -rf`, or POSIX path separators in anything committed.

### 2.2 Required Claude Code setup

Install before writing frontend code:

- `/plugin install frontend-design` — Anthropic's official plugin. It forces a design direction to be chosen before coding instead of defaulting to generic AI aesthetics.
- Playwright MCP — browser control for the screenshot review loop in §6.6.
- Context7 MCP — live version-specific docs, which prevents inventing API surfaces for React, Tailwind and FastAPI.

---

## 3. Repo layout

```
prism/
  catalog/        source ingest, brand masking, attribute assignment, embeddings
  sdk/            browser telemetry package (TypeScript, framework-agnostic)
  web/            React storefront
  server/
    ingest/       WS + HTTP endpoints, validation, persistence, session state
    features/     window-spec'd feature functions. no storage, no transport
    models/       ranker train + infer, profile updater
    recommender/  candidate gen, rerank, epsilon-greedy, impression log
  sim/            agents, calibration, ablation harness
  eval/           replay, recovery metrics, ablation reports
  tests/
  BUILD_BRIEF.md
  README.md
```

`features/` imports nothing from `ingest/`, `models/` or `recommender/`. If it needs to, the boundary is wrong.

---

## 4. Browsing mode — a first-class stratum

The single most important modeling decision in this project. Dwell time means opposite things in different contexts: in directed search, long dwell often signals **failure to find**; in discovery browsing it signals engagement. Pooling them produces a model that describes neither, and the pooled metric still looks fine, which is why the bug hides.

Grounded in [Moe (2003)](https://myscp.onlinelibrary.wiley.com/doi/abs/10.1207/S15327663JCP13-1&2_03), who separated directed buying, search and deliberation, hedonic browsing and knowledge building from navigational clickstream, and [Broder (2002)](https://sigir.org/files/forum/F2002/broder.pdf) on navigational vs informational query intent.

### 4.1 Mode assignment

Every item view carries exactly one mode, assigned at view open:

| Mode | Rule |
|---|---|
| `discovery` | No active query. Arrived via home rail, category grid, or recommendation rail |
| `directed_search` | Active query containing a model token, an invented-brand token, or ≥3 tokens |
| `broad_search` | Active query, categorical, <3 tokens, no brand or model token |
| `comparison` | ≥2 views of items within the same near-substitute set inside a 120s window |
| `refind` | Item was viewed ≥1 time earlier this session, ≥60s prior |

Precedence when several apply: `refind` > `comparison` > `directed_search` > `broad_search` > `discovery`.

A query is "active" for 180s after submission, or until a category-nav click, whichever comes first.

### 4.1a Session boundary

Everything in this brief normalizes "within session," so a session needs a definition:

```
A SESSION is the sequence of events sharing one session_id.
It ends at 30 minutes with no events, at an explicit session_end,
  or at tab close.
Reopening after a session has ended creates a NEW session_id.
A session with fewer than 3 item views is excluded from normalization
  fitting, though its events are still stored.
```

Without this, z-scoring within session is undefined for a visitor who leaves a tab open overnight, and the normalizers silently drift.

### 4.2 What mode changes

- **Normalization baseline.** Dwell is z-scored within `(session, mode, surface)`, then centered within item. A 2s grid scan and a 2s detail-page visit are not the same event.
- **Fast-skip threshold.** Fitted separately per surface and mode. Grid scanning is far faster than detail-page reading; one global threshold is wrong.
- **Expected sign.** Do not assume dwell is positively related to interest in `directed_search`. Report the relationship per mode rather than assuming it.
- **Available signals.** A results grid is dense with hover and trajectory signal across many targets. A detail page has one target and is mostly scroll and zoom. Feature availability is mode- and surface-dependent, and missingness must be represented explicitly, never imputed as zero.
- **Label meaning.** A cart-add in `directed_search` mostly reflects intent formed before arrival. A cart-add in `discovery` reflects interest formed on site, and is the only stratum where a recommender can plausibly move anything.

### 4.3 Modeling consequence

Mode is a **stratum, not a feature column**. Calibrate per mode, report metrics per mode, and never publish a pooled headline number.

---

## 5. Catalog

### 5.1 Two catalogs, one store

- **Context catalog, ~750 items.** Full breadth. Browsable, searchable, fully logged, and the recommender's candidate pool. This is what makes the store feel real and gives the taste vector something to do.
- **Instrumented core, ~60 items.** Near-substitute sets with controlled attributes, seeded to appear reliably in sessions. All controlled measurement happens here.

Both are logged identically. Only the core carries analytic weight. The simulator browses all 750; the author will never cover more than a fraction, which is precisely why the core exists.

### 5.2 Coverage targets for the context catalog

Spread across gender-coded and ungendered categories, age bands from kids to older adults, and ten interest verticals: cooking, fitness, outdoors and camping, gaming, music, reading and study, gardening, crafts, pets, travel. Roughly 15–25 items per cell. Thin for measurement, correct for context.

### 5.3 Source and identity scrubbing

Source: [Amazon Berkeley Objects](https://registry.opendata.aws/amazon-berkeley-objects/), CC BY-NC 4.0, public S3, no authentication. 147,702 listings available, so selection is a script.

**The risk lives in text, not in pixels.** A product photograph with a visible logo, used non-commercially under the dataset's license, is ordinary — this is the licensed use. What creates a problem is attaching a fabricated price, rating or review to an *identifiable* product, because that reads as a claim about a real company's goods. Break the identification and the fabricated attributes attach to nothing.

So the pipeline is text-side only:

1. **Generate titles** from product type plus attributes ("Tri-Ply Stainless Saucepan, 3qt"), never from source titles, which are dense with brand names.
2. **Replace every brand string** in descriptions, spec tables and metadata with an invented label from a generated brand list. No source manufacturer name survives into any served field.
3. **Spot-check 50 random items** before first public deploy, looking only for the case where the product *is* its branding — team jerseys, logo mugs, branded packaging. Drop those individually.

Explicitly **not** doing: OCR rejection of images with legible text, and hard filtering to low-branding product types. Both were considered and dropped. They cost most of the catalog and most of the coverage breadth in §5.2 while addressing a risk that the text scrub already handles.

Residual, accepted: some served images will show real logos. With no brand named anywhere in the page text, and a persistent banner stating that prices, ratings and reviews are fabricated, that is a photograph rather than a claim.

Measurement note: brand prominence varies across source images, so it is an uncontrolled variable wherever image attention is measured. Control it within the 60-item instrumented core by selecting comparably-branded photos inside each near-substitute set. Ignore it in the context catalog, where nothing is being measured.

### 5.4 Synthetic attributes

Prices, anchor prices, star ratings, review counts, brand tiers, stock and shipping lines are generated. Descriptions are derived from source bullets and normalized by an LLM into fixed length bands, so description length is a controlled variable rather than noise. Reviews are generated and visibly marked synthetic.

Instrumented-core sets vary **one attribute at a time**: price, rating count, description length band, gallery size, copy framing (feature-led vs benefit-led).

### 5.5 Images

Resize to a web thumbnail set (grid, detail, zoom) at build time. 750 full-resolution source images will make the store feel slow, which directly undercuts the latency work.

### 5.6 Generated attribute realism

A store where everything costs $24.99 and has 4.5 stars reads as fake within three seconds, and that impression is very hard to recover from. Generate from realistic distributions, not uniform ones:

- **Price:** log-normal per category, so each category has its own center and spread. Snap ~70% of prices to `.99`, ~15% to `.95`, leave the rest arbitrary. Include genuine outliers at both ends of each category.
- **Ratings:** mean around 4.3, left-skewed, clipped to [1, 5], rendered to one decimal. Almost nothing below 3.5 survives on a real storefront, and a handful of 2-star items make the rest believable.
- **Review counts:** heavy Pareto tail. A few items with 20,000+, most with 20 to 400, some with 3.
- **Anchor prices:** present on only ~35% of items, and the discount is a plausible 10–40%, never 70%.
- **Stock and shipping:** mostly unremarkable, occasionally "Only 3 left," rarely out of stock.

### 5.7 Seeding the instrumented core

"Appears reliably in sessions" needs a mechanism. Core items receive a placement boost: every category grid page and every recommendation rail is composed to contain at least 25% core items, positioned by the same ranking rules as anything else. The boost is applied at candidate assembly and **logged as part of the impression record**, so it is never mistaken for a model preference later.

---

## 6. Storefront — the IA to reproduce

Standard e-commerce structure, PRISM's own identity.

### 6.0 Identity

Typeface: Inter, via Google Fonts, with a system-sans fallback stack.

```
ink          #14161C      surface      #FFFFFF
slate        #5A616E      surface-alt  #F7F8FA
line         #E3E6EC
primary      #3D4EDB      primary-hover #2E3CB8
savings      #0E8A5F
```

Neutrals and the single indigo carry the entire storefront. **The spectrum is reserved for the profile panel** and appears nowhere else in the UI:

```
spectrum  #E8432F  #E88B2F  #D9C534  #3FA654  #3D8FDB  #6B4FD9
```

White light in, spectrum out, and only where the system is actually decomposing behavior into dimensions. Using these colors anywhere else in the store dissolves the one place they mean something.

No orange-on-navy, no borrowed wordmark, no borrowed typeface. Define every token as a CSS custom property in one file so the identity is swappable.

**Header.** Logo, location stub, search field with a scoped category dropdown, account stub, cart with count. Below it a horizontal category nav strip.

**Home.** Hero carousel. Then a row of four-tile category cards ("Shop by recipient", "Under $25", "Dorm essentials"). Then recommendation rails. Multiple rail types, because rail provenance is itself a signal.

**Category page.** Left facet rail (price bands, rating, category, features), sort dropdown, results grid.

**Search results.** Query echo with result count, a sponsored strip above organic results, left facet rail, results grid with badges (Best Seller, Overall Pick), price with superscript cents, rating and review count, delivery line, explicit sponsored markers. Autocomplete dropdown on the search field.

**Product detail.** Breadcrumb, gallery left with thumbnail strip and zoom, title / rating / price center, buy box right (price, delivery estimate, quantity, add to cart, add to list), "about this item" bullets, spec table, reviews with a rating histogram, then "customers also viewed" and "similar items" rails.

**Compare view.** Side-by-side of 2–4 items from one near-substitute set.

**Cart** and a **checkout stub** that ends at a confirmation page and charges nothing.

**Consent gate** on first visit, before any telemetry initializes.

**Profile side panel**, hidden by default, which sets `demo=true` for the session when opened.

---

## 6.5 Visual quality — a correctness requirement, not a preference

**This has to look genuinely good.** Not "acceptable for a research prototype." Not "clean enough." The entire project is a portfolio artifact, and the first fifteen seconds someone spends on it decide whether they read the README at all. A telemetry pipeline nobody scrolls past is worth nothing. Treat visual craft with the same seriousness as the leakage test.

The failure mode to avoid is specific and recognizable: the generic AI-generated web app. Centered everything, purple-to-blue gradients, three cards in a row with rounded corners and a drop shadow, emoji standing in for icons, inconsistent spacing, default browser form controls, no hover states, no empty states, text at 16px in a 1400px-wide column. Any reviewer has seen a thousand of these and discounts them on sight. If the output looks like that, it has failed regardless of what the tests say.

### Foundations, defined once and obeyed everywhere

- **Spacing:** a single 4px base scale (4, 8, 12, 16, 24, 32, 48, 64). No arbitrary margins. If a gap isn't on the scale, it's a bug.
- **Type scale:** six sizes, defined once (12, 14, 16, 20, 24, 32). Body text 14px on this kind of dense commerce UI, not 16px. Line height 1.5 for body, 1.2 for headings.
- **Line length:** description and review text capped at 68ch. Full-width paragraphs are the fastest way to look amateur.
- **Numerals:** prices and ratings use tabular figures so columns align. Price rendering uses the superscript-cents pattern; it's a commerce convention and its absence is conspicuous.
- **Radii and elevation:** two radii and two shadow levels for the whole app. Not five.
- **Borders over shadows** for separation in dense layouts. Shadow is for things that genuinely float, meaning dropdowns, the autocomplete panel, and modals.
- **Grid:** 12 columns, consistent gutters, content max-width around 1400px. Not everything is centered; grids are left-aligned and fill.
- **Density:** this is a shopping site. It should feel information-rich and scannable, closer to a dense catalog than to a marketing landing page. Resist whitespace that makes it look like a startup homepage.

### Every interactive element ships five states

Default, hover, focus-visible, active, disabled. A control missing hover or focus is unfinished. Focus rings are **visible and custom**, never `outline: none` with nothing in its place, and never the raw browser default either.

### Every data surface ships three states

Loaded, loading, and empty. Skeletons for grids and rails, never a spinner covering the page and never a layout that jumps when data lands. Specifically required: search with zero results, empty cart, a compare view holding one item, an item with a single image, and a profile panel with no data yet.

### Images

Fixed aspect-ratio containers so nothing shifts on load. Lazy load below the fold. A neutral placeholder or blur-up while loading. Cumulative layout shift near zero, because a store that jumps while you read it destroys the impression of engineering care and also corrupts your own dwell measurements.

### Motion

120 to 200ms, ease-out, `transform` and `opacity` only. Motion confirms an action or reveals a surface; it never decorates. Honor `prefers-reduced-motion` and drop to instant.

### Explicit prohibitions

No purple or blue gradients. No emoji as icons, use Lucide. No unstyled `<select>`, `<input>` or `<button>` anywhere. No centered hero with a single call to action, this is a store. No card with a shadow, a rounded corner and a one-line label used as the answer to every layout problem. No `lorem ipsum` reaching a screenshot. No dark mode: one theme executed well beats two executed adequately, and dark mode is out of scope.

### Reference material

Three screenshots of a major retailer live in `docs/reference/`. Use them for **structure only**: header composition, how a results grid packs information, how a detail page distributes gallery, title block and buy box, how facet rails are organized, how badges and delivery lines sit in a card. Do not copy the color, the wordmark, the typeface or any asset. PRISM's identity is §6.0 and it is not negotiable.

`docs/reference/` is **gitignored**. Those images never enter a commit.

## 6.6 The design review loop

This is the mechanism that turns "make it look nice" into something an agent can actually converge on. Run it for every surface, and do not consider a surface finished until it has been through at least two full passes.

1. Build the surface.
2. Screenshot it with Playwright at 1440×900 and at 768 wide.
3. Look at the screenshot. Compare against the reference for structural completeness and against §6.5 for craft.
4. Write down three specific defects. Not "improve spacing" but "the price sits 3px off the card's baseline grid, the rating row has no hover affordance, the badge overlaps the image at 768."
5. Fix them. Screenshot again. Repeat.

Save the final screenshots to `docs/screens/`. They become the README images, which are the highest-leverage thing on a GitHub page and are otherwise always forgotten.

### Responsive scope

Desktop-first, 1440px reference width. Must hold together down to 768. Below 768 it must remain functional and unbroken, but a notice states that behavioral capture is reduced, because touch devices have no hover and the motor signal family is unavailable. Do not spend days on a phone layout; do not ship one that is visibly broken.

### Accessibility floor

Text contrast at least 4.5:1, interactive elements 3:1. Full keyboard navigation with visible focus. Real `alt` text on product images, generated from the item title. Semantic landmarks. This is a floor, not a project goal, and the accessibility audit is part of each surface's review pass.

---

## 6.7 Admin console — built in Gate 2

The storefront is the demo. The admin console is the evidence. For anyone evaluating this project technically, it is the more interesting of the two, and it is also the tool that makes the system debuggable at all.

Route `/admin`, behind authentication **in every environment including local**: a single password read from the environment, a signed session cookie, no user accounts. Never linked from the public site, and excluded from the sitemap along with everything else under `noindex`.

### Views

**1. Sessions list.** All sessions, newest first. Columns: code, started, duration, item views, commitments, mode distribution, browser and device, consent state, `demo` flag. Filterable by real versus demo, by date, and by whether the session produced any commitment. Click through to detail.

**2. Session detail — the signal table.** The core screen. One row per item view, showing item, surface, mode, and **every signal in three columns: raw value, normalized value, and availability**. Then the predicted interest score and the label that actually materialized. Being able to look at one row and see that hover was unavailable rather than zero, and that dwell was 1.4 standard deviations above this person's baseline for that mode rather than three seconds, is what makes every later debugging session tractable.

**3. Live view.** WebSocket-fed, follows an active session as it happens: the event stream, both vectors updating, and the current slate with the reason each item was chosen — score, rail, propensity, and whether the core-seeding boost applied. Freeze and step controls, because watching it at full speed is impressive and useless for finding bugs.

**4. Event log viewer.** Raw events, filterable by type, with computed view boundaries overlaid so the opening and closing of each view is visible against the underlying events. This is the tool Gate 0's manual check requires, so it exists before this section is built.

**5. Signal distributions.** Per signal, per mode, per surface: histogram plus availability rate. This is how you notice that hover is null on every detail page, or that a normalizer is producing a degenerate distribution, before either one silently corrupts a model.

### New profile

An admin-only control that issues a fresh session id and clears local state, so cold start can be re-tested without clearing browser data. This is a development convenience and is not exposed to visitors, who have the separate and intentional deletion flow described in `COPY.md`.

### Explicitly not building

No queues, no sharding, no read replicas, no caching layer, no horizontal scaling story. One user, 750 items, a few thousand events per session, and a database that answers in single-digit milliseconds. **Any abstraction introduced "for scale" without a second implementation behind it is speculative and gets cut.** The goal of this console is legibility, not throughput, and a reviewer who knows the field reads premature scale infrastructure as inexperience rather than foresight.

### Privacy

The console displays pseudonymous session codes only. It never shows an IP, a name, or anything tying a session to a person, because none of that is collected. Authentication is required everywhere. The claims the README makes about this system's data have to stay true on the admin side too, and this is the surface where they would quietly stop being true.

---

## 7. Telemetry

### 7.1 Envelope

`{event_id, session_id, seq, ts_mono, ts_wall, demo, surface, mode, type, payload}`

`event_id` is client-generated so ingest is idempotent. `demo` is a hard boolean in the envelope. `surface` is one of `home | category | search | detail | compare | cart`.

### 7.2 Types

`page_view`, `item_impression`, `view_start`, `view_end`, `detail_view_start`, `detail_view_end`, `pointer_batch`, `scroll_batch`, `hover_start`, `hover_end`, `click`, `zoom`, `gallery_advance`, `panel_open`, `search`, `autocomplete_select`, `filter`, `sort`, `cart_add`, `cart_remove`, `wishlist`, `checkout_start`, `rec_impression`, `visibility_change`, `session_end`.

`pointer_batch`: `{t0, dt[], dx[], dy[], target_id[]}`, delta-encoded. Sample with `requestAnimationFrame` over coalesced pointer events. Flush every 250ms over WebSocket, `sendBeacon` on unload.

`rec_impression`: `{rail_id, policy_id, model_version, slate[], propensities[]}`. Log propensities from the first commit, including while the policy is random.

### 7.3 Cross-browser normalization

Pointer coalescing differs across engines, so raw trajectories partly measure the browser. **Resample every trajectory onto a fixed 60Hz grid by linear interpolation before any feature extraction.** Record browser, engine version, device pixel ratio, viewport size and pointer type on every session. Touch sessions have no hover: pointer type gates the motor family off entirely and the profile falls back to attention and exploration signals.

### 7.4 Safety

Telemetry never breaks the UI. All instrumentation wrapped, silent failure, events dropped under backpressure rather than queued unboundedly.

---

## 8. The canonical item view

One function in `features/`. One source of truth for dwell. Unit-tested against hand-built visibility timelines.

```
An item VIEW is a maximal interval where the item's card is >= 50% visible
  for >= 300ms continuously, merging gaps < 500ms into a single view.
A DETAIL_VIEW is a distinct type: the product detail page for that item.
When an item is visible in multiple surfaces at once, attribute the view to
  the surface holding pointer focus; ties resolve to the deepest surface
  (detail > compare > grid > rail).
Close a view on: visibility below 50% for >= 500ms, navigation, tab blur,
  or session end.
Mode is assigned at view OPEN and does not change mid-view.
```

Required fixtures: simple open/close, merge-gap, multi-surface tie, tab blur mid-view, rapid scroll producing sub-threshold exposures, mode precedence.

---

## 9. Features and leakage

### 9.1 The label

Tier-1 weak label for an item: a **commitment event** (cart add, wishlist, or checkout) for that item later in the session.

Features for a view are computed from the view interval **truncated at the first commitment event for that item, minus a 1000ms buffer**. Sealing is enforced by the window spec in code.

### 9.2 Signature

`f(events, window_spec, item_context) -> float | None`

`window_spec` carries explicit `[t_start, t_end]` bounds and a seal reason. Returning `None` means genuinely unavailable in this mode or surface; **never impute zero**, and carry availability as its own indicator.

Features are **recomputed from the window at each trigger**, not incrementally folded. At this catalog size that costs microseconds and removes online/offline divergence at the root.

### 9.3 Gate 0 signal set

Eight signals, all safe:

1. Item dwell, `log(1+t)`, normalized per §4.2
2. Viewport time via `IntersectionObserver`
3. Hover dwell on target element
4. Max scroll depth
5. Scroll reversals
6. Peak pointer velocity on approach
7. Trajectory curvature (area under curve) and x-flips
8. Fast skip — the negative-class definition, not a feature

### 9.4 Later signals and their leakage class

Added in Gate 1: revisit count, focused idle, acceleration profile, pause count, category breadth, query specificity, attention split across spec/images/reviews, zoom and gallery advances — all safe.

Conditional, gated: cursor-to-target distance (only when the cursor is active; excluded within 2s of a commitment event), A↔B switching and filter or sort usage (session-level only, never per-item features).

**Permanently excluded from the interest model:** micro-oscillation near Add to Cart, and all cart/wishlist/checkout events. The first is near-tautological with the label and its missingness correlates with the label; the second is the label. Both may feed a separate commitment model that is never presented as an interest model.

### 9.5 Fast-skip threshold

Not a hardcoded constant. Fit the exposure distribution per surface and mode, take the antimode of the bimodal fit, and freeze the result in a committed constant with the fitting notebook beside it. If the distribution is not bimodal, fall back to engagement banding in the manner of Lagun & Lalmas (2016). Report sensitivity at ±0.5s.

---

## 10. Gate 0 — Definition of Done

Nothing in Gate 1 begins until all of these are true.

1. Catalog pipeline produces 750 context items and 60 core items, with generated titles, all brand strings replaced in every served field, and thumbnails generated. 50 random items spot-checked by hand for products that are themselves branding.
2. Storefront serves every surface in §6 with its own identity and no borrowed trade dress.
3. Consent gate blocks all telemetry until accepted.
4. SDK emits every event type in §7.2 with correct envelopes, including `mode` and `surface`.
5. Ingest persists events idempotently and maintains Redis session state.
6. `features/` implements the eight Gate 0 signals with explicit window specs.
7. **Item-view fixtures pass**, including all six required cases.
8. **Leakage test passes** and fails the build on violation: assert no feature function reads an event at or after its window seal. Table-driven over every signal.
9. **Skew test passes:** replay a logged session offline at the same sealed checkpoints the online path used; compare with per-feature tolerances (exact for counts, 1e-9 relative for continuous). Log a continuous skew metric per deploy rather than asserting a boolean.
10. Every surface has been through the §6.6 review loop at least twice, screenshots saved to `docs/screens/`, all five interaction states and all three data states present, accessibility floor met.
11. Deployed and reachable at a URL.
12. Consent copy written, reviewed, and live. Draft it as plain language a person actually reads: what is recorded (how you move, scroll and click, not what you type), what is not (no account, no name, no IP), how long it is kept (90 days), and a visible way to delete it.
13. `README.md` exists with screenshots from `docs/screens/`, a short GIF of the profile panel updating, and the §14 honesty section. `NOTICE` file carries the ABO attribution and CC BY-NC 4.0 terms; the repo's own code license is separate from the dataset's.
14. **The author can browse one session, open the raw event log, and confirm by hand that view boundaries and modes match what actually happened.** This is a manual gate and it does not get skipped.

---

## 11. Gate 1 — modeling and simulation

**Ranker.** LambdaRank over within-session item pairs, not pointwise classification. ~20 items per session becomes ~190 comparisons, which is the difference between trainable and not. Calibrated per mode.

**The ranker trains on raw (normalized) signals, not the five family composites.** [Amended — the composite-averaging rule below was originally written for variance reduction on a small human corpus. It does not apply to a gradient-boosted ranker trained on hundreds of synthetic sessions, and hand-averaging signals into five numbers before a tree model sees them destroys exactly the interactions trees exist to find. Signals are still normalized within (session, mode, surface) per §4.2; only the further step of averaging normalized signals into family composites is skipped for this consumer. See the signal-weighting vector below for the one place composites are still the right representation, and STATE.md for the recovery numbers that surfaced this.] Raw signals are stored for ablation regardless of which representation any given consumer trains on.

**Build the simulator before the ranker.** The ranker trains primarily on synthetic sessions, so it cannot exist first. Order within Gate 1: simulator, then calibration against real traces, then ranker, then profile updater.

**Taste vector**, fully specified:

```
v_0 = catalog centroid                  # NOT the zero vector; normalize(0)
                                        # is undefined and the first update
                                        # would crash or produce NaN
w_i = clip(2 * p_i - 1, -0.5, 1.0)     # p_i = calibrated interest
w_i = -0.5                              # if the view is a fast skip
v  <- normalize( (1 - lambda) * v + eta * w_i * e_i )
eta = 0.3,  lambda = 0.067              # ~10-view half-life
```

Until a session has 3 scored views, serve the population prior rather than the session's own vector; below that the vector is mostly initialization noise and the panel will show the visitor something meaningless at exactly the moment they are deciding whether the demo is impressive.

Unit tests assert unit norm after arbitrary update sequences, bounded magnitude, and convergence into the correct region of item space for a scripted preference sequence.

**Signal-weighting vector.** Five composite weights (attention, motor conflict, exploration, comparison, availability — plus `directional` where that family exists), initialized at the prior fit on simulated data, updated within session by online ridge regression, shrunk toward the prior by evidence count. No hierarchical model, no clustering. This is the one consumer that keeps the composite representation: a session's own view count is the only evidence an online per-session estimator has, and five (or six) dimensions is what keeps that estimation tractable — a different data regime from the ranker above, which is why the two now train on two different representations of the same underlying signals rather than one.

**Simulator.** Five archetypes — Skimmer, Deliberator, Price-hunter, Image-driven, Spec-reader — each with a known taste vector and a known signal-weighting vector.

Critical: parameterize the agent **independently of the feature set**. Do not write "curvature proportional to conflict," which makes recovery tautological. Simulate the underlying process — drift-diffusion over item utility, a gaze-then-reach motor model with signal-dependent noise, a reading model for scroll — and let curvature, velocity and pause structure emerge. Fit motor and timing parameters to the author's own traces.

**Gate 1 DoD:**

- Spearman ρ > 0.6 between predicted interest and known utility on held-out simulated sessions
- Archetype separation: linear probe on recovered signal-weighting vectors classifies the five archetypes at > 70%
- **Negative control passes:** shuffle injected utilities, assert ρ ≈ 0 and archetype accuracy ≈ chance. A pipeline that clears the positive bar but fails this has leakage.
- Per-mode metrics reported separately

---

## 12. Gate 2 — recommend, ablate, ship

- Epsilon-greedy recommender over the context catalog. Candidate generation by exact cosine on the taste vector with category and price-band filters. MMR diversity. A permanent fraction of sessions served a uniformly random policy.
- **Ablation harness.** For each non-excluded signal and each family, retrain and remeasure recovery with it removed. Output a ranked contribution table. This is the most interesting artifact in the repo: it answers what trajectory curvature actually buys you under a declared generative model, and it needs no participants.
- Load test at the latency budget: **p95 < 250ms** from trigger to pushed update. Score on semantic triggers (view end, hover threshold, scroll milestone, panel open, search submit), not on every flush.
- Admin console per §6.7: sessions list, session signal table, live view, event log viewer, signal distributions, new-profile control. Behind auth. Plus feature importances, per-mode metrics, and the ablation table.
- README including the honesty section in §14.

---

## 13. Gate 3 — optional

LinUCB with propensity logging. Off-policy estimators validated **against known truth on simulated data**, where the estimator's unbiasedness can actually be demonstrated. Session-level intent model trained on [UCI, 12,330 sessions, 15.5% conversion](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset) and the [Coveo release](https://github.com/coveooss/shopper-intent-prediction-nature-2020) — the one real-human number in the project. LSTM comparison arm. Playwright simulator mode.

---

## 14. README honesty section

> **What this shows.** A real-time pipeline from raw browsing behavior to calibrated interest estimates and recommendations, p95 latency N ms, over a 750-item catalog with full e-commerce IA. On simulated shoppers with known preferences it recovers item ranking at ρ = X and separates five behavioral archetypes at Y%. An ablation over the behavioral signals quantifies each one's contribution under a declared generative model. Browsing mode is modeled as a stratum, because dwell time means opposite things in directed search and in discovery browsing.
>
> **What this does not show.** Anything about how people in general weight behavioral signals. The human data here is my own browsing plus a few consenting visitors — enough to validate the instrument and calibrate the simulator's motor parameters, not enough to support any inferential claim. The deployed ranker is trained primarily on synthetic data.
>
> **Fabricated content.** Product images derive from Amazon Berkeley Objects under CC BY-NC 4.0 and some show manufacturer logos. All brand names in the listing text are invented; prices, ratings and reviews are generated and labeled as such in the interface. Nothing here describes a real product, and this site is not affiliated with any retailer and copies no retailer's identity.
>
> **On inferring intent from motor behavior.** Cursor position is a weak proxy for attention: inactive over half the time, lagging gaze by roughly 700ms, with large individual variation. Mouse dynamics are also re-identifiable, which is why telemetry here is consent-gated, pseudonymous and deleted after 90 days. That one undergraduate can build this is the part worth sitting with.

---

## 15. Test inventory

1. Leakage audit, table-driven, build-failing
2. Online/offline skew at sealed checkpoints
3. Item-view fixtures, all six cases
4. Mode assignment fixtures, including precedence
5. Taste vector properties: unit norm, bounded magnitude, scripted convergence
6. Recovery bar and negative control
7. Invariance: curvature rotation-invariant, normalizers scale-invariant, dwell monotone in exposure
8. Resampling: one trajectory sampled at different rates yields features within tolerance
9. Load test at the latency budget
10. Availability: no feature ever imputes zero for a genuinely missing signal

---

## 16. References

- Moe (2003), *Buying, Searching, or Browsing*, J. Consumer Psychology — https://myscp.onlinelibrary.wiley.com/doi/abs/10.1207/S15327663JCP13-1&2_03
- Broder (2002), *A Taxonomy of Web Search*, SIGIR Forum — https://sigir.org/files/forum/F2002/broder.pdf
- Yi et al. (2014), *Beyond Clicks: Dwell Time for Personalization*, RecSys — https://www.hongliangjie.com/publications/recsys2014.pdf
- Lagun & Lalmas (2016), WSDM — https://dl.acm.org/doi/10.1145/2835776.2835833
- Huang, White & Buscher (2012), CHI — https://jeffhuang.com/papers/GazeCursor_CHI12.pdf
- Claypool et al. (2001), IUI — https://dl.acm.org/doi/10.1145/359784.359836
- Freeman (2018) — https://doi.org/10.1177/0963721417746793
- Leontyev & Yamauchi (2021), Cognitive Science — https://onlinelibrary.wiley.com/doi/10.1111/cogs.13046
- Requena et al. (2020), Scientific Reports — https://www.nature.com/articles/s41598-020-73622-y
- Sakar et al. (2019), Neural Computing & Applications — https://link.springer.com/article/10.1007/s00521-018-3523-0
- Amazon Berkeley Objects — https://registry.opendata.aws/amazon-berkeley-objects/
