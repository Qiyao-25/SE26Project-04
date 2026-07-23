import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  DatePicker,
  Input,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useNavigate } from 'react-router-dom';
import { ARXIV_CATEGORIES, ARXIV_TOPIC_GROUPS } from '../../data/arxivCategories';
import { deletePaper, searchPapers } from '../../services/paperService';
import { formatDateTime } from '../../utils/datetime';
import { getLibraryPageSize } from '../../utils/uiPrefs';

const { Text } = Typography;
const { RangePicker } = DatePicker;

/** column key → API sort field prefix */
const COLUMN_SORT_FIELD = {
  paperId: 'id',
  title: 'title',
  authors: 'author',
  topic: 'topic',
  primaryCategory: 'category',
  arxivId: 'arxiv',
  publishedAt: 'published',
  createdAt: 'created',
  parseStatus: 'status',
};

const SORT_LABELS = {
  id: '序号',
  title: '标题',
  author: '作者',
  topic: '主题',
  category: '类别',
  arxiv: 'arXiv',
  published: '发表时间',
  created: '入库时间',
  status: '状态',
};

const emptyFilters = {
  keyword: '',
  author: '',
  topic: undefined,
  category: undefined,
  publishedRange: null,
};

function toSortBy(field, order) {
  if (!field || !order) return 'published_desc';
  return `${field}_${order === 'ascend' ? 'asc' : 'desc'}`;
}

function parseSortBy(sortBy = 'published_desc') {
  const match = String(sortBy).match(/^(id|title|author|topic|category|arxiv|published|created|status)_(asc|desc)$/);
  if (!match) return { field: 'published', order: 'descend' };
  return { field: match[1], order: match[2] === 'asc' ? 'ascend' : 'descend' };
}

