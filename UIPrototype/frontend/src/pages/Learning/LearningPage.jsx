import { useEffect, useMemo, useState } from 'react';
import { Card, Tabs, Row, Col, List, Tag, Typography, Segmented, Switch, Input, Select, Empty, Spin, Alert, message } from 'antd';
import { READING_HISTORY, PERSONAS, MODE_DESC, PAPERS } from '../../data/papers';
import { useApp } from '../../context/AppContext';
import { getPaperDetail } from '../../services/paperService';
import { getConceptDictionary, getLearningProfile, listActions, updateLearningProfile } from '../../services/learningService';
import { USE_MOCK } from '../../services/runtimeConfig';
import { formatDateKey, parseApiDate } from '../../utils/datetime';
import PaperCard from '../../components/paper/PaperCard';

const { Text, Paragraph } = Typography;

const TOPIC_OPTIONS = ['cs.AI', 'cs.CL', 'cs.CV', 'cs.LG', 'cs.IR', 'cs.SE', 'Transformer', 'RAG', 'LLM', 'Diffusion'];

function emptyLibrary() {
  return { favorites: [], notes: [], history: [] };
}

export default function LearningPage() {
  const { userId, persona, setPersona, topics, setTopics } = useApp();
  const [historyKey, setHistoryKey] = useState('today');
  const [library, setLibrary] = useState(emptyLibrary);
  const [paperMap, setPaperMap] = useState({});
  const [loading, setLoading] = useState(!USE_MOCK);
  const [error, setError] = useState('');
  const [profile, setProfile] = useState(null);
  const [dictionary, setDictionary] = useState([]);

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
  }, [userId]);

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
      { paperId: 'attention', paper: PAPERS.attention, text: '核心创新在于完全用注意力替代 RNN', date: '2026-07-01' },
      { paperId: 'bert', paper: PAPERS.bert, text: '预训练-微调范式的里程碑', date: '2026-06-18' }
    ]
    : library.notes.map((item) => ({
      paperId: item.paper_id,
      paper: paperMap[String(item.paper_id)],
      text: item.payload_json?.text || '',
      date: item.occurred_at?.slice(0, 10) || ''
    }));
  const history = USE_MOCK ? mockHistory : apiHistory;

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
      children: notes.length ? (
        <List
          dataSource={notes.filter((item) => item.paper)}
          locale={{ emptyText: '暂无笔记或评论' }}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                title={item.paper.title}
                description={<>{item.text} · <Text type="secondary">{item.date}</Text></>}
              />
            </List.Item>
          )}
        />
      ) : <Empty description="暂无笔记或评论" />
    },
    {
      key: 'history',
      label: '阅读历史',
      children: (
        <>
          <Segmented
            options={[{ value: 'today', label: '今天' }, { value: 'yesterday', label: '昨天' }, { value: 'earlier', label: '更早' }]}
            value={historyKey}
            onChange={setHistoryKey}
            style={{ marginBottom: 16 }}
          />
          <Text strong>{history.label}</Text>
          {history.items.length ? (
            <List
              style={{ marginTop: 12 }}
              dataSource={history.items}
              renderItem={(item) => (
                <List.Item>
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
        : dictionary.length
          ? <Row gutter={[16, 16]}>{dictionary.map((item) => <Col xs={24} sm={12} lg={8} key={item.term}><Card hoverable size="small"><Text strong>{item.term}</Text><Paragraph type="secondary" style={{ margin: '6px 0 0' }}>{item.description}</Paragraph><Text type="secondary" style={{ fontSize: 12 }}>来自 {item.paper_titles?.length || 0} 篇论文</Text></Card></Col>)}</Row>
          : <Empty description="解析论文后会自动生成概念词典" />
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
