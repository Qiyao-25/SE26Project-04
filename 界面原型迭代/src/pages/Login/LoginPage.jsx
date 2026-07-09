import { useState } from 'react';
import { Card, Tabs, Form, Input, Button, Typography, message } from 'antd';
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
  const { login, loggedIn } = useApp();
  const [tab, setTab] = useState('login');
  const [showOnboard, setShowOnboard] = useState(false);
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();

  if (loggedIn) {
    navigate('/workspace', { replace: true });
    return null;
  }

  const onLogin = (values) => {
    login(values.email);
    message.success(values.email?.trim().toLowerCase() === 'admin' ? '管理员登录成功' : '登录成功');
    navigate('/workspace');
  };

  const onRegister = (values) => {
    login(values.email);
    setShowOnboard(true);
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
            <span className="auth-brand-mark">P</span>
            <span>PaperMate</span>
          </div>

          <div className="auth-hero-copy">
            <h1>让论文阅读从检索到理解都更轻松</h1>
            <p>
              PaperMate 面向 arXiv 科研阅读场景，整合论文发现、智能总结、知识图谱、
              对比阅读和学习沉淀。当前版本为静态前端演示，后续可以逐步接入后端接口。
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

        <div className="auth-floating-panel">
          <div className="auth-flow-title">原型演示流程</div>
          <div className="auth-flow">
            <span>登录/注册</span>
            <span>→</span>
            <span>首次引导</span>
            <span>→</span>
            <span>工作空间</span>
            <span>→</span>
            <span>论文详情</span>
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
                      <Input size="large" placeholder="普通用户任意输入，管理员输入 admin" prefix={<BookOutlined />} />
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
                        当前仅为前端演示：普通用户可输入任意账号；管理员演示账号为 <strong>admin</strong>。
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
                      注册并开始引导
                    </Button>
                    <div className="auth-note">
                      <Text type="secondary">
                        注册后会弹出首次引导，用于选择研究方向和阅读模式。
                      </Text>
                    </div>
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