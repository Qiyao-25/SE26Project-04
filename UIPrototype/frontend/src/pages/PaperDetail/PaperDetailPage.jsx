import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Empty,
  List,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  message
} from 'antd';
import {
  ArrowLeftOutlined,
  ExpandOutlined,
  FilePdfOutlined,
  LinkOutlined,
  MenuUnfoldOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import {
  boostParsePriority,
  getPaperContent,
  getPaperDetail,
  getPaperSummary,
  getPaperGraph,
  listPaperChunks,
  rebuildPaperGraph
} from '../../services/paperService';
import { createAction, isPersistedPaperId } from '../../services/learningService';
import PaperSidebar from '../../components/paper/detail/PaperSidebar';
import PaperGraphCanvas from '../../components/paper/detail/PaperGraphCanvas';
import PaperExcerptsPanel from '../../components/paper/detail/PaperExcerptsPanel';

const { Title, Paragraph, Text } = Typography;

function getParseStatusLabel(status) {
  const labels = {
    pending: '待解析',
    parsing: '解析中',
    queued: '排队中',
    running: '解析中',
    succeeded: '解析完成',
    completed: '已完成',
    qa_ready: '可问答',
    failed: '解析失败'
  };

  return labels[status] || status || '未知';
}

export default function PaperDetailPage() {
  const { paperId } = useParams();
  const navigate = useNavigate();
  const {
    userId,
    setCompareForPaper,
    setLockedPaperId,
    exitLockedPaper,
    comparePaperB,
    comparePreviewActive,
    setComparePreviewActive,
  } = useApp();

  const [paper, setPaper] = useState(null);
  const [content, setContent] = useState(null);
  const [summaryData, setSummaryData] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [graphError, setGraphError] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [reloadToken, setReloadToken] = useState(0);
  const [graphRefreshing, setGraphRefreshing] = useState(false);
  const [mainTab, setMainTab] = useState('content');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [pdfFullscreen, setPdfFullscreen] = useState(false);
  const [excerpts, setExcerpts] = useState([]);
  const [priorityLoading, setPriorityLoading] = useState(false);
  const historyRecordedFor = useRef(null);

  const [previewPaper, setPreviewPaper] = useState(null);
  const [previewContent, setPreviewContent] = useState(null);
  const [previewSummary, setPreviewSummary] = useState(null);
  const [previewGraph, setPreviewGraph] = useState(null);
  const [previewGraphError, setPreviewGraphError] = useState('');
  const [previewExcerpts, setPreviewExcerpts] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');

  const viewingOther = Boolean(
    comparePreviewActive
    && comparePaperB
    && String(comparePaperB) !== String(paperId)
  );

  useEffect(() => {
    if (paperId) setCompareForPaper(paperId);
  }, [paperId, setCompareForPaper]);

  // 进入详情即锁定工作空间到本篇；切换学习/设置后再点工作空间仍回来
  useEffect(() => {
    if (paperId) setLockedPaperId(String(paperId));
  }, [paperId, setLockedPaperId]);

  // Switching base paper exits compare preview; keep the original compare page intact.
  useEffect(() => {
    setComparePreviewActive(false);
  }, [paperId, setComparePreviewActive]);

  useEffect(() => {
    if (!comparePaperB) setComparePreviewActive(false);
  }, [comparePaperB, setComparePreviewActive]);

  useEffect(() => {
    setPdfFullscreen(false);
  }, [paperId, comparePreviewActive, comparePaperB]);

  useEffect(() => {
    if (!pdfFullscreen) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setPdfFullscreen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [pdfFullscreen]);

  useEffect(() => {
    let cancelled = false;

    async function loadPaper() {
      setLoading(true);
      setLoadError('');
      setPaper(null);
      setContent(null);
      setSummaryData(null);
      setGraphData(null);
      setGraphError('');
      setExcerpts([]);

      try {
        const [detailResult, contentResult, summaryResult, graphResult, chunksResult] = await Promise.allSettled([
          getPaperDetail(paperId),
          getPaperContent(paperId),
          getPaperSummary(paperId),
          getPaperGraph(paperId),
          listPaperChunks(paperId, { limit: 120 }),
        ]);

        if (cancelled) return;

        if (detailResult.status === 'rejected') throw detailResult.reason;

        setPaper(detailResult.value);
        setContent(contentResult.status === 'fulfilled' ? contentResult.value : null);
        setSummaryData(summaryResult.status === 'fulfilled' ? summaryResult.value : null);
        setGraphData(graphResult.status === 'fulfilled' ? graphResult.value : null);
        setGraphError(graphResult.status === 'rejected' ? (graphResult.reason?.message || '知识图谱加载失败') : '');
        setExcerpts(chunksResult.status === 'fulfilled' ? (chunksResult.value || []) : []);
      } catch (error) {
        if (!cancelled) {
          setLoadError(error.message || '论文加载失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadPaper();

    return () => {
      cancelled = true;
    };
  }, [paperId, reloadToken]);

  useEffect(() => {
    if (!viewingOther) {
      setPreviewPaper(null);
      setPreviewContent(null);
      setPreviewSummary(null);
      setPreviewGraph(null);
      setPreviewGraphError('');
      setPreviewExcerpts([]);
      setPreviewError('');
      setPreviewLoading(false);
      return undefined;
    }

    const previewId = String(comparePaperB);
    let cancelled = false;
    setPreviewLoading(true);
    setPreviewError('');

    (async () => {
      try {
        const [detailResult, contentResult, summaryResult, graphResult, chunksResult] = await Promise.allSettled([
          getPaperDetail(previewId),
          getPaperContent(previewId),
          getPaperSummary(previewId),
          getPaperGraph(previewId),
          listPaperChunks(previewId, { limit: 120 }),
        ]);
        if (cancelled) return;
        if (detailResult.status === 'rejected') throw detailResult.reason;
        setPreviewPaper(detailResult.value);
        setPreviewContent(contentResult.status === 'fulfilled' ? contentResult.value : null);
        setPreviewSummary(summaryResult.status === 'fulfilled' ? summaryResult.value : null);
        setPreviewGraph(graphResult.status === 'fulfilled' ? graphResult.value : null);
        setPreviewGraphError(graphResult.status === 'rejected' ? (graphResult.reason?.message || '知识图谱加载失败') : '');
        setPreviewExcerpts(chunksResult.status === 'fulfilled' ? (chunksResult.value || []) : []);
      } catch (error) {
        if (!cancelled) {
          setPreviewPaper(null);
          setPreviewExcerpts([]);
          setPreviewError(error.message || '对比论文加载失败');
        }
      } finally {
        if (!cancelled) setPreviewLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [viewingOther, comparePaperB]);

  useEffect(() => {
    if (!paper || !isPersistedPaperId(paperId) || historyRecordedFor.current === paperId) return;
    historyRecordedFor.current = paperId;
    createAction({
      userId,
      paperId,
      actionType: 'reading_history',
      payload: { section: '论文主体', duration: '刚刚' }
    }).catch(() => {
      // 阅读历史不应阻塞论文阅读。
    });
  }, [paper, paperId, userId]);

  const handleExitPaper = () => {
    exitLockedPaper();
    navigate('/workspace');
  };

  const handleGraphRefresh = async () => {
    if (graphRefreshing) return;
    const targetId = viewingOther ? String(comparePaperB) : paperId;
    setGraphRefreshing(true);
    try {
      const nextGraph = await rebuildPaperGraph(targetId);
      if (viewingOther) {
        setPreviewGraph(nextGraph);
        setPreviewGraphError('');
      } else {
        setGraphData(nextGraph);
        setGraphError('');
      }
      message.success('知识图谱已刷新');
    } catch (error) {
      message.error(error.message || '知识图谱刷新失败');
    } finally {
      setGraphRefreshing(false);
    }
  };

  const handleBoostParsePriority = async () => {
    if (priorityLoading || viewingOther) return;
    setPriorityLoading(true);
    try {
      const task = await boostParsePriority(paperId);
      const status = task?.status || '';
      if (status === 'running') {
        message.info('该论文已在解析中');
      } else {
        message.success('已提高优先级，正在立即解析');
      }
      setPaper((prev) => (prev ? {
        ...prev,
        parseStatus: status === 'running' ? 'parsing' : 'queued',
      } : prev));
      // Refresh soon so status Tag / button update after runner claims the task.
      window.setTimeout(() => setReloadToken((n) => n + 1), 2500);
    } catch (error) {
      message.error(error.message || '提高解析优先级失败');
    } finally {
      setPriorityLoading(false);
    }
  };

  const viewPaper = viewingOther ? previewPaper : paper;
  const viewContent = viewingOther ? previewContent : content;
  const viewSummary = viewingOther ? previewSummary : summaryData;
  const viewGraph = viewingOther ? previewGraph : graphData;
  const viewGraphError = viewingOther ? previewGraphError : graphError;
  const viewExcerpts = viewingOther ? previewExcerpts : excerpts;
  const viewPaperId = viewingOther ? String(comparePaperB) : paperId;

  if (loading) {
    return (
      <Card className="section-card">
        <div style={{ minHeight: 260, display: 'grid', placeItems: 'center' }}>
          <Spin tip="正在加载论文详情、原文和智能摘要..." />
        </div>
      </Card>
    );
  }

  if (loadError) {
    return (
      <div className="page-paper-detail">
        <Button icon={<ArrowLeftOutlined />} onClick={handleExitPaper} style={{ marginBottom: 12 }}>
          退出论文
        </Button>
        <Alert
          type="error"
          showIcon
          message="论文加载失败"
          description={loadError}
        />
      </div>
    );
  }

  if (!paper) {
    return (
      <div className="page-paper-detail">
        <Button icon={<ArrowLeftOutlined />} onClick={handleExitPaper} style={{ marginBottom: 12 }}>
          退出论文
        </Button>
        <Card className="section-card">
          <Empty description={`论文不存在：${paperId}`} />
        </Card>
      </div>
    );
  }

  const shownPaper = viewPaper || paper;
  const shownContent = viewingOther && viewPaper ? viewContent : content;
  const shownSummary = viewingOther && viewPaper ? viewSummary : summaryData;
  const shownGraph = viewingOther && viewPaper ? viewGraph : graphData;
  const shownGraphError = viewingOther && viewPaper ? viewGraphError : graphError;
  const shownExcerpts = viewingOther && viewPaper ? viewExcerpts : excerpts;
  const shownPaperId = viewingOther && viewPaper ? viewPaperId : paperId;
  const shownSummaryReady = ['completed', 'qa_ready'].includes(shownSummary?.parseStatus);
  const shownParseReady = ['completed', 'qa_ready', 'succeeded'].includes(shownPaper?.parseStatus);
  const canBoostParse = !viewingOther && ['pending', 'queued', 'failed'].includes(String(shownPaper?.parseStatus || ''));

  const mainTabs = [
    {
      key: 'content',
      label: 'a · 论文主体',
      children: (
        <div>
          <Title level={4} style={{ marginTop: 0 }}>
            {shownPaper.title}
          </Title>

          <Space size={6} wrap style={{ marginBottom: 12 }}>
            <Tag color="blue">{shownPaper.primaryCategory || shownPaper.tag}</Tag>
            <Tag>arXiv:{shownPaper.arxivId || shownPaper.arxiv}</Tag>
            <Tag>{shownPaper.publishedAt || shownPaper.date}</Tag>
            <Tag color={['completed', 'qa_ready'].includes(shownPaper.parseStatus) ? 'success' : 'warning'}>
              解析状态：{getParseStatusLabel(shownPaper.parseStatus)}
            </Tag>
            {canBoostParse ? (
              <Button
                type="primary"
                size="small"
                icon={<ThunderboltOutlined />}
                loading={priorityLoading}
                onClick={handleBoostParsePriority}
              >
                立即解析
              </Button>
            ) : null}
          </Space>

          <Paragraph type="secondary">
            {(shownPaper.authors || []).join?.(', ') || shownPaper.authorsText || shownPaper.authors}
          </Paragraph>

          {shownContent?.pdfUrl ? (
            <>
              <iframe
                title={`${shownPaper.title} PDF`}
                src={shownContent.pdfUrl}
                className="paper-pdf-frame"
              />

              <Space wrap style={{ marginTop: 12 }}>
                <Button
                  type="primary"
                  icon={<ExpandOutlined />}
                  onClick={() => {
                    setMainTab('content');
                    setPdfFullscreen(true);
                  }}
                >
                  全屏阅读 PDF
                </Button>

                <Button
                  icon={<FilePdfOutlined />}
                  href={shownContent.pdfUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  新窗口打开 PDF
                </Button>

                {shownContent.htmlUrl && (
                  <Button
                    icon={<LinkOutlined />}
                    href={shownContent.htmlUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 HTML 版本
                  </Button>
                )}

                {shownPaper.sourceUrl && (
                  <Button
                    icon={<LinkOutlined />}
                    href={shownPaper.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看 arXiv 详情
                  </Button>
                )}

                <Text type="secondary">
                  {shownContent.pageCount ? `共 ${shownContent.pageCount} 页` : '页数待后端解析'}
                </Text>
              </Space>
            </>
          ) : (
            <Empty description="当前论文没有可读取的 PDF" />
          )}
        </div>
      )
    },
    {
      key: 'excerpts',
      label: 'b · 原文段落',
      children: (
        <PaperExcerptsPanel
          abstractText={shownPaper.abstract || shownPaper.summary || ''}
          chunks={shownExcerpts}
          parseReady={shownParseReady || shownSummaryReady}
        />
      ),
    },
    {
      key: 'summary',
      label: 'c · 智能总结',
      children: (
        <div>
          <Space size={6} wrap style={{ marginBottom: 12 }}>
            <Tag
              color={['completed', 'qa_ready'].includes(shownSummary?.parseStatus) ? 'success' : 'warning'}
            >
              解析状态：{getParseStatusLabel(shownSummary?.parseStatus)}
            </Tag>
            {canBoostParse ? (
              <Button
                type="primary"
                size="small"
                icon={<ThunderboltOutlined />}
                loading={priorityLoading}
                onClick={handleBoostParsePriority}
              >
                立即解析
              </Button>
            ) : null}
            {!shownSummaryReady ? (
              <Text type="secondary">
                {canBoostParse
                  ? '可点「立即解析」插队执行已有任务；解析完成后按钮会消失'
                  : '后台自动解析中，完成后刷新即可查看'}
              </Text>
            ) : null}
          </Space>

          {shownSummaryReady ? (
            <>
              <Title level={5}>
                结构化摘要 {shownSummary.uncertainFields?.includes('summary') ? <Tag color="orange">不确定</Tag> : null}
              </Title>
              <Paragraph>{shownSummary.summary}</Paragraph>

              <Title level={5}>
                核心概念 {shownSummary.uncertainFields?.includes('concepts') ? <Tag color="orange">不确定</Tag> : null}
              </Title>
              <Space direction="vertical" style={{ width: '100%' }}>
                {(shownSummary.concepts || []).map((concept) => (
                  <Card size="small" key={concept.conceptId}>
                    <Text strong>{concept.name}</Text>
                    <Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 4 }}>
                      {concept.description}
                    </Paragraph>
                  </Card>
                ))}
              </Space>

              <Title level={5} style={{ marginTop: 20 }}>
                方法步骤 {shownSummary.uncertainFields?.includes('methods') ? <Tag color="orange">不确定</Tag> : null}
              </Title>
              <ol style={{ paddingLeft: 22 }}>
                {(shownSummary.methods || []).map((method) => (
                  <li key={method.order} style={{ marginBottom: 12 }}>
                    <Text strong>{method.title}</Text>
                    <Paragraph style={{ marginBottom: 0 }}>{method.description}</Paragraph>
                  </li>
                ))}
              </ol>

              <Title level={5}>
                实验与结果 {shownSummary.uncertainFields?.includes('experiments') ? <Tag color="orange">不确定</Tag> : null}
              </Title>
              {(shownSummary.experiments || []).length > 0 ? (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {shownSummary.experiments.map((experiment, index) => (
                    <Card size="small" key={`${experiment.title}-${index}`}>
                      <Text strong>{experiment.title}</Text>
                      <Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 4 }}>
                        {experiment.description}
                      </Paragraph>
                    </Card>
                  ))}
                </Space>
              ) : (
                <Text type="secondary">暂无实验结果解析。</Text>
              )}

              <Title level={5}>
                局限性 {shownSummary.uncertainFields?.includes('limitations') ? <Tag color="orange">不确定</Tag> : null}
              </Title>
              {(shownSummary.limitations || []).length > 0 ? (
                <ul style={{ paddingLeft: 22 }}>
                  {shownSummary.limitations.map((limitation) => (
                    <li key={limitation} style={{ marginBottom: 8 }}>
                      {limitation}
                    </li>
                  ))}
                </ul>
              ) : (
                <Text type="secondary">暂无局限性解析结果。</Text>
              )}

              {(shownSummary.validationFlags || []).length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message="内容校验 Agent：不确定内容已标记"
                  description={
                    <div>
                      <div style={{ marginBottom: 8 }}>
                        {(shownSummary.validationLabels || shownSummary.validationFlags).map((label) => (
                          <Tag key={label} color="gold" style={{ marginBottom: 4 }}>{label}</Tag>
                        ))}
                      </div>
                      {(shownSummary.uncertainFields || []).length > 0 && (
                        <Text type="secondary">
                          待复核字段：{shownSummary.uncertainFields.join('、')}
                        </Text>
                      )}
                    </div>
                  }
                  style={{ marginTop: 16 }}
                />
              )}
            </>
          ) : (
            <Alert
              type="info"
              showIcon
              message="智能总结暂不可用"
              description="完成论文解析后，这里才会显示摘要、核心概念、方法、实验结果和局限性。"
            />
          )}
        </div>
      )
    },
    {
      key: 'graph',
      label: 'd · 知识图谱与研究脉络',
      children: (
        <div className="graph-placeholder">
          {shownGraph ? (
            <>
              <Space wrap style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
                <Space wrap>
                  <Tag color={shownGraph.preview ? 'default' : 'success'}>
                    {shownGraph.preview ? '解析前主题预览' : '解析后结构化脉络'}
                  </Tag>
                  <Text type="secondary">节点 {shownGraph.nodes.length} 个 · 关系 {shownGraph.edges.length} 条 · 来源 {shownGraph.source || 'heuristic'}</Text>
                </Space>
                <Button icon={<ReloadOutlined />} loading={graphRefreshing} onClick={handleGraphRefresh}>
                  刷新图谱
                </Button>
              </Space>
              {shownGraph.preview && (
                <Alert
                  type="info"
                  showIcon
                  message="当前为解析前主题脉络预览"
                  description="完成正文解析后，图谱会补充概念、方法、数据集及更完整的关系。"
                  style={{ marginBottom: 12 }}
                />
              )}
              <Paragraph>{shownGraph.narrative || '暂无研究脉络说明。'}</Paragraph>
              <PaperGraphCanvas paperId={shownPaperId} nodes={shownGraph.nodes} edges={shownGraph.edges} />
              <List
                size="small"
                style={{ marginTop: 12 }}
                header={<Text strong>研究脉络</Text>}
                dataSource={shownGraph.lineage}
                locale={{ emptyText: '暂无相关论文' }}
                renderItem={(item) => (
                  <List.Item>
                    <Space direction="vertical" size={0}>
                      <Text>{item.title || item.arxivId || item.arxiv_id}</Text>
                      <Text type="secondary">{item.note}</Text>
                    </Space>
                    <Tag>{item.role}</Tag>
                  </List.Item>
                )}
              />
            </>
          ) : shownGraphError ? (
            <Alert
              type="error"
              showIcon
              message="知识图谱加载失败"
              description={shownGraphError}
              action={<Button size="small" onClick={handleGraphRefresh}>重新加载</Button>}
            />
          ) : <Spin size="small" tip="正在生成知识图谱..." />}
        </div>
      )
    }
  ];

  return (
    <div className={`page-paper-detail${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
      <Card
        size="small"
        className="section-card"
        style={{ marginBottom: 12 }}
        bodyStyle={{ padding: '10px 16px' }}
      >
        <Space wrap style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space wrap>
            <Button icon={<ArrowLeftOutlined />} onClick={handleExitPaper}>
              退出论文
            </Button>
            {shownContent?.pdfUrl ? (
              <Button
                icon={<ExpandOutlined />}
                onClick={() => {
                  setMainTab('content');
                  setPdfFullscreen(true);
                }}
              >
                全屏阅读 PDF
              </Button>
            ) : null}
            <Text type="secondary">可切换学习空间 / 设置等；再点工作空间仍回到本篇。退出后恢复检索首页</Text>
          </Space>
          <Text ellipsis style={{ maxWidth: 360 }} strong>
            {paper.title}
          </Text>
        </Space>
      </Card>

      <div className={`paper-detail-split${sidebarCollapsed ? ' is-collapsed' : ''}`}>
        <div className="paper-detail-main">
          <Card className="section-card paper-main-card">
            {viewingOther ? (
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
                message="正在查看对比论文"
                description="对比阅读侧栏仍锚定原论文。再次点击「返回原论文」可切回。"
                action={(
                  <Button size="small" onClick={() => setComparePreviewActive(false)}>
                    返回原论文
                  </Button>
                )}
              />
            ) : null}
            {viewingOther && previewLoading ? (
              <div style={{ minHeight: 260, display: 'grid', placeItems: 'center' }}>
                <Spin tip="正在加载对比论文..." />
              </div>
            ) : viewingOther && previewError ? (
              <Alert
                type="error"
                showIcon
                message="对比论文加载失败"
                description={previewError}
                action={<Button size="small" onClick={() => setComparePreviewActive(false)}>返回原论文</Button>}
              />
            ) : (
              <Tabs activeKey={mainTab} onChange={setMainTab} items={mainTabs} />
            )}
          </Card>
        </div>

        {sidebarCollapsed ? (
          <aside className="paper-sidebar-rail" aria-label="已收起的论文侧栏">
            <Button
              type="primary"
              className="paper-sidebar-expand-btn"
              icon={<MenuUnfoldOutlined />}
              onClick={() => setSidebarCollapsed(false)}
              aria-label="展开论文详情侧栏"
            >
              展开侧栏
            </Button>
          </aside>
        ) : (
          <div className="paper-detail-sidebar">
            <PaperSidebar
              paperId={paperId}
              paper={paper}
              onCollapse={() => setSidebarCollapsed(true)}
            />
          </div>
        )}
      </div>

      {pdfFullscreen && shownContent?.pdfUrl ? (
        <div className="pdf-fullscreen-overlay" role="dialog" aria-modal="true" aria-label="全屏阅读 PDF">
          <div className="pdf-fullscreen-toolbar">
            <div className="pdf-fullscreen-title">
              <FilePdfOutlined />
              <Text ellipsis style={{ maxWidth: 'min(62vw, 720px)', color: '#f8fafc' }} strong>
                {shownPaper.title}
              </Text>
            </div>
            <Space wrap>
              <Button
                icon={<FilePdfOutlined />}
                href={shownContent.pdfUrl}
                target="_blank"
                rel="noreferrer"
              >
                新窗口打开
              </Button>
              <Button type="primary" onClick={() => setPdfFullscreen(false)}>
                退出全屏（Esc）
              </Button>
            </Space>
          </div>
          <iframe
            title={`${shownPaper.title} 全屏 PDF`}
            src={shownContent.pdfUrl}
            className="pdf-fullscreen-frame"
          />
        </div>
      ) : null}
    </div>
  );
}
