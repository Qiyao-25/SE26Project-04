import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const LANE_ORDER = [
  { key: 'related', title: '关联论文' },
  { key: 'concept', title: '核心概念' },
  { key: 'current', title: '当前论文' },
  { key: 'method', title: '方法' },
  { key: 'domain', title: '数据集/领域' },
];

const TYPE_LABELS = {
  paper: '论文',
  concept: '概念',
  method: '方法',
  dataset: '数据集',
  task: '研究领域',
};

const TYPE_COLORS = {
  paper: '#2563eb',
  concept: '#7c3aed',
  method: '#0f766e',
  dataset: '#c2410c',
  task: '#475569',
};

const CARD_W = 132;
const CARD_H = 56;
const COL_GAP = 28;
const ROW_GAP = 18;
const PAD_X = 24;
const PAD_Y = 48;

function laneOf(node) {
  if (node.lane) return node.lane;
  if (node.role === 'current') return 'current';
  if (node.type === 'concept') return 'concept';
  if (node.type === 'method') return 'method';
  if (node.type === 'dataset' || node.type === 'task') return 'domain';
  if (node.type === 'paper') return 'related';
  return 'domain';
}

function buildSwimlaneLayout(nodes) {
  const columns = LANE_ORDER.map((lane) => ({
    ...lane,
    nodes: nodes.filter((node) => laneOf(node) === lane.key),
  }));
  const maxRows = Math.max(1, ...columns.map((col) => col.nodes.length || 1));
  const width = PAD_X * 2 + LANE_ORDER.length * CARD_W + (LANE_ORDER.length - 1) * COL_GAP;
  const height = PAD_Y * 2 + maxRows * CARD_H + (maxRows - 1) * ROW_GAP;
  const positions = new Map();

  columns.forEach((col, colIndex) => {
    const x = PAD_X + colIndex * (CARD_W + COL_GAP);
    col.nodes.forEach((node, rowIndex) => {
      const y = PAD_Y + rowIndex * (CARD_H + ROW_GAP);
      positions.set(node.id, { x, y, cx: x + CARD_W / 2, cy: y + CARD_H / 2 });
    });
  });

  return { columns, positions, width, height };
}

function edgePath(sourcePos, targetPos) {
  const leftToRight = sourcePos.cx <= targetPos.cx;
  const x1 = leftToRight ? sourcePos.x + CARD_W : sourcePos.x;
  const y1 = sourcePos.cy;
  const x2 = leftToRight ? targetPos.x : targetPos.x + CARD_W;
  const y2 = targetPos.cy;
  const dx = Math.max(40, Math.abs(x2 - x1) * 0.45);
  const c1x = leftToRight ? x1 + dx : x1 - dx;
  const c2x = leftToRight ? x2 - dx : x2 + dx;
  return `M ${x1} ${y1} C ${c1x} ${y1}, ${c2x} ${y2}, ${x2} ${y2}`;
}

function isPrimaryEdge(edge) {
  if (edge.tier === 'primary') return true;
  if (edge.tier === 'secondary') return false;
  return Number(edge.weight || 1) >= 0.35 || ['introduces', 'uses', 'evaluates_on', 'in_domain'].includes(edge.type);
}

