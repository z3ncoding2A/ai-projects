/**
 * Formatting utilities for display strings.
 */

/**
 * @deprecated Superseded by the tree-based category system (categoryTree in
 * useVideoStore, seeded with these same 8 ids/colors). Kept only for the
 * legacy HTML template's reference point; do not add new call sites in
 * React components — use `useCategoryColor`/`useCategoryLabel` or look the
 * node up directly in `categoryTree` instead.
 */
export const CATEGORY_COLORS = {
  public:  'var(--cat-public)',
  pending: 'var(--cat-pending)',
  least:   'var(--cat-least)',
  average: 'var(--cat-avg)',
  most:    'var(--cat-most)',
  explode: 'var(--cat-explode)',
  related: 'var(--cat-related)',
  recommended: 'var(--cat-recommended)',
};

/** @deprecated see CATEGORY_COLORS */
export const CATEGORY_LABELS = {
  none:    'Uncategorized',
  public:  'Public',
  pending: 'Pending',
  least:   'Least Liked',
  average: 'Average',
  most:    'Most Liked',
  explode: 'EXPLODE!!!',
  related: 'Related',
  recommended: 'Recommended',
};

/** @deprecated see CATEGORY_COLORS */
export const ASSIGNED_CATEGORIES = ['public', 'pending', 'least', 'average', 'most', 'explode', 'related', 'recommended'];

/** Seed data for the category tree, used once on first load if categories-schema.json is empty. */
export const SEED_CATEGORIES = [
  { id: 'public',      name: 'Public',      color: '#2ecc71', icon: '🌍', parentId: null, sortOrder: 0 },
  { id: 'pending',     name: 'Pending',     color: '#8b5cf6', icon: '⏳', parentId: null, sortOrder: 1 },
  { id: 'least',       name: 'Least Liked', color: '#7f8c9a', icon: '👎', parentId: null, sortOrder: 2 },
  { id: 'average',     name: 'Average',     color: '#3b82f6', icon: '👍', parentId: null, sortOrder: 3 },
  { id: 'most',        name: 'Most Liked',  color: '#f59e0b', icon: '🔥', parentId: null, sortOrder: 4 },
  { id: 'explode',     name: 'EXPLODE!!!',  color: '#ff2d78', icon: '💥', parentId: null, sortOrder: 5 },
  { id: 'related',     name: 'Related',     color: '#06b6d4', icon: '🔗', parentId: null, sortOrder: 6 },
  { id: 'recommended', name: 'Recommended', color: '#f97316', icon: '⭐', parentId: null, sortOrder: 7 },
];

/**
 * Build lookup indexes for a flat category tree array:
 * - byId: Map<id, node>
 * - childrenOf: Map<parentId|null, node[]> (sorted by sortOrder)
 */
export function buildCategoryIndex(nodes) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const childrenOf = new Map();
  for (const n of nodes) {
    const key = n.parentId || null;
    if (!childrenOf.has(key)) childrenOf.set(key, []);
    childrenOf.get(key).push(n);
  }
  for (const list of childrenOf.values()) list.sort((a, b) => a.sortOrder - b.sortOrder);
  return { byId, childrenOf };
}

/**
 * Generate a unique category id. `crypto.randomUUID()` requires a secure
 * context (HTTPS or localhost) — this app is served over plain HTTP via a
 * Tailscale IP, where it's undefined, so fall back to getRandomValues
 * (not secure-context-gated) or, failing that, Math.random.
 */
export function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

/** All ids in the subtree rooted at nodeId, including nodeId itself. */
export function getDescendantIds(nodeId, childrenOf) {
  const out = new Set([nodeId]);
  const stack = [nodeId];
  while (stack.length) {
    const cur = stack.pop();
    for (const child of childrenOf.get(cur) || []) {
      if (!out.has(child.id)) {
        out.add(child.id);
        stack.push(child.id);
      }
    }
  }
  return out;
}

/** Decode HTML entities from scraped titles */
export function decodeHTML(str) {
  if (!str) return '';
  const el = document.createElement('textarea');
  el.innerHTML = str;
  return el.value;
}

/** Format raw view count to human-readable string */
export function formatViews(raw) {
  if (!raw && raw !== 0) return '';
  if (raw >= 1_000_000) return `${(raw / 1_000_000).toFixed(1)}M views`;
  if (raw >= 1_000) return `${(raw / 1_000).toFixed(1)}K views`;
  return `${raw} views`;
}

/** Format raw duration (seconds) to mm:ss or hh:mm:ss */
export function formatDuration(seconds) {
  if (!seconds) return '';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** Get the effective category for a video given local overrides */
export function getVideoCategory(video, categories) {
  const localCat = categories[video.viewkey];
  if (localCat && localCat !== '' && localCat !== 'none') return localCat;
  if (video.category && video.category !== '' && video.category !== 'none') return video.category;
  return 'none';
}

/** Build the Pornhub / xHamster embed URL */
export function buildEmbedUrl(url, viewkey) {
  if (url.includes('pornhub.com')) {
    return `https://www.pornhub.com/embed/${viewkey}?hd=1&autoplay=1`;
  }
  if (url.includes('xhamster.com')) {
    const m = url.match(/videos\/[\w-]+-(\w+)$/) || url.match(/(\w+)$/);
    if (m) return `https://xhamster.com/xembed.php?video=${m[1]}&autoplay=1`;
  }
  return url;
}
