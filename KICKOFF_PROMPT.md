# Kickoff prompt for Claude Code

**Before you paste this:**

1. `gh auth login` (once)
2. `git init` in an empty directory, put `BUILD_BRIEF.md` in the root
3. Put the three retailer screenshots in `docs/reference/` — structural reference only
4. Have Postgres and Redis reachable, Python 3.11+ and Node installed
5. In Claude Code: `/plugin install frontend-design`, then add the Playwright MCP and Context7 MCP servers

Then paste everything below the line.

---

Read `BUILD_BRIEF.md` in full before writing any code. It is the specification for this project and it is authoritative. Where this message and the brief disagree, this message wins.

Four files are already in the repo and are not yours to rewrite:

- `COPY.md` — every string a person reads. Consent gate, banner, empty states, errors, terminology. Use it verbatim. Do not improvise UI copy; if a string is needed that `COPY.md` doesn't cover, write it in that file's voice and add it there.
- `assets/` — the wordmark, mark and favicon. This is the identity. Don't generate another one.
- `.gitignore` — already correct. The image corpus and `docs/reference/` must stay out of every commit.
- `NOTICE` — attribution and licensing. Keep it accurate as the catalog pipeline evolves.

We are building PRISM: an instrumented storefront that infers browsing interest from behavioral signals in real time. I am the only regular user; there are no research participants. The evaluation substrate is a simulator with known ground truth.

## How I want this run

Build continuously through all four gates. **Do not stop to ask my permission between gates.** Verify each gate's Definition of Done yourself, commit, and keep going. Stop only if you hit something genuinely ambiguous or you believe the spec is wrong, and then say which and why rather than guessing.

Before the first line of code, do these three things and then proceed without waiting:

1. List anything in the brief that is ambiguous, underspecified, or wrong. Fix what you can justify; flag what you can't.
2. State the module and file layout you're creating.
3. Confirm back to me the three constraints that are correctness requirements rather than preferences: the sealed feature window and leakage rules in §9, the canonical item-view definition in §8, and the browsing-mode stratum in §4. If any of those is implemented loosely, everything downstream is invalid and the failure is silent.

## Session continuity

This will not finish in one context window, so build for resumption from the start:

- Maintain `STATE.md` at the repo root: current gate, what's done, what's next, every open question, every decision made and why. Update it after each module, not at the end.
- Commit at every gate boundary with the gate number in the message, and commit working increments in between.
- Any follow-up session should be able to read `BUILD_BRIEF.md` plus `STATE.md` and continue without me re-explaining anything.

## Git

- `gh repo create prism --private --source=. --remote=origin` at the start. **Private**, and it stays private until the synthetic-content labeling, the consent gate, and noindex are all in place.
- Push after each gate commit.
- `.gitignore` from the first commit: raw source images, generated thumbnails, `.env`, model artifacts, Parquet dumps, `node_modules`, `__pycache__`. **Never commit the image corpus** — it is hundreds of megabytes and it will make the repo unusable. Commit the pipeline that produces it.
- Commit `.env.example`. No credentials in the repo, ever. Postgres and Redis config via environment variables.

## Build order

Gate 0 first and in this order, shortest path to something I can browse and whose event log I can read by hand: catalog pipeline → storefront surfaces → telemetry SDK → ingest → features library → the three tests. Then Gates 1, 2, 3 as specified in the brief.

## This has to look good, and I mean that literally

Read §6.5 and §6.6 of the brief before you write a single component, and treat them as correctness requirements rather than style preferences. This is a portfolio piece. If it looks like a generic AI-generated web app — centered everything, gradient hero, three shadowed cards in a row, emoji icons, default form controls, no hover or empty states — it has failed no matter how green the tests are, and I would rather you spend an extra hour per surface than ship that.

Use the `frontend-design` plugin. Choose a design direction and commit to it before coding, do not discover it while coding.

Run the screenshot review loop in §6.6 on every single surface, minimum two passes: build it, screenshot it with Playwright at 1440 and 768, actually look at the image, name three specific defects, fix them, screenshot again. "Specific" means "the price baseline is 3px off the card grid," not "improve the spacing." Save the finals to `docs/screens/` for the README.

`docs/reference/` holds three screenshots of a major retailer. Use them for structure only: header composition, how a results grid packs information, how a detail page distributes gallery and buy box, how facet rails organize. Take none of the color, wordmark, typeface or assets. PRISM's identity is §6.0. That folder is gitignored and never enters a commit.

## Constraints I will hold you to

- No real retailer's wordmark, logo, palette, typeface, or program names. Structure and interaction patterns only. PRISM's identity is specified in §6.0.
- No real brand names in any served text. Incidental logos in source photographs are fine and expected; see §5.3.
- Consent gate before any telemetry initializes.
- Every feature function takes an explicit window spec. No feature reads an event at or after its seal.
- Missing signals return `None` and carry an availability indicator. Never impute zero.
- Tests that assert correctness, not tests that assert the code does what the code does. Write them alongside each module, never at the end.
- If you find yourself weakening a test to make it pass, stop and tell me instead.

## The one manual gate

Gate 0's last item is mine, not yours: I browse a session, open the raw event log, and confirm by hand that the view boundaries and modes match what I actually did. Build me a small event-log viewer so I can do that, flag in `STATE.md` when it's ready, and continue into Gate 1 while it waits for me.
