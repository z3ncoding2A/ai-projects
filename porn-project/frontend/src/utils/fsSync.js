/**
 * File System Access API sync — ports the legacy template's "Connect Folder"
 * feature. Lets categories.json / blacklist.txt be written straight to a
 * user-chosen folder on disk, independent of serve.py's /api/* persistence.
 *
 * This is a *supplementary* sync path, not a replacement for the API:
 * - The React app always needs serve.py running to be served at all (unlike
 *   the old single-file template, which also worked from file://), so the
 *   "editing offline" rationale is weaker here.
 * - It still matters as a second write path and as a way to point the app at
 *   the actual project folder so categories.json / blacklist.txt update in
 *   place on disk without relying on the dev server's working directory.
 *
 * Conflict handling: on connect, disk contents (if present) win and are
 * merged into the store once. After that, every change writes to both the
 * API and disk in parallel — there is only one in-memory source of truth
 * (the Zustand store), so the two write targets can't disagree with each
 * other going forward, only with what was on disk before connecting.
 */

const DB_NAME = 'z3ncoding_fsapi';
const DB_STORE = 'handles';
const DB_KEY = 'projectDir';

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(DB_STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function saveDirHandle(handle) {
  const db = await openDB();
  const tx = db.transaction(DB_STORE, 'readwrite');
  tx.objectStore(DB_STORE).put(handle, DB_KEY);
  return new Promise((resolve, reject) => {
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

async function loadDirHandle() {
  const db = await openDB();
  const tx = db.transaction(DB_STORE, 'readonly');
  const req = tx.objectStore(DB_STORE).get(DB_KEY);
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

async function writeFile(dirHandle, name, content) {
  const fh = await dirHandle.getFileHandle(name, { create: true });
  const writable = await fh.createWritable();
  await writable.write(content);
  await writable.close();
}

async function readFile(dirHandle, name) {
  try {
    const fh = await dirHandle.getFileHandle(name);
    return await (await fh.getFile()).text();
  } catch (e) {
    return null; // file doesn't exist yet — not an error
  }
}

export function isSupported() {
  return typeof window !== 'undefined' && !!window.showDirectoryPicker;
}

/** Prompt the user to pick a folder, persist the handle for future sessions. */
export async function connectFolder() {
  if (!isSupported()) {
    throw new Error('Your browser does not support the File System Access API. Use Chrome or Edge.');
  }
  const dirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
  await saveDirHandle(dirHandle);
  return dirHandle;
}

/** On boot: reattach to a previously connected folder if permission is still granted. */
export async function reconnectFolder() {
  if (!isSupported()) return null;
  let dirHandle;
  try {
    dirHandle = await loadDirHandle();
  } catch (e) {
    return null;
  }
  if (!dirHandle) return null;

  try {
    const perm = await dirHandle.queryPermission({ mode: 'readwrite' });
    if (perm !== 'granted') return { dirHandle, needsReauth: true };
  } catch (e) {
    return null;
  }
  return { dirHandle, needsReauth: false };
}

/** Read categories.json + blacklist.txt from the connected folder, if present. */
export async function loadFromDisk(dirHandle) {
  const catText = await readFile(dirHandle, 'categories.json');
  const blText = await readFile(dirHandle, 'blacklist.txt');

  let categories = null;
  if (catText) {
    try {
      categories = JSON.parse(catText);
    } catch (e) {
      console.warn('Failed to parse categories.json from disk:', e);
    }
  }

  let blacklist = null;
  if (blText !== null) {
    blacklist = blText.split('\n').map((s) => s.trim()).filter(Boolean);
  }

  return { categories, blacklist };
}

/** Write categories.json + blacklist.txt to the connected folder. */
export async function saveToDisk(dirHandle, categories, blacklist) {
  const perm = await dirHandle.queryPermission({ mode: 'readwrite' });
  if (perm !== 'granted') {
    const req = await dirHandle.requestPermission({ mode: 'readwrite' });
    if (req !== 'granted') throw new Error('Permission denied');
  }
  await writeFile(dirHandle, 'categories.json', JSON.stringify(categories, null, 2));
  await writeFile(dirHandle, 'blacklist.txt', blacklist.join('\n') + '\n');
}
