/** Lightweight bus so PDF viewer can push text selections into the notes panel. */

let captureHandler = null;
let pendingSelection = null;

export function setAnnotationSelectionHandler(handler) {
  captureHandler = typeof handler === 'function' ? handler : null;
  if (captureHandler && pendingSelection) {
    const payload = pendingSelection;
    pendingSelection = null;
    captureHandler(payload);
  }
}

export function pushAnnotationSelection(payload) {
  if (!payload) return false;
  const text = String(payload.text || '').trim();
  if (text.length < 1) return false;
  const rects = Array.isArray(payload.rects)
    ? payload.rects
    : (Array.isArray(payload.highlight_rects) ? payload.highlight_rects : []);
  const normalized = {
    text,
    chunkId: payload.chunkId || payload.chunk_id || null,
    pageNo: payload.pageNo ?? payload.page_no ?? null,
    section: payload.section || null,
    rects,
    highlightColor: payload.highlightColor || payload.highlight_color || '#fde68a',
  };
  if (captureHandler) {
    captureHandler(normalized);
    return true;
  }
  pendingSelection = normalized;
  return true;
}

export function readDomSelection(container) {
  const selection = window.getSelection?.();
  if (!selection || selection.isCollapsed || selection.rangeCount < 1) return null;
  const text = String(selection.toString() || '').replace(/\s+/g, ' ').trim();
  if (text.length < 1) return null;
  const range = selection.getRangeAt(0);
  if (container && !container.contains(range.commonAncestorContainer)) return null;
  return { selection, range, text };
}
