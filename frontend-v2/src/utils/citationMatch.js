/**
 * Citation matching — maps an extracted field value back to the OCR bounding
 * box blocks it came from, so the viewer can highlight it on the page.
 *
 * The naive approach (lowercase substring of the block text) fails on most
 * real documents because the value the LLM returns is *normalized* while the
 * OCR text is *literal*:
 *
 *   value "AMITKUMAR"   vs block "First Name A M I T K U M A R"   (boxed form)
 *   value "01/07/1996"  vs block "Date of Birth 0 1 0 7 1 9 9 6"
 *   value "1250000"     vs block "Annual Income (Rs.) 12,50,000"
 *   value "Flat 302, …" vs block "Flat 302, Shanti Residency,\nLane 7, …"
 *   value "Amit Saket"  vs block "First Name A M I T Last Name S A K E T"
 *
 * So matching runs over a *compact* form — lowercase, alphanumerics only —
 * which erases spacing, separators, thousands commas, markdown and line
 * breaks on both sides at once. Four passes run in decreasing confidence:
 *
 *   exact       compact needle is a substring of the compact block
 *   partial     every significant token of the needle appears in the block
 *   approximate character-bigram similarity (survives OCR character noise)
 *   label       nothing matched the value, so point at the field's own label
 *
 * The first pass that produces a hit wins; later passes never run.
 */

// A needle shorter than this in compact form matches too much to be useful.
const MIN_NEEDLE_LEN = 3;
// A token this short ("of", "no") carries no locating power in a token match.
const MIN_TOKEN_LEN = 3;
// A needle matching more blocks than this is generic noise, not a citation.
const MAX_BLOCKS_PER_NEEDLE = 4;
// Bigram overlap required before a block counts as an approximate match.
const FUZZY_THRESHOLD = 0.62;
// Approximate matches are guesses — never highlight more than a couple.
const MAX_FUZZY_BLOCKS = 2;
// "1111111111" has one distinct bigram and would score 1.0 against any block
// holding a stray "11". Fuzzy matching needs real variety to mean anything.
const MIN_FUZZY_BIGRAMS = 6;
// Below this length an alphabetic needle is matched on word boundaries, so
// "count" cannot claim the block that says "Account".
const COMPACT_SAFE_LEN = 5;

// Values that say "this field is empty", not values to look for on the page.
const EMPTY_VALUES = new Set([
  'n/a', 'na', 'none', 'null', 'nil', 'not available', 'not applicable',
  'unknown', 'not found', 'not specified', 'not provided', '-', '--',
]);

// Words that appear on every form and would drag a highlight anywhere.
const STOPWORDS = new Set([
  'the', 'and', 'for', 'name', 'date', 'no', 'yes', 'true', 'false',
  'address', 'details', 'number', 'code', 'type', 'form', 'page',
]);

