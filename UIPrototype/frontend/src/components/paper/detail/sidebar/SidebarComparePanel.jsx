import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Empty,
  Input,
  List,
  Spin,
  Tabs,
  Tag,
  Typography,
  message
} from 'antd';
import { SearchOutlined, StarOutlined, ApartmentOutlined } from '@ant-design/icons';
import { useApp } from '../../../../context/AppContext';
import { PAPER_LIST, PAPERS } from '../../../../data/papers';
import {
  getPaperDetail,
  getPaperGraph,
  searchPapers,
  smartSearchPapers
} from '../../../../services/paperService';
import { listActions } from '../../../../services/learningService';
import { USE_MOCK } from '../../../../services/runtimeConfig';

const { Text } = Typography;

const ROWS = [
  { key: 'title', label: '标题' },
  { key: 'authors', label: '作者' },
  { key: 'tag', label: '学科' },
  { key: 'direction', label: '研究方向' },
  { key: 'keywords', label: '关键词', fmt: (p) => (p.keywords || []).join(' · ') },
  { key: 'conceptTags', label: '概念标签', fmt: (p) => (p.conceptTags || []).join(' · ') },
  { key: 'summary', label: '摘要' }
];

const EMPTY_PAPER = { title: '请选择对比论文', authors: [], keywords: [], conceptTags: [] };

function normalizePickerItem(paper) {
  if (!paper) return null;
  const paperId = paper.paperId ?? paper.paper_id ?? paper.id;
  if (paperId === undefined || paperId === null || paperId === '') return null;
  return {
    paperId: String(paperId),
    title: paper.title || `论文 ${paperId}`,
    authors: Array.isArray(paper.authors) ? paper.authors : [],
    primaryCategory: paper.primaryCategory || paper.primary_category || paper.tag || '未分类',
    summary: paper.summary || paper.abstract || '',
    keywords: paper.keywords || [],
    conceptTags: paper.conceptTags || paper.concept_tags || [],
    researchDirection: paper.researchDirection || paper.research_direction || paper.direction || '',
    source: paper.source || ''
  };
}

function displayField(paper, key) {
  if (key === 'authors') {
    if (Array.isArray(paper.authors)) return paper.authors.join(', ');
    return paper.authorsText || paper.authors || '';
  }
  return paper[key];
}

