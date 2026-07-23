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

const MIN_NODE_W = 160;
const MAX_ENTITY_W = 280;
const MAX_PAPER_W = 300;
const MAX_HUB_W = 340;
const FONT_MIN = 12;
const PAPER_SCORE_MIN = 0.28;
const GAP_X = 20;
const GAP_Y = 18;
const CHAR_PX = 13;

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

/** Default canvas: spine + hub radial only. Weak/cross links appear on focus. */
function isDefaultCanvasEdge(edge) {
  if (edge.type === 'precedes' || edge.type === 'follows') return true;
  return ['introduces', 'uses', 'evaluates_on', 'in_domain'].includes(edge.type);
}

function isPrimaryListEdge(edge) {
  if (relationKind(edge) === 'topic') return false;
  return isDefaultCanvasEdge(edge) || edge.type === 'implements';
}

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

  const canvasEdges = filteredEdges.filter(isDefaultCanvasEdge);
  const listEdges = filteredEdges
    .slice()
    .sort((a, b) => Number(b.weight || 0) - Number(a.weight || 0));

  return { nodes, canvasEdges, listEdges, currentId: current?.id || null };
}

function estimateLabelLines(label, width, maxLines) {
  const chars = String(label || '').length;
  const perLine = Math.max(6, Math.floor((width - 24) / CHAR_PX));
  return Math.min(maxLines, Math.max(1, Math.ceil(chars / perLine)));
}

/** Preferred width from label length; later may expand to fill a distributed slot. */
function preferredWidth(node, mode) {
  const label = String(node.label || '');
  const textW = label.length * CHAR_PX + 36;
  if (node.role === 'current') {
    return Math.min(MAX_HUB_W, Math.max(mode === 'vertical' ? 200 : 220, textW));
  }
  if (node.type === 'paper') {
    return Math.min(MAX_PAPER_W, Math.max(MIN_NODE_W, textW));
  }
  return Math.min(MAX_ENTITY_W, Math.max(MIN_NODE_W, textW));
}

function nodeSize(node, mode, forcedW) {
  const maxLines = node.role === 'current' || node.type === 'paper' ? 3 : 3;
  const w = forcedW || preferredWidth(node, mode);
  const lines = estimateLabelLines(node.label, w, maxLines);
  return { w, h: 36 + lines * 17 };
}

function sortPapersByTime(papers, direction) {
  return [...papers].sort((a, b) => {
    const da = Date.parse(a.publishedAt || a.published_at || '') || 0;
    const db = Date.parse(b.publishedAt || b.published_at || '') || 0;
    if (da && db && da !== db) return direction === 'asc' ? da - db : db - da;
    return Number(b.score || 0) - Number(a.score || 0);
  });
}

function boxesOverlap(a, b, gap) {
  return !(
    a.x + a.w + gap <= b.x
    || b.x + b.w + gap <= a.x
    || a.y + a.h + gap <= b.y
    || b.y + b.h + gap <= a.y
  );
}

/** Push overlapping boxes downward until gaps are clear. */
function resolveCollisions(positions, boxes, gap = 16) {
  const ids = [...boxes.keys()].sort((a, b) => {
    const A = boxes.get(a);
    const B = boxes.get(b);
    return A.y - B.y || A.x - B.x;
  });

  for (let pass = 0; pass < 8; pass += 1) {
    let moved = false;
    for (let i = 0; i < ids.length; i += 1) {
      for (let j = 0; j < i; j += 1) {
        const id = ids[i];
        const other = ids[j];
        const box = boxes.get(id);
        const prev = boxes.get(other);
        if (!boxesOverlap(box, prev, gap)) continue;
        const nextY = prev.y + prev.h + gap;
        if (nextY > box.y) {
          const dy = nextY - box.y;
          boxes.set(id, { ...box, y: nextY });
          const pos = positions.get(id);
          positions.set(id, { ...pos, y: nextY, cy: pos.cy + dy });
          moved = true;
        }
      }
    }
    if (!moved) break;
    ids.sort((a, b) => {
      const A = boxes.get(a);
      const B = boxes.get(b);
      return A.y - B.y || A.x - B.x;
    });
  }
}

/**
 * Full-width distributed rows: expand cards into equal slots so right side is used.
 */
function placeDistributedBlock({
  nodes,
  startY,
  areaX,
  areaW,
  mode,
  place,
}) {
  if (!nodes.length) return startY;
  let y = startY;

  const minCell = MIN_NODE_W + GAP_X;
  const perRow = Math.max(1, Math.floor((areaW + GAP_X) / minCell));

  for (let start = 0; start < nodes.length; start += perRow) {
    const row = nodes.slice(start, start + perRow);
    const n = row.length;
    const slotW = (areaW - (n - 1) * GAP_X) / n;
    const sizes = row.map((node) => {
      const preferred = preferredWidth(node, mode);
      const maxForType = node.role === 'current'
        ? MAX_HUB_W
        : node.type === 'paper'
          ? MAX_PAPER_W
          : MAX_ENTITY_W;
      const w = Math.min(maxForType, Math.max(preferred, Math.min(slotW, maxForType)));
      return nodeSize(node, mode, w);
    });

    const preferredSum = sizes.reduce((s, sz) => s + sz.w, 0) + (n - 1) * GAP_X;
    let xs;
    if (preferredSum <= areaW + 1) {
      xs = row.map((_, i) => areaX + i * (slotW + GAP_X) + Math.max(0, (slotW - sizes[i].w) / 2));
    } else {
      let x = areaX;
      xs = sizes.map((sz) => {
        const cur = x;
        x += sz.w + GAP_X;
        return cur;
      });
    }

    const rowH = Math.max(...sizes.map((s) => s.h));
    row.forEach((node, i) => {
      place(node, xs[i], y + (rowH - sizes[i].h) / 2, sizes[i]);
    });
    y += rowH + GAP_Y;
  }
  return y;
}

