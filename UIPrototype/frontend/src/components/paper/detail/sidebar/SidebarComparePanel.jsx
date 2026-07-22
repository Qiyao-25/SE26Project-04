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
  generatePaperCompare,
  getPaperDetail,
  getPaperGraph,
  searchPapers,
  smartSearchPapers
} from '../../../../services/paperService';
import { listActions } from '../../../../services/learningService';
import { USE_MOCK } from '../../../../services/runtimeConfig';

const { Text, Paragraph } = Typography;

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
  const [compareResult, setCompareResult] = useState(null);
  const [compareGenerating, setCompareGenerating] = useState(false);
  const [compareError, setCompareError] = useState('');

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
    setCompareResult(null);
    setCompareError('');
    setCompareGenerating(false);
  }, [comparePaperB, currentId]);

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
    message.success('已选定对比论文，可点击「生成对比」');
  };

  const handleGenerateCompare = async () => {
    if (!hasOther) {
      message.warning('请先选择对比论文');
      return;
    }
    setCompareGenerating(true);
    setCompareError('');
    try {
      const result = await generatePaperCompare(paperId, comparePaperB);
      setCompareResult(result);
      message.success(result.source === 'llm' ? '智能对比已生成' : '对比已生成');
    } catch (error) {
      setCompareResult(null);
      setCompareError(error.message || '对比生成失败');
      message.error(error.message || '对比生成失败');
    } finally {
      setCompareGenerating(false);
    }
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
        先选定对比论文，再点击「生成对比」由 LLM 输出智能总结；打开对比论文不会离开本页。
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

      {hasOther ? (
        <Button
          block
          type="primary"
          style={{ marginTop: 12 }}
          loading={compareGenerating}
          onClick={handleGenerateCompare}
        >
          {compareResult ? '重新生成对比' : '生成对比'}
        </Button>
      ) : null}

      <div className="compare-body" style={{ marginTop: 12 }}>
        {!hasOther ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请先选择对比论文" />
        ) : compareGenerating ? (
          <div style={{ textAlign: 'center', padding: 24 }}><Spin tip="正在生成智能对比…" /></div>
        ) : compareError ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={compareError} />
        ) : !compareResult ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选定后点击「生成对比」查看 LLM 总结" />
        ) : (
          <>
            <div style={{ marginBottom: 8 }}>
              <Tag color={compareResult.source === 'llm' ? 'purple' : 'default'}>
                {compareResult.source === 'llm' ? 'LLM 对比' : compareResult.source === 'mock' ? 'Mock 对比' : '启发式对比'}
              </Tag>
            </div>
            <Text strong style={{ display: 'block', marginBottom: 6 }}>总体概述</Text>
            <Paragraph style={{ fontSize: 13, marginBottom: 12 }}>{compareResult.summary}</Paragraph>

            {(compareResult.similarities || []).length > 0 ? (
              <>
                <Text strong style={{ display: 'block', marginBottom: 6 }}>相似点</Text>
                <ul style={{ paddingLeft: 18, marginTop: 0, marginBottom: 12 }}>
                  {compareResult.similarities.map((item) => (
                    <li key={item} style={{ marginBottom: 4, fontSize: 12 }}>{item}</li>
                  ))}
                </ul>
              </>
            ) : null}

            {(compareResult.differences || []).length > 0 ? (
              <>
                <Text strong style={{ display: 'block', marginBottom: 6 }}>差异点</Text>
                <ul style={{ paddingLeft: 18, marginTop: 0, marginBottom: 12 }}>
                  {compareResult.differences.map((item) => (
                    <li key={item} style={{ marginBottom: 4, fontSize: 12 }}>{item}</li>
                  ))}
                </ul>
              </>
            ) : null}

            {(compareResult.dimensions || []).map((dim) => (
              <div key={dim.aspect} className="compare-row">
                <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>{dim.aspect}</Text>
                <div className="compare-col"><Tag color="blue">当前</Tag>{dim.paperA || '—'}</div>
                <div className="compare-col"><Tag>对比</Tag>{dim.paperB || '—'}</div>
                {dim.comment ? (
                  <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>{dim.comment}</Text>
                ) : null}
              </div>
            ))}

            {compareResult.recommendation ? (
              <>
                <Text strong style={{ display: 'block', marginTop: 8, marginBottom: 6 }}>阅读建议</Text>
                <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 0 }}>
                  {compareResult.recommendation}
                </Paragraph>
              </>
            ) : null}
          </>
        )}
      </div>

      {hasOther ? (
        <Button
          block
          type={comparePreviewActive ? 'default' : 'primary'}
          ghost={!comparePreviewActive}
          style={{ marginTop: 12 }}
          onClick={toggleOpenComparePaper}
        >
          {comparePreviewActive ? '返回原论文' : '打开对比论文'}
        </Button>
      ) : null}
    </div>
  );
}
