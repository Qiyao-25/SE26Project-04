import { useEffect, useState } from 'react';
import {
  Alert, Card, Tabs, Row, Col, Statistic, List, Tag, Table, Progress, Select, Button,
  Input, Typography, message, Space, Popconfirm, Modal, Radio
} from 'antd';
import { useNavigate } from 'react-router-dom';
import { TASK_STATUS_LABELS } from '../../data/admin';
import {
  getAdminAudit,
  getAdminOverview,
  getAdminQuality,
  getAdminTasks,
  getAdminUsers,
  updateAdminUserStatus,
  deleteAdminUser,
  retryAdminParseTask,
  enqueuePendingParseTasks,
  deleteAdminParseTask,
} from '../../services/adminService';
import { deletePaper } from '../../services/paperService';
import { formatDateTime } from '../../utils/datetime';

const { Text } = Typography;

function OverviewTab({ onGo, overview, activities = [] }) {
  const metrics = overview?.metrics || {};
  const agents = overview?.agents || [];
  return (
    <>
      <Row gutter={[12, 12]}>
        {[
          { title: '总论文数', value: metrics.papers ?? 0, suffix: '数据库' },
          { title: '用户数', value: metrics.users ?? 0, suffix: '已注册' },
          { title: '可问答论文', value: metrics.qa_ready ?? 0, suffix: 'qa_ready' },
          { title: '解析任务数', value: metrics.tasks ?? 0, suffix: '全部状态' },
          { title: '系统运行时长', value: metrics.uptime || '—', suffix: '当前进程' }
        ].map((m) => (
          <Col xs={12} sm={8} lg={4} key={m.title} flex="1" style={{ minWidth: 140 }}>
            <Card size="small"><Statistic title={m.title} value={m.value} suffix={<Text type="secondary" style={{ fontSize: 11 }}>{m.suffix}</Text>} /></Card>
          </Col>
        ))}
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="Agent 就绪状态" size="small">
            <List
              dataSource={agents}
              renderItem={(a) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<Tag color={a.ready ? 'success' : 'warning'}>{a.ready ? '就绪' : '降级'}</Tag>}
                    title={a.name}
                    description={a.status}
                  />
                  <Text type="secondary" style={{ fontSize: 11 }}>{a.role || a.id}</Text>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="待办事项" size="small">
            {[['任务队列', 'tasks'], ['质量异常', 'quality'], ['用户管理', 'users']].map(([text, action]) => (
              <Card key={text} size="small" hoverable style={{ marginBottom: 8 }} onClick={() => onGo(action)}>
                <Text strong>{text}</Text>
              </Card>
            ))}
          </Card>
        </Col>
      </Row>
      <Card title="近期活动动态" size="small" style={{ marginTop: 16 }}>
        <List size="small" dataSource={activities} locale={{ emptyText: '暂无近期活动' }} renderItem={(a) => (
          <List.Item actions={[<Text type="secondary" key="t">{formatDateTime(a.time)}</Text>]}>{a.detail}</List.Item>
        )} />
      </Card>
    </>
  );
}

function TasksTab({ tasks = [] }) {
  const [status, setStatus] = useState('all');
  const filtered = status === 'all' ? tasks : tasks.filter((t) => t.status === status);
  const counts = { pending: 0, processing: 0, done: 0, failed: 0 };
  tasks.forEach((t) => { if (counts[t.status] !== undefined) counts[t.status]++; });

  return (
    <>
      <Row gutter={12} style={{ marginBottom: 16 }}>
        {Object.entries(TASK_STATUS_LABELS).map(([k, label]) => (
          <Col span={6} key={k}>
            <Card size="small"><Statistic title={label} value={counts[k]} /></Card>
          </Col>
        ))}
      </Row>
      <Card size="small" extra={
        <Select value={status} onChange={setStatus} style={{ width: 120 }} options={[
          { value: 'all', label: '全部' }, ...Object.entries(TASK_STATUS_LABELS).map(([v, l]) => ({ value: v, label: l }))
        ]} />
      }>
        <Table size="small" rowKey="id" dataSource={filtered} pagination={false} columns={[
          { title: '论文', dataIndex: 'title', ellipsis: true },
          { title: 'Agent', dataIndex: 'agent' },
          { title: '状态', dataIndex: 'status', render: (s) => <Tag>{TASK_STATUS_LABELS[s]}</Tag> },
          { title: '进度', dataIndex: 'progress', render: (p) => <Progress percent={p} size="small" /> },
          { title: '开始', dataIndex: 'start' },
          { title: '耗时', dataIndex: 'duration' }
        ]} />
      </Card>
    </>
  );
}

