import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { App as AntApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AppProvider } from '../context/AppContext';
import ProtectedRoute from './ProtectedRoute';
import MainLayout from '../layouts/MainLayout';
import LoginPage from '../pages/Login/LoginPage';
import WorkspacePage from '../pages/Workspace/WorkspacePage';
import PaperDetailPage from '../pages/PaperDetail/PaperDetailPage';
import LearningPage from '../pages/Learning/LearningPage';
import AdminPage from '../pages/Admin/AdminPage';
import SettingsPage from '../pages/Settings/SettingsPage';

const theme = {
  token: {
    colorPrimary: '#1677ff',
    borderRadius: 6,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
  }
};

export default function AppRoutes() {
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <AntApp>
        <AppProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<MainLayout />}>
                  <Route path="/" element={<Navigate to="/workspace" replace />} />
                  <Route path="/workspace" element={<WorkspacePage />} />
                  <Route path="/paper/:paperId" element={<PaperDetailPage />} />
                  <Route path="/learning" element={<LearningPage />} />
                  <Route path="/admin" element={<AdminPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
          </BrowserRouter>
        </AppProvider>
      </AntApp>
    </ConfigProvider>
  );
}
