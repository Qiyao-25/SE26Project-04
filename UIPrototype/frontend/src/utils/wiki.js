import { PAPERS } from '../data/papers';

export function searchPaperWiki(query, mode, currentPaperId) {
  const q = (query || '').trim();
  if (!q) {
    const current = PAPERS[currentPaperId];
    if (!current) return [];
    return Object.entries(PAPERS)
      .filter(([id]) => id !== currentPaperId)
      .map(([id, p]) => {
        let score = 0;
        if (p.tag === current.tag) score += 2;
        if (p.direction === current.direction) score += 3;
        const kw = new Set((current.keywords || []).map((k) => k.toLowerCase()));
        (p.keywords || []).forEach((k) => { if (kw.has(k.toLowerCase())) score += 2; });
        return { id, paper: p, score };
      })
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score);
  }

  const collect = (paper, m) => {
    const matches = [];
    const hit = (text) => text?.toLowerCase().includes(q.toLowerCase());
    if ((m === 'all' || m === 'title') && hit(paper.title)) matches.push('title');
    if (m === 'all' || m === 'author') {
      if (paper.authors.split(',').some((a) => hit(a.trim()))) matches.push('author');
    }
    if (m === 'all' || m === 'keyword') {
      if ((paper.keywords || []).some(hit)) matches.push('keyword');
    }
    if ((m === 'all' || m === 'direction') && hit(paper.direction)) matches.push('direction');
    if (m === 'all' || m === 'concept') {
      if ((paper.conceptTags || []).some(hit)) matches.push('concept');
    }
    return matches;
  };

  return Object.entries(PAPERS)
    .map(([id, paper]) => ({ id, paper, matches: collect(paper, mode) }))
    .filter((r) => r.matches.length > 0);
}