function alignRowToSpine(nodeIds, positions, boxes, spineY) {
  nodeIds.forEach((id) => {
    const pos = positions.get(id);
    if (!pos) return;
    const ny = spineY - pos.h / 2;
    positions.set(id, { ...pos, y: ny, cy: spineY });
    boxes.set(id, { x: pos.x, y: ny, w: pos.w, h: pos.h });
  });
}

function buildMetroLayout(nodes, width, mode) {
  const padX = mode === 'vertical' ? 16 : 24;
  const padY = 48;
  const hubGapX = 28;

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
  const place = (node, x, y, sizeOverride) => {
    const size = sizeOverride || nodeSize(node, mode);
    const maxX = Math.max(padX, width - size.w - padX);
    const safeX = Math.min(Math.max(padX, x), maxX);
    positions.set(node.id, {
      x: safeX,
      y,
      cx: safeX + size.w / 2,
      cy: y + size.h / 2,
      ...size,
    });
    boxes.set(node.id, { x: safeX, y, w: size.w, h: size.h });
  };

  let contentH = padY;
  const contentW = Math.max(width, mode === 'vertical' ? 360 : 640);
  let spineY = 0;
  const themeAreaX = padX;
  const themeAreaW = Math.max(MIN_NODE_W, contentW - padX * 2);

  if (mode === 'vertical') {
    let y = padY;
    const stageStack = (list) => {
      list.forEach((node) => {
        const cap = node.role === 'current' || node.type === 'paper' ? MAX_HUB_W : MAX_ENTITY_W;
        const size = nodeSize(node, mode, Math.min(cap, themeAreaW));
        place(node, padX, y, size);
        y += size.h + GAP_Y;
      });
    };

    stageStack(predecessors);
    if (current) {
      const size = nodeSize(current, mode, Math.min(MAX_HUB_W, themeAreaW));
      place(current, padX, y, size);
      y += size.h + GAP_Y + 6;
      spineY = positions.get(current.id)?.cy || y;
    }
    ['concept', 'method', 'training', 'experiment'].forEach((theme) => {
      if (!byTheme[theme].length) return;
      y = placeDistributedBlock({
        nodes: byTheme[theme],
        startY: y + 4,
        areaX: themeAreaX,
        areaW: themeAreaW,
        mode,
        place,
      }) + 4;
    });
    if (topicPapers.length) {
      y = placeDistributedBlock({
        nodes: topicPapers,
        startY: y + 4,
        areaX: themeAreaX,
        areaW: themeAreaW,
        mode,
        place,
      });
    }
    stageStack(successors);

    resolveCollisions(positions, boxes, 14);
    contentH = Math.max(...[...boxes.values()].map((b) => b.y + b.h), y) + padY;
  } else {
    const hubSize = current
      ? nodeSize(current, mode, preferredWidth(current, mode))
      : { w: 220, h: 80 };

    const aboveThemes = [
      byTheme.concept.length ? { key: 'concept', nodes: byTheme.concept } : null,
      byTheme.method.length ? { key: 'method', nodes: byTheme.method } : null,
    ].filter(Boolean);
    const belowThemes = [
      byTheme.training.length ? { key: 'training', nodes: byTheme.training } : null,
      byTheme.experiment.length ? { key: 'experiment', nodes: byTheme.experiment } : null,
    ].filter(Boolean);

    let yCursor = padY + 16;
    aboveThemes.forEach((track) => {
      yCursor = placeDistributedBlock({
        nodes: track.nodes,
        startY: yCursor,
        areaX: themeAreaX,
        areaW: themeAreaW,
        mode,
        place,
      }) + 6;
    });

    spineY = yCursor + hubSize.h / 2 + 10;
    const hubX = Math.round((contentW - hubSize.w) / 2);

    if (predecessors.length) {
      const leftW = Math.max(MIN_NODE_W, hubX - hubGapX - padX);
      placeDistributedBlock({
        nodes: predecessors,
        startY: spineY - 40,
        areaX: padX,
        areaW: leftW,
        mode,
        place,
      });
      alignRowToSpine(predecessors.map((n) => n.id), positions, boxes, spineY);
    }

    if (current) {
      place(current, hubX, spineY - hubSize.h / 2, hubSize);
    }

    if (successors.length) {
      const succAreaX = hubX + hubSize.w + hubGapX;
      const succAreaW = Math.max(MIN_NODE_W, contentW - padX - succAreaX);
      placeDistributedBlock({
        nodes: successors,
        startY: spineY - 40,
        areaX: succAreaX,
        areaW: succAreaW,
        mode,
        place,
      });
      alignRowToSpine(successors.map((n) => n.id), positions, boxes, spineY);
    }

    let belowY = spineY + hubSize.h / 2 + 24;
    belowThemes.forEach((track) => {
      belowY = placeDistributedBlock({
        nodes: track.nodes,
        startY: belowY,
        areaX: themeAreaX,
        areaW: themeAreaW,
        mode,
        place,
      }) + 6;
    });

    if (topicPapers.length) {
      belowY = placeDistributedBlock({
        nodes: topicPapers,
        startY: belowY + 6,
        areaX: themeAreaX,
        areaW: themeAreaW,
        mode,
        place,
      });
    }

    resolveCollisions(positions, boxes, 14);

    const allBoxes = [...boxes.values()];
    if (allBoxes.length) {
      const minY = Math.min(...allBoxes.map((b) => b.y));
      if (minY < padY) {
        const dy = padY - minY;
        for (const [id, pos] of positions) {
          positions.set(id, { ...pos, y: pos.y + dy, cy: pos.cy + dy });
          const box = boxes.get(id);
          boxes.set(id, { ...box, y: box.y + dy });
        }
        spineY += dy;
      }
      contentH = Math.max(...[...boxes.values()].map((b) => b.y + b.h)) + padY + 16;
    } else {
      contentH = padY * 2 + 120;
    }
  }

  const tracksMeta = [];
  if (current && positions.has(current.id)) {
    const hub = positions.get(current.id);
    ['concept', 'method', 'training', 'experiment'].forEach((theme) => {
      const themed = byTheme[theme].filter((n) => positions.has(n.id));
      if (!themed.length) return;
      const ys = themed.map((n) => positions.get(n.id).cy);
      const xs = themed.map((n) => positions.get(n.id).cx);
      tracksMeta.push({
        key: theme,
        color: LINES[theme].color,
        y: ys.reduce((a, b) => a + b, 0) / ys.length,
        x1: Math.min(hub.cx, ...xs) - 24,
        x2: Math.max(hub.cx, ...xs) + 24,
      });
    });
  }

  return {
    positions,
    boxes,
    width: contentW,
    height: Math.max(contentH, mode === 'vertical' ? 420 : 380),
    tracksMeta,
    spineY,
    mode,
  };
}

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

