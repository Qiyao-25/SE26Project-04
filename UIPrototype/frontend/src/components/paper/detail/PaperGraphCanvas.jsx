import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

const TYPE_ORDER = ['paper', 'concept', 'method', 'dataset', 'task'];

const TYPE_LABELS = {
  paper: '论文',
  concept: '概念',
  method: '方法',
  dataset: '数据集',
  task: '研究领域'
};

const TYPE_COLORS = {
  paper: '#2563eb',
  concept: '#7c3aed',
  method: '#0f766e',
  dataset: '#c2410c',
  task: '#475569'
};

const TYPE_RADIUS = {
  paper: 42,
  concept: 28,
  method: 34,
  dataset: 38,
  task: 22
};

function buildLayout(nodes) {
  const current = nodes.find((node) => node.role === 'current') || nodes.find((node) => node.type === 'paper');
  const others = nodes.filter((node) => node !== current);
  const positions = new Map();
  if (current) positions.set(current.id, { x: 50, y: 50 });

  const groups = TYPE_ORDER.map((type) => others.filter((node) => node.type === type)).filter((group) => group.length);
  // Put untyped leftovers in the last ring.
  const leftovers = others.filter((node) => !TYPE_ORDER.includes(node.type));
  if (leftovers.length) groups.push(leftovers);

  groups.forEach((group, groupIndex) => {
    const sampleType = group[0]?.type;
    const radius = TYPE_RADIUS[sampleType] || 30 + groupIndex * 6;
    group.forEach((node, index) => {
      const angle = -Math.PI / 2 + ((index + 0.5) * 2 * Math.PI) / group.length;
      // Slight radial jitter by group so rings don't collide.
      const r = radius + (groupIndex % 2 === 0 ? 0 : 2);
      positions.set(node.id, {
        x: 50 + Math.cos(angle) * r,
        y: 50 + Math.sin(angle) * r
      });
    });
  });
  return positions;
}

export default function PaperGraphCanvas({ paperId, nodes = [], edges = [] }) {
  const navigate = useNavigate();
  const positions = useMemo(() => buildLayout(nodes), [nodes]);
  const nodeMap = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const currentNodeId = useMemo(() => {
    const current = nodes.find((node) => node.role === 'current') || nodes.find((node) => node.type === 'paper');
    return current?.id;
  }, [nodes]);
  const jumpablePapers = useMemo(
    () => nodes.filter((node) => node.paperId != null && String(node.paperId) !== String(paperId)),
    [nodes, paperId]
  );

  if (!nodes.length) {
    return <div className="paper-graph-empty">暂无足够的结构化实体，请先完成论文解析。</div>;
  }

  return (
    <div className="paper-graph-wrap">
      <div className="paper-graph-canvas" role="group" aria-label="论文知识图谱">
        <svg className="paper-graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="paper-graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
          </defs>
          {edges.map((edge) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) return null;
            return (
              <line
                key={edge.id}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke={edge.type === 'precedes' || edge.type === 'follows' ? '#f59e0b' : '#cbd5e1'}
                strokeWidth={edge.weight ? 0.8 + edge.weight * 1.2 : 0.9}
                markerEnd="url(#paper-graph-arrow)"
              />
            );
          })}
        </svg>

        {nodes.map((node) => {
          const position = positions.get(node.id);
          if (!position) return null;
          const canOpen = node.paperId != null && String(node.paperId) !== String(paperId);
          const isCurrent = node.id === currentNodeId;
          return (
            <button
              type="button"
              key={node.id}
              className={`paper-graph-node paper-graph-node-${node.type}${canOpen ? ' is-link' : ''}${isCurrent ? ' is-current' : ''}`}
              style={{ left: `${position.x}%`, top: `${position.y}%`, '--node-color': TYPE_COLORS[node.type] || '#64748b' }}
              title={node.description || node.label}
              onClick={() => canOpen && navigate(`/paper/${node.paperId}`)}
            >
              <span className="paper-graph-node-type">{TYPE_LABELS[node.type] || node.type}</span>
              <span className="paper-graph-node-label">{node.label}</span>
            </button>
          );
        })}
      </div>

      <div className="paper-graph-legend" aria-label="图谱节点类型">
        {TYPE_ORDER.filter((type) => nodes.some((node) => node.type === type)).map((type) => (
          <span key={type} className="paper-graph-legend-item">
            <i style={{ background: TYPE_COLORS[type] }} />
            {TYPE_LABELS[type]}
          </span>
        ))}
      </div>

      {jumpablePapers.length > 0 && (
        <div className="paper-graph-jumps" aria-label="可跳转相关论文">
          <span className="paper-graph-jumps-label">相关论文跳转</span>
          {jumpablePapers.map((node) => (
            <button
              key={`jump-${node.id}`}
              type="button"
              className="paper-graph-jump-chip"
              onClick={() => navigate(`/paper/${node.paperId}`)}
              title={node.label}
            >
              {node.label}
            </button>
          ))}
        </div>
      )}

      <div className="paper-graph-edge-list">
        {edges.slice(0, 12).map((edge) => (
          <span key={edge.id} title={(edge.evidence || []).join(', ')}>
            {nodeMap.get(edge.source)?.label || edge.source} <b>{edge.label || edge.type}</b> {nodeMap.get(edge.target)?.label || edge.target}
          </span>
        ))}
      </div>
    </div>
  );
}
