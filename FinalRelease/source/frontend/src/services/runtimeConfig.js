export const USE_MOCK =
  String(import.meta.env.VITE_USE_MOCK ?? 'false').toLowerCase() === 'true';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
export const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 10000);
