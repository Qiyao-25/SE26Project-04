import { useEffect, useState } from 'react';
import { Select, Button, Typography, Tag, Row, Col, message } from 'antd';
import { SwapOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../../../context/AppContext';
import { PAPER_LIST, PAPERS, shortPaperTitle } from '../../../../data/papers';
import { getPaperDetail } from '../../../../services/paperService';

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

const EMPTY_PAPER = { title: '论文加载中', authors: [], keywords: [], conceptTags: [] };

export default function SidebarComparePanel({ paperId, paper }) {
  const navigate = useNavigate();
  const {
    comparePaperA, comparePaperB, compareActiveSlot, setCompareActiveSlot,
    setComparePaperA, setComparePaperB
  } = useApp();
  const [remotePapers, setRemotePapers] = useState({});

  useEffect(() => {
    let cancelled = false;
    const ids = [comparePaperA, comparePaperB].filter((id) => /^\d+$/.test(String(id)) && String(id) !== String(paperId));
    if (!ids.length) return undefined;
    Promise.all(ids.map(async (id) => [String(id), await getPaperDetail(id)]))
      .then((entries) => {
        if (!cancelled) setRemotePapers((current) => ({ ...current, ...Object.fromEntries(entries) }));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [comparePaperA, comparePaperB, paperId]);

  const resolvePaper = (id) => {
    if (String(id) === String(paperId)) return paper || EMPTY_PAPER;
    return PAPERS[id] || remotePapers[String(id)] || EMPTY_PAPER;
  };
  const paperA = resolvePaper(comparePaperA);
  const paperB = resolvePaper(comparePaperB);
  const options = PAPER_LIST.map((p) => ({ value: p.id, label: shortPaperTitle(p.id) }));
  if (/^\d+$/.test(String(paperId)) && !options.some((option) => String(option.value) === String(paperId))) {
    options.unshift({ value: paperId, label: paper?.title || `论文 ${paperId}` });
  }

  const setSlotPaper = (slot, id) => {
    if (slot === 'a') {
      setComparePaperA(id);
      if (comparePaperB === id) setComparePaperB(paperId);
    } else {
      setComparePaperB(id);
      if (comparePaperA === id) setComparePaperA(paperId);
    }
  };

  const swap = () => {
    setComparePaperA(comparePaperB);
    setComparePaperB(comparePaperA);
    message.success('已互换对比论文');
  };

  return (
    <div className="sidebar-scroll">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong>对比阅读</Text>
        <Button size="small" icon={<SwapOutlined />} onClick={swap}>互换</Button>
      </div>
      <Text type="secondary" style={{ fontSize: 12 }}>先选 A/B 栏，再点下方论文快捷切换</Text>

      <Row gutter={8} style={{ marginTop: 12 }}>
        <Col span={12}>
          <div className={`compare-slot ${compareActiveSlot === 'a' ? 'active' : ''}`} onClick={() => setCompareActiveSlot('a')}>
            <Text className="block-label">论文 A</Text>
            <Select size="small" style={{ width: '100%' }} value={comparePaperA} options={options}
              onChange={(v) => setComparePaperA(v)} onClick={(e) => e.stopPropagation()} />
          </div>
        </Col>
        <Col span={12}>
          <div className={`compare-slot ${compareActiveSlot === 'b' ? 'active' : ''}`} onClick={() => setCompareActiveSlot('b')}>
            <Text className="block-label">论文 B</Text>
            <Select size="small" style={{ width: '100%' }} value={comparePaperB} options={options}
              onChange={(v) => setComparePaperB(v)} onClick={(e) => e.stopPropagation()} />
          </div>
        </Col>
      </Row>

      <div style={{ marginTop: 12 }}>
        {PAPER_LIST.map((p) => (
          <Tag
            key={p.id}
            style={{ marginBottom: 4, cursor: 'pointer' }}
            color={p.id === comparePaperA ? 'blue' : p.id === comparePaperB ? 'default' : undefined}
            onClick={() => setSlotPaper(compareActiveSlot, p.id)}
          >
            {shortPaperTitle(p.id)}
          </Tag>
        ))}
      </div>

      <div className="compare-body" style={{ marginTop: 12 }}>
        {ROWS.map((row) => {
          const va = row.fmt ? row.fmt(paperA) : paperA[row.key];
          const vb = row.fmt ? row.fmt(paperB) : paperB[row.key];
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
