import { useEffect, useState } from 'react';
import { Card, Tabs, Form, Input, Button, Typography, message, Spin } from 'antd';
import {
  BookOutlined,
  ExperimentOutlined,
  NodeIndexOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import OnboardingModal from '../../components/auth/OnboardingModal';

const { Text } = Typography;

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, register, loggedIn, authReady } = useApp();
  const [tab, setTab] = useState('login');
  const [showOnboard, setShowOnboard] = useState(false);
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();

  useEffect(() => {
    if (authReady && loggedIn) navigate('/workspace', { replace: true });
  }, [authReady, loggedIn, navigate]);

  if (!authReady || loggedIn) return <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}><Spin tip="正在准备 PaperMate..." /></div>;

  const onLogin = async (values) => {
    try {
      await login(values.email, values.password);
      message.success(values.email?.trim().toLowerCase() === 'admin' ? '管理员登录成功' : '登录成功');
      navigate('/workspace');
    } catch (error) {
      message.error(error.message || '登录失败');
    }
  };

  const onRegister = async (values) => {
    try {
      await register(values.email, values.password);
      setShowOnboard(true);
    } catch (error) {
      message.error(error.message || '注册失败');
    }
  };

  const onOnboardDone = () => {
    setShowOnboard(false);
    message.success('引导完成，欢迎使用 PaperMate');
    navigate('/workspace');
  };

  const fillDemoUser = () => {
    loginForm.setFieldsValue({ email: 'student@example.com', password: '123456' });
    message.info('已填入普通用户演示账号');
  };

  const fillAdmin = () => {
    loginForm.setFieldsValue({ email: 'admin', password: 'admin123' });
    message.info('已填入管理员演示账号');
  };

  return (
    <div className="auth-page">
      <section className="auth-visual">
        <div>
          <div className="auth-brand">
            <span className="auth-brand-mark">PM</span>
            <span>PaperMate</span>
          </div>

          <div className="auth-hero-copy">
            <h1>让论文阅读从检索到理解都更轻松</h1>
            <p>
              PaperMate 面向 arXiv 科研阅读场景，整合论文发现、智能总结、知识图谱、
              对比阅读和学习沉淀。登录、论文数据、解析任务和学习记录均由后端提供服务。
            </p>
          </div>

          <div className="auth-metric-row">
            <div className="auth-metric-card">
              <strong>6</strong>
              <span>核心页面流程</span>
            </div>
            <div className="auth-metric-card">
              <strong>5</strong>
              <span>阅读模式画像</span>
            </div>
            <div className="auth-metric-card">
              <strong>AI</strong>
              <span>摘要 / 问答 / 图谱</span>
            </div>
          </div>
        </div>
      </section>

      <section className="auth-panel-wrap">
        <Card className="auth-card" bordered={false}>
          <div className="auth-card-title">
            <h2>欢迎回来</h2>
            <p>登录后进入你的论文工作空间</p>
          </div>

          <Tabs
            activeKey={tab}
            onChange={setTab}
            centered
            items={[
              {
                key: 'login',
                label: '登录',
                children: (
                  <Form form={loginForm} layout="vertical" onFinish={onLogin} requiredMark={false}>
                    <Form.Item
                      name="email"
                      label="账号 / 邮箱"
                      rules={[{ required: true, message: '请输入账号或邮箱' }]}
                    >
                      <Input size="large" placeholder="请输入注册邮箱或账号" prefix={<BookOutlined />} />
                    </Form.Item>
                    <Form.Item
                      name="password"
                      label="密码"
                      rules={[{ required: true, message: '请输入密码' }]}
                    >
                      <Input.Password size="large" placeholder="请输入密码" prefix={<ThunderboltOutlined />} />
                    </Form.Item>
                    <Button type="primary" htmlType="submit" size="large" block>
                      进入 PaperMate
                    </Button>
                    <div className="auth-demo-row">
                      <Button onClick={fillDemoUser}>填入普通用户</Button>
                      <Button onClick={fillAdmin}>填入管理员</Button>
                    </div>
                    <div className="auth-note">
                      <Text type="secondary">
                        普通用户需先注册；管理员演示账号为 <strong>admin / admin123</strong>。
                      </Text>
                    </div>
                  </Form>
                )
              },
              {
                key: 'register',
                label: '注册',
                children: (
                  <Form form={registerForm} layout="vertical" onFinish={onRegister} requiredMark={false}>
                    <Form.Item
                      name="email"
                      label="邮箱"
                      rules={[
                        { required: true, message: '请输入邮箱' },
                        { type: 'email', message: '邮箱格式不正确' }
                      ]}
                    >
                      <Input size="large" placeholder="注册邮箱" prefix={<ExperimentOutlined />} />
                    </Form.Item>
                    <Form.Item
                      name="password"
                      label="密码"
                      rules={[
                        { required: true, message: '请输入密码' },
                        { min: 6, message: '密码至少 6 位' }
                      ]}
                    >
                      <Input.Password size="large" placeholder="设置密码" prefix={<ThunderboltOutlined />} />
                    </Form.Item>
                    <Form.Item
                      name="confirm"
                      label="确认密码"
                      dependencies={['password']}
                      rules={[
                        { required: true, message: '请再次输入密码' },
                        ({ getFieldValue }) => ({
                          validator(_, value) {
                            if (!value || getFieldValue('password') === value) return Promise.resolve();
                            return Promise.reject(new Error('两次密码不一致'));
                          }
                        })
                      ]}
                    >
                      <Input.Password size="large" placeholder="再次输入密码" prefix={<NodeIndexOutlined />} />
                    </Form.Item>
                    <Button type="primary" htmlType="submit" size="large" block>
                      注册 PaperMate
                    </Button>
                  </Form>
                )
              }
            ]}
          />
        </Card>
      </section>

      <OnboardingModal open={showOnboard} onDone={onOnboardDone} />
    </div>
  );
}