/** Strip markdown syntax so heading/emphasis markers do not break matching. */
export function stripMarkdown(text) {
  return (text || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`/g, '')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1') // links/images → their label
    .replace(/[*_#>|]/g, ' ')
    .replace(/^\s*[-+]\s+/gm, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Lowercase, markdown-free, single-spaced. Used for token work. */
export function normalizeText(text) {
  return stripMarkdown(text).toLowerCase().trim();
}

/**
 * Lowercase alphanumerics only. This is the form everything is compared in:
 * it collapses "A M I T", "12,50,000", "01/07/1996" and "Flat 302,\nLane 7"
 * onto the same footing as the model's normalized output.
 */
export function compact(text) {
  return normalizeText(text).replace(/[^a-z0-9]/g, '');
}

/** "date_of_birth" → "date of birth", for the label fallback pass. */
export function humanizeKey(key) {
  return String(key || '')
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .toLowerCase()
    .trim();
}

/** Significant tokens of a needle — short/stopword tokens are dropped. */
function significantTokens(text) {
  return normalizeText(text)
    .split(/[^a-z0-9]+/)
    .filter(t => t.length >= MIN_TOKEN_LEN && !STOPWORDS.has(t));
}

function isEmptyValue(str) {
  return !str || EMPTY_VALUES.has(str.toLowerCase().trim());
}

/**
 * Date strings are written one way by the model and another on the page, and
 * compacting erases only the separators — not the field order. So emit every
 * plausible ordering of the parsed parts.
 */
function dateVariants(str) {
  const out = [];
  const parts = str.match(/^(\d{1,4})[-/. ](\d{1,2})[-/. ](\d{1,4})$/);
  if (!parts) return out;

  let [, a, b, c] = parts;
  let day, month, year;
  if (a.length === 4) {
    [year, month, day] = [a, b, c];       // ISO: YYYY-MM-DD
  } else if (c.length === 4) {
    [day, month, year] = [a, b, c];       // DD/MM/YYYY (also covers MM/DD)
  } else {
    return out;
  }

  const dd = day.padStart(2, '0');
  const mm = month.padStart(2, '0');
  const yy = year.slice(-2);
  out.push(`${dd}${mm}${year}`, `${mm}${dd}${year}`, `${year}${mm}${dd}`, `${dd}${mm}${yy}`);

  const monthNames = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                      'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  const monthName = monthNames[parseInt(mm, 10) - 1];
  if (monthName) out.push(`${dd}${monthName}${year}`, `${monthName}${dd}${year}`);
  return out;
}

/**
 * Numbers get reformatted between page and model ("12,50,000" → 1250000,
 * "25000" → "25000.00"), so emit the digit-only and trailing-zero-free forms.
 *
 * Only genuinely numeric values qualify. Pulling the digits out of something
 * like "QQQQQ0000Q" would produce "0000", which matches any round number on
 * the page — a false citation dressed up as an exact one.
 */
function numberVariants(str) {
  const out = [];
  if (!/\d/.test(str)) return out;
  // Allow a currency marker, but nothing else alphabetic.
  const withoutCurrency = str.replace(/\b(rs|inr|usd|eur|gbp)\b\.?/gi, '').replace(/[₹$€£]/g, '');
  if (!/^[\d.,\s/-]+$/.test(withoutCurrency.trim())) return out;

  const cleaned = str.replace(/[^\d.,-]/g, '');
  if (!cleaned) return out;

  const digitsOnly = cleaned.replace(/[^\d]/g, '');
  if (digitsOnly.length >= MIN_NEEDLE_LEN) out.push(digitsOnly);

  // "12500.00" and "12500.0" are the same amount as "12500" on the page.
  const noTrailingZeros = cleaned.replace(/\.0+$/, '');
  if (noTrailingZeros !== cleaned) out.push(noTrailingZeros);
  return out;
}

/**
 * Turn a field's value into the list of strings worth looking for.
 * `rawValue` (pre-normalization, closer to the page) is preferred over the
 * validated value, and both contribute so either spelling can hit.
 */
export function buildNeedles(value, rawValue) {
  const needles = new Map(); // compact form → display form (deduped)

  const add = (str) => {
    const c = compact(str);
    if (c.length < MIN_NEEDLE_LEN) return;
    if (!needles.has(c)) needles.set(c, String(str).trim());
  };

  const addPrimitive = (v) => {
    if (v === null || v === undefined || v === '') return;

    // A boolean is never written as "true" on a form — the checkbox next to
    // the field label is. Let the label fallback handle those.
    if (typeof v === 'boolean') return;

    const str = String(v).trim();
    if (isEmptyValue(str)) return;
    // Base64 image payloads (signature/photo crops) have nothing on the page.
    if (str.length > 512) return;

    add(str);
    dateVariants(str).forEach(add);
    numberVariants(str).forEach(add);
  };

  const walk = (v) => {
    if (Array.isArray(v)) {
      v.forEach(walk);
    } else if (v && typeof v === 'object') {
      Object.values(v).forEach(walk);
    } else {
      addPrimitive(v);
    }
  };

  // A stringified array/object arrives from the editable table fields.
  const walkMaybeJson = (v) => {
    if (typeof v === 'string') {
      const trimmed = v.trim();
      if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
        try { walk(JSON.parse(trimmed)); return; } catch { /* plain string */ }
      }
    }
    walk(v);
  };

  if (rawValue !== undefined && rawValue !== null) walkMaybeJson(rawValue);
  if (value !== undefined && value !== null) walkMaybeJson(value);

  return Array.from(needles.entries())
    .map(([c, text]) => ({ text, compact: c }))
    // Longest first: the most specific needle should claim its blocks before
    // a short generic one gets a chance to.
    .sort((a, b) => b.compact.length - a.compact.length);
}

/** Character-bigram set, for the approximate pass. */
function bigrams(str) {
  const set = new Set();
  for (let i = 0; i < str.length - 1; i++) set.add(str.slice(i, i + 2));
  return set;
}

/** Whole-word occurrence, for needles too short to trust in compact space. */
function containsWord(normalizedText, word) {
  if (!word) return false;
  const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`).test(normalizedText);
}

