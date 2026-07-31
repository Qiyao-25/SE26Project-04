/** Shared arXiv subject taxonomy for subscription / profile pickers.
 *  Users may also type any valid arXiv category code (e.g. cs.NE, math.OC).
 */
export const ARXIV_CATEGORIES = [
  // Computer Science
  { value: 'cs.AI', label: 'cs.AI · 人工智能' },
  { value: 'cs.LG', label: 'cs.LG · 机器学习' },
  { value: 'cs.CL', label: 'cs.CL · 计算语言学 / NLP' },
  { value: 'cs.CV', label: 'cs.CV · 计算机视觉' },
  { value: 'cs.IR', label: 'cs.IR · 信息检索' },
  { value: 'cs.NE', label: 'cs.NE · 神经与进化计算' },
  { value: 'cs.SE', label: 'cs.SE · 软件工程' },
  { value: 'cs.RO', label: 'cs.RO · 机器人学' },
  { value: 'cs.HC', label: 'cs.HC · 人机交互' },
  { value: 'cs.CR', label: 'cs.CR · 密码学与安全' },
  { value: 'cs.DB', label: 'cs.DB · 数据库' },
  { value: 'cs.DC', label: 'cs.DC · 分布式 / 并行 / 集群' },
  { value: 'cs.DS', label: 'cs.DS · 数据结构与算法' },
  { value: 'cs.GT', label: 'cs.GT · 计算机科学与博弈论' },
  { value: 'cs.IT', label: 'cs.IT · 信息论' },
  { value: 'cs.MA', label: 'cs.MA · 多智能体系统' },
  { value: 'cs.MM', label: 'cs.MM · 多媒体' },
  { value: 'cs.NI', label: 'cs.NI · 网络与互联网架构' },
  { value: 'cs.OS', label: 'cs.OS · 操作系统' },
  { value: 'cs.PL', label: 'cs.PL · 编程语言' },
  { value: 'cs.SI', label: 'cs.SI · 社会与信息网络' },
  { value: 'cs.SY', label: 'cs.SY · 系统与控制' },
  { value: 'cs.CY', label: 'cs.CY · 计算机与社会' },
  { value: 'cs.CG', label: 'cs.CG · 计算几何' },
  { value: 'cs.CE', label: 'cs.CE · 计算工程 / 金融 / 科学' },
  { value: 'cs.ET', label: 'cs.ET · 新兴技术' },
  { value: 'cs.FL', label: 'cs.FL · 形式语言与自动机' },
  { value: 'cs.GR', label: 'cs.GR · 图形学' },
  { value: 'cs.AR', label: 'cs.AR · 硬件架构' },
  { value: 'cs.SD', label: 'cs.SD · 声音' },
  { value: 'cs.SC', label: 'cs.SC · 符号计算' },
  { value: 'cs.OH', label: 'cs.OH · 其他计算机科学' },

  // Statistics / EESS / Math
  { value: 'stat.ML', label: 'stat.ML · 统计机器学习' },
  { value: 'stat.AP', label: 'stat.AP · 统计学应用' },
  { value: 'stat.ME', label: 'stat.ME · 方法论' },
  { value: 'stat.TH', label: 'stat.TH · 统计理论' },
  { value: 'eess.AS', label: 'eess.AS · 音频与语音处理' },
  { value: 'eess.IV', label: 'eess.IV · 图像与视频处理' },
  { value: 'eess.SP', label: 'eess.SP · 信号处理' },
  { value: 'eess.SY', label: 'eess.SY · 系统与控制' },
  { value: 'math.OC', label: 'math.OC · 优化与控制' },
  { value: 'math.PR', label: 'math.PR · 概率论' },
  { value: 'math.ST', label: 'math.ST · 统计理论' },
  { value: 'math.NA', label: 'math.NA · 数值分析' },
  { value: 'math.CO', label: 'math.CO · 组合数学' },
  { value: 'math.DS', label: 'math.DS · 动力系统' },
  { value: 'math.IT', label: 'math.IT · 信息论' },

  // Physics (common ML-adjacent + broad)
  { value: 'physics.comp-ph', label: 'physics.comp-ph · 计算物理' },
  { value: 'physics.data-an', label: 'physics.data-an · 数据分析和统计' },
  { value: 'physics.app-ph', label: 'physics.app-ph · 应用物理' },
  { value: 'cond-mat.dis-nn', label: 'cond-mat.dis-nn · 无序系统与神经网络' },
  { value: 'cond-mat.stat-mech', label: 'cond-mat.stat-mech · 统计力学' },
  { value: 'quant-ph', label: 'quant-ph · 量子物理' },
  { value: 'hep-th', label: 'hep-th · 高能理论' },
  { value: 'astro-ph.CO', label: 'astro-ph.CO · 宇宙学与天体物理' },
  { value: 'astro-ph.GA', label: 'astro-ph.GA · 天体物理学（星系）' },
  { value: 'astro-ph.IM', label: 'astro-ph.IM · 仪器与方法' },
  { value: 'gr-qc', label: 'gr-qc · 广义相对论与量子宇宙学' },
  { value: 'nlin.AO', label: 'nlin.AO · 自适应与自组织系统' },
  { value: 'nlin.CD', label: 'nlin.CD · 混沌动力学' },

  // Quantitative Biology / Finance / Economics
  { value: 'q-bio.BM', label: 'q-bio.BM · 生物分子' },
  { value: 'q-bio.GN', label: 'q-bio.GN · 基因组学' },
  { value: 'q-bio.NC', label: 'q-bio.NC · 神经元与认知' },
  { value: 'q-bio.QM', label: 'q-bio.QM · 定量方法' },
  { value: 'q-fin.CP', label: 'q-fin.CP · 计算金融' },
  { value: 'q-fin.PM', label: 'q-fin.PM · 投资组合管理' },
  { value: 'q-fin.ST', label: 'q-fin.ST · 统计金融' },
  { value: 'econ.EM', label: 'econ.EM · 计量经济学' },
  { value: 'econ.GN', label: 'econ.GN · 一般经济学' },
  { value: 'econ.TH', label: 'econ.TH · 理论经济学' },
];

/** arXiv 主题大类（用于论文库主题筛选） */
export const ARXIV_TOPIC_GROUPS = [
  { value: 'cs', label: '计算机科学 (cs)' },
  { value: 'stat', label: '统计学 (stat)' },
  { value: 'math', label: '数学 (math)' },
  { value: 'eess', label: '电气工程与系统 (eess)' },
  { value: 'physics', label: '物理学 (physics)' },
  { value: 'cond-mat', label: '凝聚态 (cond-mat)' },
  { value: 'quant-ph', label: '量子物理 (quant-ph)' },
  { value: 'astro-ph', label: '天体物理 (astro-ph)' },
  { value: 'q-bio', label: '定量生物学 (q-bio)' },
  { value: 'q-fin', label: '定量金融 (q-fin)' },
  { value: 'econ', label: '经济学 (econ)' },
  { value: 'nlin', label: '非线性科学 (nlin)' },
];

export const ARXIV_CATEGORY_LABEL_MAP = Object.fromEntries(
  ARXIV_CATEGORIES.map((item) => [item.value, item.label]),
);

/** Common profile topic chips (categories + free keywords). */
export const PROFILE_TOPIC_OPTIONS = [
  ...ARXIV_CATEGORIES.slice(0, 12).map((item) => item.value),
  'Transformer',
  'RAG',
  'LLM',
  'Diffusion',
  'Reinforcement Learning',
  'Multimodal',
];
