import { Navigate, Outlet } from 'react-router-dom';
import { useApp } from '../context/AppContext';

export default function AdminRoute() {
  const { isAdmin, authReady } = useApp();

  if (!authReady) return null;

  if (!isAdmin) {
    return <Navigate to="/workspace" replace />;
  }

  return <Outlet />;
}
