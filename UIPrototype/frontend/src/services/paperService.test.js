import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { normalizeAuthors, toPaperListItem, createCompatibleDetail, searchPapers, getPaperDetail, getPaperSummary, createParseTask } from './paperService';

vi.mock('./runtimeConfig', () => ({
  USE_MOCK: true,
  API_BASE_URL: '/api',
  API_TIMEOUT_MS: 10000
}));

vi.mock('./apiClient');

describe('normalizeAuthors', () => {
  it('should normalize array of strings', () => {
    const result = normalizeAuthors(['Alice', 'Bob', 'Charlie']);
    expect(result).toEqual(['Alice', 'Bob', 'Charlie']);
  });

  it('should normalize array of objects with name property', () => {
    const result = normalizeAuthors([{ name: 'Alice' }, { name: 'Bob' }]);
    expect(result).toEqual(['Alice', 'Bob']);
  });

  it('should handle mixed array of strings and objects', () => {
    const result = normalizeAuthors(['Alice', { name: 'Bob' }, { name: 'Charlie' }]);
    expect(result).toEqual(['Alice', 'Bob', 'Charlie']);
  });

  it('should filter out null/undefined values', () => {
    const result = normalizeAuthors(['Alice', null, undefined, { name: null }, { name: 'Bob' }]);
    expect(result).toEqual(['Alice', 'Bob']);
  });

  it('should handle string with comma separation', () => {
    const result = normalizeAuthors('Alice, Bob, Charlie');
    expect(result).toEqual(['Alice', 'Bob', 'Charlie']);
  });

  it('should handle empty string', () => {
    const result = normalizeAuthors('');
    expect(result).toEqual([]);
  });

  it('should handle undefined', () => {
    const result = normalizeAuthors(undefined);
    expect(result).toEqual([]);
  });
});

describe('toPaperListItem', () => {
  it('should convert paper object to list item format', () => {
    const input = {
      paper_id: 1,
      title: 'Test Paper',
      authors: ['Alice', 'Bob'],
      primary_category: 'cs.CL',
      arxiv_id: '2301.00001',
      published_at: '2023-01-01',
      abstract: 'Abstract text',
      parse_status: 'qa_ready',
      chunk_count: 10,
      qa_ready: true
    };

    const result = toPaperListItem(input);

    expect(result.paperId).toBe(1);
    expect(result.title).toBe('Test Paper');
    expect(result.authors).toEqual(['Alice', 'Bob']);
    expect(result.primaryCategory).toBe('cs.CL');
    expect(result.arxivId).toBe('2301.00001');
    expect(result.publishedAt).toBe('2023-01-01');
    expect(result.summary).toBe('Abstract text');
    expect(result.parseStatus).toBe('qa_ready');
    expect(result.chunkCount).toBe(10);
    expect(result.qaReady).toBe(true);
  });

  it('should use alternative field names when primary fields are missing', () => {
    const input = {
      id: 2,
      title: 'Alternative Paper',
      authors: [{ name: 'Charlie' }],
      tag: 'cs.AI',
      arxiv: '2401.00002',
      date: '2024-01-01',
      summary: 'Summary text'
    };

    const result = toPaperListItem(input);

    expect(result.paperId).toBe(2);
    expect(result.primaryCategory).toBe('cs.AI');
    expect(result.arxivId).toBe('2401.00002');
    expect(result.publishedAt).toBe('2024-01-01');
    expect(result.authors).toEqual(['Charlie']);
  });

  it('should set default values for missing fields', () => {
    const input = {
      title: 'Minimal Paper'
    };

    const result = toPaperListItem(input);

    expect(result.primaryCategory).toBe('未分类');
    expect(result.arxivId).toBe('');
    expect(result.publishedAt).toBe('');
    expect(result.summary).toBe('');
    expect(result.keywords).toEqual([]);
    expect(result.parseStatus).toBe('pending');
    expect(result.chunkCount).toBe(0);
    expect(result.qaReady).toBe(false);
  });
});

