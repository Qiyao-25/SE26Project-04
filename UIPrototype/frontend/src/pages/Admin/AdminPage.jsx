import { useEffect, useState } from 'react';
import {
  Card, Tabs, Row, Col, Statistic, List, Tag, Table, Progress, Select, Button,
  Input, Typography
} from 'antd';
import { useNavigate } from 'react-router-dom';
import { TASK_STATUS_LABELS } from '../../data/admin';
import { getAdminAudit, getAdminOverview, getAdminQuality, getAdminTasks, getAdminUsers } from '../../services/adminService';

const { Text } = Typography;

const healthColor = { ok: 'success', warn: 'warning', err: 'error' };

function OverviewTab({ onGo, overview, activities = [] }) {
  const metrics = overview?.metrics || {};
  const agents = (overview?.agents || []).map((agent) => ({
    ...agent,
    health: agent.ready ? 'ok' : 'warn',
    task: agent.status,
    latency: '—',
    cpu: '—'
  }));
  return (
    <>
      <Row gutter={[12, 12]}>
        {[
          { title: '总论文数', value: metrics.papers ?? 0, suffix: '数据库' },
          { title: '用户数', value: metrics.users ?? 0, suffix: '已注册' },
          { title: '可问答论文', value: metrics.qa_ready ?? 0, suffix: 'qa_ready' },
          { title: '解析任务数', value: metrics.tasks ?? 0, suffix: '全部状态' },
          { title: '系统运行时长', value: '—', suffix: '当前进程' }
        ].map((m) => (
          <Col xs={12} sm={8} lg={4} key={m.title} flex="1" style={{ minWidth: 140 }}>
            <Card size="small"><Statistic title={m.title} value={m.value} suffix={<Text type="secondary" style={{ fontSize: 11 }}>{m.suffix}</Text>} /></Card>
          </Col>
        ))}
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="系统健康状态 · Agent" size="small">
            <List
              dataSource={agents}
              renderItem={(a) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<Tag color={healthColor[a.health]}>{a.health === 'ok' ? '正常' : a.health === 'warn' ? '警告' : '异常'}</Tag>}
                    title={a.name}
                    description={`${a.status} · ${a.task}`}
                  />
                  <Text type="secondary" style={{ fontSize: 11 }}>延迟 {a.latency} · CPU {a.cpu}</Text>
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
          <List.Item actions={[<Text type="secondary" key="t">{a.time}</Text>]}>{a.detail}</List.Item>
        )} />
      </Card>
    </>
  );
}

function FleetTab({ agents = [] }) {
  const [selected, setSelected] = useState(null);
  const agent = agents.find((a) => a.id === selected);

  return (
    <Row gutter={16}>
      <Col xs={24} lg={14}>
        <Table
          size="small"
          rowKey="id"
          dataSource={agents}
          onRow={(r) => ({ onClick: () => setSelected(r.id), style: { cursor: 'pointer' } })}
          columns={[
            { title: 'Agent', dataIndex: 'name', render: (n, r) => <><Tag color={healthColor[r.health]} />{n}</> },
            { title: '状态', dataIndex: 'status' },
            { title: '当前任务', dataIndex: 'task', ellipsis: true },
            { title: '最后活跃', dataIndex: 'lastActive' },
          ]}
          pagination={false}
        />
      </Col>
      <Col xs={24} lg={10}>
        <Card title="Agent 详细指标 · 24h" size="small">
          {agent ? (
            <List size="small" dataSource={[
              ['状态', agent.status],
              ['当前任务', agent.task || '—'],
              ['配置状态', agent.ready ? '已配置' : '降级模式'],
              ['监控指标', '后端暂未采集']
            ]} renderItem={([k, v]) => <List.Item><Text type="secondary">{k}</Text><Text strong>{v}</Text></List.Item>} />
          ) : (
            <Text type="secondary">点击左侧 Agent 查看指标</Text>
          )}
        </Card>
      </Col>
    </Row>
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

function QualityTab({ quality }) {
  const navigate = useNavigate();
  const exceptions = quality?.exceptions || [];
  const rates = quality?.rates || {};
  return (
    <Row gutter={16}>
      <Col xs={24} lg={14}>
        <Card title="异常论文工作台" size="small">
          <List dataSource={exceptions} locale={{ emptyText: '暂无质量异常' }} renderItem={(e) => (
            <List.Item actions={[
              <Button size="small" key="fix" onClick={() => navigate(`/paper/${e.paper}`)}>人工修正</Button>
            ]}>
              <List.Item.Meta title={e.title} description={<>{e.detail}<br /><Text type="secondary">{e.type} · {e.time}</Text></>} />
            </List.Item>
          )} />
        </Card>
      </Col>
      <Col xs={24} lg={10}>
        <Card title="质量统计" size="small">
          <Text type="secondary">各 Agent 错误率（近7日）</Text>
          {Object.entries(rates).map(([label, value]) => (
            <div key={label} style={{ marginTop: 8 }}><Text style={{ width: 48, display: 'inline-block' }}>{label}</Text><Progress percent={value} size="small" showInfo={false} /><Text style={{ marginLeft: 8 }}>{value}%</Text></div>
          ))}
        </Card>
      </Col>
    </Row>
  );
}

function UsersTab({ users = [] }) {
  return (
    <Card title="用户管理" size="small">
      <Table size="small" pagination={false} rowKey="email" dataSource={users} locale={{ emptyText: '暂无注册用户' }} columns={[
        { title: '用户', dataIndex: 'email' },
        { title: '角色', dataIndex: 'role' },
        { title: '状态', dataIndex: 'status' },
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
            <List.Item><List.Item.Meta title={l.detail} description={`${l.user} · ${l.time} · ${l.type}`} /></List.Item>
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

  useEffect(() => {
    Promise.all([getAdminOverview(), getAdminTasks(), getAdminQuality(), getAdminUsers(), getAdminAudit()])
      .then(([nextOverview, nextTasks, nextQuality, nextUsers, nextAudit]) => {
        setOverview(nextOverview);
        setTasks((nextTasks || []).map((task) => ({
          id: task.id,
          title: task.title,
          agent: '解析 Agent',
          status: task.status === 'queued' ? 'pending' : task.status === 'running' ? 'processing' : task.status === 'succeeded' ? 'done' : 'failed',
          progress: task.progress,
          start: task.started_at || '—',
          duration: task.finished_at && task.started_at ? '已完成' : '—'
        })));
        setQuality(nextQuality);
        setUsers(nextUsers || []);
        setAudit(nextAudit || []);
      })
      .catch((requestError) => setError(requestError.message || '管理员数据加载失败'));
  }, []);

  const items = [
    { key: 'overview', label: '系统概览', children: <OverviewTab onGo={setTab} overview={overview} activities={audit} /> },
    { key: 'fleet', label: 'Agent舰队', children: <FleetTab agents={(overview?.agents || []).map((agent) => ({ ...agent, health: agent.ready ? 'ok' : 'warn', task: agent.status, latency: '—', cpu: '—' }))} /> },
    { key: 'tasks', label: '任务队列', children: <TasksTab tasks={tasks || []} /> },
    { key: 'quality', label: '质量异常', children: <QualityTab quality={quality} /> },
    { key: 'users', label: '用户管理', children: <UsersTab users={users} /> },
    { key: 'audit', label: '审计日志', children: <AuditTab logs={audit} /> }
  ];

  return (
    <div>
      {error && <Card className="section-card"><Text type="danger">{error}</Text></Card>}
      <Card className="section-card"><Tabs activeKey={tab} onChange={setTab} items={items} /></Card>
    </div>
  );
}
