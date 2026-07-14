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
import { useApp } from '../../context/AppContext';
import { searchPapers } from '../../services/paperService';
import { ChatBox } from '../../components/common/ChatBox';
import PaperCard from '../../components/paper/PaperCard';

const { Text } = Typography;

const DAILY = ['attention', 'gpt3', 'vlm'];
const RECOMMENDED = ['bert', 'lora', 'rag'];

const WELCOME_MESSAGE = {
  messageId: 'workspace-welcome',
  role: 'assistant',
  content: '您好，可输入自然语言检索论文。当前 P0 原型支持标题、作者、摘要、关键词和研究方向匹配。',
  status: 'success',
  citations: []
};

export default function WorkspacePage() {
  const {
    workspaceSearched,
    setWorkspaceSearched,
    lastSearchQuery,
    setLastSearchQuery
  } = useApp();

  const skipRestoreRef = useRef(false);
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [results, setResults] = useState([]);
  const [resultTotal, setResultTotal] = useState(0);
  const [searchStatus, setSearchStatus] = useState('idle');
  const [searchError, setSearchError] = useState('');

  useEffect(() => {
    if (skipRestoreRef.current) {
      skipRestoreRef.current = false;
      return undefined;
    }

    if (!workspaceSearched || !lastSearchQuery) return undefined;

    let cancelled = false;
    setSearchStatus('loading');

    searchPapers({
      query: lastSearchQuery,
      searchType: 'keyword',
      categories: [],
      sortBy: 'relevance',
      page: 1,
      pageSize: 12
    })
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

    return () => {
      cancelled = true;
    };
  }, [workspaceSearched, lastSearchQuery]);

  const handleSearch = async (text) => {
    const userMessage = {
      messageId: `workspace-user-${Date.now()}`,
      role: 'user',
      content: text,
      status: 'success',
      citations: []
    };

    setMessages((current) => [...current, userMessage]);
    skipRestoreRef.current = true;
    setLastSearchQuery(text);
    setWorkspaceSearched(true);
    setSearchStatus('loading');
    setSearchError('');

    try {
      const data = await searchPapers({
        query: text,
        searchType: 'keyword',
        categories: [],
        sortBy: 'relevance',
        page: 1,
        pageSize: 12
      });

      setResults(data.items);
      setResultTotal(data.total);
      setSearchStatus(data.total > 0 ? 'success' : 'empty');

      setMessages((current) => [
        ...current,
        {
          messageId: `workspace-assistant-${Date.now()}`,
          role: 'assistant',
          content:
            data.total > 0
              ? `检索完成，共找到 ${data.total} 篇与“${text}”相关的论文。`
              : `未找到与“${text}”匹配的论文，请尝试缩短关键词或更换研究方向。`,
          status: 'success',
          citations: []
        }
      ]);

      message.success(`检索完成，共 ${data.total} 篇`);
    } catch (error) {
      setResults([]);
      setResultTotal(0);
      setSearchStatus('failed');
      setSearchError(error.message || '检索失败');

      setMessages((current) => [
        ...current,
        {
          messageId: `workspace-error-${Date.now()}`,
          role: 'assistant',
          content: '检索请求失败，请稍后重试。',
          status: 'failed',
          errorMessage: error.message || '检索失败',
          citations: []
        }
      ]);
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

  return (
    <div className="page-workspace">
      <Card title="智能论文检索" className="section-card">
        <ChatBox
          messages={messages}
          onSend={handleSearch}
          placeholder="输入论文标题、作者、关键词或研究方向..."
          minHeight={140}
          loading={searchStatus === 'loading'}
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          发送检索请求后，推荐区域将切换为检索结果；无匹配内容时显示明确空状态。
        </Text>
      </Card>

      {!workspaceSearched ? (
        <>
          <Card title="每日 ArXiv 精选" className="section-card">
            <Row gutter={[16, 16]}>
              {DAILY.map((id) => (
                <Col xs={24} sm={12} lg={8} key={id}>
                  <PaperCard paperId={id} />
                </Col>
              ))}
            </Row>
          </Card>

          <Card title="基于画像推荐的论文" className="section-card">
            <Row gutter={[16, 16]}>
              {RECOMMENDED.map((id) => (
                <Col xs={24} sm={12} lg={8} key={id}>
                  <PaperCard paperId={id} />
                </Col>
              ))}
            </Row>
          </Card>
        </>
      ) : (
        <Card
          title={`检索结果${lastSearchQuery ? ` · 「${lastSearchQuery}」` : ''} · 共 ${resultTotal} 篇`}
          extra={
            <Button icon={<HomeOutlined />} onClick={handleBackHome}>
              返回首页
            </Button>
          }
          className="section-card"
        >
          {searchStatus === 'loading' && (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin tip="正在检索论文..." />
            </div>
          )}

          {searchStatus === 'failed' && (
            <Alert
              type="error"
              showIcon
              message="检索失败"
              description={searchError}
            />
          )}

          {searchStatus === 'empty' && (
            <Empty description="未找到匹配论文，请修改检索词后重试" />
          )}

          {searchStatus === 'success' && (
            <Row gutter={[16, 16]}>
              {results.map((paper) => (
                <Col xs={24} sm={12} lg={8} key={paper.paperId}>
                  <PaperCard paper={paper} />
                </Col>
              ))}
            </Row>
          )}
        </Card>
      )}
    </div>
  );
}