export default function PaperGraphCanvas({ paperId, nodes = [], edges = [] }) {
  const navigate = useNavigate();
  const [activeId, setActiveId] = useState(null);
  const { columns, positions, width, height } = useMemo(() => buildSwimlaneLayout(nodes), [nodes]);
  const nodeMap = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const currentNodeId = useMemo(() => {
    const current = nodes.find((node) => node.role === 'current') || nodes.find((node) => node.type === 'paper');
    return current?.id;
  }, [nodes]);

  const visibleEdges = useMemo(() => {
    if (!activeId) {
      return edges.filter(isPrimaryEdge);
    }
    return edges.filter((edge) => edge.source === activeId || edge.target === activeId || isPrimaryEdge(edge));
  }, [activeId, edges]);

  const highlighted = useMemo(() => {
    if (!activeId) return new Set();
    const ids = new Set([activeId]);
    edges.forEach((edge) => {
      if (edge.source === activeId) ids.add(edge.target);
      if (edge.target === activeId) ids.add(edge.source);
    });
    return ids;
  }, [activeId, edges]);

  if (!nodes.length) {
    return <div className="paper-graph-empty">暂无足够的结构化实体，请先完成论文解析。</div>;
  }

  return (
    <div className="paper-graph-wrap">
      <div className="paper-graph-hint">
        默认显示当前论文与实体的主关系；点击节点可高亮其二级关系。卡片按五列泳道排列，避免相互遮挡。
      </div>
      <div
        className="paper-graph-canvas paper-graph-canvas-swim"
        style={{ width: '100%', height: Math.max(320, height + 24) }}
        role="group"
        aria-label="论文知识图谱"
        onClick={() => setActiveId(null)}
      >
        <svg
          className="paper-graph-edges"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMin meet"
          aria-hidden="true"
        >
          <defs>
            <marker id="paper-graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
          </defs>
          {LANE_ORDER.map((lane, index) => {
            const x = PAD_X + index * (CARD_W + COL_GAP) + CARD_W / 2;
            return (
              <text key={lane.key} x={x} y={22} textAnchor="middle" className="paper-graph-lane-title">
                {lane.title}
              </text>
            );
          })}
          {visibleEdges.map((edge) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) return null;
            const focused = activeId && (edge.source === activeId || edge.target === activeId);
            const secondary = !isPrimaryEdge(edge);
            return (
              <path
                key={edge.id}
                d={edgePath(source, target)}
                fill="none"
                stroke={focused ? '#2563eb' : edge.type === 'precedes' || edge.type === 'follows' ? '#f59e0b' : '#cbd5e1'}
                strokeWidth={focused ? 2.2 : secondary ? 1.2 : 1.6}
                strokeOpacity={activeId && !focused ? 0.25 : secondary ? 0.7 : 0.95}
                markerEnd="url(#paper-graph-arrow)"
              />
            );
          })}
        </svg>

        {nodes.map((node) => {
          const position = positions.get(node.id);
          if (!position) return null;
          const canOpen = (node.paperId ?? node.paper_id) != null && String(node.paperId ?? node.paper_id) !== String(paperId);
          const isCurrent = node.id === currentNodeId;
          const dimmed = activeId && !highlighted.has(node.id);
          const targetPaperId = node.paperId ?? node.paper_id;
          return (
            <button
              type="button"
              key={node.id}
              className={`paper-graph-node paper-graph-node-card paper-graph-node-${node.type}${canOpen ? ' is-link' : ''}${isCurrent ? ' is-current' : ''}${dimmed ? ' is-dimmed' : ''}${activeId === node.id ? ' is-active' : ''}`}
              style={{
                left: position.x,
                top: position.y,
                width: CARD_W,
                height: CARD_H,
                '--node-color': TYPE_COLORS[node.type] || '#64748b',
              }}
              title={node.description || node.label}
              onClick={(event) => {
                event.stopPropagation();
                setActiveId((current) => (current === node.id ? null : node.id));
                if (canOpen && activeId === node.id) navigate(`/paper/${targetPaperId}`);
              }}
              onDoubleClick={(event) => {
                event.stopPropagation();
                if (canOpen) navigate(`/paper/${targetPaperId}`);
              }}
            >
              <span className="paper-graph-node-type">{TYPE_LABELS[node.type] || node.type}</span>
              <span className="paper-graph-node-label">{node.label}</span>
            </button>
          );
        })}
      </div>

      <div className="paper-graph-legend" aria-label="图谱节点类型">
        {Object.keys(TYPE_LABELS).filter((type) => nodes.some((node) => node.type === type)).map((type) => (
          <span key={type} className="paper-graph-legend-item">
            <i style={{ background: TYPE_COLORS[type] }} />
            {TYPE_LABELS[type]}
          </span>
        ))}
      </div>

      <div className="paper-graph-edge-list">
        {(activeId ? edges.filter((edge) => edge.source === activeId || edge.target === activeId) : edges.filter(isPrimaryEdge))
          .slice(0, 16)
          .map((edge) => (
            <span key={edge.id} title={(edge.evidence || []).join(', ')}>
              {nodeMap.get(edge.source)?.label || edge.source}
              {' '}
              <b>{edge.label || edge.type}</b>
              {' '}
              {nodeMap.get(edge.target)?.label || edge.target}
            </span>
          ))}
      </div>
    </div>
  );
}
