/**
 * Every user-facing string, verbatim from COPY.md. Components import from
 * here rather than writing copy inline — COPY.md is the source of truth
 * and this file is a direct transcription of it, not a paraphrase.
 */

export const consent = {
  heading: 'PRISM records how you browse',
  body: [
    'This is a research prototype, not a real store. Nothing here is for sale and no product on it is real.',
    'If you continue, PRISM records how you move your cursor, how you scroll, what you hover over, and what you click. It does not record what you type, and it never asks for your name, your email, or any account.',
    'You are identified only by a random code for this visit. Your IP address is not stored. Everything is deleted after 90 days, and you can delete it yourself at any time from the link in the footer.',
  ],
  primaryButton: 'Continue and record',
  secondaryButton: 'Browse without recording',
  footerCodePrefix: 'Your code:',
  footerRecordingOff: 'Recording off',
}

export const banner = {
  text: 'Research prototype. Products, prices, ratings and reviews are fabricated. Not affiliated with any retailer.',
}

export const reviewMarker = 'Synthetic review, generated for research'

export const emptyStates = {
  searchNoResults: {
    heading: (query: string) => `No matches for "${query}"`,
    body: 'Nothing in the catalog matches that. Try a broader word, or browse a category.',
    action: 'Clear search',
  },
  cartEmpty: {
    heading: 'Your cart is empty',
    body: 'Nothing here yet. Checkout is a stub and charges nothing.',
    action: 'Browse the catalog',
  },
  compareOneItem: {
    heading: 'Add one more to compare',
    body: 'Comparison needs at least two items. Pick another from the same category.',
    action: (category: string) => `Back to ${category}`,
  },
  profileBeforeThreeViews: {
    heading: 'Building your profile',
    body: 'PRISM needs a few more items before your profile means anything. Keep browsing.',
  },
  profileRecordingDeclined: {
    heading: 'Recording is off',
    body: "You chose to browse without recording, so there's nothing to show here. Nothing about this visit is being stored.",
  },
  railFallback: (category: string) => `Popular in ${category}`,
  filteredGridNoResults: {
    heading: 'No items match these filters',
    body: 'Try removing a filter. Price and rating are the two most likely culprits.',
    action: 'Clear all filters',
  },
}

export const loading = {
  slowNotice: 'Still working. This is a prototype on a small server.',
}

export const errors = {
  connectionLost: {
    heading: 'Recording paused',
    body: 'The connection to the server dropped. Your browsing still works and nothing is lost. PRISM will reconnect on its own.',
  },
  itemNotFound: {
    heading: "That item isn't here",
    body: 'It may have been removed from the catalog. Everything else still works.',
    action: 'Back to browsing',
  },
  deletionConfirmed: {
    heading: 'Deleted',
    body: (code: string) => `Everything recorded under ${code} is gone. If you keep browsing, a new visit starts with a new code.`,
  },
  deletionCodeNotFound: {
    heading: 'No data under that code',
    body: 'Either it was already deleted, or the code has a typo. Codes look like a7f3-92kd.',
  },
}

export const deleteDialog = {
  heading: 'Delete everything from this visit?',
  body: (code: string) => `This removes every event recorded under ${code}. It cannot be undone.`,
  confirm: 'Delete my data',
  cancel: 'Keep it',
}

export const whatGetsRecorded = {
  heading: 'What PRISM records',
  recorded:
    'Recorded: the position of your cursor over time, scroll position and speed, which items entered your screen and for how long, what you hovered over, what you clicked, what you searched for, what you added to the cart.',
  notRecorded:
    "Not recorded: what you type outside the search box, your name, your email, your IP address, anything that identifies you outside this visit.",
  why: 'Why: PRISM is a personal research project studying how browsing behavior relates to interest. Your data trains nothing that leaves this project and is never sold, shared, or published.',
  howLong: 'How long: 90 days, then automatic deletion. Or delete it now.',
}

export const reducedCaptureNotice =
  "On a touch screen, PRISM records less. Hover and cursor movement don't exist here, so about half the signals are unavailable."

export const home = {
  heroSlides: [
    {
      eyebrow: 'Instrumented catalog',
      title: 'Every item here is being measured',
      body: 'PRISM turns how you browse into a live interest profile. Nothing on this page is for sale.',
      cta: 'See what gets recorded',
      href: '/what-gets-recorded',
    },
    {
      eyebrow: 'Ten interests',
      title: "Browse like it's a real store, because the structure is",
      body: 'Categories, search and filtering work like a real storefront. Prices, ratings and reviews are generated for the study.',
      cta: 'Start browsing',
      href: '/category/Home%20%26%20Furniture',
    },
    {
      eyebrow: 'Your profile, visible',
      title: 'Watch your own profile take shape',
      body: "Open the profile panel any time to see PRISM's live read on what you're interested in.",
      cta: 'Open your profile',
      href: null,
    },
  ],
  categoryCards: [
    { title: 'Under $25', subtitle: 'Small enough to not think twice about', href: '/search?q=&price_band=Under+%2425' },
    { title: 'Rated 4.5 and up', subtitle: 'The items that held up under their own reviews', href: '/search?q=&min_rating=4.5' },
    { title: 'New in Outdoor & Garden', subtitle: 'Recently added to the catalog', href: '/category/Outdoor%20%26%20Garden' },
    { title: 'For people with pets', subtitle: 'Across food, toys and everyday supplies', href: '/category/Pet%20Supplies' },
  ],
  popularRailTitle: 'Popular right now',
}

export const detail = {
  alsoViewedTitle: 'Customers also viewed',
  similarTitle: 'Similar items',
  addToCart: 'Add to cart',
  addToList: 'Add to list',
  inStock: 'In stock',
  outOfStockNotice: 'Currently out of stock — check back later',
  qty: 'Qty',
  syntheticNotice: 'Price, rating and stock are fabricated for this research prototype',
  aboutThisItem: 'About this item',
  specifications: 'Specifications',
  reviews: 'Reviews',
}

export const compare = {
  heading: 'Compare',
  body: 'Comparing items from the same near-substitute set. Price, rating and reviews are generated; everything else is the real listing attribute.',
  remove: 'Remove',
}

export const cart = {
  heading: 'Your cart',
  itemCount: (n: number) => `${n} item${n === 1 ? '' : 's'}`,
  subtotal: 'Subtotal',
  proceedToCheckout: 'Proceed to checkout',
}

export const checkout = {
  heading: 'Checkout',
  stubNotice: 'This is a stub. No payment is collected and nothing is charged.',
  placeOrder: 'Place order',
  confirmedHeading: 'Order confirmed',
  confirmedBody: "This didn't charge you anything — checkout is a stub. Thanks for trying PRISM.",
  continueBrowsing: 'Continue browsing',
}

export const terms = {
  recording: 'recording',
  yourCode: 'your code',
  pseudonymous: 'pseudonymous',
  researchPrototype: 'research prototype',
  catalog: 'catalog',
  delete: 'delete',
  item: 'item',
}
