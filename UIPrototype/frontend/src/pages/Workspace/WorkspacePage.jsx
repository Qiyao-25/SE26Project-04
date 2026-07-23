import { HomeOutlined, ReloadOutlined } from '@ant-design/icons';
import { Navigate } from 'react-router-dom';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Pagination,
  Row,
  Space,
  Spin,
  Typography,
  message
} from 'antd';
import { useApp } from '../../context/AppContext';
import { smartSearchPapers } from '../../services/paperService';
import { fetchDailyArxivPicks, fetchProfileRecommendations, fetchSubscriptionRecommendations } from '../../services/recommendationService';
import { ChatBox } from '../../components/common/ChatBox';
import PaperCard from '../../components/paper/PaperCard';
import { getWorkspacePageSize } from '../../utils/uiPrefs';

const { Text } = Typography;

const WORKSPACE_SEARCH_CACHE_KEY = 'papermate-workspace-search-v1';

const WELCOME_MESSAGE = {
  messageId: 'workspace-welcome',
  role: 'assistant',
  content: '您好，可输入自然语言检索论文。系统会智能改写关键词、匹配数据库论文，并生成检索说明。',
  status: 'success',
  citations: []
};

function paperIds(papers = []) {
  return papers.map((paper) => paper.paperId).filter((id) => id !== undefined && id !== null);
}

