import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';

export default function ProtectedRoute() {
  const { loggedIn } = useApp();
  const location = useLocation();
  if (!loggedIn) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}
