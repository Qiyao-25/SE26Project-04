import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Spin,
  Typography,
  message
} from 'antd';
import { HomeOutlined } from '@ant-design/icons';
import { Navigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { smartSearchPapers } from '../../services/paperService';
import { fetchDailyArxivPicks, fetchProfileRecommendations } from '../../services/recommendationService';
import { ChatBox } from '../../components/common/ChatBox';
import PaperCard from '../../components/paper/PaperCard';

const { Text } = Typography;

const WELCOME_MESSAGE = {
  messageId: 'workspace-welcome',
  role: 'assistant',
  content: '您好，可输入自然语言检索论文。系统会智能改写关键词、匹配数据库论文，并生成检索说明。',
  status: 'success',
  citations: []
};

export default function WorkspacePage() {
  const {
    workspaceSearched,
    setWorkspaceSearched,
    lastSearchQuery,
    setLastSearchQuery,
    userId,
    persona,
    topics,
    lockedPaperId
  } = useApp();

  const skipRestoreRef = useRef(false);
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [results, setResults] = useState([]);
  const [resultTotal, setResultTotal] = useState(0);
  const [searchStatus, setSearchStatus] = useState('idle');
  const [searchError, setSearchError] = useState('');
  const [dailyPapers, setDailyPapers] = useState([]);
  const [profilePapers, setProfilePapers] = useState([]);
  const [recommendStatus, setRecommendStatus] = useState('idle');
  const [recommendError, setRecommendError] = useState('');

  const [dailyPapers, setDailyPapers] = useState([]);
  const [profilePapers, setProfilePapers] = useState([]);
  const [recommendStatus, setRecommendStatus] = useState('idle');
  const [recommendError, setRecommendError] = useState('');

  useEffect(() => {
    if (skipRestoreRef.current) {
      skipRestoreRef.current = false;
      return undefined;
    }
    if (!workspaceSearched || !lastSearchQuery) return undefined;
    let cancelled = false;
    setSearchStatus('loading');
    smartSearchPapers({ query: lastSearchQuery, page: 1, pageSize: 12 })
      .then((data) => {
        if (cancelled) return;
        setResults(data.items);
        setResultTotal(data.total);
        setSearchStatus(data.total > 0 ? 'success' : 'empty');
      })
      .catch((error) => {
        if (cancelled) return;
        setResults([]);
        setResultTotal(0);
        setSearchStatus('failed');
        setSearchError(error.message || '检索失败');
      });
    return () => { cancelled = true; };
  }, [workspaceSearched, lastSearchQuery]);

  useEffect(() => {
    if (workspaceSearched || lockedPaperId) return undefined;
    let cancelled = false;
    setRecommendStatus('loading');
    setRecommendError('');
    (async () => {
      try {
        const daily = await fetchDailyArxivPicks({ limit: 3 });
        if (cancelled) return;
        setDailyPapers(daily);
        const recommended = await fetchProfileRecommendations({
          userId,
          persona,
          topics,
          limit: 3,
          excludeIds: daily.map((paper) => paper.paperId)
        });
        if (cancelled) return;
        setProfilePapers(recommended);
        setRecommendStatus(daily.length || recommended.length ? 'success' : 'empty');
      } catch (error) {
        if (cancelled) return;
        setDailyPapers([]);
        setProfilePapers([]);
        setRecommendStatus('failed');
        setRecommendError(error.message || '推荐加载失败');
      }
    })();
    return () => { cancelled = true; };
  }, [workspaceSearched, persona, topics, lockedPaperId, userId]);

  const handleSearch = async (text) => {
    setMessages((current) => [...current, {
      messageId: `workspace-user-${Date.now()}`,
      role: 'user',
      content: text,
      status: 'success',
      citations: []
    }]);
    skipRestoreRef.current = true;
    setLastSearchQuery(text);
    setWorkspaceSearched(true);
    setSearchStatus('loading');
    setSearchError('');
    try {
      const data = await smartSearchPapers({ query: text, page: 1, pageSize: 12 });
      setResults(data.items);
      setResultTotal(data.total);
      setSearchStatus(data.total > 0 ? 'success' : 'empty');
      const keywordHint = data.keywords?.length ? `（匹配词：${data.keywords.slice(0, 5).join('、')}）` : '';
      setMessages((current) => [...current, {
        messageId: `workspace-assistant-${Date.now()}`,
        role: 'assistant',
        content: data.answer || (data.total > 0 ? `检索完成，共找到 ${data.total} 篇相关论文。${keywordHint}` : `未找到与“${text}”匹配的论文，请尝试缩短关键词或更换研究方向。`),
        status: 'success',
        citations: []
      }]);
      message.success(`检索完成，共 ${data.total} 篇`);
    } catch (error) {
      setResults([]);
      setResultTotal(0);
      setSearchStatus('failed');
      setSearchError(error.message || '检索失败');
      setMessages((current) => [...current, {
        messageId: `workspace-error-${Date.now()}`,
        role: 'assistant',
        content: '检索请求失败，请稍后重试。',
        status: 'failed',
        errorMessage: error.message || '检索失败',
        citations: []
      }]);
    }
  };

  const handleBackHome = () => {
    setWorkspaceSearched(false);
    setLastSearchQuery('');
    setResults([]);
    setResultTotal(0);
    setSearchStatus('idle');
    setSearchError('');
    setMessages([WELCOME_MESSAGE]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    message.success('已返回首页');
  };

  const renderPaperGrid = (papers) => (
    <Row gutter={[16, 16]}>
      {papers.map((paper) => <Col xs={24} sm={12} lg={8} key={paper.paperId}><PaperCard paper={paper} /></Col>)}
    </Row>
  );

  if (lockedPaperId) return <Navigate to={`/paper/${lockedPaperId}`} replace />;

  return (
    <div className="page-workspace">
      <Card title="智能论文检索" className="section-card">
        <ChatBox messages={messages} onSend={handleSearch} placeholder="试试：有哪些关于注意力机制或 Transformer 的论文？" minHeight={140} loading={searchStatus === 'loading'} />
        <Text type="secondary" style={{ fontSize: 12 }}>支持自然语言；系统会改写关键词并匹配数据库论文，再给出检索说明。</Text>
      </Card>
      {!workspaceSearched ? (
        <>
          {recommendStatus === 'loading' && <Card className="section-card"><div style={{ textAlign: 'center', padding: 40 }}><Spin tip="正在从数据库加载推荐论文..." /></div></Card>}
          {recommendStatus === 'failed' && <Alert type="error" showIcon message="推荐加载失败" description={recommendError} style={{ marginBottom: 16 }} />}
          {recommendStatus !== 'loading' && <>
            <Card title="每日 ArXiv 精选" className="section-card">{dailyPapers.length ? renderPaperGrid(dailyPapers) : <Empty description="暂无可用论文，请先导入种子数据或入库论文" />}</Card>
            <Card title="基于画像推荐的论文" className="section-card" extra={<Text type="secondary" style={{ fontSize: 12 }}>当前为库内推荐 · 画像 AI 接口已预留</Text>}>{profilePapers.length ? renderPaperGrid(profilePapers) : <Empty description="暂无推荐论文" />}</Card>
          </>}
        </>
      ) : (
        <Card title={`检索结果${lastSearchQuery ? ` · 「${lastSearchQuery}」` : ''} · 共 ${resultTotal} 篇`} extra={<Button icon={<HomeOutlined />} onClick={handleBackHome}>返回首页</Button>} className="section-card">
          {searchStatus === 'loading' && <div style={{ textAlign: 'center', padding: 40 }}><Spin tip="正在智能检索论文..." /></div>}
          {searchStatus === 'failed' && <Alert type="error" showIcon message="检索失败" description={searchError} />}
          {searchStatus === 'empty' && <Empty description="未找到匹配论文，请修改检索词后重试" />}
          {searchStatus === 'success' && renderPaperGrid(results)}
        </Card>
      )}
    </div>
  );
}
