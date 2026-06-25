/**
 * Formatting utilities for display strings.
 */

/** Map of category key → CSS color variable value */
export const CATEGORY_COLORS = {
  public:  'var(--cat-public)',
  pending: 'var(--cat-pending)',
  least:   'var(--cat-least)',
  average: 'var(--cat-avg)',
  most:    'var(--cat-most)',
  explode: 'var(--cat-explode)',
};

/** Map of category key → display label */
export const CATEGORY_LABELS = {
  none:    'Uncategorized',
  public:  'Public',
  pending: 'Pending',
  least:   'Least Liked',
  average: 'Average',
  most:    'Most Liked',
  explode: 'EXPLODE!!!',
};

/** Quick-action button config */
export const CATEGORY_BUTTONS = [
  { key: 'public',  label: 'PUB',  cls: 'pub' },
  { key: 'pending', label: 'PEND', cls: 'pend' },
  { key: 'least',   label: 'MIN',  cls: 'min' },
  { key: 'average', label: 'AVG',  cls: 'avg' },
  { key: 'most',    label: 'MAX',  cls: 'max' },
  { key: 'explode', label: '💥',   cls: 'exp' },
];

export const ASSIGNED_CATEGORIES = ['public', 'pending', 'least', 'average', 'most', 'explode'];

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
