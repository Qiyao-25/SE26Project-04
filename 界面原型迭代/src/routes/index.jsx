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
import AdminRoute from './AdminRoute';
import SettingsPage from '../pages/Settings/SettingsPage';

const theme = {
  token: {
    colorPrimary: '#3b63f4',
    colorInfo: '#3b63f4',
    colorSuccess: '#16a34a',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    colorText: '#111827',
    colorTextSecondary: '#667085',
    colorBgLayout: '#f6f8fc',
    colorBgContainer: '#ffffff',
    borderRadius: 14,
    wireframe: false,
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Microsoft YaHei', sans-serif"
  },
  components: {
    Layout: {
      headerBg: 'rgba(246, 248, 252, 0.78)',
      siderBg: 'rgba(255, 255, 255, 0.74)'
    },
    Card: {
      borderRadiusLG: 20
    },
    Button: {
      borderRadius: 12,
      controlHeight: 38
    },
    Menu: {
      itemBorderRadius: 14,
      itemSelectedBg: 'rgba(59, 99, 244, 0.12)',
      itemSelectedColor: '#3b63f4'
    }
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
                  <Route element={<AdminRoute />}>
                    <Route path="/admin" element={<AdminPage />} />
                  </Route>
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
