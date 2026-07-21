import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  message,
  Row,
  Segmented,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import {
  AppstoreOutlined,
  DeleteOutlined,
  PlusOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import { useOutletContext } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { updateAccount } from '../../services/authService';
import { getLearningProfile, updateLearningProfile } from '../../services/learningService';
import { syncSubscriptions } from '../../services/recommendationService';
import { USE_MOCK } from '../../services/runtimeConfig';
import { ARXIV_CATEGORIES, ARXIV_CATEGORY_LABEL_MAP } from '../../data/arxivCategories';
import {
  getLibraryPageSize,
  getUiPrefs,
  getWorkspacePageSize,
  setUiPrefs,
} from '../../utils/uiPrefs';

const SUBSCRIPTIONS_STORAGE_KEY = 'papermate-session-subscriptions';
const CATEGORY_LABEL_MAP = ARXIV_CATEGORY_LABEL_MAP;

const DEFAULT_SUBSCRIPTIONS = [
  { key: '1', type: 'category', value: 'cs.CL', enabled: true },
  { key: '2', type: 'category', value: 'cs.LG', enabled: true },
  { key: '3', type: 'keyword', value: 'Transformer', enabled: true },
];

const SUBSCRIPTION_SEGMENTED_STYLES = `
  html[data-theme='dark'] .subscription-type-segmented.ant-segmented {
    background: rgba(209, 136, 147, 0.14) !important;
    border: 1px solid rgba(225, 164, 175, 0.24);
  }
  html[data-theme='dark'] .subscription-type-segmented .ant-segmented-thumb,
  html[data-theme='dark'] .subscription-type-segmented .ant-segmented-item-selected {
    background: #f1d8de !important;
    box-shadow: 0 4px 14px rgba(209, 136, 147, 0.18) !important;
  }
  html[data-theme='dark'] .subscription-type-segmented .ant-segmented-item {
    color: #e8dde1 !important;
  }
  html[data-theme='dark'] .subscription-type-segmented .ant-segmented-item-selected,
  html[data-theme='dark'] .subscription-type-segmented .ant-segmented-item-selected .ant-segmented-item-label {
    color: #57343e !important;
    font-weight: 600;
  }
`;

function loadSessionSubscriptions() {
  try {
    const savedValue = sessionStorage.getItem(SUBSCRIPTIONS_STORAGE_KEY);
    if (!savedValue) return DEFAULT_SUBSCRIPTIONS;
    const parsedValue = JSON.parse(savedValue);
    return Array.isArray(parsedValue) ? parsedValue : DEFAULT_SUBSCRIPTIONS;
  } catch {
    return DEFAULT_SUBSCRIPTIONS;
  }
}

export default function SettingsPage() {
  const { userId, email, applyAuthResponse } = useApp();
  const outlet = useOutletContext() || {};
  const themeMode = outlet.themeMode || localStorage.getItem('papermate-theme') || 'dark';
  const setThemeMode = outlet.setThemeMode;

  const [crawlForm] = Form.useForm();
  const [accountForm] = Form.useForm();
  const [uiForm] = Form.useForm();

  const [subscriptions, setSubscriptions] = useState(loadSessionSubscriptions);
  const [subscriptionType, setSubscriptionType] = useState('keyword');
  const [keywordInput, setKeywordInput] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(undefined);
  const [categorySearch, setCategorySearch] = useState('');
  const [profileReady, setProfileReady] = useState(USE_MOCK);
  const [savedPreferences, setSavedPreferences] = useState({});
  const [syncing, setSyncing] = useState(false);
  const [accountSaving, setAccountSaving] = useState(false);
  const [lastSyncMessage, setLastSyncMessage] = useState('');

  useEffect(() => {
    try {
      sessionStorage.setItem(SUBSCRIPTIONS_STORAGE_KEY, JSON.stringify(subscriptions));
    } catch {
      // ignore
    }
  }, [subscriptions]);

  useEffect(() => {
    accountForm.setFieldsValue({ email: email || '' });
  }, [accountForm, email]);

  useEffect(() => {
    const ui = getUiPrefs();
    uiForm.setFieldsValue({
      workspacePageSize: getWorkspacePageSize(12),
      libraryPageSize: getLibraryPageSize(20),
      ...(ui || {}),
    });
  }, [themeMode, uiForm]);

  useEffect(() => {
    if (USE_MOCK) return undefined;
    getLearningProfile(userId)
      .then((profile) => {
        const preferences = profile.preferences || {};
        setSavedPreferences(preferences);
        if (Array.isArray(preferences.subscriptions)) {
          setSubscriptions(
            preferences.subscriptions.map((item) => ({
              ...item,
              enabled: item.enabled !== false,
            })),
          );
        }
        const crawl = preferences.crawl || {};
        crawlForm.setFieldsValue({
          maxPerSubscription: crawl.maxPerSubscription || 5,
          codeOnly: Boolean(crawl.codeOnly),
        });
        if (preferences.ui) {
          setUiPrefs(preferences.ui);
          uiForm.setFieldsValue({
            workspacePageSize: preferences.ui.workspacePageSize || getWorkspacePageSize(12),
            libraryPageSize: preferences.ui.libraryPageSize || getLibraryPageSize(20),
          });
          if (preferences.ui.theme && setThemeMode) {
            setThemeMode(preferences.ui.theme);
          }
        }
        if (preferences.last_subscription_sync_stats) {
          const stats = preferences.last_subscription_sync_stats;
          setLastSyncMessage(
            `上次同步：抓取 ${stats.fetched ?? 0}，新建 ${stats.created ?? 0}${stats.deduped ? `，跳过 ${stats.deduped}` : ''}`,
          );
        }
        setProfileReady(true);
      })
      .catch(() => setProfileReady(true));
    return undefined;
  }, [crawlForm, setThemeMode, themeMode, uiForm, userId]);

  useEffect(() => {
    if (!profileReady || USE_MOCK) return;
    const preferences = { ...savedPreferences, subscriptions };
    if (JSON.stringify(preferences) === JSON.stringify(savedPreferences)) return;
    setSavedPreferences(preferences);
    updateLearningProfile(userId, { preferences }).catch(() => {});
  }, [profileReady, savedPreferences, subscriptions, userId]);

  const savePreferences = async (patch, successMessage) => {
    const preferences = { ...savedPreferences, ...patch, subscriptions };
    try {
      const profile = await updateLearningProfile(userId, { preferences });
      setSavedPreferences(profile.preferences || preferences);
      message.success(successMessage);
    } catch (error) {
      message.error(error.message || '设置保存失败');
    }
  };

  const handleSyncNow = async () => {
    if (USE_MOCK) {
      message.info('Mock 模式无法同步 arXiv');
      return;
    }
    setSyncing(true);
    try {
      const crawl = crawlForm.getFieldsValue();
      const maxPerSubscription = Number(crawl.maxPerSubscription) || 5;
      await updateLearningProfile(userId, {
        preferences: {
          ...savedPreferences,
          subscriptions,
          crawl: {
            maxPerSubscription,
            codeOnly: Boolean(crawl.codeOnly),
          },
        },
      });
      const result = await syncSubscriptions(userId, { maxPerSubscription });
      setLastSyncMessage(result.message || '同步完成');
      message.success(result.message || '订阅同步完成');
      const profile = await getLearningProfile(userId);
      setSavedPreferences(profile.preferences || {});
    } catch (error) {
      message.error(error.message || '同步失败');
    } finally {
      setSyncing(false);
    }
  };

  const categoryOptions = useMemo(() => {
    const typed = categorySearch.trim();
    if (
      typed
      && !ARXIV_CATEGORIES.some((item) => item.value.toLowerCase() === typed.toLowerCase())
    ) {
      return [{ value: typed, label: `${typed} · 自定义学科` }, ...ARXIV_CATEGORIES];
    }
    return ARXIV_CATEGORIES;
  }, [categorySearch]);

  const normalizeCategoryCode = (raw) => {
    const value = String(raw || '').trim();
    if (!value) return '';
    return value.split(/[·\s]/)[0].trim();
  };

  const addSubscription = () => {
    if (subscriptionType === 'keyword') {
      const value = keywordInput.trim();
      if (!value) {
        message.warning('请输入订阅关键词');
        return;
      }
      if (subscriptions.some((item) => item.type === 'keyword' && item.value.toLowerCase() === value.toLowerCase())) {
        message.warning('该关键词已经订阅');
        return;
      }
      setSubscriptions((current) => [
        ...current,
        { key: `keyword-${Date.now()}`, type: 'keyword', value, enabled: true },
      ]);
      setKeywordInput('');
      message.success(`已添加关键词订阅：${value}`);
      return;
    }

    const categoryValue = normalizeCategoryCode(selectedCategory || categorySearch);
    if (!categoryValue) {
      message.warning('请选择或输入一个学科分类（如 cs.NE、math.OC）');
      return;
    }
    if (subscriptions.some((item) => item.type === 'category' && item.value.toLowerCase() === categoryValue.toLowerCase())) {
      message.warning('该学科分类已经订阅');
      return;
    }
    setSubscriptions((current) => [
      ...current,
      { key: `category-${Date.now()}`, type: 'category', value: categoryValue, enabled: true },
    ]);
    message.success(`已添加学科订阅：${CATEGORY_LABEL_MAP[categoryValue] || categoryValue}`);
    setSelectedCategory(undefined);
    setCategorySearch('');
  };

  const toggleSubscription = (key, enabled) => {
    setSubscriptions((current) => current.map((item) => (item.key === key ? { ...item, enabled } : item)));
  };

  const removeSubscription = (key) => {
    setSubscriptions((current) => current.filter((item) => item.key !== key));
    message.success('已删除订阅');
  };

  const handleAccountSave = async (values) => {
    if (USE_MOCK) {
      message.info('Mock 模式不支持修改账户');
      return;
    }
    const nextEmail = (values.email || '').trim();
    const currentPassword = values.currentPassword || '';
    const newPassword = values.newPassword || '';
    if (!nextEmail) {
      message.warning('请输入邮箱');
      return;
    }
    if (newPassword && !currentPassword) {
      message.warning('修改密码需要填写当前密码');
      return;
    }
    if (!newPassword && nextEmail === email) {
      message.info('没有需要保存的更改');
      return;
    }
    setAccountSaving(true);
    try {
      const data = await updateAccount({
        email: nextEmail !== email ? nextEmail : undefined,
        current_password: newPassword ? currentPassword : undefined,
        password: newPassword || undefined,
      });
      if (applyAuthResponse) applyAuthResponse(data);
      accountForm.setFieldsValue({ currentPassword: '', newPassword: '', confirmPassword: '' });
      message.success('账户信息已更新');
    } catch (error) {
      message.error(error.message || '账户更新失败');
    } finally {
      setAccountSaving(false);
    }
  };

  const handleUiSave = async (values) => {
    const ui = {
      theme: themeMode,
      workspacePageSize: Number(values.workspacePageSize) || 12,
      libraryPageSize: Number(values.libraryPageSize) || 20,
    };
    setUiPrefs(ui);
    await savePreferences({ ui }, '界面设置已保存');
  };

  const subscriptionColumns = [
    {
      title: '启用',
      dataIndex: 'enabled',
      width: 72,
      render: (enabled, record) => (
        <Switch
          size="small"
          checked={enabled !== false}
          onChange={(checked) => toggleSubscription(record.key, checked)}
        />
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      width: 100,
      render: (type) => (
        type === 'category'
          ? <Tag icon={<AppstoreOutlined />} color="magenta">学科</Tag>
          : <Tag icon={<TagsOutlined />}>关键词</Tag>
      ),
    },
    {
      title: '订阅内容',
      dataIndex: 'value',
      render: (value, record) => (
        record.type === 'category' ? (CATEGORY_LABEL_MAP[value] || value) : value
      ),
    },
    {
      title: '操作',
      width: 72,
      align: 'center',
      render: (_, record) => (
        <Button type="text" danger icon={<DeleteOutlined />} onClick={() => removeSubscription(record.key)} />
      ),
    },
  ];

  const enabledCount = subscriptions.filter((item) => item.enabled !== false).length;

  const tabItems = [
    {
      key: 'fetch',
      label: '订阅与同步',
      children: (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={14}>
            <Card title="我的订阅" size="small">
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Typography.Text type="secondary">
                  关键词或 arXiv 学科均可订阅；学科可从列表选择，也可输入任意代码（如 cs.NE）。关闭「启用」后不会参与同步。
                </Typography.Text>
                <Segmented
                  className="subscription-type-segmented"
                  block
                  value={subscriptionType}
                  onChange={(value) => {
                    setSubscriptionType(value);
                    setKeywordInput('');
                    setSelectedCategory(undefined);
                    setCategorySearch('');
                  }}
                  options={[
                    { label: '关键词', value: 'keyword', icon: <TagsOutlined /> },
                    { label: '学科分类', value: 'category', icon: <AppstoreOutlined /> },
                  ]}
                />
                <Space.Compact style={{ width: '100%' }}>
                  {subscriptionType === 'keyword' ? (
                    <Input
                      value={keywordInput}
                      placeholder="例如：Transformer、RAG"
                      onChange={(event) => setKeywordInput(event.target.value)}
                      onPressEnter={addSubscription}
                    />
                  ) : (
                    <Select
                      showSearch
                      allowClear
                      value={selectedCategory}
                      placeholder="选择或输入学科，例如 cs.CL、math.OC"
                      options={categoryOptions}
                      optionFilterProp="label"
                      filterOption={(input, option) => {
                        const q = input.toLowerCase();
                        return (
                          String(option?.label || '').toLowerCase().includes(q)
                          || String(option?.value || '').toLowerCase().includes(q)
                        );
                      }}
                      style={{ width: '100%' }}
                      onSearch={setCategorySearch}
                      onChange={(value) => {
                        setSelectedCategory(value);
                        setCategorySearch(value || '');
                      }}
                      onInputKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault();
                          addSubscription();
                        }
                      }}
                      notFoundContent={
                        categorySearch.trim()
                          ? `将添加自定义「${categorySearch.trim()}」`
                          : '输入学科代码或从列表选择'
                      }
                    />
                  )}
                  <Button type="primary" icon={<PlusOutlined />} onClick={addSubscription}>添加</Button>
                </Space.Compact>
                <Table
                  rowKey="key"
                  size="small"
                  pagination={false}
                  dataSource={subscriptions}
                  columns={subscriptionColumns}
                  locale={{ emptyText: '暂无订阅内容' }}
                />
              </Space>
            </Card>
          </Col>
          <Col xs={24} lg={10}>
            <Card title="同步设置" size="small">
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
                message={`当前启用 ${enabledCount} 项订阅。定时抓取由服务器统一调度；此处可立即同步并配置过滤条件。`}
              />
              <Form
                form={crawlForm}
                layout="vertical"
                initialValues={{ maxPerSubscription: 5, codeOnly: false }}
                onFinish={(values) => savePreferences({
                  crawl: {
                    maxPerSubscription: Number(values.maxPerSubscription) || 5,
                    codeOnly: Boolean(values.codeOnly),
                  },
                }, '同步设置已保存')}
              >
                <Form.Item
                  name="maxPerSubscription"
                  label="每个订阅每次抓取新论文数"
                  extra="会跳过库中已有论文，尽量只入库新条目"
                >
                  <InputNumber min={1} max={15} style={{ width: '100%' }} />
                </Form.Item>
                <Form.Item
                  name="codeOnly"
                  label="仅同步疑似有代码的论文"
                  valuePropName="checked"
                  extra="根据摘要/标题中的 GitHub、开源等信号过滤"
                >
                  <Switch />
                </Form.Item>
                <Space wrap>
                  <Button type="primary" htmlType="submit">保存设置</Button>
                  <Button loading={syncing} onClick={handleSyncNow}>立即同步 arXiv</Button>
                </Space>
                {lastSyncMessage ? (
                  <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
                    {lastSyncMessage}
                  </Typography.Paragraph>
                ) : null}
              </Form>
            </Card>
          </Col>
        </Row>
      ),
    },
    {
      key: 'account',
      label: '个人账户',
      children: (
        <Card style={{ maxWidth: 480 }} size="small" title="账户安全">
          <Form
            form={accountForm}
            layout="vertical"
            initialValues={{ email: email || '' }}
            onFinish={handleAccountSave}
          >
            <Form.Item
              name="email"
              label="登录邮箱"
              rules={[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入正确的邮箱格式' },
              ]}
            >
              <Input placeholder="you@example.com" />
            </Form.Item>
            <Form.Item name="currentPassword" label="当前密码" extra="仅在修改密码时需要">
              <Input.Password autoComplete="current-password" placeholder="修改密码时填写" />
            </Form.Item>
            <Form.Item
              name="newPassword"
              label="新密码"
              rules={[{ min: 6, message: '新密码至少 6 位' }]}
            >
              <Input.Password autoComplete="new-password" placeholder="不修改请留空" />
            </Form.Item>
            <Form.Item
              name="confirmPassword"
              label="确认新密码"
              dependencies={['newPassword']}
              rules={[
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    const next = getFieldValue('newPassword');
                    if (!next || value === next) return Promise.resolve();
                    return Promise.reject(new Error('两次输入的新密码不一致'));
                  },
                }),
              ]}
            >
              <Input.Password autoComplete="new-password" placeholder="再次输入新密码" />
            </Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={accountSaving}>保存账户</Button>
            </Space>
          </Form>
        </Card>
      ),
    },
    {
      key: 'web',
      label: '界面',
      children: (
        <Card style={{ maxWidth: 480 }} size="small" title="显示与列表">
          <Form
            form={uiForm}
            layout="vertical"
            initialValues={{
              workspacePageSize: getWorkspacePageSize(12),
              libraryPageSize: getLibraryPageSize(20),
            }}
            onFinish={handleUiSave}
          >
            <Form.Item name="workspacePageSize" label="工作台检索每页条数" extra="影响智能检索结果列表">
              <Select
                options={[
                  { value: 8, label: '8 条' },
                  { value: 12, label: '12 条' },
                  { value: 16, label: '16 条' },
                  { value: 24, label: '24 条' },
                ]}
              />
            </Form.Item>
            <Form.Item name="libraryPageSize" label="论文库默认每页条数" extra="仅管理员论文库页面">
              <Select
                options={[
                  { value: 10, label: '10 条' },
                  { value: 20, label: '20 条' },
                  { value: 50, label: '50 条' },
                ]}
              />
            </Form.Item>
            <Button type="primary" htmlType="submit">保存界面设置</Button>
          </Form>
        </Card>
      ),
    },
  ];

  return (
    <>
      <style>{SUBSCRIPTION_SEGMENTED_STYLES}</style>
      <Card className="section-card">
        <Tabs items={tabItems} />
      </Card>
    </>
  );
}
