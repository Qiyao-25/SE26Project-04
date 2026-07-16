const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export async function requestApi(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {})
    }
  });
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(`后端返回了无效响应（HTTP ${response.status}）`);
  }
  if (!response.ok || body.code !== 'OK') {
    const error = new Error(body.message || `请求失败（HTTP ${response.status}）`);
    error.code = body.code || 'HTTP_ERROR';
    error.status = response.status;
    error.requestId = body.request_id;
    throw error;
  }
  return body.data;
}

export function isApiEnabled() {
  return import.meta.env.VITE_USE_MOCK !== 'true';
}
