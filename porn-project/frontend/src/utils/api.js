/**
 * API utility module — wraps fetch calls to serve.py REST endpoints.
 * During development, Vite proxies /api/* to localhost:8888.
 * In production, requests go to the same origin (serve.py serves both).
 */

import toast from 'react-hot-toast';

const API_BASE = '/api';

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(errBody.error || `HTTP ${res.status}`);
  }
  return res.json();
}

async function fetchJSONWithToast(url, options, successMsg) {
  const promise = fetchJSON(url, options);
  toast.promise(promise, {
    loading: 'Saving...',
    success: successMsg,
    error: (err) => `Error: ${err.message}`,
  });
  return promise;
}

// ── GET endpoints ──────────────────────────────────────────────────────

export async function fetchVideos() {
  return fetchJSON(`${API_BASE}/videos`);
}

export async function fetchCategories() {
  return fetchJSON(`${API_BASE}/categories`);
}

export async function fetchCategorySchema() {
  return fetchJSON(`${API_BASE}/categoriesSchema`);
}

export async function fetchBlacklist() {
  return fetchJSON(`${API_BASE}/blacklist`);
}

export async function fetchPlaylists() {
  return fetchJSON(`${API_BASE}/playlists`);
}

export async function fetchTags() {
  return fetchJSON(`${API_BASE}/tags`);
}

export async function fetchHistory() {
  return fetchJSON(`${API_BASE}/history`);
}

export async function fetchStreams(videoUrl) {
  return fetchJSON(`${API_BASE}/streams?url=${encodeURIComponent(videoUrl)}`);
}

/**
 * Ask the server to re-scrape a fresh remoteThumbnail for one video (its
 * signed CDN preview URL has likely expired) and persist it to videos.json.
 * Resolves to the fresh URL, or '' if none could be found.
 */
export async function refreshThumbnail(viewkey) {
  const { remoteThumbnail } = await fetchJSON(`${API_BASE}/refresh-thumbnail?viewkey=${encodeURIComponent(viewkey)}`);
  return remoteThumbnail || '';
}

export async function fetchFilterPresets() {
  return fetchJSON(`${API_BASE}/filter_presets`);
}

// ── POST endpoints ─────────────────────────────────────────────────────

/**
 * Ask Claude to suggest a category for one or more videos by title.
 * `items` is [{ viewkey, title }, ...]. Resolves to
 * [{ viewkey, category_id }, ...] (no toast — callers show suggestions
 * inline rather than treating this as a save).
 */
export async function suggestCategories(items) {
  const { suggestions } = await fetchJSON(`${API_BASE}/categorize`, {
    method: 'POST',
    body: JSON.stringify(items),
  });
  return suggestions;
}

export async function saveCategories(data) {
  return fetchJSONWithToast(`${API_BASE}/categories`, {
    method: 'POST',
    body: JSON.stringify(data),
  }, 'Categories saved');
}

export async function saveCategorySchema(data) {
  return fetchJSONWithToast(`${API_BASE}/categoriesSchema`, {
    method: 'POST',
    body: JSON.stringify(data),
  }, 'Categories updated');
}

export async function saveBlacklist(data) {
  return fetchJSONWithToast(`${API_BASE}/blacklist`, {
    method: 'POST',
    body: JSON.stringify(data),
  }, 'Blacklist updated');
}

export async function savePlaylists(data) {
  return fetchJSONWithToast(`${API_BASE}/playlists`, {
    method: 'POST',
    body: JSON.stringify(data),
  }, 'Playlists saved');
}

export async function saveTags(data) {
  return fetchJSONWithToast(`${API_BASE}/tags`, {
    method: 'POST',
    body: JSON.stringify(data),
  }, 'Tags saved');
}

export async function saveHistory(data) {
  // Silent save for history to avoid spamming toasts
  return fetchJSON(`${API_BASE}/history`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function saveFilterPresets(data) {
  return fetchJSONWithToast(`${API_BASE}/filter_presets`, {
    method: 'POST',
    body: JSON.stringify(data),
  }, 'Saved search updated');
}