function QualityTab({ quality, onRefresh }) {
  const navigate = useNavigate();
  const exceptions = quality?.exceptions || [];
  const rates = quality?.rates || {};
  const queue = quality?.queue || {};
  const [busyKey, setBusyKey] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteMode, setDeleteMode] = useState('task');

  const runAction = async (key, action, successText) => {
    setBusyKey(key);
    try {
      await action();
      message.success(successText);
      await onRefresh?.();
    } catch (error) {
      message.error(error.message || '操作失败');
    } finally {
      setBusyKey('');
    }
  };

  const openDeleteModal = (item) => {
    setDeleteTarget(item);
    setDeleteMode('task');
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const key = `delete-${deleteTarget.task_id}`;
    const mode = deleteMode;
    const target = deleteTarget;
    setDeleteTarget(null);
    if (mode === 'paper') {
      await runAction(
        key,
        () => deletePaper(target.paper),
        '已删除论文（软删除）',
      );
      return;
    }
    await runAction(
      key,
      () => deleteAdminParseTask(target.task_id),
      '已删除解析任务',
    );
  };

  return (
    <Row gutter={16}>
      <Col span={24} style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          message="质量异常处理说明"
          description="重试=失败任务再跑；删除=可仅删任务或直接删论文；入队待解析=把未解析论文入队；打开论文=人工查看。"
        />
      </Col>
      <Col xs={24} lg={14}>
        <Card
          title="异常论文工作台"
          size="small"
          extra={(
            <Space>
              <Button
                size="small"
                loading={busyKey === 'enqueue'}
                onClick={() => runAction('enqueue', () => enqueuePendingParseTasks(20), '已将待解析论文加入队列')}
              >
                入队待解析
              </Button>
              <Button size="small" onClick={() => onRefresh?.()}>刷新</Button>
            </Space>
          )}
        >
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
            汇总解析失败 / 超时任务。PDF/HTML 均空会自动软删；崩溃类失败最多自动重试 1 次，仍失败则软删。可手动重试或删除。
          </Text>
          <List dataSource={exceptions} locale={{ emptyText: '暂无质量异常' }} renderItem={(e) => (
            <List.Item actions={[
              e.retryable ? (
                <Button
                  size="small"
                  key="retry"
                  loading={busyKey === `retry-${e.task_id}`}
                  onClick={() => runAction(`retry-${e.task_id}`, () => retryAdminParseTask(e.task_id), '已重试解析任务')}
                >
                  重试
                </Button>
              ) : null,
              <Button
                size="small"
                danger
                key="delete"
                loading={busyKey === `delete-${e.task_id}`}
                onClick={() => openDeleteModal(e)}
              >
                删除
              </Button>,
              <Button size="small" key="view" onClick={() => navigate(`/paper/${e.paper}`)}>打开论文</Button>
            ].filter(Boolean)}
            >
              <List.Item.Meta
                title={e.title}
                description={(
                  <>
                    <div>
                      <Tag color="blue">{e.agent || '解析流水线'}</Tag>
                      <Tag>{e.stage_label || e.type || '未知阶段'}</Tag>
                    </div>
                    <div style={{ marginTop: 6 }}>{e.detail}</div>
                    <Text type="secondary">
                      {e.error_code || e.type} · {e.status} · 第 {e.attempt || 1} 次 · {formatDateTime(e.time)}
                    </Text>
                  </>
                )}
              />
            </List.Item>
          )} />
        </Card>
      </Col>
      <Col xs={24} lg={10}>
        <Card title="队列与质量统计" size="small">
          <List
            size="small"
            dataSource={[
              ['待解析论文', queue.pending_papers ?? 0],
              ['排队中任务', queue.queued_tasks ?? 0],
              ['运行中任务', queue.running_tasks ?? 0],
              ['失败任务', queue.failed_tasks ?? 0],
            ]}
            renderItem={([label, value]) => (
              <List.Item>
                <Text type="secondary">{label}</Text>
                <Text strong>{value}</Text>
              </List.Item>
            )}
          />
          <Text type="secondary" style={{ display: 'block', marginTop: 12 }}>各阶段失败占比</Text>
          {Object.entries(rates).map(([label, value]) => (
            <div key={label} style={{ marginTop: 8 }}>
              <Text style={{ width: 64, display: 'inline-block' }}>{label}</Text>
              <Progress percent={value} size="small" showInfo={false} />
              <Text style={{ marginLeft: 8 }}>{value}%</Text>
            </div>
          ))}
        </Card>
      </Col>

      <Modal
        title="删除异常项"
        open={Boolean(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
        onOk={confirmDelete}
        okText="确认删除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
      >
        <Text style={{ display: 'block', marginBottom: 12 }}>
          {deleteTarget?.title || '选中的异常论文'}
        </Text>
        <Radio.Group
          value={deleteMode}
          onChange={(event) => setDeleteMode(event.target.value)}
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          <Radio value="task">仅删除解析任务（保留论文）</Radio>
          <Radio value="paper">直接删除论文（软删除，论文库不再展示）</Radio>
        </Radio.Group>
      </Modal>
    </Row>
  );
}

function UsersTab({ users = [], onStatusChange, onDelete }) {
  return (
    <Card title="用户管理" size="small">
      <Table size="small" pagination={false} rowKey="email" dataSource={users} locale={{ emptyText: '暂无注册用户' }} columns={[
        { title: '用户', dataIndex: 'email' },
        { title: '角色', dataIndex: 'role' },
        { title: '状态', dataIndex: 'status' },
        { title: '操作', render: (_, user) => (
          user.role === 'admin'
            ? <Text type="secondary">不可禁用</Text>
            : (
              <Space>
                <Button size="small" onClick={() => onStatusChange(user)}>{user.status === '启用' ? '禁用' : '启用'}</Button>
                <Popconfirm title={`确定删除用户 ${user.email}？`} onConfirm={() => onDelete?.(user)}>
                  <Button size="small" danger>删除</Button>
                </Popconfirm>
              </Space>
            )
        ) }
      ]} />
    </Card>
  );
}

function AuditTab({ logs = [] }) {
  const [query, setQuery] = useState('');
  const filteredLogs = logs.filter((item) => `${item.detail} ${item.type} ${item.user}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <Row gutter={16}>
      <Col xs={24} lg={12}>
        <Card title="操作审计日志" size="small">
          <List size="small" dataSource={filteredLogs} locale={{ emptyText: '暂无审计记录' }} renderItem={(l) => (
            <List.Item><List.Item.Meta title={l.detail} description={`${l.user} · ${formatDateTime(l.time)} · ${l.type}`} /></List.Item>
          )} />
        </Card>
      </Col>
      <Col xs={24} lg={12}>
        <Card title="系统运行日志" size="small">
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="关键词" size="small" style={{ width: 120 }} />
          <List size="small" dataSource={filteredLogs} locale={{ emptyText: '暂无系统记录' }} renderItem={(l) => (
            <List.Item><Tag color={l.level === 'Error' ? 'error' : 'default'}>{l.level}</Tag>{l.detail}</List.Item>
          )} />
        </Card>
      </Col>
    </Row>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState('overview');
  const [overview, setOverview] = useState(null);
  const [tasks, setTasks] = useState(null);
  const [quality, setQuality] = useState(null);
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [error, setError] = useState('');

  const handleUserStatusChange = async (user) => {
    try {
      const updated = await updateAdminUserStatus(user.id, user.status !== '启用');
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item));
      message.success(`${updated.email} 已${updated.status}`);
    } catch (requestError) {
      message.error(requestError.message || '用户状态更新失败');
    }
  };

  const handleUserDelete = async (user) => {
    try {
      await deleteAdminUser(user.id);
      setUsers((current) => current.filter((item) => item.id !== user.id));
      message.success(`已删除用户 ${user.email}`);
    } catch (requestError) {
      message.error(requestError.message || '用户删除失败');
    }
  };

  const refreshAdminData = async () => {
    const [nextOverview, nextTasks, nextQuality, nextUsers, nextAudit] = await Promise.all([
      getAdminOverview(), getAdminTasks(), getAdminQuality(), getAdminUsers(), getAdminAudit()
    ]);
    setOverview(nextOverview);
    setTasks((nextTasks || []).map((task) => ({
      id: task.id,
      title: task.title,
      agent: task.stage ? `流水线 · ${task.stage}` : '解析流水线',
      status: task.status === 'queued' ? 'pending' : task.status === 'running' ? 'processing' : task.status === 'succeeded' ? 'done' : 'failed',
      progress: task.progress,
      start: formatDateTime(task.started_at),
      duration: task.finished_at && task.started_at ? '已完成' : '—'
    })));
    setQuality(nextQuality);
    setUsers(nextUsers || []);
    setAudit(nextAudit || []);
  };

  useEffect(() => {
    refreshAdminData().catch((requestError) => setError(requestError.message || '管理员数据加载失败'));
  }, []);

  const items = [
    { key: 'overview', label: '系统概览', children: <OverviewTab onGo={setTab} overview={overview} activities={audit} /> },
    { key: 'tasks', label: '任务队列', children: <TasksTab tasks={tasks || []} /> },
    { key: 'quality', label: '质量异常', children: <QualityTab quality={quality} onRefresh={refreshAdminData} /> },
    { key: 'users', label: '用户管理', children: <UsersTab users={users} onStatusChange={handleUserStatusChange} onDelete={handleUserDelete} /> },
    { key: 'audit', label: '审计日志', children: <AuditTab logs={audit} /> }
  ];

  return (
    <div className="page-admin">
      {error && <Card className="section-card"><Text type="danger">{error}</Text></Card>}
      <Card className="section-card"><Tabs activeKey={tab} onChange={setTab} items={items} /></Card>
    </div>
  );
}
