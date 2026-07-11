import { Row, Col, Card, Tabs, Typography, Tag } from 'antd';
import { useParams } from 'react-router-dom';
import { useEffect } from 'react';
import { PAPERS } from '../../data/papers';
import { useApp } from '../../context/AppContext';
import PaperSidebar from '../../components/paper/detail/PaperSidebar';

const { Title, Paragraph, Text } = Typography;

export default function PaperDetailPage() {
  const { paperId } = useParams();
  const paper = PAPERS[paperId];
  const { setCompareForPaper } = useApp();

  useEffect(() => {
    if (paperId) setCompareForPaper(paperId);
  }, [paperId, setCompareForPaper]);

  if (!paper) {
    return <Card>论文不存在</Card>;
  }

  const mainTabs = [
    {
      key: 'content',
      label: 'a · 论文主体',
      children: (
        <div className="pdf-placeholder">
          <Text type="secondary">[ PDF / HTML 原文阅读区 ]</Text>
          <Paragraph style={{ marginTop: 16 }}>{paper.title}</Paragraph>
          <Paragraph type="secondary">{paper.summary}</Paragraph>
        </div>
      )
    },
    {
      key: 'summary',
      label: 'b · 智能总结',
      children: (
        <div>
          <Title level={5}>摘要</Title>
          <Paragraph>{paper.summary}</Paragraph>
          <Title level={5}>核心概念</Title>
          <Paragraph>{(paper.conceptTags || []).join('、')}</Paragraph>
          <Title level={5}>方法论</Title>
          <Paragraph>基于 {paper.direction} 的方法设计与实验验证（原型占位）。</Paragraph>
        </div>
      )
    },
    {
      key: 'graph',
      label: 'c · 知识图谱&脉络',
      children: (
        <div className="graph-placeholder">
          <Tag>{paper.title.split(':')[0]}</Tag>
          {(paper.conceptTags || []).map((c) => (
            <Tag key={c} color="processing" style={{ margin: 8 }}>{c}</Tag>
          ))}
          <Paragraph type="secondary" style={{ marginTop: 16 }}>[ 关联论文与概念关系图谱 ]</Paragraph>
        </div>
      )
    }
  ];

  return (
    <div className="page-paper-detail">
      <Row gutter={16} align="stretch">
        <Col xs={24} lg={15}>
          <Card className="section-card paper-main-card">
            <Tabs items={mainTabs} />
          </Card>
        </Col>
        <Col xs={24} lg={9}>
          <PaperSidebar paperId={paperId} paper={paper} />
        </Col>
      </Row>
    </div>
  );
}
