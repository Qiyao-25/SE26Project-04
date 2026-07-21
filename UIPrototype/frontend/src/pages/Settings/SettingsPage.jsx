import { useEffect, useState } from 'react';
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
} from "@ant-design/icons";

const ARXIV_CATEGORIES = [
  {
    value: "cs.AI",
    label: "cs.AI · 人工智能",
  },
  {
    value: "cs.CL",
    label: "cs.CL · 计算与语言",
  },
  {
    value: "cs.CV",
    label: "cs.CV · 计算机视觉",
  },
  {
    value: "cs.LG",
    label: "cs.LG · 机器学习",
  },
  {
    value: "cs.IR",
    label: "cs.IR · 信息检索",
  },
  {
    value: "cs.SE",
    label: "cs.SE · 软件工程",
  },
  {
    value: "cs.RO",
    label: "cs.RO · 机器人学",
  },
  {
    value: "stat.ML",
    label: "stat.ML · 统计机器学习",
  },
];

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

const CATEGORY_LABEL_MAP = Object.fromEntries(
  ARXIV_CATEGORIES.map((item) => [item.value, item.label]),
);

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
  const [subscriptions, setSubscriptions] = useState(loadSessionSubscriptions);

  const [subscriptionType, setSubscriptionType] = useState("keyword");
  const [keywordInput, setKeywordInput] = useState("");
  const [selectedCategory, setSelectedCategory] = useState(undefined);

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
        },
      ]);

      setKeywordInput("");
      message.success(`已添加关键词订阅：${value}`);
      return;
    }

    if (!selectedCategory) {
      message.warning("请选择一个学科分类");
      return;
    }

    const alreadyExists = subscriptions.some(
      (item) => item.type === "category" && item.value === selectedCategory,
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
        value: selectedCategory,
      },
    ]);

    message.success(
      `已添加学科订阅：${
        CATEGORY_LABEL_MAP[selectedCategory] || selectedCategory
      }`,
    );

    setSelectedCategory(undefined);
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
                  请先选择要添加的是普通关键词还是 arXiv 学科分类。
                </Typography.Text>

                <Segmented
                  className="subscription-type-segmented"
                  block
                  value={subscriptionType}
                  onChange={(value) => {
                    setSubscriptionType(value);
                    setKeywordInput("");
                    setSelectedCategory(undefined);
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
                      placeholder="选择学科分类，例如：cs.CL"
                      options={ARXIV_CATEGORIES}
                      optionFilterProp="label"
                      style={{ width: "100%" }}
                      onChange={setSelectedCategory}
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
                layout="vertical"
                initialValues={{
                  frequency: "每日",
                  codeOnly: false,
                  engineeringOnly: false,
                }}
                onFinish={() => message.success("抓取资源配置已保存")}
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

                <Button type="primary" htmlType="submit">
                  保存配置
                </Button>
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
