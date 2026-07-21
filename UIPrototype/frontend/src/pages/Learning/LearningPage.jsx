import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Tabs, Row, Col, List, Tag, Typography, Segmented, Switch, Input, Select, Empty, Spin, Alert, message, Button, Popconfirm, Pagination, Space } from 'antd';
import { READING_HISTORY, PERSONAS, MODE_DESC, PAPERS } from '../../data/papers';
import { useApp } from '../../context/AppContext';
import { getPaperDetail } from '../../services/paperService';
import { getConceptDictionary, getLearningProfile, listActions, updateLearningProfile, deleteAction, deleteActionsByType } from '../../services/learningService';
import { USE_MOCK } from '../../services/runtimeConfig';
import { formatDateKey, parseApiDate } from '../../utils/datetime';
import PaperCard from '../../components/paper/PaperCard';
import { PROFILE_TOPIC_OPTIONS } from '../../data/arxivCategories';

const { Text, Paragraph } = Typography;
const DICT_PAGE_SIZE = 9;

const TOPIC_OPTIONS = PROFILE_TOPIC_OPTIONS;

function emptyLibrary() {
  return { favorites: [], notes: [], history: [] };
}

export default function LearningPage() {
  const navigate = useNavigate();
  const { userId, persona, setPersona, topics, setTopics } = useApp();
  const [historyKey, setHistoryKey] = useState('today');
  const [library, setLibrary] = useState(emptyLibrary);
  const [paperMap, setPaperMap] = useState({});
  const [loading, setLoading] = useState(!USE_MOCK);
  const [error, setError] = useState('');
  const [profile, setProfile] = useState(null);
  const [dictionary, setDictionary] = useState([]);
  const [reloadToken, setReloadToken] = useState(0);
  const [notesSearch, setNotesSearch] = useState('');
  const [historySearch, setHistorySearch] = useState('');
  const [dictSearch, setDictSearch] = useState('');
  const [dictPage, setDictPage] = useState(1);

  useEffect(() => {
    if (USE_MOCK) return undefined;
    let cancelled = false;
    Promise.all([getLearningProfile(userId), getConceptDictionary(userId)])
      .then(([nextProfile, nextDictionary]) => {
        if (cancelled) return;
        setProfile(nextProfile);
        setDictionary(nextDictionary || []);
        if (nextProfile.persona) setPersona(nextProfile.persona);
        if (Array.isArray(nextProfile.topics)) setTopics(nextProfile.topics);
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.message || '画像数据加载失败');
      });
    return () => { cancelled = true; };
  }, [userId, setPersona, setTopics]);

  const handlePersonaChange = (nextPersona) => {
    setPersona(nextPersona);
    if (!USE_MOCK) {
      updateLearningProfile(userId, { persona: nextPersona })
        .then(setProfile)
        .catch((requestError) => setError(requestError.message || '画像保存失败'));
    }
  };

  const handleTopicsChange = (nextTopics) => {
    const normalized = (nextTopics || []).map((item) => String(item).trim()).filter(Boolean).slice(0, 20);
    setTopics(normalized);
    if (!USE_MOCK) {
      updateLearningProfile(userId, { topics: normalized })
        .then((nextProfile) => {
          setProfile(nextProfile);
          message.success('兴趣主题已更新');
        })
        .catch((requestError) => setError(requestError.message || '兴趣主题保存失败'));
    }
  };

  useEffect(() => {
    if (USE_MOCK) return undefined;
    let cancelled = false;
    setLoading(true);
    setError('');
    listActions({ userId })
      .then(async (actions) => {
        const ids = [...new Set(actions.map((action) => action.paper_id))];
        const details = await Promise.all(ids.map(async (id) => {
          try {
            return [String(id), await getPaperDetail(id)];
          } catch {
            return [String(id), null];
          }
        }));
        if (cancelled) return;
        setPaperMap(Object.fromEntries(details.filter(([, paper]) => paper)));
        setLibrary({
          favorites: actions.filter((action) => action.action_type === 'favorite' && action.payload_json?.favorite !== false),
          notes: actions.filter((action) => action.action_type === 'note'),
          history: (() => {
            const seen = new Set();
            const rows = [];
            for (const action of actions.filter((item) => item.action_type === 'reading_history')) {
              const key = String(action.paper_id);
              if (seen.has(key)) continue;
              seen.add(key);
              rows.push(action);
            }
            return rows;
          })()
        });
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.message || '学习数据加载失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [userId, reloadToken]);

  const refreshDictionary = async () => {
    const nextDictionary = await getConceptDictionary(userId);
    setDictionary(nextDictionary || []);
  };

  const handleDeleteNote = async (actionId) => {
    try {
      await deleteAction(actionId);
      message.success('已删除笔记');
      setReloadToken((token) => token + 1);
    } catch (requestError) {
      message.error(requestError.message || '删除失败');
    }
  };

  const handleDeleteHistory = async (actionId) => {
    try {
      await deleteAction(actionId);
      message.success('已删除阅读记录');
      setReloadToken((token) => token + 1);
    } catch (requestError) {
      message.error(requestError.message || '删除失败');
    }
  };

  const handleClearHistory = async () => {
    try {
      await deleteActionsByType(userId, 'reading_history');
      message.success('已清空阅读历史');
      setReloadToken((token) => token + 1);
    } catch (requestError) {
      message.error(requestError.message || '清空失败');
    }
  };

  const hideDictionaryTerms = async (terms) => {
    const uniqueTerms = [...new Set((terms || []).map((term) => String(term || '').trim()).filter(Boolean))];
    if (!uniqueTerms.length) return;
    const hidden = [
      ...new Set([
        ...(profile?.preferences?.hidden_dictionary_terms || []),
        ...uniqueTerms
      ])
    ];
    try {
      const nextProfile = await updateLearningProfile(userId, {
        preferences: { ...(profile?.preferences || {}), hidden_dictionary_terms: hidden }
      });
      setProfile(nextProfile);
      await refreshDictionary();
      message.success(uniqueTerms.length > 1 ? '已清空词典词条' : '已删除词条');
    } catch (requestError) {
      message.error(requestError.message || '操作失败');
    }
  };

  const mockHistory = READING_HISTORY[historyKey];
  const apiHistory = useMemo(() => {
    const today = formatDateKey(new Date());
    const yesterday = formatDateKey(new Date(Date.now() - 86400000));
    const dayKey = (item) => formatDateKey(item.occurred_at) || item.occurred_at?.slice(0, 10);
    const matches = {
      today: (item) => dayKey(item) === today,
      yesterday: (item) => dayKey(item) === yesterday,
      earlier: (item) => ![today, yesterday].includes(dayKey(item))
    };
    const items = library.history.filter(matches[historyKey]).map((item) => {
      const occurred = parseApiDate(item.occurred_at);
      const hhmm = occurred
        ? occurred.toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false })
        : (item.occurred_at?.slice(11, 16) || '');
      return {
        id: item.id,
        paper: String(item.paper_id),
        time: item.payload_json?.time || hhmm,
        section: item.payload_json?.section || '论文主体',
        duration: item.payload_json?.duration || '已记录'
      };
    });
    return { label: historyKey === 'today' ? '今天' : historyKey === 'yesterday' ? '昨天' : '更早', items };
  }, [historyKey, library.history]);

  const favorites = USE_MOCK ? ['attention', 'bert', 'lora'].map((id) => ({ paper: PAPERS[id], paperId: id })) : library.favorites.map((item) => ({ paper: paperMap[String(item.paper_id)], paperId: item.paper_id }));
  const notes = USE_MOCK
    ? [
      { id: 'mock-note-1', paperId: 'attention', paper: PAPERS.attention, text: '核心创新在于完全用注意力替代 RNN', date: '2026-07-01' },
      { id: 'mock-note-2', paperId: 'bert', paper: PAPERS.bert, text: '预训练-微调范式的里程碑', date: '2026-06-18' }
    ]
    : library.notes.map((item) => ({
      id: item.id,
      paperId: item.paper_id,
      paper: paperMap[String(item.paper_id)],
      text: item.payload_json?.text || '',
      date: item.occurred_at?.slice(0, 10) || ''
    }));
  const history = USE_MOCK ? mockHistory : apiHistory;

  const filteredNotes = useMemo(() => {
    const q = notesSearch.trim().toLowerCase();
    return notes.filter((item) => {
      if (!item.paper) return false;
      if (!q) return true;
      const title = String(item.paper.title || '').toLowerCase();
      const text = String(item.text || '').toLowerCase();
      return title.includes(q) || text.includes(q);
    });
  }, [notes, notesSearch]);

  const filteredHistoryItems = useMemo(() => {
    const q = historySearch.trim().toLowerCase();
    const items = history.items || [];
    if (!q) return items;
    return items.filter((item) => {
      const paper = USE_MOCK ? PAPERS[item.paper] : paperMap[item.paper];
      const title = String(paper?.title || '').toLowerCase();
      const section = String(item.section || '').toLowerCase();
      return title.includes(q) || section.includes(q);
    });
  }, [history.items, historySearch, paperMap]);

  const filteredDictionary = useMemo(() => {
    const q = dictSearch.trim().toLowerCase();
    if (!q) return dictionary;
    return dictionary.filter((item) => {
      const term = String(item.term || '').toLowerCase();
      const description = String(item.description || '').toLowerCase();
      return term.includes(q) || description.includes(q);
    });
  }, [dictionary, dictSearch]);

  const pagedDictionary = useMemo(() => {
    const start = (dictPage - 1) * DICT_PAGE_SIZE;
    return filteredDictionary.slice(start, start + DICT_PAGE_SIZE);
  }, [filteredDictionary, dictPage]);

  useEffect(() => {
    setDictPage(1);
  }, [dictSearch]);

  const tabItems = [
    {
      key: 'favorites',
      label: '收藏夹',
      children: loading ? <Spin /> : favorites.length ? (
        <Row gutter={[16, 16]}>
          {favorites.filter(({ paper }) => paper).map(({ paper, paperId }) => (
            <Col xs={24} sm={12} lg={8} key={paperId}><PaperCard paper={paper} /></Col>
          ))}
        </Row>
      ) : <Empty description="暂无收藏论文" />
    },
    {
      key: 'notes',
      label: '笔记/评论',
      children: (
        <>
          <Input
            allowClear
            placeholder="搜索笔记标题或内容"
            value={notesSearch}
            onChange={(event) => setNotesSearch(event.target.value)}
            style={{ marginBottom: 16, maxWidth: 360 }}
          />
          {filteredNotes.length ? (
            <List
              dataSource={filteredNotes}
              locale={{ emptyText: '暂无笔记或评论' }}
              renderItem={(item) => (
                <List.Item
                  actions={!USE_MOCK ? [
                    <Popconfirm key="delete" title="确定删除这条笔记？" onConfirm={() => handleDeleteNote(item.id)}>
                      <Button type="link" danger size="small">删除</Button>
                    </Popconfirm>
                  ] : undefined}
                >
                  <List.Item.Meta
                    title={(
                      <a onClick={() => navigate(`/paper/${item.paperId}`)} style={{ cursor: 'pointer' }}>
                        {item.paper.title}
                      </a>
                    )}
                    description={<>{item.text} · <Text type="secondary">{item.date}</Text></>}
                  />
                </List.Item>
              )}
            />
          ) : <Empty description="暂无笔记或评论" />}
        </>
      )
    },
    {
      key: 'history',
      label: '阅读历史',
      children: (
        <>
          <Space wrap style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
            <Space wrap>
              <Segmented
                options={[{ value: 'today', label: '今天' }, { value: 'yesterday', label: '昨天' }, { value: 'earlier', label: '更早' }]}
                value={historyKey}
                onChange={setHistoryKey}
              />
              <Input
                allowClear
                placeholder="搜索阅读历史"
                value={historySearch}
                onChange={(event) => setHistorySearch(event.target.value)}
                style={{ width: 220 }}
              />
            </Space>
            {!USE_MOCK && (
              <Popconfirm title="确定清空全部阅读历史？" onConfirm={handleClearHistory}>
                <Button danger size="small">清空历史</Button>
              </Popconfirm>
            )}
          </Space>
          <Text strong>{history.label}</Text>
          {filteredHistoryItems.length ? (
            <List
              style={{ marginTop: 12 }}
              dataSource={filteredHistoryItems}
              renderItem={(item) => (
                <List.Item
                  actions={!USE_MOCK && item.id ? [
                    <Popconfirm key="delete" title="确定删除这条阅读记录？" onConfirm={() => handleDeleteHistory(item.id)}>
                      <Button type="link" danger size="small">删除</Button>
                    </Popconfirm>
                  ] : undefined}
                >
                  <PaperCard paper={USE_MOCK ? PAPERS[item.paper] : paperMap[item.paper]} compact />
                  <Text type="secondary" style={{ fontSize: 12 }}>{item.time} · {item.section} · {item.duration}</Text>
                </List.Item>
              )}
            />
          ) : <Empty style={{ marginTop: 20 }} description="暂无阅读记录" />}
        </>
      )
    },
    {
      key: 'wiki',
      label: '概念词典',
      children: USE_MOCK
        ? <Row gutter={[16, 16]}>{['Self-Attention', 'Pre-training', 'LoRA'].map((name) => <Col xs={24} sm={8} key={name}><Card hoverable size="small"><Text strong>{name}</Text><br /><Text type="secondary" style={{ fontSize: 12 }}>Wiki 词条</Text></Card></Col>)}</Row>
        : (
          <>
            <Space wrap style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
              <Input
                allowClear
                placeholder="搜索概念词条"
                value={dictSearch}
                onChange={(event) => setDictSearch(event.target.value)}
                style={{ width: 260 }}
              />
              <Popconfirm
                title="确定清空当前可见词条？"
                onConfirm={() => hideDictionaryTerms(filteredDictionary.map((item) => item.term))}
                disabled={!filteredDictionary.length}
              >
                <Button danger size="small" disabled={!filteredDictionary.length}>清空词典</Button>
              </Popconfirm>
            </Space>
            {filteredDictionary.length ? (
              <>
                <Row gutter={[16, 16]}>
                  {pagedDictionary.map((item) => (
                    <Col xs={24} sm={12} lg={8} key={item.term}>
                      <Card
                        hoverable
                        size="small"
                        extra={(
                          <Popconfirm title="确定隐藏该词条？" onConfirm={() => hideDictionaryTerms([item.term])}>
                            <Button type="link" danger size="small">删除</Button>
                          </Popconfirm>
                        )}
                      >
                        <Text strong>{item.term}</Text>
                        <Paragraph type="secondary" style={{ margin: '6px 0 0' }}>{item.description}</Paragraph>
                        <Text type="secondary" style={{ fontSize: 12 }}>来自 {item.paper_titles?.length || 0} 篇论文</Text>
                      </Card>
                    </Col>
                  ))}
                </Row>
                <div style={{ marginTop: 16, textAlign: 'right' }}>
                  <Pagination
                    current={dictPage}
                    pageSize={DICT_PAGE_SIZE}
                    total={filteredDictionary.length}
                    onChange={setDictPage}
                    showSizeChanger={false}
                  />
                </div>
              </>
            ) : <Empty description="解析论文后会自动生成概念词典" />}
          </>
        )
    },
    {
      key: 'profile',
      label: '个人画像',
      children: (
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Card title="兴趣主题" size="small">
              <Paragraph type="secondary" style={{ marginBottom: 8 }}>
                用于个性化推荐；可选择常见方向或自定义输入。
              </Paragraph>
              <Select
                mode="tags"
                style={{ width: '100%' }}
                placeholder="例如 cs.CL、Transformer"
                value={topics}
                options={TOPIC_OPTIONS.map((value) => ({ value, label: value }))}
                onChange={handleTopicsChange}
                tokenSeparators={[',']}
              />
              <div style={{ marginTop: 12 }}>
                <Text type="secondary">当前模式 </Text>
                <Tag color="processing">{profile?.persona || persona}</Tag>
              </div>
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card title="偏好设置" size="small">
              <Paragraph type="secondary" style={{ marginBottom: 8 }}>
                会参与「基于画像推荐」打分：开启「偏好有代码」时更倾向摘要中提到开源/代码的论文；关注作者/机构按逗号分隔，匹配作者名或摘要时加权。
              </Paragraph>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>偏好有代码</span>
                <Switch
                  checked={profile?.preferences?.code ?? true}
                  onChange={(checked) => {
                    updateLearningProfile(userId, { preferences: { ...(profile?.preferences || {}), code: checked } })
                      .then(setProfile);
                  }}
                />
              </div>
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">关注作者/机构</Text>
                <Input
                  placeholder="例如 Vaswani, Google, Stanford"
                  defaultValue={profile?.preferences?.authors || ''}
                  onBlur={(event) => updateLearningProfile(userId, {
                    preferences: { ...(profile?.preferences || {}), authors: event.target.value }
                  }).then(setProfile)}
                  style={{ marginTop: 4 }}
                />
              </div>
            </Card>
          </Col>
        </Row>
      )
    },
    {
      key: 'mode',
      label: '默认模式',
      children: <Card><Paragraph type="secondary">设置全局默认阅读模式；论文详情页可快捷切换</Paragraph><Segmented block options={PERSONAS} value={persona} onChange={handlePersonaChange} /><Paragraph style={{ marginTop: 16, padding: 12, background: '#fafafa' }}>{MODE_DESC[persona]}</Paragraph></Card>
    }
  ];

  return (
    <Card className="section-card">
      {error && <Alert type="error" showIcon message="学习数据加载失败" description={error} style={{ marginBottom: 16 }} />}
      <Tabs items={tabItems} />
    </Card>
  );
}
