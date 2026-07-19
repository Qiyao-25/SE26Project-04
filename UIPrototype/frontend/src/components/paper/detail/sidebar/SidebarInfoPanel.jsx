import { useState, useMemo, useEffect } from 'react';
import { Tag, Input, Button, Space, Typography, List, Segmented } from 'antd';
import { SearchOutlined, LinkOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { searchPaperWiki as searchMockPaperWiki } from '../../../../utils/wiki';
import { searchPaperWiki as searchRemotePaperWiki } from '../../../../services/paperService';
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

export default function SidebarInfoPanel({ paper, paperId }) {
  const navigate = useNavigate();
  const [mode, setMode] = useState('all');
  const [query, setQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [remoteResults, setRemoteResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const persisted = isPersistedPaperId(paperId);
  const localResults = useMemo(() => searchMockPaperWiki(query, mode, paperId), [query, mode, paperId]);

  useEffect(() => {
    if (!persisted || !submittedQuery) {
      setRemoteResults([]);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    searchRemotePaperWiki(submittedQuery)
      .then((items) => { if (!cancelled) setRemoteResults(items); })
      .catch(() => { if (!cancelled) setRemoteResults([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [persisted, submittedQuery]);

  const results = persisted ? remoteResults : localResults;
  const submitSearch = () => setSubmittedQuery(query.trim());

  const quickTags = [
    ...(paper.direction ? [{ text: paper.direction, mode: 'direction' }] : []),
    ...(paper.keywords || []).map((k) => ({ text: k, mode: 'keyword' })),
    ...(paper.conceptTags || []).map((c) => ({ text: c, mode: 'concept' }))
  ];

  return (
    <div className="sidebar-scroll">
      <div style={{ marginBottom: 16 }}>
        <Space size={4} wrap>
          <Tag color="blue">{paper.tag}</Tag>
          <Tag>arXiv:{paper.arxiv}</Tag>
        </Space>
        <Title level={5} style={{ marginTop: 8 }}>{paper.title}</Title>
        <Text type="secondary" style={{ fontSize: 12 }}>{paper.authors}</Text>
        <Paragraph style={{ fontSize: 13 }}>{paper.summary}</Paragraph>
        <FavoriteButton paperId={paperId} block />
        <Button block icon={<LinkOutlined />} style={{ marginTop: 8 }}>原文链接</Button>
      </div>

      <div className="wiki-section">
        <Title level={5}>论文知识 Wiki</Title>
        <Text type="secondary" style={{ fontSize: 12 }}>按标题、作者、关键词、研究方向、概念标签检索</Text>
        <Segmented
          size="small"
          options={WIKI_MODES}
          value={mode}
          onChange={setMode}
          style={{ margin: '10px 0', flexWrap: 'wrap' }}
          block
        />
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入检索词..."
            onPressEnter={submitSearch}
          />
          <Button icon={<SearchOutlined />} type="primary" loading={loading} onClick={submitSearch}>检索</Button>
        </Space.Compact>
        <Text className="block-label" style={{ marginTop: 12 }}>本篇 Wiki 标签</Text>
        <Space wrap size={4}>
          {quickTags.map((t) => (
            <Tag
              key={t.text}
              style={{ cursor: 'pointer' }}
              onClick={() => { setMode(t.mode); setQuery(t.text); }}
            >
              {t.text}
            </Tag>
          ))}
        </Space>
        <Text className="block-label" style={{ marginTop: 12 }}>检索结果 · {results.length} 条</Text>
        <List
          size="small"
          dataSource={results}
          locale={{ emptyText: query ? '未找到匹配' : '输入关键词或点击标签检索' }}
          renderItem={(item) => (
            <List.Item
              className="wiki-result-item"
              onClick={() => item.id !== paperId && navigate(`/paper/${item.id}`)}
              style={{ cursor: item.id === paperId ? 'default' : 'pointer' }}
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
