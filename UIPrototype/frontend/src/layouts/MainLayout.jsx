import {
  Layout,
  Menu,
  Button,
  Typography,
  Space,
  Tag,
} from 'antd';

import {
  HomeOutlined,
  BookOutlined,
  SettingOutlined,
  LogoutOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  MoonOutlined,
  SunOutlined,
} from '@ant-design/icons';

import {
  Outlet,
  useNavigate,
  useLocation,
} from 'react-router-dom';

import { useApp } from '../context/AppContext';
import { useI18n } from '../i18n';

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

export default function MainLayout({
  themeMode,
  setThemeMode,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useI18n();

  const {
    logout,
    persona,
    topics,
    isAdmin,
    showAdminNav,
    lockedPaperId,
  } = useApp();

  const onPaperDetail = location.pathname.startsWith('/paper/');
  // 论文详情归属工作空间页签
  const pathKey = onPaperDetail ? '/workspace' : location.pathname;

  const workspaceMeta = lockedPaperId
    ? {
        title: onPaperDetail ? t('page.workspace.readingTitle') : t('page.workspace.title'),
        sub: onPaperDetail
          ? t('page.workspace.readingSub')
          : t('page.workspace.lockedSub'),
      }
    : {
        title: t('page.workspace.title'),
        sub: t('page.workspace.sub'),
      };

  const pageTitles = {
    '/workspace': workspaceMeta,
    '/learning': { title: t('page.learning.title'), sub: t('page.learning.sub') },
    '/admin': { title: t('page.admin.title'), sub: t('page.admin.sub') },
    '/papers': { title: t('page.library.title'), sub: t('page.library.sub') },
    '/settings': { title: t('page.settings.title'), sub: t('page.settings.sub') },
  };

  const meta = onPaperDetail || pathKey === '/workspace'
    ? workspaceMeta
    : (pageTitles[pathKey] || {
        title: 'PaperMate',
        sub: '',
      });

  const menuItems = [
    {
      key: '/workspace',
      icon: <HomeOutlined />,
      label: lockedPaperId ? t('nav.workspaceReading') : t('nav.workspace'),
    },
    {
      key: '/learning',
      icon: <BookOutlined />,
      label: t('nav.learning'),
    },
    ...(showAdminNav
      ? [
          {
            key: '/papers',
            icon: <DatabaseOutlined />,
            label: t('nav.library'),
          },
          {
            key: '/admin',
            icon: <DashboardOutlined />,
            label: t('nav.admin'),
          },
        ]
      : []),
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: t('nav.settings'),
    },
  ];

  const toggleTheme = () => {
    setThemeMode(
      themeMode === 'dark'
        ? 'light'
        : 'dark'
    );
  };

  const handleMenuClick = ({ key }) => {
    // 工作空间被论文锁定时：点「工作空间」回到该论文详情
    if (key === '/workspace' && lockedPaperId) {
      navigate(`/paper/${lockedPaperId}`);
      return;
    }
    navigate(key);
  };

  const handleLogout = () => {
    // 清理只属于当前登录会话的数据，再由全局上下文清理登录态
    sessionStorage.removeItem('papermate-session-subscriptions');
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <Layout className="main-layout">
      <Sider
        width={248}
        theme={themeMode === 'dark' ? 'dark' : 'light'}
        className="main-sider"
        style={{
          position: 'sticky',
          top: 0,
          height: '100vh',
          alignSelf: 'flex-start',
        }}
      >
        <div className="logo-area">
          <div className="logo-row">
            <span className="logo-mark">
              PM
            </span>

            <div className="logo-text">
              <Title
                level={5}
                style={{ margin: 0 }}
              >
                PaperMate
              </Title>

              <Text
                type="secondary"
                style={{ fontSize: 12 }}
              >
                ArXiv 智能论文阅读
              </Text>
            </div>
          </div>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[pathKey]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
          }}
        />

        <div
          className="sider-footer"
          style={{
            marginTop: 'auto',
            flexShrink: 0,
          }}
        >
          <Button
            block
            icon={<LogoutOutlined />}
            onClick={handleLogout}
          >
            {t('nav.logout')}
          </Button>
        </div>
      </Sider>

      <Layout>
        <Header className="main-header">
          <div className="header-title-wrap">
            <Title
              level={4}
              style={{ margin: 0 }}
            >
              {meta.title}
            </Title>

            <Text type="secondary">
              {meta.sub}
            </Text>
          </div>

          <Space
            className="header-tags"
            size={8}
            wrap
          >
            <Button
              className="theme-toggle-btn"
              icon={
                themeMode === 'dark'
                  ? <SunOutlined />
                  : <MoonOutlined />
              }
              onClick={toggleTheme}
              title={
                themeMode === 'dark'
                  ? '切换到浅色模式'
                  : '切换到深色模式'
              }
            >
              {themeMode === 'dark'
                ? t('nav.themeLight')
                : t('nav.themeDark')}
            </Button>

            <Tag color={isAdmin ? 'red' : 'blue'}>
              {isAdmin
                ? '管理员'
                : `画像: ${persona}`}
            </Tag>

            <Tag>
              {Array.isArray(topics) && topics.length > 0
                ? topics.join(', ')
                : '未设置研究方向'}
            </Tag>
          </Space>
        </Header>

        <Content className="main-content">
          <Outlet context={{ themeMode, setThemeMode }} />
        </Content>
      </Layout>
    </Layout>
  );
}
