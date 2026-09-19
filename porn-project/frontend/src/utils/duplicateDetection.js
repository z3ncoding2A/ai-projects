/**
 * Fuzzy duplicate detection for the video library. The scraper pulls from
 * the profile page plus "related" and "recommended" crawls, so the same
 * underlying video very plausibly appears more than once under different
 * viewkeys (different site, re-upload, etc.) — see plans/improvements_audit.md.
 *
 * Strategy: comparing all pairs of 8,000+ videos (~65M comparisons) isn't
 * something to run on a UI thread. Instead:
 *   1. Sort by duration (cheap, O(n log n)).
 *   2. Slide a window over the sorted list — only compare a video against
 *      others within a small duration tolerance. Two unrelated videos are
 *      extremely unlikely to run for the exact same number of seconds, so
 *      this prunes the vast majority of the 8,103×8,103 comparison space
 *      before any string comparison happens.
 *   3. Within a duration-tolerant window, compare normalized titles with a
 *      token-overlap (Jaccard) similarity score.
 *   4. Union matching pairs into groups (union-find), return groups of 2+.
 */

const STOPWORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'with', 'for',
  'her', 'his', 'she', 'he', 'my', 'i', 'is', 'gets', 'get',
]);

/** Lowercase, strip punctuation, drop stopwords, return a token array. */
function tokenize(title) {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length > 1 && !STOPWORDS.has(t));
}

/** Jaccard similarity of two token sets: |intersection| / |union|. */
function similarity(tokensA, tokensB) {
  if (tokensA.length === 0 || tokensB.length === 0) return 0;
  const setA = new Set(tokensA);
  const setB = new Set(tokensB);
  let intersection = 0;
  for (const t of setA) if (setB.has(t)) intersection++;
  const union = setA.size + setB.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

class UnionFind {
  constructor(ids) {
    this.parent = new Map(ids.map((id) => [id, id]));
  }
  find(x) {
    while (this.parent.get(x) !== x) {
      this.parent.set(x, this.parent.get(this.parent.get(x)));
      x = this.parent.get(x);
    }
    return x;
  }
  union(a, b) {
    const ra = this.find(a);
    const rb = this.find(b);
    if (ra !== rb) this.parent.set(ra, rb);
  }
}

/**
 * @param {Array} videos - video objects with viewkey, title, rawDuration, rawViews
 * @param {object} opts
 * @param {number} opts.durationToleranceSec - max duration difference to even consider comparing titles
 * @param {number} opts.similarityThreshold - minimum Jaccard score to treat two videos as duplicates
 * @returns {Array<Array>} groups of 2+ video objects, sorted by group size desc then total views desc
 */
export function findDuplicateGroups(videos, { durationToleranceSec = 3, similarityThreshold = 0.6 } = {}) {
  const withDuration = videos.filter((v) => v.rawDuration > 0 && v.title);
  const sorted = [...withDuration].sort((a, b) => a.rawDuration - b.rawDuration);
  const tokensByViewkey = new Map(sorted.map((v) => [v.viewkey, tokenize(v.title)]));

  const uf = new UnionFind(sorted.map((v) => v.viewkey));

  for (let i = 0; i < sorted.length; i++) {
    const a = sorted[i];
    const tokensA = tokensByViewkey.get(a.viewkey);
    for (let j = i + 1; j < sorted.length; j++) {
      const b = sorted[j];
      if (b.rawDuration - a.rawDuration > durationToleranceSec) break; // sorted — nothing further can match
      const sim = similarity(tokensA, tokensByViewkey.get(b.viewkey));
      if (sim >= similarityThreshold) uf.union(a.viewkey, b.viewkey);
    }
  }

  const groupsByRoot = new Map();
  for (const v of sorted) {
    const root = uf.find(v.viewkey);
    if (!groupsByRoot.has(root)) groupsByRoot.set(root, []);
    groupsByRoot.get(root).push(v);
  }

  return Array.from(groupsByRoot.values())
    .filter((g) => g.length >= 2)
    .sort((a, b) => {
      if (b.length !== a.length) return b.length - a.length;
      const viewsA = a.reduce((s, v) => s + (v.rawViews || 0), 0);
      const viewsB = b.reduce((s, v) => s + (v.rawViews || 0), 0);
      return viewsB - viewsA;
    });
}
