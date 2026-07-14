import { Card, Tag, Typography, Space } from 'antd';
import { FileTextOutlined, CalendarOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PAPERS } from '../../data/papers';

const { Text, Paragraph } = Typography;

function getAuthorText(authors) {
  if (Array.isArray(authors)) {
    return authors
      .map((author) => (typeof author === 'string' ? author : author?.name))
      .filter(Boolean)
      .join(', ');
  }

  return authors || '作者信息待补充';
}

export default function PaperCard({ paperId, paper: paperProp, compact = false }) {
  const navigate = useNavigate();
  const paper = paperProp || PAPERS[paperId];

  if (!paper) return null;

  const resolvedPaperId = paper.paperId || paper.id || paperId;
  const category = paper.primaryCategory || paper.tag || '未分类';
  const arxivId = paper.arxivId || paper.arxiv || '待补充';
  const publishedAt = paper.publishedAt || paper.date || '待补充';
  const authorText = getAuthorText(paper.authors);

  if (compact) {
    return (
      <Card
        size="small"
        hoverable
        className="paper-card-compact"
        onClick={() => navigate(`/paper/${resolvedPaperId}`)}
      >
        <Space align="start">
          <FileTextOutlined style={{ fontSize: 22, color: '#8b5cf6', marginTop: 3 }} />
          <div>
            <Text strong ellipsis style={{ maxWidth: 280 }}>
              {paper.title}
            </Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {authorText}
            </Text>
          </div>
          <Tag color="blue">{category}</Tag>
        </Space>
      </Card>
    );
  }

  return (
    <Card
      hoverable
      className="paper-card"
      onClick={() => navigate(`/paper/${resolvedPaperId}`)}
    >
      <div className="paper-card-thumb">
        <FileTextOutlined style={{ fontSize: 32, color: '#8b5cf6' }} />
        <Text type="secondary" style={{ fontSize: 11, marginTop: 6 }}>
          PDF
        </Text>
      </div>

      <div className="paper-card-body">
        <Paragraph
          className="paper-card-title"
          strong
          ellipsis={{ rows: 2 }}
          style={{ marginBottom: 0 }}
        >
          {paper.title}
        </Paragraph>

        <div className="paper-card-meta-row">
          <span>{authorText}</span>
        </div>

        <Space size={6} wrap>
          <Tag color="blue">{category}</Tag>
          <Tag>arXiv:{arxivId}</Tag>
          <Tag icon={<CalendarOutlined />}>{publishedAt}</Tag>
        </Space>

        <Paragraph
          type="secondary"
          ellipsis={{ rows: 2 }}
          style={{ fontSize: 13, marginTop: 12, marginBottom: 0 }}
        >
          {paper.summary}
        </Paragraph>

        <div className="paper-keywords">
          {(paper.keywords || []).slice(0, 3).map((keyword) => (
            <Tag key={keyword} color="geekblue">
              {keyword}
            </Tag>
          ))}
        </div>
      </div>
    </Card>
  );
}
