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
  Row,
  Col,
  message
} from 'antd';
import { SearchOutlined, StarOutlined, ApartmentOutlined, SwapOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../../../context/AppContext';
import { PAPER_LIST, PAPERS, shortPaperTitle } from '../../../../data/papers';
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

function slotLabel(paper, fallback = '未选择') {
  if (!paper?.title || paper.title === EMPTY_PAPER.title) return fallback;
  const title = paper.title;
  return title.length > 36 ? `${title.slice(0, 36)}…` : title;
}

function displayField(paper, key) {
  if (key === 'authors') {
    if (Array.isArray(paper.authors)) return paper.authors.join(', ');
    return paper.authorsText || paper.authors || '';
  }
  return paper[key];
}

export default function SidebarComparePanel({ paperId, paper }) {
  const navigate = useNavigate();
  const { userId, comparePaperA, comparePaperB, compareActiveSlot, setCompareActiveSlot, setComparePaperA, setComparePaperB } = useApp();

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
    const ids = [comparePaperA, comparePaperB]
      .map((id) => String(id))
      .filter((id) => id && id !== currentId && (/^\d+$/.test(id) || PAPERS[id]));
    if (!ids.length) return undefined;
    Promise.all(ids.map((id) => ensureRemotePaper(id)))
      .then((items) => {
        if (cancelled) return;
        const next = {};
        items.forEach((item) => {
          if (item) next[item.paperId] = item;
        });
        if (Object.keys(next).length) {
          setRemotePapers((current) => ({ ...current, ...next }));
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [comparePaperA, comparePaperB, currentId, ensureRemotePaper]);

  useEffect(() => {
    if (pickerTab === 'favorites') loadFavorites();
    if (pickerTab === 'related') loadRelated();
  }, [loadFavorites, loadRelated, pickerTab]);

  useEffect(() => {
    let cancelled = false;
    async function suggestDefaultCompareTarget() {
      const slotA = String(comparePaperA);
      const slotB = String(comparePaperB);
      // B may equal the paper currently being read — that is valid when reading B.
      const missingB = !slotB || (USE_MOCK ? !PAPERS[slotB] : !/^\d+$/.test(slotB));
      const sameAsA = Boolean(slotB) && slotB === slotA;
      if (!missingB && !sameAsA) return;

      const exclude = new Set([slotA, currentId].filter(Boolean));

      if (USE_MOCK) {
        const candidate = PAPER_LIST.map((item) => item.id).find((id) => !exclude.has(String(id)));
        if (candidate && !cancelled) setComparePaperB(candidate);
        return;
      }

      try {
        const favoriteActions = await listActions({ userId, actionType: 'favorite' });
        const favoriteId = favoriteActions
          .map((action) => String(action.paper_id))
          .find((id) => id && !exclude.has(id));
        if (favoriteId) {
          if (!cancelled) setComparePaperB(favoriteId);
          return;
        }

        const graph = await getPaperGraph(paperId);
        const lineageId = (graph?.lineage || [])
          .map((item) => String(item.paperId ?? item.paper_id ?? ''))
          .find((id) => id && !exclude.has(id));
        if (lineageId && !cancelled) setComparePaperB(lineageId);
      } catch {
        // Keep empty slot B until user picks manually.
      }
    }
    suggestDefaultCompareTarget();
    return () => { cancelled = true; };
  }, [comparePaperA, comparePaperB, currentId, paperId, setComparePaperB, userId]);

  const resolvePaper = useCallback((id) => {
    if (String(id) === currentId) {
      return paper
        ? {
            ...paper,
            tag: paper.tag || paper.primaryCategory,
            direction: paper.direction || paper.researchDirection,
            authorsText: Array.isArray(paper.authors) ? paper.authors.join(', ') : paper.authors
          }
        : EMPTY_PAPER;
    }
    const cached = PAPERS[id] || remotePapers[String(id)];
    if (!cached) return EMPTY_PAPER;
    return {
      ...cached,
      tag: cached.tag || cached.primaryCategory,
      direction: cached.direction || cached.researchDirection,
      authorsText: Array.isArray(cached.authors) ? cached.authors.join(', ') : cached.authors
    };
  }, [currentId, paper, remotePapers]);

  const paperA = resolvePaper(comparePaperA);
  const paperB = resolvePaper(comparePaperB);

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

  const setSlotPaper = (slot, id) => {
    const nextId = String(id);
    if (nextId === String(comparePaperA) && slot === 'a') return;
    if (nextId === String(comparePaperB) && slot === 'b') return;
    if (slot === 'a') {
      setComparePaperA(nextId);
      // Do not reshuffle B when A is set to what was B — keep B, user can change later
      if (String(comparePaperB) === nextId) {
        message.warning('论文 B 已是该篇，请另选一篇作为 B，或先互换');
      }
    } else {
      setComparePaperB(nextId);
      if (String(comparePaperA) === nextId) {
        message.warning('论文 A 已是该篇，请另选一篇作为 A，或先互换');
      }
    }
    message.success(`已设为论文 ${slot.toUpperCase()}`);
  };

  const swap = () => {
    setComparePaperA(comparePaperB);
    setComparePaperB(comparePaperA);
    message.success('已互换对比论文');
  };

  const renderPickerItem = (item) => (
    <List.Item
      key={item.paperId}
      className="compare-picker-item"
      onClick={() => setSlotPaper(compareActiveSlot, item.paperId)}
      actions={[
        String(item.paperId) === String(comparePaperA) ? <Tag key="slot-a" color="blue">A</Tag> : null,
        String(item.paperId) === String(comparePaperB) ? <Tag key="slot-b">B</Tag> : null
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
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无相关论文，可先阅读或解析当前论文" /> }}
          dataSource={relatedPapers}
          renderItem={renderPickerItem}
        />
      )
    }
  ], [
    comparePaperA,
    comparePaperB,
    compareActiveSlot,
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong>对比阅读</Text>
        <Button size="small" icon={<SwapOutlined />} onClick={swap}>互换</Button>
      </div>
      <Text type="secondary" style={{ fontSize: 12 }}>
        先选 A/B 栏，再通过搜索或收藏选择对比论文
      </Text>

      <Row gutter={8} style={{ marginTop: 12 }}>
        <Col span={12}>
          <div className={`compare-slot ${compareActiveSlot === 'a' ? 'active' : ''}`} onClick={() => setCompareActiveSlot('a')}>
            <Text className="block-label">论文 A</Text>
            <Text ellipsis style={{ display: 'block', fontSize: 12, marginTop: 4 }}>
              {slotLabel(paperA, USE_MOCK ? shortPaperTitle(comparePaperA) : '未选择')}
            </Text>
          </div>
        </Col>
        <Col span={12}>
          <div className={`compare-slot ${compareActiveSlot === 'b' ? 'active' : ''}`} onClick={() => setCompareActiveSlot('b')}>
            <Text className="block-label">论文 B</Text>
            <Text ellipsis style={{ display: 'block', fontSize: 12, marginTop: 4 }}>
              {slotLabel(paperB, USE_MOCK ? shortPaperTitle(comparePaperB) : '未选择')}
            </Text>
          </div>
        </Col>
      </Row>

      <div className="compare-picker" style={{ marginTop: 12 }}>
        <Tabs size="small" activeKey={pickerTab} onChange={setPickerTab} items={pickerTabs} />
      </div>

      <div className="compare-body" style={{ marginTop: 12 }}>
        {ROWS.map((row) => {
          const va = row.fmt ? row.fmt(paperA) : displayField(paperA, row.key);
          const vb = row.fmt ? row.fmt(paperB) : displayField(paperB, row.key);
          return (
            <div key={row.key} className="compare-row">
              <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>{row.label}</Text>
              <div className={`compare-col ${va !== vb ? 'diff' : ''}`}><Tag>A</Tag>{va || '—'}</div>
              <div className={`compare-col ${va !== vb ? 'diff' : ''}`}><Tag>B</Tag>{vb || '—'}</div>
            </div>
          );
        })}
      </div>

      <Button block style={{ marginTop: 12 }} onClick={() => navigate(`/paper/${comparePaperA}`)}>阅读论文 A</Button>
      <Button block style={{ marginTop: 8 }} onClick={() => navigate(`/paper/${comparePaperB}`)}>阅读论文 B</Button>
    </div>
  );
}
