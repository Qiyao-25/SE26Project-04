import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

/** Theme lines (metro colors) */
const LINES = {
  method: { key: 'method', title: '模型结构 / 方法', color: '#2563eb', dash: false },
  concept: { key: 'concept', title: '核心概念', color: '#7c3aed', dash: false },
  training: { key: 'training', title: '训练与优化', color: '#059669', dash: false },
  experiment: { key: 'experiment', title: '实验 / 数据集 / 评测', color: '#ea580c', dash: false },
  topic: { key: 'topic', title: '主题相关（非引用）', color: '#94a3b8', dash: true },
};

const TYPE_LABELS = {
  paper: '论文',
  concept: '概念',
  method: '方法',
  dataset: '数据集',
  task: '领域',
  training: '训练',
};

const LIMITS = {
  concept: 6,
  method: 5,
  dataset: 3,
  paper: 5,
};

const MIN_NODE_W = 150;
const FONT_MIN = 12;
const PAPER_SCORE_MIN = 0.28;

const TRAINING_HINTS = [
  'train', 'optim', 'loss', 'gradient', 'fine-tun', 'finetun', '学习率', '优化', '训练',
  'adam', 'sgd', '正则', 'dropout', 'warm', 'schedul', '蒸馏', 'distill', 'rlhf', 'reward',
];

function normalizeName(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ');
}

function isTrainingMethod(node) {
  const text = `${node.label || ''} ${node.description || ''}`.toLowerCase();
  return TRAINING_HINTS.some((hint) => text.includes(hint));
}

function themeOf(node) {
  if (node.type === 'concept') return 'concept';
  if (node.type === 'dataset' || node.type === 'task') return 'experiment';
  if (node.type === 'method') return isTrainingMethod(node) ? 'training' : 'method';
  if (node.type === 'paper' && (node.role === 'related' || node.relationKind === 'topic')) return 'topic';
  return null;
}

function relationKind(edge) {
  if (edge.type === 'precedes' || edge.type === 'follows') return 'lineage';
  if (edge.type === 'related_to') return 'topic';
  if (['introduces', 'uses', 'evaluates_on', 'in_domain', 'implements'].includes(edge.type)) return 'theme';
  return Number(edge.weight || 0) >= 0.35 ? 'theme' : 'topic';
}

function isCanvasEdge(edge) {
  // Topic-related edges stay on canvas as gray dashed — never styled as citations
  if (relationKind(edge) === 'topic' || edge.type === 'related_to') return true;
  if (edge.tier === 'secondary' && edge.type === 'implements') return false;
  if (edge.tier === 'secondary' && Number(edge.weight || 0) < 0.35) return false;
  return true;
}

function isPrimaryListEdge(edge) {
  if (relationKind(edge) === 'topic') return false;
  return isCanvasEdge(edge) || edge.type === 'implements';
}

/**
 * Deduplicate, cap counts, keep one best method↔concept link, split weak topic edges off canvas.
 */
