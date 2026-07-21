import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PaperCard from './PaperCard';

const mockPaper = {
  paperId: 'P1',
  title: 'Attention Is All You Need',
  authors: ['Vaswani', 'Shazeer', 'Parmar', 'Uszkoreit', 'Jones', 'Gomez', 'Kaiser', 'Polosukhin'],
  primaryCategory: 'cs.CL',
  arxivId: '1706.03762',
  publishedAt: '2017-06-12',
  summary: 'The Transformer architecture relies entirely on attention mechanisms, dispensing with recurrence and convolutions entirely.',
  keywords: ['transformer', 'attention', 'NLP'],
  parseStatus: 'qa_ready',
  chunkCount: 12,
  qaReady: true
};

const mockPaperWithObjectAuthors = {
  paperId: 'P2',
  title: 'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding',
  authors: [
    { name: 'Devlin' },
    { name: 'Chang' },
    { name: 'Lee' },
    { name: 'Toutanova' }
  ],
  primaryCategory: 'cs.CL',
  arxivId: '1810.04805',
  publishedAt: '2018-10-11',
  summary: 'We introduce a new language representation model called BERT.',
  keywords: ['BERT', 'pre-training']
};

function renderWithRouter(component) {
  return render(<MemoryRouter>{component}</MemoryRouter>);
}

describe('PaperCard Component', () => {
  it('renders null when paper prop is not provided', () => {
    const { container } = renderWithRouter(<PaperCard />);
    expect(container.firstChild).toBeNull();
  });

  it('renders null when paper is undefined', () => {
    const { container } = renderWithRouter(<PaperCard paper={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders paper title correctly', () => {
    renderWithRouter(<PaperCard paper={mockPaper} />);
    expect(screen.getByText('Attention Is All You Need')).toBeInTheDocument();
  });

  it('renders author names as comma-separated string', () => {
    renderWithRouter(<PaperCard paper={mockPaper} />);
    expect(screen.getByText('Vaswani, Shazeer, Parmar, Uszkoreit, Jones, Gomez, Kaiser, Polosukhin')).toBeInTheDocument();
  });

  it('handles authors as objects with name property', () => {
    renderWithRouter(<PaperCard paper={mockPaperWithObjectAuthors} />);
    expect(screen.getByText('Devlin, Chang, Lee, Toutanova')).toBeInTheDocument();
  });

  it('renders category tag', () => {
    renderWithRouter(<PaperCard paper={mockPaper} />);
    expect(screen.getByText('cs.CL')).toBeInTheDocument();
  });

  it('renders arxiv ID tag', () => {
    renderWithRouter(<PaperCard paper={mockPaper} />);
    expect(screen.getByText('arXiv:1706.03762')).toBeInTheDocument();
  });

  it('renders published date tag', () => {
    renderWithRouter(<PaperCard paper={mockPaper} />);
    expect(screen.getByText('2017-06-12')).toBeInTheDocument();
  });

  it('renders summary with ellipsis', () => {
    renderWithRouter(<PaperCard paper={mockPaper} />);
    expect(screen.getByText(/The Transformer architecture/)).toBeInTheDocument();
  });

  it('renders keywords as tags', () => {
    renderWithRouter(<PaperCard paper={mockPaper} />);
    expect(screen.getByText('transformer')).toBeInTheDocument();
    expect(screen.getByText('attention')).toBeInTheDocument();
    expect(screen.getByText('NLP')).toBeInTheDocument();
  });

  it('renders compact mode correctly', () => {
    const { container } = renderWithRouter(<PaperCard paper={mockPaper} compact />);
    const card = container.querySelector('.ant-card');
    expect(card).toHaveClass('paper-card-compact');
    expect(screen.getByText('Attention Is All You Need')).toBeInTheDocument();
    expect(screen.getByText('cs.CL')).toBeInTheDocument();
  });

  it('uses paper.paperId when present', () => {
    const { container } = renderWithRouter(<PaperCard paper={mockPaper} />);
    const card = container.querySelector('.ant-card');
    expect(card).toBeInTheDocument();
  });

  it('renders hoverable card', () => {
    const { container } = renderWithRouter(<PaperCard paper={mockPaper} />);
    const card = container.querySelector('.ant-card');
    expect(card).toHaveClass('ant-card-hoverable');
  });
});