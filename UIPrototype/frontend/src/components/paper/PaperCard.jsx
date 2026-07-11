import { Card, Tag, Typography, Space } from 'antd';
import { FileTextOutlined, CalendarOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PAPERS } from '../../data/papers';

const { Text, Paragraph } = Typography;

export default function PaperCard({ paperId, compact = false }) {
  const navigate = useNavigate();
  const paper = PAPERS[paperId];
  if (!paper) return null;

  if (compact) {
    return (
      <Card size="small" hoverable className="paper-card-compact" onClick={() => navigate(`/paper/${paperId}`)}>
        <Space align="start">
          <FileTextOutlined style={{ fontSize: 22, color: '#8b5cf6', marginTop: 3 }} />
          <div>
            <Text strong ellipsis style={{ maxWidth: 280 }}>{paper.title}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>{paper.authors}</Text>
          </div>
          <Tag color="blue">{paper.tag}</Tag>
        </Space>
      </Card>
    );
  }

  return (
    <Card hoverable className="paper-card" onClick={() => navigate(`/paper/${paperId}`)}>
      <div className="paper-card-thumb">
        <FileTextOutlined style={{ fontSize: 32,color: '#8b5cf6' }} />
        <Text type="secondary" style={{ fontSize: 11, marginTop: 6 }}>PDF</Text>
      </div>

      <div className="paper-card-body">
        <Paragraph className="paper-card-title" strong ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }}>
          {paper.title}
        </Paragraph>

        <div className="paper-card-meta-row">
          <span>{paper.authors}</span>
        </div>

        <Space size={6} wrap>
          <Tag color="blue">{paper.tag}</Tag>
          <Tag>arXiv:{paper.arxiv}</Tag>
          <Tag icon={<CalendarOutlined />}>{paper.date}</Tag>
        </Space>

        <Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ fontSize: 13, marginTop: 12, marginBottom: 0 }}>
          {paper.summary}
        </Paragraph>

        <div className="paper-keywords">
          {(paper.keywords || []).slice(0, 3).map((keyword) => (
            <Tag key={keyword} color="geekblue">{keyword}</Tag>
          ))}
        </div>
      </div>
    </Card>
  );
}
