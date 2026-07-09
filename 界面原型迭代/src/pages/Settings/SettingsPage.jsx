import { useState } from 'react';
import { Card, Tabs, Table, Input, Select, Button, Switch, Row, Col, Form, message } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

export default function SettingsPage() {
  const [subs, setSubs] = useState([
    { key: '1', type: '学科', value: 'cs.CL' },
    { key: '2', type: '学科', value: 'cs.LG' },
    { key: '3', type: '关键词', value: 'Transformer' }
  ]);

  const addSub = (type, value) => {
    if (!value) return;
    setSubs([...subs, { key: String(Date.now()), type, value }]);
    message.success('已添加订阅');
  };

  const tabItems = [
    {
      key: 'fetch',
      label: '抓取与订阅',
      children: (
        <Row gutter={16}>
          <Col xs={24} md={14}>
            <Card title="订阅设置" size="small">
              <Table
                size="small"
                pagination={false}
                dataSource={subs}
                columns={[
                  { title: '类型', dataIndex: 'type', width: 80 },
                  { title: '值', dataIndex: 'value' },
                  {
                    title: '操作',
                    width: 60,
                    render: (_, r) => (
                      <Button type="text" danger icon={<DeleteOutlined />} onClick={() => setSubs(subs.filter((s) => s.key !== r.key))} />
                    )
                  }
                ]}
              />
              <Input.Search
                style={{ marginTop: 12 }}
                placeholder="新关键词/学科"
                enterButton={<><PlusOutlined /> 添加</>}
                onSearch={(v) => addSub('关键词', v)}
              />
            </Card>
          </Col>
          <Col xs={24} md={10}>
            <Card title="抓取资源配置" size="small">
              <Form layout="vertical">
                <Form.Item label="抓取频率">
                  <Select defaultValue="每日" options={[{ value: '每日' }, { value: '每周' }]} />
                </Form.Item>
                <Form.Item label="仅抓取有代码论文"><Switch /></Form.Item>
                <Form.Item label="仅抓取工程型论文"><Switch /></Form.Item>
              </Form>
            </Card>
          </Col>
        </Row>
      )
    },
    {
      key: 'account',
      label: '个人账户',
      children: (
        <Card style={{ maxWidth: 480 }}>
          <Form layout="vertical" onFinish={() => message.success('账户设置已保存')}>
            <Form.Item label="邮箱" initialValue="user@example.com"><Input /></Form.Item>
            <Form.Item label="密码" initialValue="******"><Input.Password /></Form.Item>
            <Button type="primary" htmlType="submit">保存</Button>
          </Form>
        </Card>
      )
    },
    {
      key: 'web',
      label: '网页设置',
      children: (
        <Card style={{ maxWidth: 480 }}>
          <Form layout="vertical" onFinish={() => message.success('网页设置已保存')}>
            <Form.Item label="界面语言"><Select defaultValue="zh" options={[{ value: 'zh', label: '简体中文' }, { value: 'en', label: 'English' }]} /></Form.Item>
            <Form.Item label="每页条数"><Select defaultValue="10" options={[{ value: '10' }, { value: '20' }]} /></Form.Item>
            <Button type="primary" htmlType="submit">保存</Button>
          </Form>
        </Card>
      )
    }
  ];

  return <Card className="section-card"><Tabs items={tabItems} /></Card>;
}
