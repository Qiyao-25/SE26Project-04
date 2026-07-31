import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import { useApp } from '../context/AppContext';

export default function ProtectedRoute() {
  const { loggedIn, authReady } = useApp();
  const location = useLocation();
  if (!authReady) return <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}><Spin tip="正在验证登录状态..." /></div>;
  if (!loggedIn) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}
