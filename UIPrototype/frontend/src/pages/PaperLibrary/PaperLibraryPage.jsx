import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Input,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { deletePaper, searchPapers } from '../../services/paperService';
import { formatDateTime } from '../../utils/datetime';
import { getLibraryPageSize } from '../../utils/uiPrefs';

const { Text } = Typography;

export default function PaperLibraryPage() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => getLibraryPageSize(20));
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const loadPapers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await searchPapers({ query, page, pageSize });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      message.error(error.message || '论文库加载失败');
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [query, page, pageSize]);

  useEffect(() => {
    loadPapers();
  }, [loadPapers]);

  const handleSearch = () => {
    setPage(1);
    setQuery(keyword.trim());
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
      title: 'ID',
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
      title: '分类',
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
      <Card
        className="section-card"
        title="论文库"
        extra={
          <Space wrap>
            <Input.Search
              allowClear
              placeholder="搜索标题 / 摘要 / arXiv / 分类"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              onSearch={handleSearch}
              enterButton={<><SearchOutlined /> 搜索</>}
              style={{ width: 360, maxWidth: '100%' }}
            />
            <Button icon={<ReloadOutlined />} onClick={loadPapers}>刷新</Button>
          </Space>
        }
      >
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          管理员可翻页浏览库中论文元数据，支持搜索与删除。
        </Text>
        <Table
          rowKey="paperId"
          loading={loading}
          columns={columns}
          dataSource={items}
          scroll={{ x: 1100 }}
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