/**
 * Does this block contain the needle? Compact containment is the workhorse —
 * it is what makes "A M I T K U M A R" and "12,50,000" matchable at all — but
 * a short all-letters needle is checked on word boundaries instead, where
 * compact matching would find it buried inside an unrelated word.
 */
function blockContains(candidate, needleCompact) {
  const isShortAlpha = needleCompact.length < COMPACT_SAFE_LEN && !/\d/.test(needleCompact);
  if (isShortAlpha) return containsWord(candidate.normalized, needleCompact);
  return candidate.compact.includes(needleCompact);
}

/** Fraction of the needle's bigrams present in the block. */
function bigramOverlap(needleGrams, blockCompact) {
  if (!needleGrams.size) return 0;
  const blockGrams = bigrams(blockCompact);
  let hits = 0;
  for (const g of needleGrams) if (blockGrams.has(g)) hits++;
  return hits / needleGrams.size;
}

/**
 * Locate the blocks a field value came from.
 *
 * @param {Array}  blocks     OCR blocks: { page, content, type, top_left_x, … }
 * @param {string} fieldKey   Field key, used for the label fallback
 * @param {*}      value      Validated (normalized) value
 * @param {*}      rawValue   Raw pre-normalization value, if available
 * @param {number} pageIndex  Page being displayed; blocks on other pages are
 *                            excluded so a page-2 box never lands on page 1
 * @returns {{ blocks: Array, matchType: 'exact'|'partial'|'approximate'|'label'|null }}
 */
