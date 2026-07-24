/** Lightweight bus so paper detail body can push text selections into the notes panel. */

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
  const normalized = {
    text,
    chunkId: payload.chunkId || null,
    pageNo: payload.pageNo ?? null,
    section: payload.section || null,
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

/** Wrap current selection in <mark>; returns selected text or null. */
export function highlightDomSelection(container) {
  const read = readDomSelection(container);
  if (!read) return null;

  container.querySelectorAll('mark.pm-annotation-highlight').forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) return;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
    parent.normalize?.();
  });

  try {
    const mark = document.createElement('mark');
    mark.className = 'pm-annotation-highlight';
    read.range.surroundContents(mark);
  } catch {
    // Cross-node ranges cannot always be wrapped; quote fill still works.
  }

  read.selection.removeAllRanges();
  return read.text;
}