function prepareGraph(rawNodes = [], rawEdges = []) {
  const byType = { paper: [], concept: [], method: [], dataset: [], task: [] };
  const seen = new Map();

  for (const node of rawNodes) {
    const type = byType[node.type] ? node.type : null;
    if (!type) continue;
    const key = `${type}:${normalizeName(node.label)}`;
    if (seen.has(key)) continue;
    seen.set(key, true);
    byType[type].push({ ...node });
  }

  const current =
    byType.paper.find((n) => n.role === 'current') ||
    byType.paper[0] ||
    null;

  const relatedPapers = byType.paper
    .filter((n) => n.id !== current?.id)
    .map((n) => {
      const score = Number(n.score ?? 0);
      const role = n.role || 'related';
      const relationKindValue =
        role === 'predecessor' || role === 'successor' ? 'lineage' : 'topic';
      return {
        ...n,
        score,
        relationKind: relationKindValue,
        role: score < PAPER_SCORE_MIN && role !== 'predecessor' && role !== 'successor' ? 'related' : role,
      };
    })
    .filter((n) => {
      if (n.role === 'predecessor' || n.role === 'successor') return Number(n.score ?? 1) >= 0.18;
      return Number(n.score ?? 0) >= PAPER_SCORE_MIN;
    })
    .sort((a, b) => Number(b.score || 0) - Number(a.score || 0))
    .slice(0, LIMITS.paper);

  const concepts = byType.concept.slice(0, LIMITS.concept);
  const methods = byType.method.slice(0, LIMITS.method).map((n) => ({
    ...n,
    theme: isTrainingMethod(n) ? 'training' : 'method',
  }));
  const datasets = [...byType.dataset, ...byType.task].slice(0, LIMITS.dataset);

  const nodes = [
    ...(current ? [{ ...current, role: 'current', size: 'hub' }] : []),
    ...relatedPapers.map((n) => ({ ...n, size: 'paper' })),
    ...concepts.map((n) => ({ ...n, size: 'entity', theme: 'concept' })),
    ...methods.map((n) => ({ ...n, size: 'entity', theme: n.theme })),
    ...datasets.map((n) => ({ ...n, size: 'entity', theme: 'experiment' })),
  ];
  const nodeIds = new Set(nodes.map((n) => n.id));

  const edges = (rawEdges || [])
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({ ...e, kind: relationKind(e) }));

  // Each method keeps only its strongest concept link
  const methodConcept = edges
    .filter((e) => e.type === 'implements')
    .sort((a, b) => Number(b.weight || 0) - Number(a.weight || 0));
  const bestByMethod = new Map();
  for (const edge of methodConcept) {
    const methodId = nodes.find((n) => n.id === edge.source)?.type === 'method' ? edge.source : edge.target;
    if (!bestByMethod.has(methodId)) bestByMethod.set(methodId, edge.id);
  }

  const filteredEdges = edges.filter((e) => {
    if (e.type !== 'implements') return true;
    const methodId = nodes.find((n) => n.id === e.source)?.type === 'method' ? e.source : e.target;
    return bestByMethod.get(methodId) === e.id;
  });

  const canvasEdges = filteredEdges.filter(isCanvasEdge);
  // Promote the single best method-concept link onto canvas as a transfer hint
  for (const edge of filteredEdges) {
    if (edge.type === 'implements' && bestByMethod.get(edge.source) === edge.id) {
      if (!canvasEdges.some((e) => e.id === edge.id)) {
        canvasEdges.push({ ...edge, tier: 'primary', kind: 'theme' });
      }
    }
  }

  const listEdges = filteredEdges
    .slice()
    .sort((a, b) => Number(b.weight || 0) - Number(a.weight || 0));

  return { nodes, canvasEdges, listEdges, currentId: current?.id || null };
}

function nodeSize(node, mode) {
  if (node.role === 'current') {
    return { w: mode === 'mobile' ? 168 : 200, h: mode === 'mobile' ? 76 : 88 };
  }
  if (node.type === 'paper') {
    return { w: Math.max(MIN_NODE_W, mode === 'mobile' ? 156 : 172), h: mode === 'mobile' ? 64 : 70 };
  }
  return { w: Math.max(MIN_NODE_W, mode === 'mobile' ? 150 : 156), h: mode === 'mobile' ? 48 : 52 };
}

function sortPapersByTime(papers, direction) {
  return [...papers].sort((a, b) => {
    const da = Date.parse(a.publishedAt || a.published_at || '') || 0;
    const db = Date.parse(b.publishedAt || b.published_at || '') || 0;
    if (da && db && da !== db) return direction === 'asc' ? da - db : db - da;
    return Number(b.score || 0) - Number(a.score || 0);
  });
}

/**
 * Container-driven metro layout. Same coordinate system for SVG edges and HTML stations.
 */