describe('createCompatibleDetail', () => {
  it('should create compatible detail with normalized fields', () => {
    const input = {
      paperId: 'P1',
      title: 'Test Paper',
      authors: ['Alice', 'Bob'],
      primaryCategory: 'cs.CL',
      arxivId: '2301.00001',
      publishedAt: '2023-01-01',
      summary: 'Abstract text',
      keywords: ['keyword1']
    };

    const result = createCompatibleDetail(input);

    expect(result.id).toBe('P1');
    expect(result.tag).toBe('cs.CL');
    expect(result.arxiv).toBe('2301.00001');
    expect(result.date).toBe('2023-01-01');
    expect(result.authorsText).toBe('Alice, Bob');
    expect(result.categories).toEqual(['cs.CL']);
    expect(result.abstract).toBe('Abstract text');
    expect(result.pdfUrl).toBe('https://arxiv.org/pdf/2301.00001');
    expect(result.sourceUrl).toBe('https://arxiv.org/abs/2301.00001');
  });

  it('should force pending status when forcePending is true', () => {
    const input = {
      paperId: 'P1',
      title: 'Test Paper',
      parseStatus: 'qa_ready',
      chunkCount: 10,
      qaReady: true
    };

    const result = createCompatibleDetail(input, { forcePending: true });

    expect(result.parseStatus).toBe('pending');
    expect(result.chunkCount).toBe(0);
    expect(result.qaReady).toBe(false);
  });
});

describe('searchPapers', () => {
  it('should search papers with default parameters', async () => {
    const result = await searchPapers();

    expect(result).toHaveProperty('searchId');
    expect(result).toHaveProperty('total');
    expect(result).toHaveProperty('items');
    expect(Array.isArray(result.items)).toBe(true);
    expect(result.page).toBe(1);
    expect(result.pageSize).toBe(12);
  });

  it('should search papers with query parameter', async () => {
    const result = await searchPapers({ query: 'transformer', page: 1, pageSize: 5 });

    expect(result.query).toBe('transformer');
    expect(result.page).toBe(1);
    expect(result.pageSize).toBe(5);
  });

  it('should sort by date when sortBy is date', async () => {
    const result = await searchPapers({ sortBy: 'date' });

    expect(result.sortBy).toBe('date');
    const items = result.items;
    for (let i = 1; i < items.length; i++) {
      expect(items[i - 1].publishedAt >= items[i].publishedAt).toBe(true);
    }
  });
});

describe('getPaperDetail', () => {
  it('should return paper detail for existing paper', async () => {
    const result = await getPaperDetail('attention');

    expect(result).not.toBeNull();
    expect(result).toHaveProperty('paperId');
    expect(result).toHaveProperty('title');
    expect(result).toHaveProperty('authors');
    expect(result).toHaveProperty('authorsText');
  });

  it('should return null for non-existent paper', async () => {
    const result = await getPaperDetail('non-existent-id');

    expect(result).toBeNull();
  });
});

describe('getPaperSummary', () => {
  it('should return paper summary for existing paper', async () => {
    const result = await getPaperSummary('attention');

    expect(result).not.toBeNull();
    expect(result).toHaveProperty('paperId', 'attention');
    expect(result).toHaveProperty('parseStatus');
    expect(result).toHaveProperty('summary');
  });

  it('should return null for non-existent paper', async () => {
    const result = await getPaperSummary('non-existent-id');

    expect(result).toBeNull();
  });
});

describe('createParseTask', () => {
  it('should create parse task and mark as parsed', async () => {
    const result = await createParseTask('P1');

    expect(result).toHaveProperty('taskId');
    expect(result).toHaveProperty('paperId', 'P1');
    expect(result.status).toBe('succeeded');
  });

  it('should create parse task with force option', async () => {
    const result = await createParseTask('P1', { force: true });

    expect(result).toHaveProperty('taskId');
    expect(result.status).toBe('succeeded');
  });
});