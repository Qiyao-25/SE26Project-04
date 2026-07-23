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

const SORT_OPTIONS = [
  { value: 'published_desc', label: '发表时间 ↓' },
  { value: 'published_asc', label: '发表时间 ↑' },
  { value: 'created_desc', label: '入库时间 ↓' },
  { value: 'created_asc', label: '入库时间 ↑' },
  { value: 'title_asc', label: '标题首字母 A→Z' },
  { value: 'title_desc', label: '标题首字母 Z→A' },
  { value: 'id_desc', label: '序号 ↓' },
  { value: 'id_asc', label: '序号 ↑' },
  { value: 'relevance', label: '相关度（有关键词时）' },
];

const emptyFilters = {
  keyword: '',
  author: '',
  topic: undefined,
  category: undefined,
  publishedRange: null,
  sortBy: 'published_desc',
};

export default function PaperLibraryPage() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState(emptyFilters);
  const [applied, setApplied] = useState(emptyFilters);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => getLibraryPageSize(20));
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const categoryOptions = useMemo(() => {
    if (!applied.topic) return ARXIV_CATEGORIES;
    return ARXIV_CATEGORIES.filter(
      (item) => item.value === applied.topic || item.value.startsWith(`${applied.topic}.`),
    );
  }, [applied.topic]);

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
        sortBy: applied.sortBy,
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
  }, [applied, page, pageSize]);

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

  const columns = [
    {
      title: '序号',
      dataIndex: 'paperId',
      width: 72,
    },
    {
      title: '标题',
      dataIndex: 'title',
      ellipsis: true,
      render: (title, record) => (
        <Button type="link" style={{ padding: 0, height: 'auto', whiteSpace: 'normal', textAlign: 'left' }} onClick={() => navigate(`/paper/${record.paperId}`)}>
          {title}
        </Button>
      ),
    },
    {
      title: '作者',
      dataIndex: 'authors',
      width: 180,
      ellipsis: true,
      render: (authors) => (Array.isArray(authors) ? authors.join(', ') : authors) || '—',
    },
    {
      title: '主题',
      dataIndex: 'topic',
      width: 90,
      render: (value, record) => <Tag color="geekblue">{value || (record.primaryCategory || '').split('.')[0] || '—'}</Tag>,
    },
    {
      title: '类别',
      dataIndex: 'primaryCategory',
      width: 110,
      render: (value) => <Tag>{value || '未分类'}</Tag>,
    },
    {
      title: 'arXiv',
      dataIndex: 'arxivId',
      width: 130,
      render: (value) => value || '—',
    },
    {
      title: '发表时间',
      dataIndex: 'publishedAt',
      width: 150,
      render: (value) => (value ? formatDateTime(value) : '—'),
    },
    {
      title: '入库时间',
      dataIndex: 'createdAt',
      width: 150,
      render: (value) => (value ? formatDateTime(value) : '—'),
    },
    {
      title: '状态',
      dataIndex: 'parseStatus',
      width: 100,
      render: (value, record) => (
        <Space direction="vertical" size={0}>
          <Text>{value || 'pending'}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>块 {record.chunkCount ?? 0}</Text>
        </Space>
      ),
    },
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

  return (
    <div className="page-paper-library">
      <Card className="section-card" title="论文库">
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          支持按关键词、作者、发表时间、主题大类与 arXiv 类别筛选，并按首字母、序号或入库时间排序。
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
          <Col xs={24} sm={12} md={8} lg={5}>
            <Select
              style={{ width: '100%' }}
              options={SORT_OPTIONS}
              value={draft.sortBy}
              onChange={(value) => setDraft((current) => ({ ...current, sortBy: value }))}
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
        {(applied.topic || applied.category || applied.author || applied.keyword || applied.publishedRange) && (
          <Space wrap size={4} style={{ marginBottom: 12 }}>
            {applied.keyword ? <Tag>关键词：{applied.keyword}</Tag> : null}
            {applied.author ? <Tag>作者：{applied.author}</Tag> : null}
            {applied.topic ? <Tag color="blue">主题：{applied.topic}</Tag> : null}
            {applied.category ? <Tag color="cyan">类别：{applied.category}</Tag> : null}
            {applied.publishedRange ? <Tag>时间范围已选</Tag> : null}
            <Tag>排序：{SORT_OPTIONS.find((item) => item.value === applied.sortBy)?.label || applied.sortBy}</Tag>
            {categoryOptions.length < ARXIV_CATEGORIES.length ? (
              <Text type="secondary" style={{ fontSize: 12 }}>当前主题下可选类别 {categoryOptions.length} 项</Text>
            ) : null}
          </Space>
        )}
        <Table
          rowKey="paperId"
          loading={loading}
          columns={columns}
          dataSource={items}
          scroll={{ x: 1280 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (count) => `共 ${count} 篇`,
            onChange: (nextPage, nextSize) => {
              setPage(nextPage);
              setPageSize(nextSize);
            },
          }}
        />
      </Card>
    </div>
  );
}