function buildMetroLayout(nodes, canvasEdges, width, mode) {
  const padX = mode === 'mobile' ? 16 : 28;
  const padY = mode === 'mobile' ? 56 : 48;
  const hubGapX = mode === 'mobile' ? 28 : 40;
  const stationGapY = 18;

  const current = nodes.find((n) => n.role === 'current');
  const predecessors = sortPapersByTime(
    nodes.filter((n) => n.role === 'predecessor'),
    'asc',
  );
  const successors = sortPapersByTime(
    nodes.filter((n) => n.role === 'successor'),
    'asc',
  );
  const topicPapers = nodes.filter((n) => n.type === 'paper' && n.role === 'related');

  const byTheme = {
    concept: nodes.filter((n) => n.theme === 'concept'),
    method: nodes.filter((n) => n.theme === 'method'),
    training: nodes.filter((n) => n.theme === 'training'),
    experiment: nodes.filter((n) => n.theme === 'experiment'),
  };

  const positions = new Map();
  const boxes = new Map();
  const place = (node, x, y) => {
    const size = nodeSize(node, mode);
    positions.set(node.id, { x, y, cx: x + size.w / 2, cy: y + size.h / 2, ...size });
    boxes.set(node.id, { x, y, w: size.w, h: size.h });
  };

  let contentH = padY;
  let contentW = Math.max(width, mode === 'mobile' ? 360 : 640);

  if (mode === 'mobile') {
    // Vertical stage map: 前驱 → 当前(换乘) → 主题线分组 → 后续
    let y = padY;
    const colX = padX;

    predecessors.forEach((node) => {
      place(node, colX, y);
      y += nodeSize(node, mode).h + stationGapY;
    });

    if (current) {
      place(current, colX, y);
      y += nodeSize(current, mode).h + stationGapY + 8;
    }

    const themeOrder = ['concept', 'method', 'training', 'experiment'];
    themeOrder.forEach((theme) => {
      const list = byTheme[theme];
      if (!list.length) return;
      list.forEach((node) => {
        place(node, colX + 12, y);
        y += nodeSize(node, mode).h + stationGapY;
      });
      y += 10;
    });

    topicPapers.forEach((node) => {
      place(node, colX + 12, y);
      y += nodeSize(node, mode).h + stationGapY;
    });

    successors.forEach((node) => {
      place(node, colX, y);
      y += nodeSize(node, mode).h + stationGapY;
    });

    contentH = y + padY;
    contentW = Math.max(width, padX * 2 + MIN_NODE_W + 24);
  } else {
    // Desktop / tablet: horizontal timeline spine + parallel theme tracks
    const hubSize = current ? nodeSize(current, mode) : { w: 200, h: 88 };
    const leftPapers = predecessors;
    const rightPapers = successors;

    const leftBlockW = leftPapers.reduce((sum, n, i) => sum + nodeSize(n, mode).w + (i ? hubGapX : 0), 0);

    const trackList = [];
    if (byTheme.concept.length) trackList.push({ key: 'concept', nodes: byTheme.concept });
    if (byTheme.method.length) trackList.push({ key: 'method', nodes: byTheme.method });
    trackList.push({ key: 'spine', nodes: [] });
    if (byTheme.training.length) trackList.push({ key: 'training', nodes: byTheme.training });
    if (byTheme.experiment.length) trackList.push({ key: 'experiment', nodes: byTheme.experiment });

    const spineIndex = trackList.findIndex((t) => t.key === 'spine');
    const aboveTracks = trackList.slice(0, spineIndex).reverse();
    const belowTracks = trackList.slice(spineIndex + 1);

    // Place spine papers centered horizontally
    const hubX = Math.max(
      padX + leftBlockW + (leftBlockW ? hubGapX : 0),
      Math.max(padX, (width - hubSize.w) / 2),
    );
    // Provisional spine Y — will expand with theme stacks
    let spineY = padY + 40;
    const aboveHeight = aboveTracks.reduce(
      (sum, track) => sum + track.nodes.reduce((s, n) => s + nodeSize(n, mode).h + stationGapY, 0) + 12,
      0,
    );
    spineY = padY + aboveHeight + hubSize.h / 2;

    let x = hubX - (leftBlockW ? hubGapX : 0) - leftBlockW;
    leftPapers.forEach((node) => {
      const size = nodeSize(node, mode);
      place(node, x, spineY - size.h / 2);
      x += size.w + hubGapX;
    });
    if (current) {
      place(current, hubX, spineY - hubSize.h / 2);
    }
    x = hubX + hubSize.w + hubGapX;
    rightPapers.forEach((node) => {
      const size = nodeSize(node, mode);
      place(node, x, spineY - size.h / 2);
      x += size.w + hubGapX;
    });

    const hubCx = hubX + hubSize.w / 2;
    const usableW = Math.max(MIN_NODE_W, width - padX * 2);

    const placeThemeRow = (tracks, direction) => {
      let cursor = direction === 'up'
        ? spineY - hubSize.h / 2 - stationGapY - 8
        : spineY + hubSize.h / 2 + stationGapY + 8;

      tracks.forEach((track) => {
        const count = track.nodes.length;
        track.nodes.forEach((node, i) => {
          const size = nodeSize(node, mode);
          // Spread along a dedicated track row — fixed vertical pitch, horizontal spread
          const y = direction === 'up' ? cursor - size.h : cursor;
          const spread = Math.min(size.w + 20, Math.floor(usableW / Math.max(count, 1)));
          const rowWidth = spread * count - (spread - size.w);
          const startX = Math.max(padX, Math.min(width - padX - rowWidth, hubCx - rowWidth / 2));
          const xPos = startX + i * spread;
          place(node, xPos, y);
        });
        const rowH = Math.max(...track.nodes.map((n) => nodeSize(n, mode).h), 52);
        cursor = direction === 'up'
          ? cursor - rowH - stationGapY - 10
          : cursor + rowH + stationGapY + 10;
      });
    };

    placeThemeRow(aboveTracks, 'up');
    placeThemeRow(belowTracks, 'down');

    // Topic-related papers: lower gray spur — not on the citation spine
    if (topicPapers.length) {
      let topicY = Math.max(
        ...[...boxes.values()].map((b) => b.y + b.h),
        spineY + hubSize.h / 2,
      ) + 36;
      let topicX = Math.max(padX, hubX - 20);
      topicPapers.forEach((node) => {
        const size = nodeSize(node, mode);
        if (topicX + size.w > width - padX) {
          topicX = Math.max(padX, hubX - 20);
          topicY += size.h + stationGapY;
        }
        place(node, topicX, topicY);
        topicX += size.w + hubGapX;
      });
    }

    const allBoxes = [...boxes.values()];
    if (!allBoxes.length) {
      contentH = padY * 2 + 120;
      contentW = Math.max(width, 640);
    } else {
      const maxX = Math.max(...allBoxes.map((b) => b.x + b.w), hubX + hubSize.w);
      const minY = Math.min(...allBoxes.map((b) => b.y), spineY);
      if (minY < padY) {
        const dy = padY - minY;
        for (const [id, pos] of positions) {
          positions.set(id, { ...pos, y: pos.y + dy, cy: pos.cy + dy });
          const box = boxes.get(id);
          boxes.set(id, { ...box, y: box.y + dy });
        }
      }
      contentH = Math.max(...[...boxes.values()].map((b) => b.y + b.h)) + padY + 24;
      contentW = Math.max(width, maxX + padX, 640);
    }
  }

  // Line tracks metadata for drawing
  const tracksMeta = [];
  if (current && positions.has(current.id)) {
    const hub = positions.get(current.id);
    ['concept', 'method', 'training', 'experiment'].forEach((theme) => {
      const themed = byTheme[theme].filter((n) => positions.has(n.id));
      if (!themed.length) return;
      const ys = themed.map((n) => positions.get(n.id).cy);
      tracksMeta.push({
        key: theme,
        color: LINES[theme].color,
        y: ys.reduce((a, b) => a + b, 0) / ys.length,
        x1: Math.min(hub.cx, ...themed.map((n) => positions.get(n.id).cx)) - 40,
        x2: Math.max(hub.cx, ...themed.map((n) => positions.get(n.id).cx)) + 40,
      });
    });
  }

  return {
    positions,
    boxes,
    width: contentW,
    height: Math.max(contentH, mode === 'mobile' ? 420 : 360),
    tracksMeta,
    mode,
  };
}

