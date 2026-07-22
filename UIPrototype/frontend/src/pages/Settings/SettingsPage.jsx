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
import { useApp } from '../../context/AppContext';
import { useI18n } from '../../i18n';
import { updateAccount } from '../../services/authService';
import { getLearningProfile, updateLearningProfile } from '../../services/learningService';
import { syncSubscriptions } from '../../services/recommendationService';
import { getAdminCrawlSettings, updateAdminCrawlSettings } from '../../services/adminService';
import { USE_MOCK } from '../../services/runtimeConfig';
import { ARXIV_CATEGORIES, ARXIV_CATEGORY_LABEL_MAP } from '../../data/arxivCategories';
import {
  getLanguage,
  getUiPrefs,
  getWorkspacePageSize,
  setUiPrefs,
} from '../../utils/uiPrefs';
import {
  isSubscriptionSyncing,
  runSubscriptionSync,
  subscribeSubscriptionSync,
} from '../../utils/subscriptionSyncLock';

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
  const { userId, email, applyAuthResponse, isAdmin } = useApp();
  const { t, language, setLanguage } = useI18n();

  const [crawlForm] = Form.useForm();
  const [accountForm] = Form.useForm();
  const [uiForm] = Form.useForm();
  const [crawlAdminForm] = Form.useForm();

  const [subscriptions, setSubscriptions] = useState(loadSessionSubscriptions);
  const [subscriptionType, setSubscriptionType] = useState('keyword');
  const [keywordInput, setKeywordInput] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(undefined);
  const [categorySearch, setCategorySearch] = useState('');
  const [profileReady, setProfileReady] = useState(USE_MOCK);
  const [savedPreferences, setSavedPreferences] = useState({});
  const [syncing, setSyncing] = useState(() => isSubscriptionSyncing());
  const [accountSaving, setAccountSaving] = useState(false);
  const [lastSyncMessage, setLastSyncMessage] = useState('');
  const [crawlAdminSaving, setCrawlAdminSaving] = useState(false);

  useEffect(() => subscribeSubscriptionSync(setSyncing), []);

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
      language: getLanguage('zh'),
      ...(ui || {}),
      language: ui?.language === 'en' ? 'en' : getLanguage('zh'),
    });
  }, [uiForm, language]);

  useEffect(() => {
    if (!isAdmin) return undefined;
    if (USE_MOCK) {
      crawlAdminForm.setFieldsValue({ crawlEnabled: true, crawlIntervalHours: 6 });
      return undefined;
    }
    getAdminCrawlSettings()
      .then((data) => {
        crawlAdminForm.setFieldsValue({
          crawlEnabled: data.crawl_enabled !== false,
          crawlIntervalHours: Math.max(1 / 60, Number(data.crawl_interval_s || 21600) / 3600),
        });
      })
      .catch(() => message.error(t('settings.crawlAdmin.loadFailed')));
    return undefined;
  }, [crawlAdminForm, isAdmin, t]);

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
            language: preferences.ui.language === 'en' ? 'en' : getLanguage('zh'),
          });
          if (preferences.ui.language === 'en' || preferences.ui.language === 'zh') {
            setLanguage(preferences.ui.language);
          }
        }
        if (preferences.last_subscription_sync_stats) {
          const stats = preferences.last_subscription_sync_stats;
          const updatedPart = stats.updated ? `，更新 ${stats.updated}` : '';
          const skipPart = stats.deduped ? `，跳过 ${stats.deduped}` : '';
          setLastSyncMessage(
            `上次同步：抓取 ${stats.fetched ?? 0}，新建 ${stats.created ?? 0}${updatedPart}${skipPart}`,
          );
        }
        setProfileReady(true);
      })
      .catch(() => setProfileReady(true));
    return undefined;
  }, [crawlForm, uiForm, userId]);

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
    try {
      const result = await runSubscriptionSync(async () => {
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
        const syncResult = await syncSubscriptions(userId, { maxPerSubscription });
        const profile = await getLearningProfile(userId);
        setSavedPreferences(profile.preferences || {});
        return syncResult;
      });
      setLastSyncMessage(result.message || '同步完成');
      message.success(result.message || '订阅同步完成');
    } catch (error) {
      message.error(error.message || '同步失败');
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
    const nextLang = values.language === 'en' ? 'en' : 'zh';
    const ui = {
      workspacePageSize: Number(values.workspacePageSize) || 12,
      language: nextLang,
    };
    setLanguage(nextLang);
    setUiPrefs(ui);
    await savePreferences({ ui }, t('settings.ui.saved'));
  };

  const handleCrawlAdminSave = async (values) => {
    if (!isAdmin) return;
    setCrawlAdminSaving(true);
    try {
      const hours = Number(values.crawlIntervalHours);
      const seconds = Math.max(60, Math.round((Number.isFinite(hours) ? hours : 6) * 3600));
      if (USE_MOCK) {
        crawlAdminForm.setFieldsValue({
          crawlEnabled: Boolean(values.crawlEnabled),
          crawlIntervalHours: seconds / 3600,
        });
        message.success(t('settings.crawlAdmin.saved'));
        return;
      }
      const data = await updateAdminCrawlSettings({
        crawl_enabled: Boolean(values.crawlEnabled),
        crawl_interval_s: seconds,
      });
      crawlAdminForm.setFieldsValue({
        crawlEnabled: data.crawl_enabled !== false,
        crawlIntervalHours: Math.max(1 / 60, Number(data.crawl_interval_s || seconds) / 3600),
      });
      message.success(t('settings.crawlAdmin.saved'));
    } catch (error) {
      message.error(error.message || t('settings.crawlAdmin.loadFailed'));
    } finally {
      setCrawlAdminSaving(false);
    }
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
      label: t('settings.tab.fetch'),
      children: (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={14}>
            <Card title={t('settings.subscriptions.title')} size="small">
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Typography.Text type="secondary">
                  {t('settings.subscriptions.hint')}
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
                    { label: t('settings.subscriptions.keyword'), value: 'keyword', icon: <TagsOutlined /> },
                    { label: t('settings.subscriptions.category'), value: 'category', icon: <AppstoreOutlined /> },
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
            <Card title={t('settings.sync.title')} size="small">
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
                message={t('settings.sync.alert', { count: enabledCount })}
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
                }, t('settings.sync.save'))}
              >
                <Form.Item
                  name="maxPerSubscription"
                  label={t('settings.sync.maxPer')}
                  extra={t('settings.sync.maxPerExtra')}
                >
                  <InputNumber min={1} max={15} style={{ width: '100%' }} />
                </Form.Item>
                <Form.Item
                  name="codeOnly"
                  label={t('settings.sync.codeOnly')}
                  valuePropName="checked"
                  extra={t('settings.sync.codeOnlyExtra')}
                >
                  <Switch />
                </Form.Item>
                <Space wrap>
                  <Button type="primary" htmlType="submit">{t('settings.sync.save')}</Button>
                  <Button loading={syncing} onClick={handleSyncNow}>{t('settings.sync.now')}</Button>
                </Space>
                {lastSyncMessage ? (
                  <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
                    {lastSyncMessage}
                  </Typography.Paragraph>
                ) : null}
              </Form>
            </Card>
            {isAdmin ? (
              <Card title={t('settings.crawlAdmin.title')} size="small" style={{ marginTop: 16 }}>
                <Form
                  form={crawlAdminForm}
                  layout="vertical"
                  initialValues={{ crawlEnabled: true, crawlIntervalHours: 6 }}
                  onFinish={handleCrawlAdminSave}
                >
                  <Form.Item
                    name="crawlEnabled"
                    label={t('settings.crawlAdmin.enabled')}
                    valuePropName="checked"
                    extra={t('settings.crawlAdmin.enabledExtra')}
                  >
                    <Switch />
                  </Form.Item>
                  <Form.Item
                    name="crawlIntervalHours"
                    label={t('settings.crawlAdmin.interval')}
                    extra={t('settings.crawlAdmin.intervalExtra')}
                    rules={[{ required: true, message: t('settings.crawlAdmin.interval') }]}
                  >
                    <InputNumber min={1 / 60} max={168} step={0.5} style={{ width: '100%' }} />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={crawlAdminSaving}>
                    {t('settings.crawlAdmin.save')}
                  </Button>
                </Form>
              </Card>
            ) : null}
          </Col>
        </Row>
      ),
    },
    {
      key: 'account',
      label: t('settings.tab.account'),
      children: (
        <Card style={{ maxWidth: 480 }} size="small" title={t('settings.account.title')}>
          <Form
            form={accountForm}
            layout="vertical"
            initialValues={{ email: email || '' }}
            onFinish={handleAccountSave}
          >
            <Form.Item
              name="email"
              label={t('settings.account.email')}
              rules={[
                { required: true, message: t('settings.account.email') },
                { type: 'email', message: 'Invalid email' },
              ]}
            >
              <Input placeholder="you@example.com" />
            </Form.Item>
            <Form.Item name="currentPassword" label={t('settings.account.currentPassword')} extra={t('settings.account.currentPasswordExtra')}>
              <Input.Password autoComplete="current-password" />
            </Form.Item>
            <Form.Item
              name="newPassword"
              label={t('settings.account.newPassword')}
              rules={[{ min: 6, message: 'min 6' }]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            <Form.Item
              name="confirmPassword"
              label={t('settings.account.confirmPassword')}
              dependencies={['newPassword']}
              rules={[
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    const next = getFieldValue('newPassword');
                    if (!next || value === next) return Promise.resolve();
                    return Promise.reject(new Error('Password mismatch'));
                  },
                }),
              ]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={accountSaving}>{t('settings.account.save')}</Button>
            </Space>
          </Form>
        </Card>
      ),
    },
    {
      key: 'web',
      label: t('settings.tab.web'),
      children: (
        <Card style={{ maxWidth: 480 }} size="small" title={t('settings.ui.title')}>
          <Form
            form={uiForm}
            layout="vertical"
            initialValues={{
              workspacePageSize: getWorkspacePageSize(12),
              language: getLanguage('zh'),
            }}
            onFinish={handleUiSave}
          >
            <Form.Item name="language" label={t('settings.ui.language')} extra={t('settings.ui.languageExtra')}>
              <Segmented
                block
                options={[
                  { label: t('settings.ui.zh'), value: 'zh' },
                  { label: t('settings.ui.en'), value: 'en' },
                ]}
                onChange={(value) => {
                  setLanguage(value);
                  uiForm.setFieldsValue({ language: value });
                }}
              />
            </Form.Item>
            <Form.Item name="workspacePageSize" label={t('settings.ui.pageSize')} extra={t('settings.ui.pageSizeExtra')}>
              <Select
                options={[8, 12, 16, 24].map((n) => ({
                  value: n,
                  label: t('settings.ui.pageSizeOption', { n }),
                }))}
              />
            </Form.Item>
            <Button type="primary" htmlType="submit">{t('settings.ui.save')}</Button>
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
