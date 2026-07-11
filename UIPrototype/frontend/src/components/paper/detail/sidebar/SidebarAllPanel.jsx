import { Card, Tag, Typography, Button, Space } from 'antd';
import { StarOutlined, LinkOutlined } from '@ant-design/icons';
import { useApp } from '../../../../context/AppContext';
import { MODE_ASSIST } from '../../../../data/papers';
import SidebarNotesPreview from './SidebarNotesPreview';
import { ChatBox } from '../../../common/ChatBox';
import { mockPaperReply } from '../../../../utils/mock';
import { useState } from 'react';

const { Title, Text, Paragraph } = Typography;

function InfoBlock({ paper, compact }) {
  return (
    <div>
      <Space size={4} wrap>
        <Tag color="blue">{paper.tag}</Tag>
        <Tag>arXiv:{paper.arxiv}</Tag>
      </Space>
      <Title level={compact ? 5 : 5} style={{ marginTop: 8 }}>{paper.title}</Title>
      <Text type="secondary" style={{ fontSize: 12 }}>{paper.authors}</Text>
      <br />
      <Text type="secondary" style={{ fontSize: 12 }}>{paper.date}</Text>
      {!compact && (
        <>
          <Paragraph style={{ fontSize: 13, marginTop: 12 }}>{paper.summary}</Paragraph>
          <Button block icon={<StarOutlined />} style={{ marginTop: 8 }}>收藏</Button>
          <Button block icon={<LinkOutlined />} style={{ marginTop: 8 }}>原文链接</Button>
        </>
      )}
      {compact && <Button size="small" icon={<StarOutlined />} style={{ marginTop: 8 }}>收藏</Button>}
    </div>
  );
}

export default function SidebarAllPanel({ paper, paperId, onGoTab }) {
  const { persona } = useApp();
  const [messages, setMessages] = useState([{ role: 'bot', text: '可围绕本篇论文提问' }]);

  const handleChat = (text) => {
    setMessages((m) => [...m, { role: 'user', text }]);
    setTimeout(() => {
      setMessages((m) => [...m, { role: 'bot', text: mockPaperReply(text, paperId) }]);
      onGoTab('qa');
    }, 400);
  };

  const sections = [
    { key: 'info', title: '论文信息', extra: '查看 →', content: <InfoBlock paper={paper} compact /> },
    {
      key: 'assist',
      title: '辅助阅读',
      extra: <Tag>{persona}模式</Tag>,
      content: <Paragraph style={{ fontSize: 12, margin: 0, whiteSpace: 'pre-wrap' }}>{MODE_ASSIST[persona](paper)}</Paragraph>
    },
    { key: 'notes', title: '笔记与评论', extra: '展开 →', content: <SidebarNotesPreview paperId={paperId} /> },
    {
      key: 'compare',
      title: '对比阅读',
      extra: '展开 →',
      content: <Text type="secondary" style={{ fontSize: 12 }}>双论文并排对比，快捷切换</Text>
    },
    {
      key: 'qa',
      title: '智能问答',
      extra: '展开 →',
      content: <ChatBox messages={messages} onSend={handleChat} minHeight={100} />
    }
  ];

  return (
    <div className="sidebar-scroll">
      {sections.map((s) => (
        <Card
          key={s.key}
          size="small"
          className="sidebar-jump-card"
          title={s.title}
          extra={s.extra}
          onClick={(e) => {
            if (e.target.closest('button, input, textarea, .ant-input, .ant-btn')) return;
            onGoTab(s.key);
          }}
        >
          {s.content}
        </Card>
      ))}
    </div>
  );
}