/** Edge anchors on node box borders; smooth cubic that stays outside cards. */
function edgePath(sourceBox, targetBox) {
  const scx = sourceBox.x + sourceBox.w / 2;
  const scy = sourceBox.y + sourceBox.h / 2;
  const tcx = targetBox.x + targetBox.w / 2;
  const tcy = targetBox.y + targetBox.h / 2;

  const dx = tcx - scx;
  const dy = tcy - scy;
  let x1;
  let y1;
  let x2;
  let y2;

  if (Math.abs(dx) >= Math.abs(dy)) {
    x1 = dx >= 0 ? sourceBox.x + sourceBox.w : sourceBox.x;
    y1 = scy;
    x2 = dx >= 0 ? targetBox.x : targetBox.x + targetBox.w;
    y2 = tcy;
  } else {
    x1 = scx;
    y1 = dy >= 0 ? sourceBox.y + sourceBox.h : sourceBox.y;
    x2 = tcx;
    y2 = dy >= 0 ? targetBox.y : targetBox.y + targetBox.h;
  }

  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  // Orthogonal-ish cubic: control points keep the stroke from cutting through cards
  if (Math.abs(dx) >= Math.abs(dy)) {
    return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
  }
  return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
}

function strokeForEdge(edge, nodeMap) {
  if (edge.kind === 'topic' || edge.type === 'related_to') {
    return { color: LINES.topic.color, dash: '6 5', width: 1.4 };
  }
  if (edge.type === 'precedes' || edge.type === 'follows') {
    return { color: '#475569', dash: '', width: 2 };
  }
  const target = nodeMap.get(edge.target);
  const source = nodeMap.get(edge.source);
  const theme = target?.theme || source?.theme || themeOf(target) || themeOf(source);
  if (theme && LINES[theme]) {
    return { color: LINES[theme].color, dash: '', width: 1.8 };
  }
  return { color: '#94a3b8', dash: '', width: 1.5 };
}

