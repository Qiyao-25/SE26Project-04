/** Keep「立即同步」loading across route/tab switches while a sync request is in flight. */

let inflight = null;
const listeners = new Set();

function notify(syncing) {
  listeners.forEach((listener) => {
    try {
      listener(syncing);
    } catch {
      // ignore
    }
  });
}

export function isSubscriptionSyncing() {
  return Boolean(inflight);
}

export function subscribeSubscriptionSync(listener) {
  listeners.add(listener);
  listener(Boolean(inflight));
  return () => listeners.delete(listener);
}

export async function runSubscriptionSync(task) {
  if (inflight) return inflight;
  inflight = (async () => {
    notify(true);
    try {
      return await task();
    } finally {
      inflight = null;
      notify(false);
    }
  })();
  return inflight;
}
