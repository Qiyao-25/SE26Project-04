import { Card, Tag, Typography, Button, Space } from 'antd';
import { LinkOutlined } from '@ant-design/icons';
import { useApp } from '../../../../context/AppContext';
import SidebarNotesPreview from './SidebarNotesPreview';
import { ChatBox } from '../../../common/ChatBox';
import FavoriteButton from './FavoriteButton';
import SidebarAssistPreview from './SidebarAssistPreview';

const { Title, Text, Paragraph } = Typography;

function getAuthorText(authors, authorsText) {
  if (authorsText) return authorsText;

  if (Array.isArray(authors)) {
    return authors
      .map((author) => (typeof author === 'string' ? author : author?.name))
      .filter(Boolean)
      .join(', ');
  }

  return authors || '作者信息待补充';
}

function GoViewButton({ onClick }) {
  return (
    <Button
      type="link"
      size="small"
      style={{ padding: 0, height: 'auto' }}
      onClick={(event) => {
        event.stopPropagation();
        onClick?.();
      }}
    >
      前往查看
    </Button>
  );
}

function InfoBlock({ paper, paperId, compact }) {
  const category = paper.primaryCategory || paper.tag || '未分类';
  const arxivId = paper.arxivId || paper.arxiv || '待补充';
  const publishedAt = paper.publishedAt || paper.date || '待补充';
  const authorText = getAuthorText(paper.authors, paper.authorsText);

  return (
    <div>
      <Space size={4} wrap>
        <Tag color="blue">{category}</Tag>
        <Tag>arXiv:{arxivId}</Tag>
      </Space>

      <Title level={5} style={{ marginTop: 8 }}>
        {paper.title}
      </Title>

      <Text type="secondary" style={{ fontSize: 12 }}>
        {authorText}
      </Text>
      <br />
      <Text type="secondary" style={{ fontSize: 12 }}>
        {publishedAt}
      </Text>

      {!compact && (
        <>
          <Paragraph style={{ fontSize: 13, marginTop: 12 }}>
            {paper.summary}
          </Paragraph>
          <FavoriteButton paperId={paperId} block />
          <Button
            block
            icon={<LinkOutlined />}
            style={{ marginTop: 8 }}
            href={paper.sourceUrl}
            target="_blank"
            rel="noreferrer"
          >
            原文链接
          </Button>
        </>
      )}

      {compact && (
        <FavoriteButton paperId={paperId} size="small" />
      )}
    </div>
  );
}

export default function SidebarAllPanel({
  paper,
  paperId,
  onGoTab,
  messages,
  onSend,
  qaStatus
}) {
  const { persona } = useApp();
  const parsed = ['completed', 'qa_ready'].includes(paper.parseStatus);

  const sections = [
    {
      key: 'info',
      title: '论文信息',
      extra: <GoViewButton onClick={() => onGoTab('info')} />,
      content: <InfoBlock paper={paper} paperId={paperId} compact />
    },
    {
      key: 'assist',
      title: '辅助阅读',
      extra: <GoViewButton onClick={() => onGoTab('assist')} />,
      content: parsed ? (
        <SidebarAssistPreview paper={paper} paperId={paperId} />
      ) : (
        <Text type="secondary" style={{ fontSize: 12 }}>
          完成解析后可用 · 当前 {persona}模式
        </Text>
      )
    },
    {
      key: 'notes',
      title: '笔记与评论',
      extra: <GoViewButton onClick={() => onGoTab('notes')} />,
      content: <SidebarNotesPreview paperId={paperId} />
    },
    {
      key: 'compare',
      title: '对比阅读',
      extra: <GoViewButton onClick={() => onGoTab('compare')} />,
      content: (
        <Text type="secondary" style={{ fontSize: 12 }}>
          双论文并排对比，快捷切换
        </Text>
      )
    },
    {
      key: 'qa',
      title: '智能问答',
      extra: <GoViewButton onClick={() => onGoTab('qa')} />,
      content: (
        <ChatBox
          messages={messages}
          onSend={onSend}
          loading={qaStatus === 'generating'}
          placeholder="围绕当前论文提问..."
          minHeight={120}
        />
      )
    }
  ];

  return (
    <div className="sidebar-scroll">
      {sections.map((section) => (
        <Card
          key={section.key}
          size="small"
          className="sidebar-jump-card"
          title={section.title}
          extra={section.extra}
          onClick={(event) => {
            if (event.target.closest('button, a, input, textarea, .ant-input, .ant-btn')) {
              return;
            }
            onGoTab(section.key);
          }}
        >
          {section.content}
        </Card>
      ))}
    </div>
  );
}