export default function SidebarComparePanel({ paperId, paper }) {
  const {
    userId,
    comparePaperB,
    setComparePaperB,
    comparePreviewActive,
    setComparePreviewActive,
  } = useApp();

  const [remotePapers, setRemotePapers] = useState({});
  const remoteCacheRef = useRef({});
  const [pickerTab, setPickerTab] = useState('search');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchHint, setSearchHint] = useState('');
  const [favorites, setFavorites] = useState([]);
  const [favoritesLoading, setFavoritesLoading] = useState(false);
  const [relatedPapers, setRelatedPapers] = useState([]);
  const [relatedLoading, setRelatedLoading] = useState(false);

  const currentId = String(paperId);

  const ensureRemotePaper = useCallback(async (id) => {
    const key = String(id);
    if (!key || key === currentId) return paper ? normalizePickerItem(paper) : null;
    if (PAPERS[key]) return normalizePickerItem(PAPERS[key]);
    if (remoteCacheRef.current[key]) return remoteCacheRef.current[key];
    try {
      const detail = await getPaperDetail(key);
      const normalized = normalizePickerItem(detail);
      if (normalized) {
        remoteCacheRef.current[key] = normalized;
        setRemotePapers((current) => ({ ...current, [key]: normalized }));
      }
      return normalized;
    } catch {
      return null;
    }
  }, [currentId, paper]);

  const loadFavorites = useCallback(async () => {
    if (USE_MOCK) {
      setFavorites(['attention', 'bert', 'lora']
        .filter((id) => id !== currentId)
        .map((id) => normalizePickerItem(PAPERS[id]))
        .filter(Boolean));
      return;
    }
    setFavoritesLoading(true);
    try {
      const actions = await listActions({ userId, actionType: 'favorite' });
      const ids = [...new Set(
        actions
          .filter((action) => action.payload_json?.favorite !== false)
          .map((action) => String(action.paper_id))
          .filter((id) => id !== currentId)
      )];
      const items = (await Promise.all(ids.map((id) => ensureRemotePaper(id)))).filter(Boolean);
      setFavorites(items);
    } catch {
      setFavorites([]);
    } finally {
      setFavoritesLoading(false);
    }
  }, [currentId, ensureRemotePaper, userId]);

  const loadRelated = useCallback(async () => {
    setRelatedLoading(true);
    try {
      if (USE_MOCK) {
        const candidates = PAPER_LIST
          .map((item) => normalizePickerItem(PAPERS[item.id]))
          .filter((item) => item && item.paperId !== currentId);
        setRelatedPapers(candidates.slice(0, 8));
        return;
      }

      const related = [];
      const seen = new Set([currentId]);
      const [graphResult, historyActions] = await Promise.allSettled([
        getPaperGraph(paperId),
        listActions({ userId, actionType: 'reading_history' })
      ]);

      if (graphResult.status === 'fulfilled') {
        for (const item of graphResult.value?.lineage || []) {
          const id = String(item.paperId ?? item.paper_id ?? '');
          if (!id || seen.has(id)) continue;
          seen.add(id);
          related.push(normalizePickerItem({
            paperId: id,
            title: item.title,
            source: 'lineage',
            primaryCategory: item.role || '相关论文'
          }));
        }
      }

      if (historyActions.status === 'fulfilled') {
        const historyIds = [...new Set(
          historyActions.value
            .map((action) => String(action.paper_id))
            .filter((id) => id && !seen.has(id) && id !== currentId)
        )].slice(0, 6);
        const historyItems = await Promise.all(historyIds.map((id) => ensureRemotePaper(id)));
        historyItems.forEach((item) => {
          if (!item || seen.has(item.paperId)) return;
          seen.add(item.paperId);
          related.push({ ...item, source: 'history' });
        });
      }

      setRelatedPapers(related.slice(0, 12));
    } catch {
      setRelatedPapers([]);
    } finally {
      setRelatedLoading(false);
    }
  }, [currentId, ensureRemotePaper, paperId, userId]);

  useEffect(() => {
    let cancelled = false;
    const otherId = String(comparePaperB || '');
    if (!otherId || otherId === currentId) return undefined;
    ensureRemotePaper(otherId)
      .then((item) => {
        if (cancelled || !item) return;
        setRemotePapers((current) => ({ ...current, [item.paperId]: item }));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [comparePaperB, currentId, ensureRemotePaper]);

  useEffect(() => {
    if (pickerTab === 'favorites') loadFavorites();
    if (pickerTab === 'related') loadRelated();
  }, [loadFavorites, loadRelated, pickerTab]);

  const currentPaper = useMemo(() => {
    if (!paper) return EMPTY_PAPER;
    return {
      ...paper,
      tag: paper.tag || paper.primaryCategory,
      direction: paper.direction || paper.researchDirection,
      authorsText: Array.isArray(paper.authors) ? paper.authors.join(', ') : paper.authors
    };
  }, [paper]);

  const otherPaper = useMemo(() => {
    const id = String(comparePaperB || '');
    if (!id || id === currentId) return EMPTY_PAPER;
    const cached = PAPERS[id] || remotePapers[id];
    if (!cached) return { ...EMPTY_PAPER, title: '正在加载对比论文…' };
    return {
      ...cached,
      tag: cached.tag || cached.primaryCategory,
      direction: cached.direction || cached.researchDirection,
      authorsText: Array.isArray(cached.authors) ? cached.authors.join(', ') : cached.authors
    };
  }, [comparePaperB, currentId, remotePapers]);

  const hasOther = Boolean(comparePaperB) && String(comparePaperB) !== currentId && otherPaper.title !== EMPTY_PAPER.title;

  const handleSearch = async (value) => {
    const query = (value ?? searchQuery).trim();
    if (!query) {
      message.warning('请输入检索词');
      return;
    }
    setSearching(true);
    setSearchHint('');
    try {
      const data = USE_MOCK
        ? await searchPapers({ query, page: 1, pageSize: 12 })
        : await smartSearchPapers({ query, page: 1, pageSize: 12 });
      const items = (data.items || [])
        .map(normalizePickerItem)
        .filter((item) => item && item.paperId !== currentId);
      setSearchResults(items);
      setSearchHint(data.total > 0 ? `找到 ${data.total} 篇，展示前 ${items.length} 篇` : '未找到匹配论文');
    } catch (error) {
      setSearchResults([]);
      setSearchHint(error.message || '检索失败');
    } finally {
      setSearching(false);
    }
  };

  const selectOtherPaper = (id) => {
    const nextId = String(id);
    if (nextId === currentId) {
      message.warning('不能与当前论文自身对比');
      return;
    }
    setComparePaperB(nextId);
    ensureRemotePaper(nextId);
    message.success('已选定对比论文，下方自动生成对比');
  };

  const toggleOpenComparePaper = () => {
    if (comparePreviewActive) {
      setComparePreviewActive(false);
      message.success('已返回原论文');
      return;
    }
    setComparePreviewActive(true);
    message.success('已打开对比论文（对比阅读页不关闭）');
  };

  const renderPickerItem = (item) => (
    <List.Item
      key={item.paperId}
      className="compare-picker-item"
      onClick={() => selectOtherPaper(item.paperId)}
      actions={[
        String(item.paperId) === String(comparePaperB) ? <Tag key="selected" color="blue">已选</Tag> : null
      ].filter(Boolean)}
    >
      <List.Item.Meta
        title={<Text ellipsis style={{ maxWidth: 220 }}>{item.title}</Text>}
        description={
          <Text type="secondary" style={{ fontSize: 12 }}>
            {[item.primaryCategory, item.source === 'lineage' ? '知识图谱' : item.source === 'history' ? '阅读历史' : ''].filter(Boolean).join(' · ')}
          </Text>
        }
      />
    </List.Item>
  );

  const pickerTabs = useMemo(() => [
    {
      key: 'search',
      label: <span><SearchOutlined /> 搜索</span>,
      children: (
        <>
          <Input.Search
            allowClear
            placeholder="标题、作者、关键词…"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            onSearch={handleSearch}
            loading={searching}
            enterButton="检索"
          />
          {searchHint ? <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>{searchHint}</Text> : null}
          <List
            size="small"
            style={{ marginTop: 8 }}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="输入关键词后检索" /> }}
            dataSource={searchResults}
            renderItem={renderPickerItem}
          />
        </>
      )
    },
    {
      key: 'favorites',
      label: <span><StarOutlined /> 收藏</span>,
      children: favoritesLoading ? (
        <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
      ) : (
        <List
          size="small"
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="收藏夹暂无论文" /> }}
          dataSource={favorites}
          renderItem={renderPickerItem}
        />
      )
    },
    {
      key: 'related',
      label: <span><ApartmentOutlined /> 相关</span>,
      children: relatedLoading ? (
        <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
      ) : (
        <List
          size="small"
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无相关论文" /> }}
          dataSource={relatedPapers}
          renderItem={renderPickerItem}
        />
      )
    }
  ], [
    comparePaperB,
    favorites,
    favoritesLoading,
    relatedLoading,
    relatedPapers,
    searchHint,
    searchQuery,
    searchResults,
    searching
  ]);

  return (
    <div className="sidebar-scroll">
      <Text strong>对比阅读</Text>
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
        当前论文固定为对比基准；请搜索或从收藏选择另一篇。打开对比论文时不会离开本页，再次点击可返回原论文。
      </Text>

      <div className="compare-slot" style={{ marginTop: 12 }}>
        <Text className="block-label">当前论文</Text>
        <Text ellipsis style={{ display: 'block', fontSize: 12, marginTop: 4 }}>
          {currentPaper.title || '—'}
        </Text>
      </div>
      <div className={`compare-slot ${hasOther ? 'active' : ''}`} style={{ marginTop: 8 }}>
        <Text className="block-label">对比论文</Text>
        <Text ellipsis style={{ display: 'block', fontSize: 12, marginTop: 4 }}>
          {hasOther ? otherPaper.title : '尚未选择'}
        </Text>
      </div>

      <div className="compare-picker" style={{ marginTop: 12 }}>
        <Tabs size="small" activeKey={pickerTab} onChange={setPickerTab} items={pickerTabs} />
      </div>

      <div className="compare-body" style={{ marginTop: 12 }}>
        {!hasOther ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选定对比论文后自动生成对比内容" />
        ) : (
          ROWS.map((row) => {
            const va = row.fmt ? row.fmt(currentPaper) : displayField(currentPaper, row.key);
            const vb = row.fmt ? row.fmt(otherPaper) : displayField(otherPaper, row.key);
            return (
              <div key={row.key} className="compare-row">
                <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>{row.label}</Text>
                <div className={`compare-col ${va !== vb ? 'diff' : ''}`}><Tag color="blue">当前</Tag>{va || '—'}</div>
                <div className={`compare-col ${va !== vb ? 'diff' : ''}`}><Tag>对比</Tag>{vb || '—'}</div>
              </div>
            );
          })
        )}
      </div>

      {hasOther ? (
        <Button
          block
          type={comparePreviewActive ? 'default' : 'primary'}
          style={{ marginTop: 12 }}
          onClick={toggleOpenComparePaper}
        >
          {comparePreviewActive ? '返回原论文' : '打开对比论文'}
        </Button>
      ) : null}
    </div>
  );
}
