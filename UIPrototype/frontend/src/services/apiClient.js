import axios from 'axios';
import { API_BASE_URL, API_TIMEOUT_MS } from './runtimeConfig';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' }
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('papermate.accessToken');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response.data?.data ?? response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('papermate.accessToken');
      window.dispatchEvent(new Event('papermate:auth-expired'));
    }
    if (error.code === 'ECONNABORTED') {
      return Promise.reject(new Error('请求超时，请确认后端服务已启动后重试'));
    }
    if (!error.response) {
      return Promise.reject(new Error('无法连接后端服务，请检查 FastAPI 是否运行在 8000 端口'));
    }
    const payload = error.response.data;
    const message = payload?.message || payload?.detail || `请求失败（HTTP ${error.response.status}）`;
    return Promise.reject(new Error(message));
  }
);

export default apiClient;
