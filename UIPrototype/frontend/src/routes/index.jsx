import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { App as AntApp, ConfigProvider } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import zhCN from 'antd/locale/zh_CN';
import enUS from 'antd/locale/en_US';
import { AppProvider } from '../context/AppContext';
import { LanguageProvider, useI18n } from '../i18n';
import ProtectedRoute from './ProtectedRoute';
import MainLayout from '../layouts/MainLayout';
import LoginPage from '../pages/Login/LoginPage';
import WorkspacePage from '../pages/Workspace/WorkspacePage';
import PaperDetailPage from '../pages/PaperDetail/PaperDetailPage';
import LearningPage from '../pages/Learning/LearningPage';
import AdminPage from '../pages/Admin/AdminPage';
import AdminRoute from './AdminRoute';
import SettingsPage from '../pages/Settings/SettingsPage';
import PaperLibraryPage from '../pages/PaperLibrary/PaperLibraryPage';


const getAntdTheme = (mode) => {
  if (mode === 'dark') {
    return {
      token: {
        colorPrimary: '#D18893',
        colorInfo: '#D18893',
        colorSuccess: '#22A06B',
        colorWarning: '#D97706',
        colorError: '#DC2626',

        colorText: '#F4EDF0',
        colorTextSecondary: '#B9ADB3',
        colorTextTertiary: '#8D8287',

        colorBgLayout: '#090708',
        colorBgContainer: '#151317',
        colorBorder: '#2A2328',
        colorBorderSecondary: '#332A30',

        borderRadius: 2,
        borderRadiusLG: 0,
        borderRadiusSM: 2,

        wireframe: false,

        fontFamily:
          "Inter, 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      },

      components: {
        Layout: {
          headerBg: 'rgba(17, 16, 19, 0.94)',
          siderBg: '#120E11',
          bodyBg: '#090708',
        },

        Card: {
          colorBgContainer: '#151317',
          colorBorderSecondary: '#2A2328',
          borderRadiusLG: 0,
        },

        Button: {
          borderRadius: 2,
          controlHeight: 40,
          colorPrimary: '#D18893',
          colorPrimaryHover: '#DB98A3',
          colorPrimaryActive: '#BC737F',
          primaryColor: '#FFFFFF',
        },

        Menu: {
          itemBg: 'transparent',
          itemColor: 'rgba(255, 255, 255, 0.76)',
          itemHoverColor: '#FFFFFF',
          itemHoverBg: 'rgba(255, 255, 255, 0.08)',
          itemSelectedColor: '#FFFFFF',
          itemSelectedBg: 'rgba(209, 136, 147, 0.18)',
          itemBorderRadius: 0,
        },

        Input: {
          colorBgContainer: '#171419',
          colorText: '#F4EDF0',
          colorTextPlaceholder: '#7D7278',
          colorBorder: '#30282E',
          activeBorderColor: '#D18893',
          borderRadius: 2,
        },

        Select: {
          colorBgContainer: '#171419',
          colorText: '#F4EDF0',
          colorBorder: '#30282E',
          borderRadius: 2,
        },

        Tabs: {
          itemColor: '#9B8F96',
          itemSelectedColor: '#F0D8DD',
          itemHoverColor: '#D18893',
          inkBarColor: '#D18893',
        },

        Table: {
          colorBgContainer: '#151317',
          headerBg: '#1B171B',
          headerColor: '#F4EDF0',
          colorText: '#F4EDF0',
          colorBorderSecondary: '#2A2328',
          borderRadius: 0,
        },

        Tag: {
          borderRadiusSM: 2,
        },

        Modal: {
          borderRadiusLG: 0,
        },
      },
    };
  }

  return {
    token: {
      colorPrimary: '#C97A88',
      colorInfo: '#C97A88',
      colorSuccess: '#22A06B',
      colorWarning: '#D97706',
      colorError: '#DC2626',

      colorText: '#231F22',
      colorTextSecondary: '#746A70',
      colorTextTertiary: '#9A8E95',

      colorBgLayout: '#F4EFF1',
      colorBgContainer: '#FBF8F9',
      colorBorder: '#E6DCE0',
      colorBorderSecondary: '#EFE7EA',

      borderRadius: 2,
      borderRadiusLG: 0,
      borderRadiusSM: 2,

      wireframe: false,

      fontFamily:
        "Inter, 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    },

    components: {
      Layout: {
        headerBg: 'rgba(251, 248, 249, 0.95)',
        siderBg: '#FCFAFB',
        bodyBg: '#F4EFF1',
      },

      Card: {
        colorBgContainer: '#FBF8F9',
        colorBorderSecondary: '#E9E0E4',
        borderRadiusLG: 0,
      },

      Button: {
        borderRadius: 2,
        controlHeight: 40,
        colorPrimary: '#C97A88',
        colorPrimaryHover: '#D48A97',
        colorPrimaryActive: '#B96C79',
        primaryColor: '#FFFFFF',
      },

      Menu: {
        itemBg: 'transparent',
        itemColor: '#5E545A',
        itemHoverColor: '#231F22',
        itemHoverBg: '#F3EAED',
        itemSelectedColor: '#B95F71',
        itemSelectedBg: '#F6EDEE',
        itemBorderRadius: 0,
      },

      Input: {
        colorBgContainer: '#FCFAFB',
        colorText: '#231F22',
        colorTextPlaceholder: '#A3949B',
        colorBorder: '#E2D7DB',
        activeBorderColor: '#C97A88',
        borderRadius: 2,
      },

      Select: {
        colorBgContainer: '#FCFAFB',
        colorText: '#231F22',
        colorBorder: '#E2D7DB',
        borderRadius: 2,
      },

      Tabs: {
        itemColor: '#80757C',
        itemSelectedColor: '#B95F71',
        itemHoverColor: '#C97A88',
        inkBarColor: '#C97A88',
      },

      Table: {
        colorBgContainer: '#FBF8F9',
        headerBg: '#F2EAED',
        headerColor: '#2B2428',
        colorText: '#231F22',
        colorBorderSecondary: '#E9E0E4',
        borderRadius: 0,
      },

      Tag: {
        borderRadiusSM: 2,
      },

      Modal: {
        borderRadiusLG: 0,
      },
    },
  };
};
export default function AppRoutes() {
  const [themeMode, setThemeMode] = useState(
    localStorage.getItem('papermate-theme') || 'dark'
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', themeMode);
    localStorage.setItem('papermate-theme', themeMode);
  }, [themeMode]);

  const theme = useMemo(() => getAntdTheme(themeMode), [themeMode]);
  return (
    <LanguageProvider>
      <LocalizedApp theme={theme} themeMode={themeMode} setThemeMode={setThemeMode} />
    </LanguageProvider>
  );
}

function LocalizedApp({ theme, themeMode, setThemeMode }) {
  const { language } = useI18n();
  const locale = language === 'en' ? enUS : zhCN;
  return (
    <ConfigProvider locale={locale} theme={theme}>
      <AntApp>
        <AppProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<ProtectedRoute />}>
                <Route
                  element={
                    <MainLayout
                      themeMode={themeMode}
                      setThemeMode={setThemeMode}
                    />
                  }
                >
                  <Route path="/" element={<Navigate to="/workspace" replace />} />
                  <Route path="/workspace" element={<WorkspacePage />} />
                  <Route path="/paper/:paperId" element={<PaperDetailPage />} />
                  <Route path="/learning" element={<LearningPage />} />
                  <Route element={<AdminRoute />}>
                    <Route path="/admin" element={<AdminPage />} />
                    <Route path="/papers" element={<PaperLibraryPage />} />
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