function readSearchCache() {
  try {
    const raw = sessionStorage.getItem(WORKSPACE_SEARCH_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function writeSearchCache(payload) {
  try {
    sessionStorage.setItem(WORKSPACE_SEARCH_CACHE_KEY, JSON.stringify(payload));
  } catch {
    // ignore quota / private mode
  }
}

function clearSearchCache() {
  try {
    sessionStorage.removeItem(WORKSPACE_SEARCH_CACHE_KEY);
  } catch {
    // ignore
  }
}

/** Last page should show only remaining items (e.g. 8 of 12), never pad to pageSize. */
function slicePageItems(items, page, pageSize, total) {
  const list = Array.isArray(items) ? items : [];
  if (!total || total <= 0) return list.slice(0, pageSize);
  const start = (Math.max(1, page) - 1) * pageSize;
  const remaining = Math.max(0, total - start);
  return list.slice(0, Math.min(pageSize, remaining));
}

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
  const [searchPage, setSearchPage] = useState(1);
  const [searchPageSize] = useState(() => getWorkspacePageSize(12));
  const [searchStatus, setSearchStatus] = useState('idle');
  const [searchError, setSearchError] = useState('');
  const [pageLoading, setPageLoading] = useState(false);
  const [dailyPapers, setDailyPapers] = useState([]);
  const [profilePapers, setProfilePapers] = useState([]);
  const [subscriptionPapers, setSubscriptionPapers] = useState([]);
  const [bootStatus, setBootStatus] = useState('idle');
  const [bootError, setBootError] = useState('');
  const [dailyLoading, setDailyLoading] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const dailyRef = useRef([]);
  const profileRef = useRef([]);
  const subscriptionRef = useRef([]);

  useEffect(() => { dailyRef.current = dailyPapers; }, [dailyPapers]);
  useEffect(() => { profileRef.current = profilePapers; }, [profilePapers]);
  useEffect(() => { subscriptionRef.current = subscriptionPapers; }, [subscriptionPapers]);

  const applySearchResult = useCallback((data, { query, page, answerText, messagesSnapshot, rewrittenQuery, keywords, category, categoryHints } = {}) => {
    const nextPage = page || data.page || 1;
    const nextTotal = data.total || 0;
    const nextItems = slicePageItems(data.items || [], nextPage, data.pageSize || searchPageSize, nextTotal);
    const nextAnswer = answerText
      || data.answer
      || (nextTotal > 0
        ? `检索完成，共找到 ${nextTotal} 篇相关论文。`
        : `未找到与“${query}”匹配的论文，请尝试缩短关键词或更换研究方向。`);
    const nextRewritten = rewrittenQuery || data.rewrittenQuery || query;
    const nextKeywords = keywords || data.keywords || [];
    const nextCategory = category !== undefined ? category : (data.category || null);
    const nextCategoryHints = categoryHints || data.categoryHints || [];
    setResults(nextItems);
    setResultTotal(nextTotal);
    setSearchPage(nextPage);
    setSearchStatus(nextTotal > 0 ? 'success' : 'empty');
    if (messagesSnapshot) setMessages(messagesSnapshot);
    const previous = readSearchCache();
    const sameQuery = previous?.query === query;
    const pageItems = sameQuery ? { ...(previous?.pageItems || {}) } : {};
    pageItems[String(nextPage)] = nextItems;
    writeSearchCache({
      query,
      page: nextPage,
      pageSize: data.pageSize || searchPageSize,
      total: nextTotal,
      items: nextItems,
      pageItems,
      rewrittenQuery: nextRewritten,
      keywords: nextKeywords,
      category: nextCategory,
      categoryHints: nextCategoryHints,
      answer: nextAnswer,
      messages: messagesSnapshot || (sameQuery ? previous?.messages : undefined)
    });
    return nextAnswer;
  }, [searchPageSize]);

  useEffect(() => {
    if (skipRestoreRef.current) {
      skipRestoreRef.current = false;
      return undefined;
    }
    if (!workspaceSearched || !lastSearchQuery) return undefined;

    const cache = readSearchCache();
    if (
      cache
      && cache.query === lastSearchQuery
      && Array.isArray(cache.items)
    ) {
      const restoredPage = cache.page || 1;
      const restoredTotal = cache.total || cache.items.length;
      const restoredItems = slicePageItems(
        cache.items,
        restoredPage,
        cache.pageSize || searchPageSize,
        restoredTotal,
      );
      setResults(restoredItems);
      setResultTotal(restoredTotal);
      setSearchPage(restoredPage);
      setSearchStatus(restoredTotal > 0 ? 'success' : 'empty');
      if (Array.isArray(cache.messages) && cache.messages.length) {
        setMessages(cache.messages);
      }
      return undefined;
    }

    let cancelled = false;
    setSearchStatus('loading');
    smartSearchPapers({ query: lastSearchQuery, page: cache?.page || 1, pageSize: searchPageSize })
      .then((data) => {
        if (cancelled) return;
        applySearchResult(data, { query: lastSearchQuery, page: data.page || cache?.page || 1 });
      })
      .catch((error) => {
        if (cancelled) return;
        setResults([]);
        setResultTotal(0);
        setSearchStatus('failed');
        setSearchError(error.message || '检索失败');
      });
    return () => { cancelled = true; };
  }, [workspaceSearched, lastSearchQuery, applySearchResult, searchPageSize]);

  const refreshDaily = useCallback(async ({ excludeCurrent = true } = {}) => {
    setDailyLoading(true);
    try {
      const excludeIds = [
        ...paperIds(profileRef.current),
        ...paperIds(subscriptionRef.current),
        ...(excludeCurrent ? paperIds(dailyRef.current) : [])
      ];
      const daily = await fetchDailyArxivPicks({ limit: 3, excludeIds });
      setDailyPapers(daily);
      return daily;
    } finally {
      setDailyLoading(false);
    }
  }, []);

  const refreshProfile = useCallback(async ({ excludeCurrent = true } = {}) => {
    setProfileLoading(true);
    try {
      const excludeIds = [
        ...paperIds(dailyRef.current),
        ...paperIds(subscriptionRef.current),
        ...(excludeCurrent ? paperIds(profileRef.current) : [])
      ];
      const recommended = await fetchProfileRecommendations({
        userId,
        persona,
        topics,
        limit: 3,
        excludeIds
      });
      setProfilePapers(recommended);
      return recommended;
    } finally {
      setProfileLoading(false);
    }
  }, [userId, persona, topics]);

  const refreshSubscriptions = useCallback(async ({ excludeCurrent = true } = {}) => {
    setSubscriptionLoading(true);
    try {
      const excludeIds = [
        ...paperIds(dailyRef.current),
        ...paperIds(profileRef.current),
        ...(excludeCurrent ? paperIds(subscriptionRef.current) : [])
      ];
      const subscribed = await fetchSubscriptionRecommendations({
        userId,
        limit: 6,
        excludeIds
      });
      setSubscriptionPapers(subscribed);
      return subscribed;
    } finally {
      setSubscriptionLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (workspaceSearched || lockedPaperId) return undefined;
    let cancelled = false;
    setBootStatus('loading');
    setBootError('');
    (async () => {
      try {
        await refreshDaily({ excludeCurrent: false });
        if (cancelled) return;
        await refreshProfile({ excludeCurrent: false });
        if (cancelled) return;
        await refreshSubscriptions({ excludeCurrent: false });
        if (cancelled) return;
        setBootStatus('success');
      } catch (error) {
        if (cancelled) return;
        setBootStatus('failed');
        setBootError(error.message || '推荐加载失败');
      }
    })();
    return () => { cancelled = true; };
  }, [workspaceSearched, lockedPaperId, refreshDaily, refreshProfile, refreshSubscriptions]);

  const runSearch = async ({ query, page = 1, appendUser = false }) => {
    let nextMessages = messages;
    if (appendUser) {
      nextMessages = [...messages, {
        messageId: `workspace-user-${Date.now()}`,
        role: 'user',
        content: query,
        status: 'success',
        citations: []
      }];
      setMessages(nextMessages);
    }
    skipRestoreRef.current = true;
    setLastSearchQuery(query);
    setWorkspaceSearched(true);
    setSearchStatus('loading');
    setSearchError('');
    setSearchPage(page);
    try {
      const data = await smartSearchPapers({ query, page, pageSize: searchPageSize });
      const keywordHint = data.keywords?.length ? `（匹配词：${data.keywords.slice(0, 5).join('、')}）` : '';
      const planHint = data.rewrittenQuery && data.rewrittenQuery !== query
        ? `\n检索改写：${data.rewrittenQuery}`
        : '';
      const answerText = data.answer || (data.total > 0
        ? `检索完成，共找到 ${data.total} 篇相关论文。${keywordHint}${planHint}`
        : `未找到与“${query}”匹配的论文，请尝试缩短关键词或更换研究方向。`);
      const citations = (data.citations || data.items?.slice(0, 5) || []).map((item, index) => ({
        paperId: String(item.paperId || item.paper_id || ''),
        title: item.title || `相关论文 ${index + 1}`,
      })).filter((item) => item.paperId);
      const withAssistant = appendUser
        ? [...nextMessages, {
          messageId: `workspace-assistant-${Date.now()}`,
          role: 'assistant',
          content: answerText,
          status: 'success',
          citations
        }]
        : nextMessages;
      applySearchResult(data, {
        query,
        page,
        answerText,
        messagesSnapshot: withAssistant
      });
      if (appendUser) {
        setMessages(withAssistant);
        message.success(`检索完成，共 ${data.total} 篇`);
      }
    } catch (error) {
      setResults([]);
      setResultTotal(0);
      setSearchStatus('failed');
      setSearchError(error.message || '检索失败');
      if (appendUser) {
        setMessages((current) => [...current, {
          messageId: `workspace-error-${Date.now()}`,
          role: 'assistant',
          content: '检索请求失败，请稍后重试。',
          status: 'failed',
          errorMessage: error.message || '检索失败',
          citations: []
        }]);
      }
    }
  };

  const handleSearch = async (text) => {
    await runSearch({ query: text, page: 1, appendUser: true });
  };

  const handlePageChange = async (page) => {
    if (!lastSearchQuery || page === searchPage || pageLoading) return;
    const cache = readSearchCache();
    const stableTotal = cache?.total || resultTotal || 0;
    const cachedPage = cache?.pageItems?.[String(page)];
    if (Array.isArray(cachedPage) && cachedPage.length) {
      const capped = slicePageItems(cachedPage, page, searchPageSize, stableTotal);
      setResults(capped);
      setSearchPage(page);
      writeSearchCache({
        ...cache,
        page,
        items: capped,
        pageItems: { ...(cache.pageItems || {}), [String(page)]: capped },
      });
      return;
    }

    setPageLoading(true);
    try {
      const data = await smartSearchPapers({
        query: lastSearchQuery,
        page,
        pageSize: searchPageSize,
        rewrittenQuery: cache?.rewrittenQuery,
        keywords: cache?.keywords,
        category: cache?.category || undefined,
        includeAnswer: false,
      });
      const previous = readSearchCache() || {};
      const pinnedTotal = previous.total || data.total || 0;
      const nextItems = slicePageItems(data.items || [], page, searchPageSize, pinnedTotal);
      const pageItems = { ...(previous.pageItems || {}) };
      pageItems[String(page)] = nextItems;
      setResults(nextItems);
      setResultTotal(pinnedTotal);
      setSearchPage(page);
      if (pinnedTotal > 0) {
        setSearchStatus('success');
      }
      writeSearchCache({
        ...previous,
        query: lastSearchQuery,
        page,
        pageSize: searchPageSize,
        total: pinnedTotal,
        items: nextItems,
        pageItems,
        rewrittenQuery: previous.rewrittenQuery || data.rewrittenQuery,
        keywords: previous.keywords?.length ? previous.keywords : data.keywords,
        category: previous.category ?? data.category,
        categoryHints: previous.categoryHints?.length ? previous.categoryHints : data.categoryHints,
      });
    } catch (error) {
      message.error(error.message || '翻页失败');
    } finally {
      setPageLoading(false);
    }
  };

  const handleBackHome = () => {
    setWorkspaceSearched(false);
    setLastSearchQuery('');
    setResults([]);
    setResultTotal(0);
    setSearchPage(1);
    setSearchStatus('idle');
    setSearchError('');
    setMessages([WELCOME_MESSAGE]);
    clearSearchCache();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    message.success('已返回首页');
  };

  const renderPaperGrid = (papers) => (
    <Row gutter={[16, 16]}>
      {papers.map((paper) => <Col xs={24} sm={12} lg={8} key={paper.paperId}><PaperCard paper={paper} /></Col>)}
    </Row>
  );

  const sectionRefresh = (label, loading, onClick) => (
    <Button
      size="small"
      icon={<ReloadOutlined />}
      loading={loading}
      onClick={async () => {
        try {
          await onClick();
          message.success(`已刷新${label}`);
        } catch (error) {
          message.error(error.message || `${label}刷新失败`);
        }
      }}
    >
      刷新
    </Button>
  );

  if (lockedPaperId) return <Navigate to={`/paper/${lockedPaperId}`} replace />;

  return (
    <div className="page-workspace">
      <Card title="智能论文检索" className="section-card smart-search-card">
        <ChatBox messages={messages} onSend={handleSearch} placeholder="试试：有哪些关于注意力机制或 Transformer 的论文？" minHeight={140} loading={searchStatus === 'loading'} />
        <Text type="secondary" style={{ fontSize: 12 }}>支持自然语言；系统会改写关键词并匹配数据库论文，再给出检索说明。</Text>
      </Card>
      {!workspaceSearched ? (
        <>
          {bootStatus === 'loading' && !dailyPapers.length && !profilePapers.length && !subscriptionPapers.length && (
            <Card className="section-card"><div style={{ textAlign: 'center', padding: 40 }}><Spin tip="正在从数据库加载推荐论文..." /></div></Card>
          )}
          {bootStatus === 'failed' && (
            <Alert
              type="error"
              showIcon
              message="推荐加载失败"
              description={bootError}
              style={{ marginBottom: 16 }}
              action={(
                <Button
                  size="small"
                  onClick={async () => {
                    setBootStatus('loading');
                    try {
                      await refreshDaily({ excludeCurrent: false });
                      await refreshProfile({ excludeCurrent: false });
                      await refreshSubscriptions({ excludeCurrent: false });
                      setBootStatus('success');
                    } catch (error) {
                      setBootStatus('failed');
                      setBootError(error.message || '推荐加载失败');
                    }
                  }}
                >
                  重试
                </Button>
              )}
            />
          )}
          {(bootStatus !== 'loading' || dailyPapers.length || profilePapers.length || subscriptionPapers.length) && (
            <>
              <Card title="每日 ArXiv 精选" className="section-card" extra={sectionRefresh('每日精选', dailyLoading, () => refreshDaily({ excludeCurrent: true }))}>
                {dailyLoading && !dailyPapers.length ? <Spin /> : (dailyPapers.length ? renderPaperGrid(dailyPapers) : <Empty description="暂无可用论文，请先导入种子数据或入库论文" />)}
              </Card>
              <Card
                title="基于画像推荐的论文"
                className="section-card"
                extra={<Space size={8}><Text type="secondary" style={{ fontSize: 12 }}>兴趣主题 + 阅读历史</Text>{sectionRefresh('画像推荐', profileLoading, () => refreshProfile({ excludeCurrent: true }))}</Space>}
              >
                {profileLoading && !profilePapers.length ? <Spin /> : (profilePapers.length ? renderPaperGrid(profilePapers) : <Empty description="暂无推荐论文，请先在学习页设置兴趣主题" />)}
              </Card>
              <Card
                title="订阅更新"
                className="section-card"
                extra={<Space size={8}><Text type="secondary" style={{ fontSize: 12 }}>来自设置页订阅 · 可立即同步 arXiv</Text>{sectionRefresh('订阅更新', subscriptionLoading, () => refreshSubscriptions({ excludeCurrent: true }))}</Space>}
              >
                {subscriptionLoading && !subscriptionPapers.length ? <Spin /> : (subscriptionPapers.length ? renderPaperGrid(subscriptionPapers) : <Empty description="暂无订阅更新，请到设置页添加订阅并点击「立即同步」" />)}
              </Card>
            </>
          )}
        </>
      ) : (
        <Card
          title={`检索结果${lastSearchQuery ? ` · 「${lastSearchQuery}」` : ''} · 共 ${resultTotal} 篇，当前第 ${searchPage} 页`}
          extra={<Button icon={<HomeOutlined />} onClick={handleBackHome}>返回首页</Button>}
          className="section-card"
        >
          {searchStatus === 'loading' && <div style={{ textAlign: 'center', padding: 40 }}><Spin tip="正在智能检索论文..." /></div>}
          {searchStatus === 'failed' && <Alert type="error" showIcon message="检索失败" description={searchError} />}
          {searchStatus === 'empty' && <Empty description="未找到匹配论文，请修改检索词后重试" />}
          {searchStatus === 'success' && (
            <>
              <Spin spinning={pageLoading} tip="加载本页…">
                {renderPaperGrid(results)}
              </Spin>
              <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                <Text type="secondary">共 {resultTotal} 篇，当前第 {searchPage} 页</Text>
                <Pagination
                  current={searchPage}
                  pageSize={searchPageSize}
                  total={resultTotal}
                  onChange={handlePageChange}
                  showSizeChanger={false}
                  disabled={pageLoading}
                />
              </div>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