function useContainerSize(ref) {
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const update = (entry) => {
      const rect = entry?.contentRect || el.getBoundingClientRect();
      setSize({
        width: Math.max(280, Math.floor(rect.width)),
        height: Math.floor(rect.height),
      });
    };
    update();
    if (typeof ResizeObserver === 'undefined') {
      const onResize = () => update();
      window.addEventListener('resize', onResize);
      return () => window.removeEventListener('resize', onResize);
    }
    const ro = new ResizeObserver((entries) => update(entries[0]));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);

  return size;
}

function layoutMode(width) {
  if (width < 640) return 'mobile';
  if (width < 960) return 'medium';
  return 'desktop';
}

export default function PaperGraphCanvas({ paperId, nodes = [], edges = [] }) {
  const navigate = useNavigate();
  const shellRef = useRef(null);
  const { width: containerW } = useContainerSize(shellRef);
  const [activeId, setActiveId] = useState(null);
  const [hoverId, setHoverId] = useState(null);

  const prepared = useMemo(() => prepareGraph(nodes, edges), [nodes, edges]);
  const mode = layoutMode(containerW || 960);

  const layout = useMemo(() => {
    if (!prepared.nodes.length || !containerW) {
      return { positions: new Map(), boxes: new Map(), width: 640, height: 360, tracksMeta: [], mode };
    }
    return buildMetroLayout(prepared.nodes, prepared.canvasEdges, containerW, mode);
  }, [prepared, containerW, mode]);

  const nodeMap = useMemo(
    () => new Map(prepared.nodes.map((n) => [n.id, n])),
    [prepared.nodes],
  );

  const focusId = hoverId || activeId;

  const highlighted = useMemo(() => {
    if (!focusId) return new Set();
    const ids = new Set([focusId]);
    prepared.listEdges.forEach((edge) => {
      if (edge.source === focusId) ids.add(edge.target);
      if (edge.target === focusId) ids.add(edge.source);
    });
    return ids;
  }, [focusId, prepared.listEdges]);

  const highlightedLines = useMemo(() => {
    if (!focusId) return new Set();
    const set = new Set();
    const node = nodeMap.get(focusId);
    if (node?.theme) set.add(node.theme);
    if (node?.role === 'related') set.add('topic');
    prepared.listEdges.forEach((edge) => {
      if (edge.source !== focusId && edge.target !== focusId) return;
      const other = nodeMap.get(edge.source === focusId ? edge.target : edge.source);
      if (other?.theme) set.add(other.theme);
      if (other?.role === 'related' || edge.kind === 'topic') set.add('topic');
    });
    return set;
  }, [focusId, nodeMap, prepared.listEdges]);

  const visibleCanvasEdges = useMemo(() => {
    const base = prepared.canvasEdges;
    if (!focusId) return base;
    const related = prepared.listEdges.filter(
      (e) => e.source === focusId || e.target === focusId,
    );
    const ids = new Set(base.map((e) => e.id));
    const merged = [...base];
    related.forEach((e) => {
      if (!ids.has(e.id)) merged.push(e);
    });
    return merged;
  }, [focusId, prepared.canvasEdges, prepared.listEdges]);

  if (!nodes.length) {
    return <div className="paper-graph-empty">暂无足够的结构化实体，请先完成论文解析。</div>;
  }

  return (
    <div className="paper-graph-wrap paper-graph-metro">
      <div className="paper-graph-hint">
        地铁线路图式研究脉络：横轴为前驱 → 当前论文 → 后续；彩色线路表示概念、方法、训练与评测维度。
        灰色虚线仅为主题相关，不是真实引用。悬浮高亮直接关系；点击其他论文可跳转详情。
      </div>

      <div className="paper-graph-legend" aria-label="线路与站点图例">
        {Object.values(LINES).map((line) => (
          <span key={line.key} className="paper-graph-legend-item">
            <i
              className={line.dash ? 'is-dash' : ''}
              style={{ background: line.dash ? 'transparent' : line.color, borderColor: line.color }}
            />
            {line.title}
          </span>
        ))}
        <span className="paper-graph-legend-item">
          <i className="is-hub" />
          当前论文（换乘站）
        </span>
        <span className="paper-graph-legend-item">
          <i className="is-paper" />
          相关论文站点
        </span>
        <span className="paper-graph-legend-item">
          <i className="is-entity" />
          概念 / 方法 / 数据站点
        </span>
      </div>

      <div
        ref={shellRef}
        className={`paper-graph-canvas paper-graph-canvas-metro is-${mode}`}
        style={{
          width: '100%',
          height: Math.min(Math.max(layout.height + 8, 320), mode === 'mobile' ? 720 : 820),
          fontSize: FONT_MIN,
        }}
        role="group"
        aria-label="论文研究脉络地铁图"
        onClick={() => setActiveId(null)}
      >
        <div
          className="paper-graph-stage"
          style={{ width: layout.width, height: layout.height, minWidth: '100%' }}
        >
          <svg
            className="paper-graph-edges"
            width={layout.width}
            height={layout.height}
            viewBox={`0 0 ${layout.width} ${layout.height}`}
            preserveAspectRatio="xMidYMin meet"
            aria-hidden="true"
          >
            <defs>
              <pattern id="metro-grid" width="24" height="24" patternUnits="userSpaceOnUse">
                <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(148,163,184,0.12)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width={layout.width} height={layout.height} fill="url(#metro-grid)" />

            {/* Theme track guides */}
            {layout.tracksMeta.map((track) => {
              const dim =
                focusId && highlightedLines.size && !highlightedLines.has(track.key);
              return (
                <line
                  key={`track-${track.key}`}
                  x1={track.x1}
                  y1={track.y}
                  x2={track.x2}
                  y2={track.y}
                  stroke={LINES[track.key]?.color || '#cbd5e1'}
                  strokeWidth={6}
                  strokeLinecap="round"
                  strokeOpacity={dim ? 0.12 : 0.22}
                />
              );
            })}

            {/* Spine guide + stage captions for desktop */}
            {mode !== 'mobile' && prepared.currentId && layout.positions.get(prepared.currentId) && (
              <>
                <line
                  x1={28}
                  y1={layout.positions.get(prepared.currentId).cy}
                  x2={layout.width - 28}
                  y2={layout.positions.get(prepared.currentId).cy}
                  stroke="#cbd5e1"
                  strokeWidth={5}
                  strokeLinecap="round"
                  strokeOpacity={0.35}
                />
                <text x={36} y={24} className="paper-graph-stage-caption" fill="#64748b" fontSize="11" fontWeight="600">
                  前驱工作 → 当前论文 → 后续发展
                </text>
              </>
            )}
            {mode === 'mobile' && (
              <text x={16} y={28} className="paper-graph-stage-caption" fill="#64748b" fontSize="11" fontWeight="600">
                纵向阶段：前驱 → 当前 → 主题线路 → 后续
              </text>
            )}

            {visibleCanvasEdges.map((edge) => {
              const source = layout.boxes.get(edge.source);
              const target = layout.boxes.get(edge.target);
              if (!source || !target) return null;
              const focused = focusId && (edge.source === focusId || edge.target === focusId);
              const dimmed = focusId && !focused;
              const stroke = strokeForEdge(edge, nodeMap);
              return (
                <path
                  key={edge.id}
                  d={edgePath(source, target)}
                  fill="none"
                  stroke={focused ? '#1d4ed8' : stroke.color}
                  strokeWidth={focused ? stroke.width + 0.6 : stroke.width}
                  strokeDasharray={stroke.dash || undefined}
                  strokeOpacity={dimmed ? 0.18 : 0.92}
                  strokeLinecap="round"
                />
              );
            })}
          </svg>

          {prepared.nodes.map((node) => {
            const pos = layout.positions.get(node.id);
            if (!pos) return null;
            const targetPaperId = node.paperId ?? node.paper_id;
            const canOpen =
              targetPaperId != null && String(targetPaperId) !== String(paperId);
            const isCurrent = node.role === 'current';
            const dimmed = focusId && !highlighted.has(node.id);
            const theme = node.theme || themeOf(node);
            const lineColor =
              (theme && LINES[theme]?.color) ||
              (isCurrent ? '#1e40af' : node.type === 'paper' ? '#334155' : '#64748b');

            return (
              <button
                type="button"
                key={node.id}
                className={[
                  'paper-graph-node',
                  'paper-graph-node-metro',
                  `paper-graph-node-${node.type}`,
                  `is-size-${node.size || 'entity'}`,
                  canOpen ? 'is-link' : '',
                  isCurrent ? 'is-current' : '',
                  dimmed ? 'is-dimmed' : '',
                  activeId === node.id ? 'is-active' : '',
                  node.role === 'related' ? 'is-topic' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                style={{
                  left: pos.x,
                  top: pos.y,
                  width: pos.w,
                  height: pos.h,
                  '--node-color': lineColor,
                  fontSize: FONT_MIN,
                }}
                title={node.description || node.label}
                onMouseEnter={() => setHoverId(node.id)}
                onMouseLeave={() => setHoverId(null)}
                onClick={(event) => {
                  event.stopPropagation();
                  if (canOpen && activeId === node.id) {
                    navigate(`/paper/${targetPaperId}`);
                    return;
                  }
                  setActiveId((cur) => (cur === node.id ? null : node.id));
                }}
                onDoubleClick={(event) => {
                  event.stopPropagation();
                  if (canOpen) navigate(`/paper/${targetPaperId}`);
                }}
              >
                <span className="paper-graph-node-type">
                  {isCurrent
                    ? '当前论文 · 换乘站'
                    : node.role === 'predecessor'
                      ? '前驱论文'
                      : node.role === 'successor'
                        ? '后续发展'
                        : node.role === 'related'
                          ? '主题相关'
                          : TYPE_LABELS[node.type] || node.type}
                </span>
                <span className="paper-graph-node-label">{node.label}</span>
                {node.score != null && node.role !== 'current' && node.type === 'paper' && (
                  <span className="paper-graph-node-meta">相关度 {(Number(node.score) * 100).toFixed(0)}%</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      <div className="paper-graph-edge-list" aria-label="关系列表">
        <div className="paper-graph-edge-list-title">
          {focusId ? '选中站点的直接关系' : '主路径与高权重关系（弱关系仅在选中时显示）'}
        </div>
        {(focusId
          ? prepared.listEdges.filter((e) => e.source === focusId || e.target === focusId)
          : prepared.listEdges.filter(isPrimaryListEdge)
        )
          .slice(0, 18)
          .map((edge) => {
            const kind = edge.kind || relationKind(edge);
            return (
              <span
                key={edge.id}
                className={`paper-graph-rel is-${kind}`}
                title={(edge.evidence || []).join(' · ') || edge.label}
              >
                <em>{kind === 'topic' ? '主题相关' : kind === 'lineage' ? '时序脉络' : '主题线路'}</em>
                {nodeMap.get(edge.source)?.label || edge.source}
                {' '}
                <b>{edge.label || edge.type}</b>
                {' '}
                {nodeMap.get(edge.target)?.label || edge.target}
              </span>
            );
          })}
      </div>
    </div>
  );
}
