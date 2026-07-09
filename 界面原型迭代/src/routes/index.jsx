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
    colorPrimary: '#A7793D',
    colorInfo: '#A7793D',
    colorSuccess: '#2F7D5C',
    colorWarning: '#C28A2E',
    colorError: '#B64B4B',

    colorText: '#1B2430',
    colorTextSecondary: '#6E6251',
    colorTextTertiary: '#9A8D78',

    colorBgLayout: '#0D1624',
    colorBgContainer: '#F4EBDD',
    colorBorder: 'rgba(93, 72, 46, 0.22)',

    borderRadius: 16,
    wireframe: false,

    fontFamily:
      "Inter, 'Times New Roman', 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  },

  components: {
    Layout: {
      headerBg: 'rgba(244, 235, 221, 0.88)',
      siderBg: '#0D1624',
      bodyBg: '#0D1624',
    },

    Card: {
      colorBgContainer: '#F4EBDD',
      colorBorderSecondary: 'rgba(93, 72, 46, 0.20)',
      borderRadiusLG: 20,
    },

    Button: {
      borderRadius: 12,
      controlHeight: 40,
      colorPrimary: '#A7793D',
      colorPrimaryHover: '#B98B4B',
      colorPrimaryActive: '#7E5A2B',
      primaryColor: '#FFF8EA',
    },

    Menu: {
      itemBg: 'transparent',
      itemColor: 'rgba(244, 235, 221, 0.72)',
      itemHoverColor: '#D8B36A',
      itemHoverBg: 'rgba(216, 179, 106, 0.10)',
      itemSelectedColor: '#F3D58A',
      itemSelectedBg: 'rgba(216, 179, 106, 0.16)',
      itemBorderRadius: 14,
    },

    Input: {
      colorBgContainer: '#FFF8EA',
      colorText: '#1B2430',
      colorTextPlaceholder: '#9A8D78',
      colorBorder: 'rgba(93, 72, 46, 0.24)',
      activeBorderColor: '#A7793D',
    },

    Select: {
      colorBgContainer: '#FFF8EA',
      colorText: '#1B2430',
      colorBorder: 'rgba(93, 72, 46, 0.24)',
    },

    Tabs: {
      itemColor: '#7C715F',
      itemSelectedColor: '#8A612F',
      itemHoverColor: '#A7793D',
      inkBarColor: '#A7793D',
    },

    Table: {
      colorBgContainer: '#F4EBDD',
      headerBg: '#E8DDC7',
      headerColor: '#1B2430',
      colorText: '#1B2430',
      colorBorderSecondary: 'rgba(93, 72, 46, 0.16)',
    },

    Tag: {
      borderRadiusSM: 999,
    },
  },
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