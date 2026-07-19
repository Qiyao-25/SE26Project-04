import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Space,
  Spin,
  Tag,
  Timeline,
  Typography
} from 'antd';
import { ApartmentOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getPaperGraph, rebuildPaperGraph } from '../../../services/paperService';

const { Title, Paragraph, Text } = Typography;

const TYPE_META = {
  concept: { color: 'purple', label: '概念' },
  method: { color: 'green', label: '方法' },
  dataset: { color: 'orange', label: '数据集' },
  task: { color: 'magenta', label: '任务/领域' },
  paper: { color: 'blue', label: '论文' }
};

const ROLE_COLOR = {
  current: 'blue',
  precursor: 'default',
  followup: 'green',
  related: 'geekblue'
};

const ROLE_LABEL = {
  current: '当前论文',
  precursor: '前驱工作',
  followup: '后续发展',
  related: '主题相关'
};

function shortTitle(title, max = 42) {
  const value = String(title || '').replace(/\s+/g, ' ').trim();
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

function partitionGraph(graph, paperId) {
  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const current =
    nodes.find((n) => n.type === 'paper' && (n.role === 'current' || String(n.paper_id) === String(paperId))) ||
    nodes.find((n) => n.type === 'paper') ||
    null;

  const concepts = nodes.filter((n) => n.type === 'concept').slice(0, 8);
  const methods = nodes.filter((n) => n.type === 'method').slice(0, 6);
  const others = nodes.filter((n) => ['dataset', 'task'].includes(n.type)).slice(0, 4);

  const relatedFromNodes = nodes.filter(
    (n) => n.type === 'paper' && n.role !== 'current' && String(n.paper_id) !== String(paperId)
  );
  const relatedFromLineage = (graph?.lineage || []).filter(
    (item) => item.role !== 'current' && String(item.paper_id) !== String(paperId)
  );

  // Prefer lineage for related papers (has notes); fall back to graph nodes
  const relatedMap = new Map();
  relatedFromLineage.forEach((item) => {
    const key = String(item.paper_id || item.arxiv_id || item.title);
    relatedMap.set(key, {
      paper_id: item.paper_id,
      arxiv_id: item.arxiv_id,
      title: item.title,
      published_at: item.published_at,
      role: item.role || 'related',
      note: item.note || ''
    });
  });
  relatedFromNodes.forEach((node) => {
    const key = String(node.paper_id || node.arxiv_id || node.label);
    if (!relatedMap.has(key)) {
      relatedMap.set(key, {
        paper_id: node.paper_id,
        arxiv_id: node.arxiv_id,
        title: node.label,
        published_at: node.published_at,
        role: node.role || 'related',
        note: ''
      });
    }
  });

  const coreIds = new Set([
    ...(current ? [current.id] : []),
    ...concepts.map((n) => n.id),
    ...methods.map((n) => n.id),
    ...others.map((n) => n.id)
  ]);
  const coreEdges = edges
    .filter((e) => coreIds.has(e.source) && coreIds.has(e.target))
    .slice(0, 16);

  return {
    current,
    concepts,
    methods,
    others,
    related: [...relatedMap.values()].slice(0, 8),
    coreEdges,
    lineage: graph?.lineage || []
  };
}

function RelationChip({ edge, nodeMap }) {
  const target = nodeMap[edge.target] || nodeMap[edge.source];
  if (!target || target.type === 'paper') return null;
  const meta = TYPE_META[target.type] || TYPE_META.concept;
  return (
    <Tag color={meta.color} style={{ marginBottom: 6, whiteSpace: 'normal', height: 'auto', lineHeight: 1.4 }}>
      {edge.label || meta.label} · {target.label}
    </Tag>
  );
}

export default function PaperGraphPanel({ paperId, paperTitle }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState('');
  const [graph, setGraph] = useState(null);

  const load = useCallback(async ({ force = false } = {}) => {
    setError('');
    if (force) setRebuilding(true);
    else setLoading(true);
    try {
      const data = force ? await rebuildPaperGraph(paperId) : await getPaperGraph(paperId);
      setGraph(data);
    } catch (err) {
      setError(err.message || '图谱加载失败');
      setGraph(null);
    } finally {
      setLoading(false);
      setRebuilding(false);
    }
  }, [paperId]);

  useEffect(() => {
    load();
  }, [load]);

  const view = useMemo(() => partitionGraph(graph, paperId), [graph, paperId]);
  const nodeMap = useMemo(() => {
    const map = {};
    (graph?.nodes || []).forEach((n) => {
      map[n.id] = n;
    });
    return map;
  }, [graph]);

  if (loading) {
    return (
      <div style={{ minHeight: 240, display: 'grid', placeItems: 'center' }}>
        <Spin tip="正在加载知识图谱与研究脉络..." />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="图谱加载失败"
        description={error}
        action={
          <Button size="small" onClick={() => load()}>
            重试
          </Button>
        }
      />
    );
  }

  if (!graph || !(graph.nodes || []).length) {
    return (
      <Empty description="暂无图谱数据。可先完成解析，或点击生成。">
        <Button type="primary" icon={<ApartmentOutlined />} loading={rebuilding} onClick={() => load({ force: true })}>
          生成知识图谱
        </Button>
      </Empty>
    );
  }

  const currentLabel = view.current?.label || paperTitle || '当前论文';

  return (
    <div className="paper-graph-panel">
      <Space wrap style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Title level={5} style={{ margin: 0 }}>
            知识图谱
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            来源：{graph.source || 'unknown'}
            {graph.generated ? ' · 刚生成' : ' · 已缓存'} · 以概念/方法为主，相关论文见下方列表
          </Text>
        </div>
        <Button icon={<ReloadOutlined />} loading={rebuilding} onClick={() => load({ force: true })}>
          重新生成
        </Button>
      </Space>

      {graph.narrative && (
        <Alert
          type="info"
          showIcon
          message="主题说明"
          description={graph.narrative}
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 可读结构图：中心论文 + 左右概念/方法，避免节点堆叠 */}
      <Card size="small" style={{ marginBottom: 16, background: '#f8fafc' }}>
        <div style={{ textAlign: 'center', marginBottom: 16 }}>
          <Tag color="blue">当前论文</Tag>
          <Title level={5} style={{ margin: '8px 0 4px' }}>
            {currentLabel}
          </Title>
          {view.current?.arxiv_id && (
            <Text type="secondary">arXiv:{view.current.arxiv_id}</Text>
          )}
        </div>

        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Card size="small" title={<Space><Tag color="purple">概念</Tag><Text>核心概念</Text></Space>}>
              {view.concepts.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无概念节点" />
              ) : (
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  {view.concepts.map((node) => (
                    <div
                      key={node.id}
                      style={{
                        padding: '8px 10px',
                        background: '#fff',
                        border: '1px solid #ede9fe',
                        borderRadius: 8
                      }}
                    >
                      <Text strong>{node.label}</Text>
                      {node.description && (
                        <Paragraph type="secondary" style={{ margin: '4px 0 0', fontSize: 12 }} ellipsis={{ rows: 2 }}>
                          {node.description}
                        </Paragraph>
                      )}
                    </div>
                  ))}
                </Space>
              )}
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card size="small" title={<Space><Tag color="green">方法</Tag><Text>关键方法</Text></Space>}>
              {view.methods.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无方法节点" />
              ) : (
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  {view.methods.map((node, index) => (
                    <div
                      key={node.id}
                      style={{
                        padding: '8px 10px',
                        background: '#fff',
                        border: '1px solid #d1fae5',
                        borderRadius: 8
                      }}
                    >
                      <Text strong>
                        {index + 1}. {node.label}
                      </Text>
                      {node.description && (
                        <Paragraph type="secondary" style={{ margin: '4px 0 0', fontSize: 12 }} ellipsis={{ rows: 2 }}>
                          {node.description}
                        </Paragraph>
                      )}
                    </div>
                  ))}
                </Space>
              )}
            </Card>
          </Col>
        </Row>

        {(view.others.length > 0 || view.coreEdges.length > 0) && (
          <div style={{ marginTop: 16 }}>
            {view.others.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <Text type="secondary" style={{ marginRight: 8 }}>
                  其他实体：
                </Text>
                {view.others.map((node) => (
                  <Tag key={node.id} color={(TYPE_META[node.type] || TYPE_META.task).color}>
                    {(TYPE_META[node.type] || TYPE_META.task).label} · {node.label}
                  </Tag>
                ))}
              </div>
            )}
            {view.coreEdges.length > 0 && (
              <div>
                <Text type="secondary" style={{ display: 'block', marginBottom: 6 }}>
                  与当前论文的关系：
                </Text>
                <Space size={[4, 4]} wrap>
                  {view.coreEdges.map((edge) => (
                    <RelationChip key={edge.id} edge={edge} nodeMap={nodeMap} />
                  ))}
                </Space>
              </div>
            )}
          </div>
        )}
      </Card>

      <Title level={5}>相关论文（主题邻近）</Title>
      {view.related.length === 0 ? (
        <Empty description="暂无相关论文" style={{ marginBottom: 16 }} />
      ) : (
        <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
          {view.related.map((item) => (
            <Col xs={24} sm={12} key={String(item.paper_id || item.arxiv_id || item.title)}>
              <Card
                size="small"
                hoverable={Boolean(item.paper_id)}
                onClick={() => {
                  if (item.paper_id) navigate(`/paper/${item.paper_id}`);
                }}
              >
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color={ROLE_COLOR[item.role] || 'default'}>{ROLE_LABEL[item.role] || item.role}</Tag>
                    {item.published_at && (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {String(item.published_at).slice(0, 10)}
                      </Text>
                    )}
                  </Space>
                  <Text strong>
                    <FileTextOutlined style={{ marginRight: 6 }} />
                    {shortTitle(item.title, 64)}
                  </Text>
                  {item.arxiv_id && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      arXiv:{item.arxiv_id}
                    </Text>
                  )}
                  {item.note && (
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: 12 }} ellipsis={{ rows: 2 }}>
                      {item.note}
                    </Paragraph>
                  )}
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Title level={5}>研究主题脉络</Title>
      {view.lineage.length === 0 ? (
        <Empty description="暂无脉络条目" />
      ) : (
        <Timeline
          items={view.lineage.map((item) => ({
            color:
              item.role === 'current' ? 'blue' : item.role === 'followup' ? 'green' : 'gray',
            children: (
              <div>
                <Space wrap size={6}>
                  <Tag color={ROLE_COLOR[item.role] || 'default'}>{ROLE_LABEL[item.role] || item.role}</Tag>
                  {item.published_at && (
                    <Text type="secondary">{String(item.published_at).slice(0, 10)}</Text>
                  )}
                  {item.arxiv_id && <Tag>arXiv:{item.arxiv_id}</Tag>}
                </Space>
                <div style={{ marginTop: 6 }}>
                  {item.paper_id && String(item.paper_id) !== String(paperId) ? (
                    <Button
                      type="link"
                      style={{ padding: 0, height: 'auto', whiteSpace: 'normal', textAlign: 'left' }}
                      onClick={() => navigate(`/paper/${item.paper_id}`)}
                    >
                      {item.title || paperTitle}
                    </Button>
                  ) : (
                    <Text strong>{item.title || paperTitle}</Text>
                  )}
                </div>
                {item.note && (
                  <Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 4, fontSize: 13 }}>
                    {item.note}
                  </Paragraph>
                )}
              </div>
            )
          }))}
        />
      )}
    </div>
  );
}
