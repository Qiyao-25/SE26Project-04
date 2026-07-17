import { useEffect, useMemo, useState } from 'react';
import { Card, Tabs, Row, Col, List, Tag, Typography, Segmented, Switch, Input, Empty, Spin, Alert } from 'antd';
import { READING_HISTORY, PERSONAS, MODE_DESC, PAPERS } from '../../data/papers';
import { useApp } from '../../context/AppContext';
import { getPaperDetail } from '../../services/paperService';
import { listActions } from '../../services/learningService';
import { USE_MOCK } from '../../services/runtimeConfig';
import PaperCard from '../../components/paper/PaperCard';

const { Text, Paragraph } = Typography;

function emptyLibrary() {
  return { favorites: [], notes: [], history: [] };
}

export default function LearningPage() {
  const { userId, persona, setPersona } = useApp();
  const [historyKey, setHistoryKey] = useState('today');
  const [library, setLibrary] = useState(emptyLibrary);
  const [paperMap, setPaperMap] = useState({});
  const [loading, setLoading] = useState(!USE_MOCK);
  const [error, setError] = useState('');

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
          history: actions.filter((action) => action.action_type === 'reading_history')
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
    const now = new Date();
    const today = now.toISOString().slice(0, 10);
    const yesterday = new Date(now.getTime() - 86400000).toISOString().slice(0, 10);
    const matches = {
      today: (item) => item.occurred_at?.slice(0, 10) === today,
      yesterday: (item) => item.occurred_at?.slice(0, 10) === yesterday,
      earlier: (item) => ![today, yesterday].includes(item.occurred_at?.slice(0, 10))
    };
    const items = library.history.filter(matches[historyKey]).map((item) => ({
      paper: String(item.paper_id),
      time: item.payload_json?.time || item.occurred_at?.slice(11, 16) || '',
      section: item.payload_json?.section || '论文主体',
      duration: item.payload_json?.duration || '已记录'
    }));
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
      children: <Row gutter={[16, 16]}>{['Self-Attention', 'Pre-training', 'LoRA'].map((name) => <Col xs={24} sm={8} key={name}><Card hoverable size="small"><Text strong>{name}</Text><br /><Text type="secondary" style={{ fontSize: 12 }}>Wiki 词条</Text></Card></Col>)}</Row>
    },
    {
      key: 'profile',
      label: '个人画像',
      children: <Row gutter={16}><Col xs={24} md={12}><Card title="画像标签（系统自动）" size="small"><div><Text type="secondary">常看方向</Text> <Tag>NLP</Tag><Tag>Transformer</Tag></div><div style={{ marginTop: 8 }}><Text type="secondary">偏好难度</Text> <Tag>中等偏高</Tag></div></Card></Col><Col xs={24} md={12}><Card title="手动微调" size="small"><div style={{ display: 'flex', justifyContent: 'space-between' }}><span>偏好有代码</span><Switch defaultChecked /></div><div style={{ marginTop: 8 }}><Text type="secondary">关注作者/机构</Text><Input defaultValue="Google, OpenAI" style={{ marginTop: 4 }} /></div></Card></Col></Row>
    },
    {
      key: 'mode',
      label: '默认模式',
      children: <Card><Paragraph type="secondary">设置全局默认阅读模式；论文详情页可快捷切换</Paragraph><Segmented block options={PERSONAS} value={persona} onChange={setPersona} /><Paragraph style={{ marginTop: 16, padding: 12, background: '#fafafa' }}>{MODE_DESC[persona]}</Paragraph></Card>
    }
  ];

  return (
    <Card className="section-card">
      {error && <Alert type="error" showIcon message="学习数据加载失败" description={error} style={{ marginBottom: 16 }} />}
      <Tabs items={tabItems} />
    </Card>
  );
}
