import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
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
} from "antd";

import {
  AppstoreOutlined,
  DeleteOutlined,
  PlusOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import { useApp } from '../../context/AppContext';
import { getLearningProfile, updateLearningProfile } from '../../services/learningService';
import { syncSubscriptions } from '../../services/recommendationService';
import { USE_MOCK } from '../../services/runtimeConfig';
import { ARXIV_CATEGORIES, ARXIV_CATEGORY_LABEL_MAP } from '../../data/arxivCategories';


const SUBSCRIPTIONS_STORAGE_KEY = "papermate-session-subscriptions";

const DEFAULT_SUBSCRIPTIONS = [
  {
    key: "1",
    type: "category",
    value: "cs.CL",
  },
  {
    key: "2",
    type: "category",
    value: "cs.LG",
  },
  {
    key: "3",
    type: "keyword",
    value: "Transformer",
  },
];

const loadSessionSubscriptions = () => {
  try {
    const savedValue = sessionStorage.getItem(SUBSCRIPTIONS_STORAGE_KEY);

    if (!savedValue) {
      return DEFAULT_SUBSCRIPTIONS;
    }

    const parsedValue = JSON.parse(savedValue);

    if (!Array.isArray(parsedValue)) {
      return DEFAULT_SUBSCRIPTIONS;
    }

    return parsedValue;
  } catch (error) {
    console.error("读取订阅设置失败：", error);
    return DEFAULT_SUBSCRIPTIONS;
  }
};

const CATEGORY_LABEL_MAP = ARXIV_CATEGORY_LABEL_MAP;

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

export default function SettingsPage() {
  const { userId } = useApp();
  const [crawlForm] = Form.useForm();
  const [subscriptions, setSubscriptions] = useState(loadSessionSubscriptions);

  const [subscriptionType, setSubscriptionType] = useState("keyword");
  const [keywordInput, setKeywordInput] = useState("");
  const [selectedCategory, setSelectedCategory] = useState(undefined);
  const [categorySearch, setCategorySearch] = useState("");
  const [profileReady, setProfileReady] = useState(USE_MOCK);
  const [savedPreferences, setSavedPreferences] = useState({});
  const [syncing, setSyncing] = useState(false);
  const [lastSyncMessage, setLastSyncMessage] = useState("");

  useEffect(() => {
    try {
      sessionStorage.setItem(
        SUBSCRIPTIONS_STORAGE_KEY,
        JSON.stringify(subscriptions),
      );
    } catch (error) {
      console.error("保存订阅设置失败：", error);
    }
  }, [subscriptions]);

  useEffect(() => {
    if (USE_MOCK) return undefined;
    getLearningProfile(userId)
      .then((profile) => {
        const preferences = profile.preferences || {};
        setSavedPreferences(preferences);
        if (Array.isArray(preferences.subscriptions)) {
          setSubscriptions(preferences.subscriptions);
        }
        if (preferences.crawl) crawlForm.setFieldsValue(preferences.crawl);
        if (preferences.last_subscription_sync_stats) {
          const stats = preferences.last_subscription_sync_stats;
          setLastSyncMessage(
            `上次同步：抓取 ${stats.fetched ?? 0}，新建 ${stats.created ?? 0}`,
          );
        }
        setProfileReady(true);
      })
      .catch(() => setProfileReady(true));
    return undefined;
  }, [crawlForm, userId]);

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
      message.error(error.message || "设置保存失败");
    }
  };

  const handleSyncNow = async () => {
    if (USE_MOCK) {
      message.info("Mock 模式无法同步 arXiv");
      return;
    }
    setSyncing(true);
    try {
      await updateLearningProfile(userId, {
        preferences: { ...savedPreferences, subscriptions },
      });
      const result = await syncSubscriptions(userId, { maxPerSubscription: 5 });
      setLastSyncMessage(result.message || "同步完成");
      message.success(result.message || "订阅同步完成");
      const profile = await getLearningProfile(userId);
      setSavedPreferences(profile.preferences || {});
    } catch (error) {
      message.error(error.message || "同步失败");
    } finally {
      setSyncing(false);
    }
  };

  const categoryOptions = useMemo(() => {
    const typed = categorySearch.trim();
    if (
      typed &&
      !ARXIV_CATEGORIES.some((item) => item.value.toLowerCase() === typed.toLowerCase())
    ) {
      return [{ value: typed, label: `${typed} · 自定义学科（回车或点选添加）` }, ...ARXIV_CATEGORIES];
    }
    return ARXIV_CATEGORIES;
  }, [categorySearch]);

  const normalizeCategoryCode = (raw) => {
    const value = String(raw || "").trim();
    if (!value) return "";
    // Allow "cs.NE · 说明" paste → take left token
    return value.split(/[·\s]/)[0].trim();
  };

  const addSubscription = () => {
    if (subscriptionType === "keyword") {
      const value = keywordInput.trim();

      if (!value) {
        message.warning("请输入订阅关键词");
        return;
      }

      const alreadyExists = subscriptions.some(
        (item) =>
          item.type === "keyword" &&
          item.value.toLowerCase() === value.toLowerCase(),
      );

      if (alreadyExists) {
        message.warning("该关键词已经订阅");
        return;
      }

      setSubscriptions((current) => [
        ...current,
        {
          key: `keyword-${Date.now()}`,
          type: "keyword",
          value,
          enabled: true,
        },
      ]);

      setKeywordInput("");
      message.success(`已添加关键词订阅：${value}`);
      return;
    }

    const categoryValue = normalizeCategoryCode(selectedCategory || categorySearch);

    if (!categoryValue) {
      message.warning("请选择或输入一个学科分类（如 cs.NE、math.OC）");
      return;
    }

    const alreadyExists = subscriptions.some(
      (item) => item.type === "category" && item.value.toLowerCase() === categoryValue.toLowerCase(),
    );

    if (alreadyExists) {
      message.warning("该学科分类已经订阅");
      return;
    }

    setSubscriptions((current) => [
      ...current,
      {
        key: `category-${Date.now()}`,
        type: "category",
        value: categoryValue,
        enabled: true,
      },
    ]);

    message.success(
      `已添加学科订阅：${
        CATEGORY_LABEL_MAP[categoryValue] || categoryValue
      }`,
    );

    setSelectedCategory(undefined);
    setCategorySearch("");
  };

  const removeSubscription = (key) => {
    setSubscriptions((current) => current.filter((item) => item.key !== key));

    message.success("已删除订阅");
  };

  const subscriptionColumns = [
    {
      title: "类型",
      dataIndex: "type",
      width: 110,
      render: (type) =>
        type === "category" ? (
          <Tag icon={<AppstoreOutlined />} color="magenta">
            学科
          </Tag>
        ) : (
          <Tag icon={<TagsOutlined />}>关键词</Tag>
        ),
    },
    {
      title: "订阅内容",
      dataIndex: "value",
      render: (value, record) => {
        if (record.type === "category") {
          return CATEGORY_LABEL_MAP[value] || value;
        }

        return value;
      },
    },
    {
      title: "操作",
      width: 80,
      align: "center",
      render: (_, record) => (
        <Button
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={() => removeSubscription(record.key)}
        />
      ),
    },
  ];

  const tabItems = [
    {
      key: "fetch",
      label: "抓取与订阅",
      children: (
        <Row gutter={[16, 16]}>
          <Col xs={24} md={14}>
            <Card title="订阅设置" size="small">
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Typography.Text type="secondary">
                  可订阅关键词或 arXiv 学科；学科支持从列表选择，也可直接输入任意分类代码（如 cs.NE、q-bio.NC）。
                </Typography.Text>

                <Segmented
                  className="subscription-type-segmented"
                  block
                  value={subscriptionType}
                  onChange={(value) => {
                    setSubscriptionType(value);
                    setKeywordInput("");
                    setSelectedCategory(undefined);
                    setCategorySearch("");
                  }}
                  options={[
                    {
                      label: "关键词",
                      value: "keyword",
                      icon: <TagsOutlined />,
                    },
                    {
                      label: "学科分类",
                      value: "category",
                      icon: <AppstoreOutlined />,
                    },
                  ]}
                />

                <Space.Compact style={{ width: "100%" }}>
                  {subscriptionType === "keyword" ? (
                    <Input
                      value={keywordInput}
                      placeholder="输入关键词，例如：Transformer、RAG"
                      onChange={(event) => setKeywordInput(event.target.value)}
                      onPressEnter={addSubscription}
                    />
                  ) : (
                    <Select
                      showSearch
                      allowClear
                      value={selectedCategory}
                      placeholder="选择或输入学科，例如：cs.CL、math.OC、physics.comp-ph"
                      options={categoryOptions}
                      optionFilterProp="label"
                      filterOption={(input, option) => {
                        const q = input.toLowerCase();
                        return (
                          String(option?.label || "").toLowerCase().includes(q) ||
                          String(option?.value || "").toLowerCase().includes(q)
                        );
                      }}
                      style={{ width: "100%" }}
                      onSearch={setCategorySearch}
                      onChange={(value) => {
                        setSelectedCategory(value);
                        setCategorySearch(value || "");
                      }}
                      onInputKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          addSubscription();
                        }
                      }}
                      notFoundContent={
                        categorySearch.trim()
                          ? `未在列表中：将添加自定义「${categorySearch.trim()}」`
                          : "输入学科代码或从列表选择"
                      }
                    />
                  )}

                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={addSubscription}
                  >
                    添加
                  </Button>
                </Space.Compact>

                <Table
                  rowKey="key"
                  size="small"
                  pagination={false}
                  dataSource={subscriptions}
                  columns={subscriptionColumns}
                  locale={{
                    emptyText: "暂无订阅内容",
                  }}
                />
              </Space>
            </Card>
          </Col>

          <Col xs={24} md={10}>
            <Card title="抓取资源配置" size="small">
              <Form
                form={crawlForm}
                layout="vertical"
                initialValues={{
                  frequency: "每日",
                  codeOnly: false,
                  engineeringOnly: false,
                }}
                onFinish={(values) =>
                  savePreferences({ crawl: values }, "抓取资源配置已保存")
                }
              >
                <Form.Item name="frequency" label="抓取频率">
                  <Select
                    options={[
                      {
                        value: "每日",
                        label: "每日",
                      },
                      {
                        value: "每周",
                        label: "每周",
                      },
                    ]}
                  />
                </Form.Item>

                <Form.Item
                  name="codeOnly"
                  label="仅抓取有代码论文"
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>

                <Form.Item
                  name="engineeringOnly"
                  label="仅抓取工程型论文"
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>

                <Space>
                  <Button type="primary" htmlType="submit">
                    保存配置
                  </Button>
                  <Button loading={syncing} onClick={handleSyncNow}>
                    立即同步 arXiv
                  </Button>
                </Space>
                {lastSyncMessage ? (
                  <Typography.Paragraph
                    type="secondary"
                    style={{ marginTop: 12, marginBottom: 0 }}
                  >
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
      key: "account",
      label: "个人账户",
      children: (
        <Card style={{ maxWidth: 480 }}>
          <Form
            layout="vertical"
            initialValues={{
              email: "user@example.com",
              password: "******",
            }}
            onFinish={() => message.success("账户设置已保存")}
          >
            <Form.Item
              name="email"
              label="邮箱"
              rules={[
                {
                  required: true,
                  message: "请输入邮箱",
                },
                {
                  type: "email",
                  message: "请输入正确的邮箱格式",
                },
              ]}
            >
              <Input />
            </Form.Item>

            <Form.Item name="password" label="密码">
              <Input.Password />
            </Form.Item>

            <Button type="primary" htmlType="submit">
              保存
            </Button>
          </Form>
        </Card>
      ),
    },
    {
      key: "web",
      label: "网页设置",
      children: (
        <Card style={{ maxWidth: 480 }}>
          <Form
            layout="vertical"
            initialValues={{
              language: "zh",
              pageSize: "10",
            }}
            onFinish={() => message.success("网页设置已保存")}
          >
            <Form.Item name="language" label="界面语言">
              <Select
                options={[
                  {
                    value: "zh",
                    label: "简体中文",
                  },
                  {
                    value: "en",
                    label: "English",
                  },
                ]}
              />
            </Form.Item>

            <Form.Item name="pageSize" label="每页条数">
              <Select
                options={[
                  {
                    value: "10",
                    label: "10 条",
                  },
                  {
                    value: "20",
                    label: "20 条",
                  },
                ]}
              />
            </Form.Item>

            <Button type="primary" htmlType="submit">
              保存
            </Button>
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
