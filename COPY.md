# PRISM — interface copy

Every string a person reads. Written here rather than improvised during the build, because the consent screen is the first thing anyone sees and empty states are where demos visibly fall apart.

**Voice:** plain, direct, a little dry. This is a research instrument wearing a store's clothes, and it does not pretend otherwise. No exclamation marks. No "Oops!" No euphemism about what is recorded.

---

## 1. Consent gate

Full-screen, before any telemetry initializes. No store visible behind it, because letting someone browse for two seconds before asking is the dark pattern this screen exists to avoid.

**Heading**
> PRISM records how you browse

**Body**
> This is a research prototype, not a real store. Nothing here is for sale and no product on it is real.
>
> If you continue, PRISM records how you move your cursor, how you scroll, what you hover over, and what you click. It does not record what you type, and it never asks for your name, your email, or any account.
>
> You are identified only by a random code for this visit. Your IP address is not stored. Everything is deleted after 90 days, and you can delete it yourself at any time from the link in the footer.

**Primary button**
> Continue and record

**Secondary button**
> Browse without recording

**Footer line**
> Your code: `a7f3-92kd` · [What gets recorded](#) · [Delete my data](#)

**Note for the build:** "Browse without recording" must actually work and must not nag. A consent screen with one real option is not consent. Sessions that decline get no `session_id`, emit no events, and see a small persistent footer note reading `Recording off`.

---

## 2. Persistent site banner

Top of every page, above the header, dismissible per session but reappearing on a new one.

> Research prototype. Products, prices, ratings and reviews are fabricated. Not affiliated with any retailer.

---

## 3. Review block marker

On every review, inline, not hidden in a tooltip.

> Synthetic review, generated for research

---

## 4. Empty states

Each one is: what this is, why it's empty, what to do.

**Search, no results**
> No matches for "{query}"
> Nothing in the catalog matches that. Try a broader word, or browse a category.
> `[Clear search]`

**Cart, empty**
> Your cart is empty
> Nothing here yet. Checkout is a stub and charges nothing.
> `[Browse the catalog]`

**Compare, one item**
> Add one more to compare
> Comparison needs at least two items. Pick another from the same category.
> `[Back to {category}]`

**Profile panel, before three scored views**
> Building your profile
> PRISM needs a few more items before your profile means anything. Keep browsing.

**Profile panel, recording declined**
> Recording is off
> You chose to browse without recording, so there's nothing to show here. Nothing about this visit is being stored.

**Recommendation rail, insufficient data**
> Popular in {category}
> (Rail falls back to popularity silently. No empty state, no apology, no "we don't know you yet." A rail that explains itself is a rail that has given up.)

**Filtered grid, no results**
> No items match these filters
> Try removing a filter. Price and rating are the two most likely culprits.
> `[Clear all filters]`

---

## 5. Loading states

Skeletons everywhere, no spinners, no copy. A skeleton that matches the shape of what's coming says "loading" better than the word does.

The one exception, if a request exceeds 3 seconds:

> Still working. This is a prototype on a small server.

---

## 6. Errors

Structure: what happened, why, what to do.

**Connection lost**
> Recording paused
> The connection to the server dropped. Your browsing still works and nothing is lost. PRISM will reconnect on its own.

**Recommendations failed**
> (Silent. Fall back to popularity ranking. Never show a person an error for a feature they did not ask for.)

**Item not found**
> That item isn't here
> It may have been removed from the catalog. Everything else still works.
> `[Back to browsing]`

**Data deletion confirmed**
> Deleted
> Everything recorded under `{code}` is gone. If you keep browsing, a new visit starts with a new code.

**Data deletion, code not found**
> No data under that code
> Either it was already deleted, or the code has a typo. Codes look like `a7f3-92kd`.

---

## 7. Deletion confirmation dialog

**Heading**
> Delete everything from this visit?

**Body**
> This removes every event recorded under `{code}`. It cannot be undone.

**Buttons**
> `[Delete my data]` `[Keep it]`

Not "OK" and "Cancel." The buttons say what they do.

---

## 8. "What gets recorded" page

Reachable from the consent screen and the footer. The full data dictionary in plain language, then the field-level table.

**Heading**
> What PRISM records

**Body**
> **Recorded:** the position of your cursor over time, scroll position and speed, which items entered your screen and for how long, what you hovered over, what you clicked, what you searched for, what you added to the cart.
>
> **Not recorded:** what you type outside the search box, your name, your email, your IP address, anything that identifies you outside this visit.
>
> **Why:** PRISM is a personal research project studying how browsing behavior relates to interest. Your data trains nothing that leaves this project and is never sold, shared, or published.
>
> **How long:** 90 days, then automatic deletion. Or delete it now.

Followed by the generated field table from the event schema, so the page cannot drift out of date with the code.

---

## 9. Reduced capture notice, under 768px

> On a touch screen, PRISM records less. Hover and cursor movement don't exist here, so about half the signals are unavailable.

---

## 10. Terms to keep consistent

| Use | Never |
|---|---|
| recording | tracking, monitoring, surveilling |
| your code | your ID, your user ID, your session token |
| pseudonymous | anonymous |
| research prototype | demo, beta, MVP |
| catalog | inventory, store, shop |
| delete | clear, remove, reset |
| item | product, SKU, listing |

"Anonymous" is the important one. The data is pseudonymous, mouse dynamics are re-identifiable in principle, and claiming anonymity would be a false statement rather than a loose one.

---

## 11. Additional interface copy (added during build)

Strings the original brief didn't cover, written in this file's voice per
the build instructions, and kept here so they stay auditable in one place
rather than scattered inline in components.

### 11.1 Home hero carousel

**Slide 1**
> Instrumented catalog
> Every item here is being measured
> PRISM turns how you browse into a live interest profile. Nothing on this page is for sale.
> `[See what gets recorded]`

**Slide 2**
> 750 items, ten interests
> Browse like it's a real store, because the structure is
> Categories, search and filtering work like a real storefront. Prices, ratings and reviews are generated for the study.
> `[Start browsing]`

**Slide 3**
> Your profile, visible
> Watch your own profile take shape
> Open the profile panel any time to see PRISM's live read on what you're interested in.
> `[Open your profile]`

### 11.2 Home category cards

> Under $25
> Small enough to not think twice about

> Rated 4.5 and up
> The items that held up under their own reviews

> New in Outdoor & Garden
> Recently added to the catalog

> For people with pets
> Across food, toys and everyday supplies

### 11.3 Rail titles

- "Popular right now" (home, popularity fallback rail)
- "Customers also viewed" (detail page)
- "Similar items" (detail page)
- `Popular in {category}` (fallback, already in §4)

### 11.4 Buy box (product detail)

> Add to cart
> Add to list
> In stock
> `{n} left` (low stock)
> Currently out of stock — check back later
> Qty

### 11.5 Compare view

> Compare
> Comparing items from the same near-substitute set. Price, rating and reviews are generated; everything else is the real listing attribute.
> `[Remove]` (per column)

### 11.6 Cart & checkout stub

> Your cart
> `{n} item(s)`
> Subtotal
> `[Proceed to checkout]`
> Checkout
> This is a stub. No payment is collected and nothing is charged.
> `[Place order]`
> Order confirmed
> This didn't charge you anything — checkout is a stub. Thanks for trying PRISM.
> `[Continue browsing]`

### 11.7 Item detail — synthetic content marker

Same marker as reviews (§3), shown once near price:
> Price, rating and stock are fabricated for this research prototype

### 11.8 404 / item not found page action

Reuses §6 "Item not found" copy verbatim; the "Back to browsing" link
points to `/`.

