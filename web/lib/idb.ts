import type { Story, TimelineEvent } from "./types";

const DB_NAME = "timeliner";
const DB_VERSION = 1;
const STORE_STORIES = "stories";
const STORE_EVENTS = "events";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_STORIES))
        db.createObjectStore(STORE_STORIES, { keyPath: "slug" });
      if (!db.objectStoreNames.contains(STORE_EVENTS))
        db.createObjectStore(STORE_EVENTS, { keyPath: "id" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function cacheStories(stories: Story[]): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  const db = await openDb();
  const tx = db.transaction(STORE_STORIES, "readwrite");
  const store = tx.objectStore(STORE_STORIES);
  stories.forEach((s) => store.put(s));
  return new Promise((res, rej) => {
    tx.oncomplete = () => res();
    tx.onerror = () => rej(tx.error);
  });
}

export async function getCachedStories(): Promise<Story[]> {
  if (typeof indexedDB === "undefined") return [];
  const db = await openDb();
  const tx = db.transaction(STORE_STORIES, "readonly");
  return new Promise((res, rej) => {
    const req = tx.objectStore(STORE_STORIES).getAll();
    req.onsuccess = () => res(req.result as Story[]);
    req.onerror = () => rej(req.error);
  });
}

export async function cacheEvents(events: TimelineEvent[]): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  const db = await openDb();
  const tx = db.transaction(STORE_EVENTS, "readwrite");
  const store = tx.objectStore(STORE_EVENTS);
  events.forEach((e) => store.put(e));
  return new Promise((res, rej) => {
    tx.oncomplete = () => res();
    tx.onerror = () => rej(tx.error);
  });
}

export async function getCachedEventsByStory(
  storyId: string
): Promise<TimelineEvent[]> {
  if (typeof indexedDB === "undefined") return [];
  const db = await openDb();
  const tx = db.transaction(STORE_EVENTS, "readonly");
  return new Promise((res, rej) => {
    const req = tx.objectStore(STORE_EVENTS).getAll();
    req.onsuccess = () =>
      res((req.result as TimelineEvent[]).filter((e) => e.story_id === storyId));
    req.onerror = () => rej(req.error);
  });
}