/** <960px uses vertical stage map to avoid horizontal squeeze. */
function layoutMode(width) {
  if (width < 960) return 'vertical';
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
      return {
        positions: new Map(),
        boxes: new Map(),
        width: 640,
        height: 360,
        tracksMeta: [],
        spineY: 0,
        mode,
      };
    }
    return buildMetroLayout(prepared.nodes, containerW, mode);
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
    if (!focusId) return prepared.canvasEdges;
    const related = prepared.listEdges.filter(
      (e) => e.source === focusId || e.target === focusId,
    );
    const ids = new Set(prepared.canvasEdges.map((e) => e.id));
    const merged = [...prepared.canvasEdges];
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
        地铁线路图：站点按全宽均分排布；概念/方法/领域等标题最多显示 3 行。默认只画主路径与换乘线，悬停可看弱关系。
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
          height: Math.min(Math.max(layout.height + 8, 320), mode === 'vertical' ? 760 : 900),
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
                  strokeWidth={5}
                  strokeLinecap="round"
                  strokeOpacity={dim ? 0.1 : 0.18}
                />
              );
            })}

            {mode === 'desktop' && prepared.currentId && layout.positions.get(prepared.currentId) && (
              <>
                <line
                  x1={28}
                  y1={layout.positions.get(prepared.currentId).cy}
                  x2={layout.width - 28}
                  y2={layout.positions.get(prepared.currentId).cy}
                  stroke="#cbd5e1"
                  strokeWidth={4}
                  strokeLinecap="round"
                  strokeOpacity={0.3}
                />
                <text x={36} y={22} fill="#64748b" fontSize="11" fontWeight="600">
                  前驱工作 → 当前论文 → 后续发展
                </text>
              </>
            )}
            {mode === 'vertical' && (
              <text x={16} y={24} fill="#64748b" fontSize="11" fontWeight="600">
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
                  strokeWidth={focused ? stroke.width + 0.5 : stroke.width}
                  strokeDasharray={stroke.dash || undefined}
                  strokeOpacity={dimmed ? 0.15 : 0.9}
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
            const tip = [
              node.label,
              node.description,
              node.score != null && node.type === 'paper' ? `相关度 ${(Number(node.score) * 100).toFixed(0)}%` : '',
            ].filter(Boolean).join('\n');

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
                title={tip}
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
              </button>
            );
          })}
        </div>
      </div>

      <div className="paper-graph-edge-list" aria-label="关系列表">
        <div className="paper-graph-edge-list-title">
          {focusId ? '选中站点的直接关系' : '主路径关系（弱关系 / 主题相关请悬停节点查看）'}
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