export function findCitationBlocks({ blocks, fieldKey, value, rawValue, pageIndex = 0 }) {
  const empty = { blocks: [], matchType: null };
  if (!Array.isArray(blocks) || !blocks.length || !fieldKey) return empty;

  const candidates = blocks
    .filter(b => b.type !== 'image')
    .filter(b => b.page === undefined || b.page === null || b.page === pageIndex)
    .map(b => ({ block: b, compact: compact(b.content), normalized: normalizeText(b.content) }))
    .filter(c => c.compact.length > 0);

  if (!candidates.length) return empty;

  const needles = buildNeedles(value, rawValue);

  // ── Pass 1: exact containment in compact space ──
  // Needles are ordered longest-first; a needle that lights up half the page
  // is generic (a stray "20" or "no") and is dropped rather than trusted.
  const exact = new Set();
  for (const needle of needles) {
    const hits = candidates.filter(c => blockContains(c, needle.compact));
    if (!hits.length || hits.length > MAX_BLOCKS_PER_NEEDLE) continue;
    // Once a specific needle has landed, ignore the short ones that follow.
    if (exact.size && needle.compact.length < MIN_TOKEN_LEN + 1) continue;
    hits.forEach(h => exact.add(h.block));
  }
  if (exact.size) return { blocks: Array.from(exact), matchType: 'exact' };

  // ── Pass 2: all significant tokens present ──
  // Catches labels interleaved with the value, e.g. the value "Amit Saket"
  // against "First Name A M I T Last Name S A K E T".
  for (const needle of needles) {
    const tokens = significantTokens(needle.text).map(compact).filter(t => t.length >= MIN_TOKEN_LEN);
    if (tokens.length < 2) continue;
    const hits = candidates.filter(c => tokens.every(t => blockContains(c, t)));
    if (hits.length && hits.length <= MAX_BLOCKS_PER_NEEDLE) {
      return { blocks: hits.map(h => h.block), matchType: 'partial' };
    }
  }

  // ── Pass 3: approximate, for OCR character noise ──
  const longest = needles.find(n => n.compact.length >= 6);
  const grams = longest ? bigrams(longest.compact) : new Set();
  if (grams.size >= MIN_FUZZY_BIGRAMS) {
    const scored = candidates
      .map(c => ({ block: c.block, score: bigramOverlap(grams, c.compact) }))
      .filter(s => s.score >= FUZZY_THRESHOLD)
      .sort((a, b) => b.score - a.score)
      .slice(0, MAX_FUZZY_BLOCKS);
    if (scored.length) {
      return { blocks: scored.map(s => s.block), matchType: 'approximate' };
    }
  }

  // ── Pass 4: label fallback ──
  // The value is a checkbox, an image crop, or simply absent from the text
  // layer. Pointing at the field's own label still shows where to look.
  // Tried whole first, then the label's own significant tokens, so
  // "signature_detected" still finds the block containing "Signature".
  const label = humanizeKey(fieldKey);
  const labelNeedles = [compact(label), ...significantTokens(label).map(compact)]
    .filter(c => c.length >= MIN_NEEDLE_LEN);
  for (const labelNeedle of labelNeedles) {
    // Labels are printed as real words, so they are matched as real words.
    const hits = candidates.filter(c => containsWord(c.normalized, labelNeedle));
    if (hits.length && hits.length <= MAX_BLOCKS_PER_NEEDLE) {
      return { blocks: hits.map(h => h.block), matchType: 'label' };
    }
  }

  return empty;
}

// Strongest first — used to pick which page holds the best evidence.
const MATCH_RANK = { exact: 4, partial: 3, approximate: 2, label: 1 };

/**
 * Run the match over every page and return the page with the strongest
 * evidence, so hovering a field on a multi-page document lands on the page the
 * value actually appears on rather than silently finding nothing.
 *
 * Matching stays per-page rather than across the whole document: the
 * "too many blocks, this needle is generic" guard only means something
 * relative to a single page.
 *
 * @param {number} preferredPage Page currently on screen; wins ties, so the
 *                               view does not jump when the page in front of
 *                               the user is already as good a match as any.
 * @returns {{ blocks: Array, matchType: string|null, page: number|null }}
 */
export function findCitationAcrossPages({ blocks, fieldKey, value, rawValue, preferredPage = 0 }) {
  const none = { blocks: [], matchType: null, page: null };
  if (!Array.isArray(blocks) || !blocks.length) return none;

  const pages = Array.from(new Set(blocks.map(b => b.page ?? 0))).sort((a, b) => a - b);
  let best = none;
  let bestRank = 0;

  for (const page of pages) {
    const result = findCitationBlocks({ blocks, fieldKey, value, rawValue, pageIndex: page });
    if (!result.blocks.length) continue;
    const rank = MATCH_RANK[result.matchType] || 0;
    const winsOutright = rank > bestRank;
    const winsTie = rank === bestRank && page === preferredPage;
    if (winsOutright || winsTie) {
      best = { ...result, page };
      bestRank = rank;
    }
  }

  return best;
}
