import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  message
} from 'antd';
import { FilePdfOutlined, LinkOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import {
  getPaperContent,
  getPaperDetail,
  getPaperSummary,
  createParseTask,
  getParseTask
} from '../../services/paperService';
import { createAction, isPersistedPaperId } from '../../services/learningService';
import PaperSidebar from '../../components/paper/detail/PaperSidebar';

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
  const { userId, setCompareForPaper } = useApp();

  const [paper, setPaper] = useState(null);
  const [content, setContent] = useState(null);
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [reloadToken, setReloadToken] = useState(0);
  const [parseTask, setParseTask] = useState(null);
  const [parseLoading, setParseLoading] = useState(false);
  const historyRecordedFor = useRef(null);

  useEffect(() => {
    if (paperId) setCompareForPaper(paperId);
  }, [paperId, setCompareForPaper]);

  useEffect(() => {
    let cancelled = false;

    async function loadPaper() {
      setLoading(true);
      setLoadError('');
      setPaper(null);
      setContent(null);
      setSummaryData(null);

      try {
        const [detail, paperContent, paperSummary] = await Promise.all([
          getPaperDetail(paperId),
          getPaperContent(paperId),
          getPaperSummary(paperId)
        ]);

        if (cancelled) return;

        setPaper(detail);
        setContent(paperContent);
        setSummaryData(paperSummary);
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
    const taskId = parseTask?.task_id || parseTask?.taskId;
    const status = parseTask?.status;
    if (!taskId || !['queued', 'running'].includes(status)) return undefined;

    let cancelled = false;
    let timer;
    let timeout;
    const poll = async () => {
      try {
        const next = await getParseTask(taskId);
        if (cancelled) return;
        setParseTask(next);
        if (['succeeded', 'failed', 'timed_out'].includes(next.status)) {
          window.clearTimeout(timeout);
          window.clearInterval(timer);
          setParseLoading(false);
          if (next.status === 'succeeded') {
            message.success('论文解析完成，正在刷新结构化结果');
            setReloadToken((value) => value + 1);
          } else {
            message.error(next.error_code || '论文解析失败');
          }
        }
      } catch (error) {
        if (!cancelled) {
          setParseLoading(false);
          message.error(error.message || '解析任务查询失败');
        }
      }
    };
    timer = window.setInterval(poll, 1200);
    timeout = window.setTimeout(() => {
      window.clearInterval(timer);
      setParseLoading(false);
      message.warning('解析任务仍在排队，请确认后台 Worker 已启动');
    }, 120000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.clearTimeout(timeout);
    };
  }, [parseTask]);

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

  const handleParse = async () => {
    if (parseLoading) return;
    if (!isPersistedPaperId(paperId)) {
      message.info('当前为演示论文，切换到检索结果中的数据库论文后可启动解析');
      return;
    }
    setParseLoading(true);
    setLoadError('');
    try {
      const task = await createParseTask(paperId, { force: paper.parseStatus === 'completed' });
      setParseTask(task);
      if (task.status === 'succeeded') {
        setParseLoading(false);
        setReloadToken((value) => value + 1);
        message.success('论文解析已完成');
      } else {
        message.info(`解析任务已${task.status === 'running' ? '开始' : '排队'}`);
      }
    } catch (error) {
      setParseLoading(false);
      message.error(error.message || '解析任务创建失败');
    }
  };

  const structuredSummaryReady = ['completed', 'qa_ready'].includes(summaryData?.parseStatus);

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
      <Alert
        type="error"
        showIcon
        message="论文加载失败"
        description={loadError}
      />
    );
  }

  if (!paper) {
    return (
      <Card className="section-card">
        <Empty description={`论文不存在：${paperId}`} />
      </Card>
    );
  }

  const mainTabs = [
    {
      key: 'content',
      label: 'a · 论文主体',
      children: (
        <div>
          <Title level={4} style={{ marginTop: 0 }}>
            {paper.title}
          </Title>

          <Space size={6} wrap style={{ marginBottom: 12 }}>
            <Tag color="blue">{paper.primaryCategory || paper.tag}</Tag>
            <Tag>arXiv:{paper.arxivId || paper.arxiv}</Tag>
            <Tag>{paper.publishedAt || paper.date}</Tag>
            <Tag color={['completed', 'qa_ready'].includes(paper.parseStatus) ? 'success' : 'warning'}>
              解析状态：{getParseStatusLabel(paper.parseStatus)}
            </Tag>
            <Button size="small" loading={parseLoading} onClick={handleParse}>
              {['completed', 'qa_ready'].includes(paper.parseStatus) ? '重新解析' : '开始解析'}
            </Button>
          </Space>

          <Paragraph type="secondary">
            {(paper.authors || []).join?.(', ') || paper.authorsText || paper.authors}
          </Paragraph>

          {content?.pdfUrl ? (
            <>
              <iframe
                title={`${paper.title} PDF`}
                src={content.pdfUrl}
                style={{
                  width: '100%',
                  height: '72vh',
                  minHeight: 560,
                  border: '1px solid #e5e7eb',
                  borderRadius: 8,
                  background: '#ffffff'
                }}
              />

              <Space wrap style={{ marginTop: 12 }}>
                <Button
                  type="primary"
                  icon={<FilePdfOutlined />}
                  href={content.pdfUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  新窗口打开 PDF
                </Button>

                {content.htmlUrl && (
                  <Button
                    icon={<LinkOutlined />}
                    href={content.htmlUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 HTML 版本
                  </Button>
                )}

                {paper.sourceUrl && (
                  <Button
                    icon={<LinkOutlined />}
                    href={paper.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看 arXiv 详情
                  </Button>
                )}

                <Text type="secondary">
                  {content.pageCount ? `共 ${content.pageCount} 页` : '页数待后端解析'}
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
      key: 'summary',
      label: 'b · 智能总结',
      children: (
        <div>
          <Space size={6} wrap style={{ marginBottom: 12 }}>
            <Tag
              color={['completed', 'qa_ready'].includes(summaryData?.parseStatus) ? 'success' : 'warning'}
            >
              解析状态：{getParseStatusLabel(summaryData?.parseStatus)}
            </Tag>
            {parseTask && <Text type="secondary">解析任务：{parseTask.task_id || parseTask.taskId} · {getParseStatusLabel(parseTask.status)}</Text>}
          </Space>

          {structuredSummaryReady ? (
            <>
              <Title level={5}>结构化摘要</Title>
              <Paragraph>{summaryData.summary}</Paragraph>

              <Title level={5}>核心概念</Title>
              <Space direction="vertical" style={{ width: '100%' }}>
                {(summaryData.concepts || []).map((concept) => (
                  <Card size="small" key={concept.conceptId}>
                    <Text strong>{concept.name}</Text>
                    <Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 4 }}>
                      {concept.description}
                    </Paragraph>
                  </Card>
                ))}
              </Space>

              <Title level={5} style={{ marginTop: 20 }}>
                方法步骤
              </Title>
              <ol style={{ paddingLeft: 22 }}>
                {(summaryData.methods || []).map((method) => (
                  <li key={method.order} style={{ marginBottom: 12 }}>
                    <Text strong>{method.title}</Text>
                    <Paragraph style={{ marginBottom: 0 }}>{method.description}</Paragraph>
                  </li>
                ))}
              </ol>

              <Title level={5}>实验与结果</Title>
              {(summaryData.experiments || []).length > 0 ? (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {summaryData.experiments.map((experiment, index) => (
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

              <Title level={5}>局限性</Title>
              {(summaryData.limitations || []).length > 0 ? (
                <ul style={{ paddingLeft: 22 }}>
                  {summaryData.limitations.map((limitation) => (
                    <li key={limitation} style={{ marginBottom: 8 }}>
                      {limitation}
                    </li>
                  ))}
                </ul>
              ) : (
                <Text type="secondary">暂无局限性解析结果。</Text>
              )}

              {(summaryData.validationFlags || []).length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message="解析校验提示"
                  description={summaryData.validationFlags.join('；')}
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
      label: 'c · 知识图谱&脉络',
      children: (
        <div className="graph-placeholder">
          <Tag>{paper.title.split(':')[0]}</Tag>
          {(paper.conceptTags || []).map((concept) => (
            <Tag key={concept} color="processing" style={{ margin: 8 }}>
              {concept}
            </Tag>
          ))}
          <Paragraph type="secondary" style={{ marginTop: 16 }}>
            知识图谱属于 P1。本轮保留论文节点和核心概念节点，后续接入关系边接口。
          </Paragraph>
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
