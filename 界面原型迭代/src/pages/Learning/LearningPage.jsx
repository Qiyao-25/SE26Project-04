import { useState } from 'react';
import { Card, Tabs, Row, Col, List, Tag, Typography, Segmented, Switch, Input, Form, Button, message } from 'antd';
import { READING_HISTORY, PERSONAS, MODE_DESC, PAPERS } from '../../data/papers';
import { useApp } from '../../context/AppContext';
import PaperCard from '../../components/paper/PaperCard';

const { Text, Paragraph } = Typography;

export default function LearningPage() {
  const { persona, setPersona } = useApp();
  const [historyKey, setHistoryKey] = useState('today');
  const history = READING_HISTORY[historyKey];

  const tabItems = [
    {
      key: 'favorites',
      label: '收藏夹',
      children: (
        <Row gutter={[16, 16]}>
          {['attention', 'bert', 'lora'].map((id) => (
            <Col xs={24} sm={12} lg={8} key={id}><PaperCard paperId={id} /></Col>
          ))}
        </Row>
      )
    },
    {
      key: 'notes',
      label: '笔记/评论',
      children: (
        <List
          dataSource={[
            { paper: 'attention', text: '核心创新在于完全用注意力替代 RNN', date: '2026-07-01' },
            { paper: 'bert', text: '预训练-微调范式的里程碑', date: '2026-06-18' }
          ]}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                title={PAPERS[item.paper]?.title}
                description={<>{item.text} · <Text type="secondary">{item.date}</Text></>}
              />
            </List.Item>
          )}
        />
      )
    },
    {
      key: 'history',
      label: '阅读历史',
      children: (
        <>
          <Segmented
            options={[
              { value: 'today', label: '今天' },
              { value: 'yesterday', label: '昨天' },
              { value: 'earlier', label: '更早' }
            ]}
            value={historyKey}
            onChange={setHistoryKey}
            style={{ marginBottom: 16 }}
          />
          <Text strong>{history.label}</Text>
          <List
            style={{ marginTop: 12 }}
            dataSource={history.items}
            renderItem={(item) => (
              <List.Item>
                <PaperCard paperId={item.paper} compact />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {item.time} · {item.section} · {item.duration}
                </Text>
              </List.Item>
            )}
          />
        </>
      )
    },
    {
      key: 'wiki',
      label: '概念词典',
      children: (
        <Row gutter={[16, 16]}>
          {['Self-Attention', 'Pre-training', 'LoRA'].map((name) => (
            <Col xs={24} sm={8} key={name}>
              <Card hoverable size="small">
                <Text strong>{name}</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>Wiki 词条</Text>
              </Card>
            </Col>
          ))}
        </Row>
      )
    },
    {
      key: 'profile',
      label: '个人画像',
      children: (
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Card title="画像标签（系统自动）" size="small">
              <div><Text type="secondary">常看方向</Text> <Tag>NLP</Tag><Tag>Transformer</Tag></div>
              <div style={{ marginTop: 8 }}><Text type="secondary">偏好难度</Text> <Tag>中等偏高</Tag></div>
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card title="手动微调" size="small">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>偏好有代码</span><Switch defaultChecked /></div>
              <div style={{ marginTop: 8 }}><Text type="secondary">关注作者/机构</Text><Input defaultValue="Google, OpenAI" style={{ marginTop: 4 }} /></div>
            </Card>
          </Col>
        </Row>
      )
    },
    {
      key: 'mode',
      label: '默认模式',
      children: (
        <Card>
          <Paragraph type="secondary">设置全局默认阅读模式；论文详情页可快捷切换</Paragraph>
          <Segmented block options={PERSONAS} value={persona} onChange={setPersona} />
          <Paragraph style={{ marginTop: 16, padding: 12, background: '#fafafa' }}>{MODE_DESC[persona]}</Paragraph>
        </Card>
      )
    }
  ];

  return (
    <Card className="section-card">
      <Tabs items={tabItems} />
    </Card>
  );
}
