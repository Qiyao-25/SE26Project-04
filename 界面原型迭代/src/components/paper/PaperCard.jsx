import { Card, Tag, Typography, Space } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
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
        <Space>
          <FileTextOutlined style={{ fontSize: 20, color: '#999' }} />
          <div>
            <Text strong ellipsis style={{ maxWidth: 280 }}>{paper.title}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>{paper.authors}</Text>
          </div>
          <Tag>{paper.tag}</Tag>
        </Space>
      </Card>
    );
  }

  return (
    <Card hoverable className="paper-card" onClick={() => navigate(`/paper/${paperId}`)}>
      <div className="paper-card-thumb">
        <FileTextOutlined style={{ fontSize: 32, color: '#bfbfbf' }} />
        <Text type="secondary" style={{ fontSize: 11 }}>PDF</Text>
      </div>
      <div className="paper-card-body">
        <Paragraph strong ellipsis={{ rows: 2 }} style={{ marginBottom: 8 }}>{paper.title}</Paragraph>
        <Text type="secondary" style={{ fontSize: 12 }}>{paper.authors}</Text>
        <br />
        <Space size={4} style={{ marginTop: 8 }}>
          <Tag color="blue">{paper.tag}</Tag>
          <Tag>arXiv:{paper.arxiv}</Tag>
        </Space>
        <Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ fontSize: 12, marginTop: 8, marginBottom: 0 }}>
          {paper.summary}
        </Paragraph>
      </div>
    </Card>
  );
}