export default function PaperLibraryPage() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState(emptyFilters);
  const [applied, setApplied] = useState(emptyFilters);
  const [sortBy, setSortBy] = useState('published_desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => getLibraryPageSize(20));
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const { field: sortField, order: sortOrder } = useMemo(() => parseSortBy(sortBy), [sortBy]);

  const draftCategoryOptions = useMemo(() => {
    if (!draft.topic) return ARXIV_CATEGORIES;
    return ARXIV_CATEGORIES.filter(
      (item) => item.value === draft.topic || item.value.startsWith(`${draft.topic}.`),
    );
  }, [draft.topic]);

  const loadPapers = useCallback(async () => {
    setLoading(true);
    try {
      const [from, to] = applied.publishedRange || [];
      const data = await searchPapers({
        query: applied.keyword,
        author: applied.author,
        topic: applied.topic,
        category: applied.category,
        publishedFrom: from ? dayjs(from).startOf('day').toISOString() : undefined,
        publishedTo: to ? dayjs(to).endOf('day').toISOString() : undefined,
        sortBy,
        page,
        pageSize,
      });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      message.error(error.message || '论文库加载失败');
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [applied, sortBy, page, pageSize]);

  useEffect(() => {
    loadPapers();
  }, [loadPapers]);

  const handleSearch = () => {
    setPage(1);
    setApplied({ ...draft });
  };

  const handleReset = () => {
    setDraft(emptyFilters);
    setApplied(emptyFilters);
    setSortBy('published_desc');
    setPage(1);
  };

  const handleDelete = async (paperId) => {
    setDeletingId(paperId);
    try {
      await deletePaper(paperId);
      message.success('已删除论文');
      await loadPapers();
    } catch (error) {
      message.error(error.message || '删除失败');
    } finally {
      setDeletingId(null);
    }
  };

  const sortableColumn = (key, config) => {
    const field = COLUMN_SORT_FIELD[key];
    return {
      ...config,
      key,
      dataIndex: key,
      sorter: true,
      sortOrder: sortField === field ? sortOrder : null,
      sortDirections: ['ascend', 'descend', 'ascend'],
      showSorterTooltip: { title: '点击排序，再次点击切换正序/倒序' },
    };
  };

  const columns = [
    sortableColumn('paperId', {
      title: '序号',
      width: 88,
    }),
    sortableColumn('title', {
      title: '标题',
      ellipsis: true,
      render: (title, record) => (
        <Button type="link" style={{ padding: 0, height: 'auto', whiteSpace: 'normal', textAlign: 'left' }} onClick={() => navigate(`/paper/${record.paperId}`)}>
          {title}
        </Button>
      ),
    }),
    sortableColumn('authors', {
      title: '作者',
      width: 180,
      ellipsis: true,
      render: (authors) => (Array.isArray(authors) ? authors.join(', ') : authors) || '—',
    }),
    sortableColumn('topic', {
      title: '主题',
      width: 90,
      render: (value, record) => <Tag color="geekblue">{value || (record.primaryCategory || '').split('.')[0] || '—'}</Tag>,
    }),
    sortableColumn('primaryCategory', {
      title: '类别',
      width: 110,
      render: (value) => <Tag>{value || '未分类'}</Tag>,
    }),
    sortableColumn('arxivId', {
      title: 'arXiv',
      width: 130,
      render: (value) => value || '—',
    }),
    sortableColumn('publishedAt', {
      title: '发表时间',
      width: 150,
      render: (value) => (value ? formatDateTime(value) : '—'),
    }),
    sortableColumn('createdAt', {
      title: '入库时间',
      width: 150,
      render: (value) => (value ? formatDateTime(value) : '—'),
    }),
    sortableColumn('parseStatus', {
      title: '状态',
      width: 100,
      render: (value, record) => (
        <Space direction="vertical" size={0}>
          <Text>{value || 'pending'}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>块 {record.chunkCount ?? 0}</Text>
        </Space>
      ),
    }),
    {
      title: '操作',
      key: 'actions',
      width: 100,
      fixed: 'right',
      render: (_, record) => (
        <Popconfirm
          title="确认删除该论文？"
          description="将从论文库中软删除，列表与推荐中不再显示。"
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
          onConfirm={() => handleDelete(record.paperId)}
        >
          <Button
            danger
            type="text"
            icon={<DeleteOutlined />}
            loading={deletingId === record.paperId}
          />
        </Popconfirm>
      ),
    },
  ];

  const handleTableChange = (pagination, _filters, sorter) => {
    const nextPage = pagination?.current || 1;
    const nextSize = pagination?.pageSize || pageSize;
    if (nextPage !== page) setPage(nextPage);
    if (nextSize !== pageSize) setPageSize(nextSize);

    const active = Array.isArray(sorter) ? sorter.find((item) => item.order) || sorter[0] : sorter;
    const columnKey = active?.columnKey || active?.field;
    const field = COLUMN_SORT_FIELD[columnKey];
    if (!field || !active?.order) return;

    const nextSortBy = toSortBy(field, active.order);
    if (nextSortBy !== sortBy) {
      setSortBy(nextSortBy);
      setPage(1);
    }
  };

  return (
    <div className="page-paper-library">
      <Card className="section-card" title="论文库">
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          支持按关键词、作者、发表时间、主题大类与 arXiv 类别筛选。点击表头列名排序，箭头表示当前方向，再次点击切换正序/倒序。
        </Text>
        <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
          <Col xs={24} sm={12} md={8} lg={6}>
            <Input
              allowClear
              placeholder="关键词（标题/摘要/arXiv）"
              value={draft.keyword}
              onChange={(event) => setDraft((current) => ({ ...current, keyword: event.target.value }))}
              onPressEnter={handleSearch}
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={5}>
            <Input
              allowClear
              placeholder="作者"
              value={draft.author}
              onChange={(event) => setDraft((current) => ({ ...current, author: event.target.value }))}
              onPressEnter={handleSearch}
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={5}>
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="主题分类"
              style={{ width: '100%' }}
              options={ARXIV_TOPIC_GROUPS}
              value={draft.topic}
              onChange={(value) => setDraft((current) => ({
                ...current,
                topic: value,
                category: current.category && value && !String(current.category).startsWith(`${value}.`) && current.category !== value
                  ? undefined
                  : current.category,
              }))}
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={5}>
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="类别（arXiv）"
              style={{ width: '100%' }}
              options={draftCategoryOptions}
              value={draft.category}
              onChange={(value) => setDraft((current) => ({ ...current, category: value }))}
            />
          </Col>
          <Col xs={24} sm={12} md={10} lg={8}>
            <RangePicker
              style={{ width: '100%' }}
              value={draft.publishedRange}
              onChange={(value) => setDraft((current) => ({ ...current, publishedRange: value }))}
              placeholder={['发表起', '发表止']}
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={6}>
            <Space wrap>
              <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>筛选</Button>
              <Button onClick={handleReset}>重置</Button>
              <Button icon={<ReloadOutlined />} onClick={loadPapers}>刷新</Button>
            </Space>
          </Col>
        </Row>
        {(applied.topic || applied.category || applied.author || applied.keyword || applied.publishedRange || sortBy !== 'published_desc') && (
          <Space wrap size={4} style={{ marginBottom: 12 }}>
            {applied.keyword ? <Tag>关键词：{applied.keyword}</Tag> : null}
            {applied.author ? <Tag>作者：{applied.author}</Tag> : null}
            {applied.topic ? <Tag color="blue">主题：{applied.topic}</Tag> : null}
            {applied.category ? <Tag color="cyan">类别：{applied.category}</Tag> : null}
            {applied.publishedRange ? <Tag>时间范围已选</Tag> : null}
            <Tag color="purple">
              排序：{SORT_LABELS[sortField] || sortField} {sortOrder === 'ascend' ? '↑' : '↓'}
            </Tag>
          </Space>
        )}
        <Table
          rowKey="paperId"
          loading={loading}
          columns={columns}
          dataSource={items}
          scroll={{ x: 1280 }}
          onChange={handleTableChange}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (count) => `共 ${count} 篇`,
          }}
        />
      </Card>
    </div>
  );
}
