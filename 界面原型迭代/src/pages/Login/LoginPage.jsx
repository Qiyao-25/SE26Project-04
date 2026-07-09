import { useState } from 'react';
import { Card, Tabs, Form, Input, Button, Typography, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import OnboardingModal from '../../components/auth/OnboardingModal';

const { Title, Text, Paragraph } = Typography;

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, loggedIn } = useApp();
  const [tab, setTab] = useState('login');
  const [showOnboard, setShowOnboard] = useState(false);

  if (loggedIn) {
    navigate('/workspace', { replace: true });
    return null;
  }

  const onLogin = (values) => {
    login(values.email);
    message.success('登录成功');
    navigate('/workspace');
  };

  const onRegister = () => {
    login('user@example.com');
    setShowOnboard(true);
  };

  const onOnboardDone = () => {
    setShowOnboard(false);
    message.success('引导完成，欢迎使用 PaperMate');
    navigate('/workspace');
  };

  return (
    <div className="auth-page">
      <Card className="auth-card" bordered>
        <Title level={3} style={{ textAlign: 'center' }}>PaperMate</Title>
        <Paragraph type="secondary" style={{ textAlign: 'center' }}>ArXiv 论文阅读工具</Paragraph>
        <Tabs
          activeKey={tab}
          onChange={setTab}
          centered
          items={[
            {
              key: 'login',
              label: '登录',
              children: (
                <Form layout="vertical" onFinish={onLogin}>
                  <Form.Item name="email" label="账号 / 邮箱" rules={[{ required: true }]}>
                    <Input placeholder="输入账号或邮箱" />
                  </Form.Item>
                  <Form.Item name="password" label="密码" rules={[{ required: true }]}>
                    <Input.Password placeholder="输入密码" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" block>登录</Button>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 12 }}>
                    普通用户：任意账号 · 管理员演示：输入 admin
                  </Text>
                </Form>
              )
            },
            {
              key: 'register',
              label: '注册',
              children: (
                <Form layout="vertical" onFinish={onRegister}>
                  <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}>
                    <Input placeholder="注册邮箱" />
                  </Form.Item>
                  <Form.Item name="password" label="密码" rules={[{ required: true }]}>
                    <Input.Password placeholder="设置密码" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" block>注册</Button>
                </Form>
              )
            }
          ]}
        />
      </Card>
      <OnboardingModal open={showOnboard} onDone={onOnboardDone} />
    </div>
  );
}
