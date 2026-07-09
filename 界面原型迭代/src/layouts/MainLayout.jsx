import { Layout, Menu, Button, Typography, Space, Tag } from 'antd';
import {
  HomeOutlined,
  BookOutlined,
  SettingOutlined,
  LogoutOutlined,
  DashboardOutlined
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

const PAGE_TITLES = {
  '/workspace': { title: '论文检索与发现', sub: '工作空间 · 推荐与搜索' },
  '/learning': { title: '学习空间', sub: '收藏 / 笔记 / 历史 / 画像' },
  '/admin': { title: '管理员后台', sub: '系统管理端' },
  '/settings': { title: '设置', sub: '抓取订阅 / 账户 / 网页' }
};

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, persona, topics, isAdmin, showAdminNav } = useApp();

  const pathKey = location.pathname.startsWith('/paper') ? '/workspace' : location.pathname;
  const meta = PAGE_TITLES[pathKey] || { title: 'PaperMate', sub: '' };

  const menuItems = [
    { key: '/workspace', icon: <HomeOutlined />, label: '工作空间' },
    { key: '/learning', icon: <BookOutlined />, label: '学习空间' },
    ...(showAdminNav ? [{ key: '/admin', icon: <DashboardOutlined />, label: '管理员后台' }] : []),
    { key: '/settings', icon: <SettingOutlined />, label: '设置' }
  ];

  return (
    <Layout className="main-layout">
      <Sider width={248} theme="light" className="main-sider">
        <div className="logo-area">
          <div className="logo-row">
            <span className="logo-mark">P</span>
            <div className="logo-text">
              <Title level={5} style={{ margin: 0 }}>PaperMate</Title>
              <Text type="secondary" style={{ fontSize: 12 }}>ArXiv 智能论文阅读</Text>
            </div>
          </div>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[pathKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />

        <div className="sider-footer">
          {showAdminNav && !isAdmin && (
            <Text className="demo-admin-tip">
              演示模式：管理员入口暂时可见，正式环境可关闭。
            </Text>
          )}
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
            <Title level={4} style={{ margin: 0 }}>{meta.title}</Title>
            <Text type="secondary">{meta.sub}</Text>
          </div>
          <Space className="header-tags" wrap>
            <Tag color={isAdmin ? 'red' : 'blue'}>
              {isAdmin ? '管理员' : `画像: ${persona}`}
            </Tag>
            <Tag>{topics.join(', ')}</Tag>
          </Space>
        </Header>
        <Content className="main-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}