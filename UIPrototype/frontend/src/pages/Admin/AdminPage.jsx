import { useState } from 'react';
import {
  Card, Tabs, Row, Col, Statistic, List, Tag, Table, Progress, Select, Button,
  Input, Modal, Typography, message, Alert
} from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  ADMIN_AGENTS, ADMIN_TASKS, ADMIN_EXCEPTIONS, ADMIN_ACTIVITY,
  ADMIN_TODOS, ADMIN_USERS, TASK_STATUS_LABELS
} from '../../data/admin';

const { Text, Paragraph } = Typography;

const healthColor = { ok: 'success', warn: 'warning', err: 'error' };

function OverviewTab({ onGo }) {
  return (
    <>
      <Row gutter={[12, 12]}>
        {[
          { title: '总论文数', value: 12847, suffix: '+128 本周' },
          { title: '总用户数', value: 3562, suffix: '+42 本周' },
          { title: '今日活跃用户', value: 486, suffix: '较昨日 +12%' },
          { title: '今日新增论文', value: 37, suffix: '抓取完成 35' },
          { title: '系统运行时长', value: '18d 6h', suffix: '自上次部署' }
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
              dataSource={ADMIN_AGENTS}
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
            {ADMIN_TODOS.map((t) => (
              <Card key={t.text} size="small" hoverable style={{ marginBottom: 8 }} onClick={() => onGo(t.action)}>
                <Text strong>{t.text}</Text>
              </Card>
            ))}
          </Card>
        </Col>
      </Row>
      <Card title="近期活动动态" size="small" style={{ marginTop: 16 }}>
        <List size="small" dataSource={ADMIN_ACTIVITY} renderItem={(a) => (
          <List.Item actions={[<Text type="secondary" key="t">{a.time}</Text>]}>{a.text}</List.Item>
        )} />
      </Card>
    </>
  );
}

function FleetTab() {
  const [selected, setSelected] = useState(null);
  const agent = ADMIN_AGENTS.find((a) => a.id === selected);

  return (
    <Row gutter={16}>
      <Col xs={24} lg={14}>
        <Table
          size="small"
          rowKey="id"
          dataSource={ADMIN_AGENTS}
          onRow={(r) => ({ onClick: () => setSelected(r.id), style: { cursor: 'pointer' } })}
          columns={[
            { title: 'Agent', dataIndex: 'name', render: (n, r) => <><Tag color={healthColor[r.health]} />{n}</> },
            { title: '状态', dataIndex: 'status' },
            { title: '当前任务', dataIndex: 'task', ellipsis: true },
            { title: '最后活跃', dataIndex: 'lastActive' },
            {
              title: '运维',
              render: (_, r) => (
                <Button size="small" onClick={(e) => { e.stopPropagation(); message.success(`${r.name} 已重启`); }}>重启</Button>
              )
            }
          ]}
          pagination={false}
        />
      </Col>
      <Col xs={24} lg={10}>
        <Card title="Agent 详细指标 · 24h" size="small">
          {agent ? (
            <List size="small" dataSource={[
              ['处理量', `${agent.processed24h} 篇`],
              ['平均耗时', agent.avgTime],
              ['成功率', `${agent.successRate}%`],
              ['失败率', `${agent.failRate}%`]
            ]} renderItem={([k, v]) => <List.Item><Text type="secondary">{k}</Text><Text strong>{v}</Text></List.Item>} />
          ) : (
            <Text type="secondary">点击左侧 Agent 查看指标</Text>
          )}
        </Card>
      </Col>
    </Row>
  );
}

function TasksTab() {
  const [status, setStatus] = useState('all');
  const filtered = status === 'all' ? ADMIN_TASKS : ADMIN_TASKS.filter((t) => t.status === status);
  const counts = { pending: 0, processing: 0, done: 0, failed: 0 };
  ADMIN_TASKS.forEach((t) => counts[t.status]++);

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

function QualityTab() {
  const navigate = useNavigate();
  return (
    <Row gutter={16}>
      <Col xs={24} lg={14}>
        <Card title="异常论文工作台" size="small">
          <List dataSource={ADMIN_EXCEPTIONS} renderItem={(e) => (
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
          {[{ l: '抓取', v: 0.8 }, { l: '摘要', v: 5.9 }, { l: '问答', v: 12 }].map((d) => (
            <div key={d.l} style={{ marginTop: 8 }}><Text style={{ width: 48, display: 'inline-block' }}>{d.l}</Text><Progress percent={d.v * 8} size="small" showInfo={false} /><Text style={{ marginLeft: 8 }}>{d.v}%</Text></div>
          ))}
        </Card>
      </Col>
    </Row>
  );
}

function UsersTab() {
  return (
    <Card title="用户管理" size="small">
      <Table size="small" pagination={false} rowKey="email" dataSource={ADMIN_USERS} columns={[
        { title: '用户', dataIndex: 'email' },
        { title: '角色', dataIndex: 'role' },
        { title: '状态', dataIndex: 'status' },
        { title: '操作', render: (_, r) => <Button size="small">{r.status === '启用' ? '禁用' : '启用'}</Button> }
      ]} />
    </Card>
  );
}

function AuditTab() {
  const logs = [
    { user: 'admin', time: '2026-07-09 09:45', type: '重启Agent', detail: '重启摘要Agent' },
    { user: 'admin', time: '2026-07-08 16:20', type: '人工修正', detail: '修正 methods.md' }
  ];
  const sysLogs = [
    { level: 'Info', msg: 'FetchAgent: 37 papers ingested' },
    { level: 'Error', msg: 'QAAgent: connection timeout' }
  ];
  return (
    <Row gutter={16}>
      <Col xs={24} lg={12}>
        <Card title="操作审计日志" size="small">
          <List size="small" dataSource={logs} renderItem={(l) => (
            <List.Item><List.Item.Meta title={l.detail} description={`${l.user} · ${l.time} · ${l.type}`} /></List.Item>
          )} />
        </Card>
      </Col>
      <Col xs={24} lg={12}>
        <Card title="系统运行日志" size="small" extra={<Input placeholder="关键词" size="small" style={{ width: 120 }} />}>
          <List size="small" dataSource={sysLogs} renderItem={(l) => (
            <List.Item><Tag color={l.level === 'Error' ? 'error' : 'default'}>{l.level}</Tag>{l.msg}</List.Item>
          )} />
        </Card>
      </Col>
    </Row>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState('overview');
  const items = [
    { key: 'overview', label: '系统概览', children: <OverviewTab onGo={setTab} /> },
    { key: 'fleet', label: 'Agent舰队', children: <FleetTab /> },
    { key: 'tasks', label: '任务队列', children: <TasksTab /> },
    { key: 'quality', label: '质量异常', children: <QualityTab /> },
    { key: 'users', label: '用户管理', children: <UsersTab /> },
    { key: 'audit', label: '审计日志', children: <AuditTab /> }
  ];

  return (
    <div>
      <Alert message="管理员专用 · 系统管理端" description="正式环境仅管理员账户可见" type="info" showIcon style={{ marginBottom: 16 }} />
      <Card className="section-card"><Tabs activeKey={tab} onChange={setTab} items={items} /></Card>
    </div>
  );
}
