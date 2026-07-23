import { useState, useMemo, useEffect } from 'react';
import { Tag, Input, Button, Space, Typography, List, Segmented, Alert } from 'antd';
import { SearchOutlined, LinkOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { searchPaperWiki as searchMockPaperWiki } from '../../../../utils/wiki';
import { getPaperSummary, searchPaperWiki as searchRemotePaperWiki } from '../../../../services/paperService';
import { isPersistedPaperId } from '../../../../services/learningService';
import FavoriteButton from './FavoriteButton';

const { Text, Paragraph, Title } = Typography;

const WIKI_MODES = [
  { value: 'all', label: '全部' },
  { value: 'title', label: '标题' },
  { value: 'author', label: '作者' },
  { value: 'keyword', label: '关键词' },
  { value: 'direction', label: '研究方向' },
  { value: 'concept', label: '概念标签' }
];

function conceptNames(summary) {
  const items = summary?.concepts || [];
  return items
    .map((item) => (typeof item === 'string' ? item : item?.name))
    .filter(Boolean)
    .slice(0, 8);
}

export default function SidebarInfoPanel({ paper, paperId }) {
  const navigate = useNavigate();
  const [mode, setMode] = useState('all');
  const [query, setQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [submittedMode, setSubmittedMode] = useState('all');
  const [remoteResults, setRemoteResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [wikiTags, setWikiTags] = useState({ concepts: [], direction: '' });

  const persisted = isPersistedPaperId(paperId);
  const localResults = useMemo(
    () => searchMockPaperWiki(submittedQuery || query, submittedMode || mode, paperId),
    [query, mode, submittedQuery, submittedMode, paperId],
  );

  useEffect(() => {
    if (!persisted) {
      setWikiTags({
        concepts: paper.conceptTags || [],
        direction: paper.direction || paper.researchDirection || paper.primaryCategory || paper.tag || '',
      });
      return undefined;
    }
    let cancelled = false;
    getPaperSummary(paperId)
      .then((summary) => {
        if (cancelled) return;
        setWikiTags({
          concepts: conceptNames(summary),
          direction: paper.primaryCategory || paper.tag || paper.direction || '',
        });
      })
      .catch(() => {
        if (!cancelled) {
          setWikiTags({
            concepts: [],
            direction: paper.primaryCategory || paper.tag || '',
          });
        }
      });
    return () => { cancelled = true; };
  }, [persisted, paperId, paper.primaryCategory, paper.tag, paper.direction, paper.researchDirection, paper.conceptTags]);

  useEffect(() => {
    if (!persisted || !submittedQuery) {
      setRemoteResults([]);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    searchRemotePaperWiki(submittedQuery, { mode: submittedMode })
      .then((items) => { if (!cancelled) setRemoteResults(items); })
      .catch(() => { if (!cancelled) setRemoteResults([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [persisted, submittedQuery, submittedMode]);

  const results = persisted ? remoteResults : localResults;
  const submitSearch = (nextQuery = query, nextMode = mode) => {
    const trimmed = String(nextQuery || '').trim();
    setMode(nextMode);
    setQuery(trimmed);
    setSubmittedMode(nextMode);
    setSubmittedQuery(trimmed);
  };

  const quickTags = [
    ...(wikiTags.direction ? [{ text: wikiTags.direction, mode: 'direction' }] : []),
    ...((paper.keywords || []).map((k) => ({ text: k, mode: 'keyword' }))),
    ...(wikiTags.concepts.map((c) => ({ text: c, mode: 'concept' }))),
  ];

  return (
    <div className="sidebar-scroll">
      <div style={{ marginBottom: 16 }}>
        <Space size={4} wrap>
          <Tag color="blue">{paper.tag || paper.primaryCategory}</Tag>
          <Tag>arXiv:{paper.arxiv || paper.arxivId}</Tag>
        </Space>
        <Title level={5} style={{ marginTop: 8 }}>{paper.title}</Title>
        <Text type="secondary" style={{ fontSize: 12 }}>{paper.authorsText || paper.authors}</Text>
        <Paragraph style={{ fontSize: 13 }}>{paper.summary || paper.abstract}</Paragraph>
        <FavoriteButton paperId={paperId} block />
        {(paper.sourceUrl || paper.pdfUrl) && (
          <Button
            block
            icon={<LinkOutlined />}
            style={{ marginTop: 8 }}
            href={paper.sourceUrl || paper.pdfUrl}
            target="_blank"
            rel="noreferrer"
          >
            原文链接
          </Button>
        )}
      </div>

      <div className="wiki-section">
        <Title level={5}>论文知识 Wiki</Title>
        <Text type="secondary" style={{ fontSize: 12 }}>按标题、作者、关键词、研究方向、概念标签检索</Text>
        <Alert
          type="info"
          showIcon
          style={{ margin: '8px 0' }}
          message="主题/概念关联请在主区「知识图谱」查看；关联为语义主题相关，非文献引用网络。"
        />
        <Segmented
          size="small"
          options={WIKI_MODES}
          value={mode}
          onChange={(value) => setMode(value)}
          style={{ margin: '10px 0', flexWrap: 'wrap' }}
          block
        />
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              mode === 'author' ? '输入作者名…'
                : mode === 'direction' ? '输入类别或主题，如 cs.CL…'
                  : mode === 'concept' ? '输入概念标签…'
                    : '输入检索词…'
            }
            onPressEnter={() => submitSearch()}
          />
          <Button icon={<SearchOutlined />} type="primary" loading={loading} onClick={() => submitSearch()}>检索</Button>
        </Space.Compact>
        <Text className="block-label" style={{ marginTop: 12 }}>本篇 Wiki 标签</Text>
        <Space wrap size={4}>
          {quickTags.length ? quickTags.map((t) => (
            <Tag
              key={`${t.mode}-${t.text}`}
              style={{ cursor: 'pointer' }}
              onClick={() => submitSearch(t.text, t.mode)}
            >
              {t.text}
            </Tag>
          )) : (
            <Text type="secondary" style={{ fontSize: 12 }}>解析完成后将显示概念与研究方向标签</Text>
          )}
        </Space>
        <Text className="block-label" style={{ marginTop: 12 }}>
          检索结果 · {results.length} 条
          {submittedMode && submittedQuery ? ` · ${WIKI_MODES.find((item) => item.value === submittedMode)?.label || submittedMode}` : ''}
        </Text>
        <List
          size="small"
          dataSource={results}
          locale={{ emptyText: submittedQuery ? '未找到匹配' : '输入关键词或点击标签检索' }}
          renderItem={(item) => (
            <List.Item
              className="wiki-result-item"
              onClick={() => item.id !== String(paperId) && navigate(`/paper/${item.id}`)}
              style={{ cursor: item.id === String(paperId) ? 'default' : 'pointer' }}
            >
              <List.Item.Meta
                title={<Text strong style={{ fontSize: 12 }}>{item.paper.title}</Text>}
                description={
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {item.paper.authors} · {item.paper.tag}
                  </Text>
                }
              />
            </List.Item>
          )}
        />
      </div>
    </div>
  );
}
