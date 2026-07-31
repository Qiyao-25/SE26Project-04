/** Display timezone for the product UI (China). */
export const DISPLAY_TIME_ZONE = 'Asia/Shanghai';

/**
 * Parse API timestamps. Backend often stores UTC as naive ISO
 * (no "Z" / offset); treat those as UTC so they are not shown 8h early.
 */
export function parseApiDate(value) {
  if (value == null || value === '' || value === '—') return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  if (typeof value === 'number') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const text = String(value).trim();
  if (!text) return null;

  // Already has timezone: Z or ±HH:MM
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(text)) {
    const date = new Date(text);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  // Naive ISO / SQLite style → assume UTC
  const normalized = text.includes('T') ? text : text.replace(' ', 'T');
  const date = new Date(`${normalized}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(value, { withSeconds = false, fallback = '—' } = {}) {
  const date = parseApiDate(value);
  if (!date) return value == null || value === '' ? fallback : String(value);

  return date.toLocaleString('zh-CN', {
    timeZone: DISPLAY_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    ...(withSeconds ? { second: '2-digit' } : {}),
    hour12: false,
  });
}

/** Calendar date in Asia/Shanghai, e.g. 2026-07-21 */
export function formatDateKey(value = new Date()) {
  const date = value instanceof Date ? value : parseApiDate(value);
  if (!date) return '';
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: DISPLAY_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}
