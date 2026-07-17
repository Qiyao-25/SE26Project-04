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
  MoonOutlined,
  SunOutlined,
} from '@ant-design/icons';

import {
  Outlet,
  useNavigate,
  useLocation,
} from 'react-router-dom';

import { useApp } from '../context/AppContext';

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

const PAGE_TITLES = {
  '/workspace': {
    title: '论文检索与发现',
    sub: '工作空间 · 推荐与搜索',
  },
  '/learning': {
    title: '学习空间',
    sub: '收藏 / 笔记 / 历史 / 画像',
  },
  '/admin': {
    title: '管理员后台',
    sub: '系统管理端',
  },
  '/settings': {
    title: '设置',
    sub: '抓取订阅 / 账户 / 网页',
  },
};

export default function MainLayout({
  themeMode,
  setThemeMode,
}) {
  const navigate = useNavigate();
  const location = useLocation();

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
        title: onPaperDetail ? '论文详情' : PAGE_TITLES['/workspace'].title,
        sub: onPaperDetail
          ? '工作空间 · 阅读中（可切换其他页签，返回工作空间仍保留本篇）'
          : '工作空间仍保留正在阅读的论文 · 点「工作空间」可回到详情',
      }
    : PAGE_TITLES['/workspace'];

  const meta = onPaperDetail || pathKey === '/workspace'
    ? workspaceMeta
    : (PAGE_TITLES[pathKey] || {
        title: 'PaperMate',
        sub: '',
      });

  const menuItems = [
    {
      key: '/workspace',
      icon: <HomeOutlined />,
      label: lockedPaperId ? '工作空间（阅读中）' : '工作空间',
    },
    {
      key: '/learning',
      icon: <BookOutlined />,
      label: '学习空间',
    },
    ...(showAdminNav
      ? [
          {
            key: '/admin',
            icon: <DashboardOutlined />,
            label: '管理员后台',
          },
        ]
      : []),
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '设置',
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

  return (
    <Layout className="main-layout">
      <Sider
        width={248}
        theme={themeMode === 'dark' ? 'dark' : 'light'}
        className="main-sider"
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
        />

        <div className="sider-footer">
          <Button
            block
            icon={<LogoutOutlined />}
            onClick={() => {
              logout();
              navigate('/login');
            }}
          >
            退出登录
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
                ? '浅色模式'
                : '深色模式'}
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
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
