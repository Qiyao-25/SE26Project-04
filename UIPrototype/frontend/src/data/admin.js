export const ADMIN_AGENTS = [
  { id: 'fetch', name: '抓取Agent', health: 'ok', status: '运行中', task: 'arXiv cs.LG 批量抓取', lastActive: '刚刚', latency: '120ms', cpu: '18%', mem: '256MB', processed24h: 342, avgTime: '2.1s', successRate: 99.2, failRate: 0.8 },
  { id: 'read', name: '阅读Agent', health: 'ok', status: '运行中', task: 'GPT-3 PDF 解析', lastActive: '1 分钟前', latency: '340ms', cpu: '42%', mem: '1.2GB', processed24h: 128, avgTime: '8.4s', successRate: 97.5, failRate: 2.5 },
  { id: 'summary', name: '摘要Agent', health: 'warn', status: '运行中', task: 'BERT summary 生成', lastActive: '30 秒前', latency: '1.2s', cpu: '68%', mem: '2.1GB', processed24h: 96, avgTime: '45s', successRate: 94.1, failRate: 5.9 },
  { id: 'verify', name: '校验Agent', health: 'ok', status: '空闲', task: '—', lastActive: '3 分钟前', latency: '210ms', cpu: '8%', mem: '512MB', processed24h: 89, avgTime: '12s', successRate: 91.0, failRate: 9.0 },
  { id: 'qa', name: '问答Agent', health: 'err', status: '异常', task: '队列积压', lastActive: '12 分钟前', latency: '—', cpu: '—', mem: '—', processed24h: 0, avgTime: '—', successRate: 0, failRate: 100 }
];

export const ADMIN_TASKS = [
  { id: 't1', paper: 'bert', title: 'BERT: Pre-training of Deep Bidirectional Transformers', agent: '摘要Agent', status: 'processing', progress: 60, start: '11:02', duration: '3m 20s' },
  { id: 't2', paper: 'gpt3', title: 'GPT-3: Language Models are Few-Shot Learners', agent: '阅读Agent', status: 'processing', progress: 30, start: '11:08', duration: '1m 45s' },
  { id: 't3', paper: 'lora', title: 'LoRA: Low-Rank Adaptation of LLMs', agent: '校验Agent', status: 'processing', progress: 90, start: '10:45', duration: '8m 10s' },
  { id: 't4', paper: 'attention', title: 'Attention Is All You Need', agent: '校验Agent', status: 'done', progress: 100, start: '09:30', duration: '12m 00s' },
  { id: 't5', paper: 'rag', title: 'Retrieval-Augmented Generation', agent: '抓取Agent', status: 'pending', progress: 0, start: '—', duration: '—' },
  { id: 't6', paper: 'vlm', title: 'Vision-Language Model Survey', agent: '问答Agent', status: 'failed', progress: 15, start: '10:20', duration: '2m 30s' }
];

export const ADMIN_EXCEPTIONS = [
  { id: 'e1', paper: 'bert', title: 'BERT · §4.2 实验结果', type: '数值不一致', detail: '摘要中 F1 分数与原文 Table 2 不一致', time: '2026-07-09 10:53', status: '待处理' },
  { id: 'e2', paper: 'gpt3', title: 'GPT-3 · emergent ability', type: '概念模糊', detail: '概念定义抽取置信度较低', time: '2026-07-09 09:12', status: '待处理' },
  { id: 'e3', paper: 'lora', title: 'LoRA · methods.md', type: '参数不匹配', detail: '学习率数值与原文不完全匹配', time: '2026-07-08 18:40', status: '复核中' }
];

export const ADMIN_ACTIVITY = [
  { text: '已抓取 37 篇新论文', time: '11:28' },
  { text: '摘要生成完成 12 篇', time: '11:15' },
  { text: '校验Agent 标记 3 篇需复核', time: '10:53' },
  { text: '问答Agent 异常告警', time: '10:22' }
];

export const ADMIN_TODOS = [
  { text: '3 篇论文校验未通过', action: 'quality' },
  { text: '2 个任务处理超时', action: 'tasks' },
  { text: '查看多 Agent 流水线就绪状态', action: 'overview' }
];

export const ADMIN_USERS = [
  { email: 'admin@papermate.io', role: '管理员', status: '启用' },
  { email: 'user@example.com', role: '普通用户', status: '启用' },
  { email: 'researcher@lab.edu', role: '高级用户', status: '启用' },
  { email: 'spam@test.com', role: '普通用户', status: '禁用' }
];

export const TASK_STATUS_LABELS = { pending: '待处理', processing: '处理中', done: '已完成', failed: '失败' };
