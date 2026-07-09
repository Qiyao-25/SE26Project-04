import { useState } from 'react';
import { Card, Tabs, message } from 'antd';
import SidebarAllPanel from './sidebar/SidebarAllPanel';
import SidebarInfoPanel from './sidebar/SidebarInfoPanel';
import SidebarQaPanel from './sidebar/SidebarQaPanel';
import SidebarAssistPanel from './sidebar/SidebarAssistPanel';
import SidebarNotesPanel from './sidebar/SidebarNotesPanel';
import SidebarComparePanel from './sidebar/SidebarComparePanel';

export default function PaperSidebar({ paperId, paper }) {
  const [activeKey, setActiveKey] = useState('all');

  const goTab = (key) => {
    setActiveKey(key);
    const labels = { all: '全部', info: '信息', qa: '问答', assist: '辅助', notes: '笔记', compare: '对比阅读' };
    message.info(`已展开${labels[key] || ''}`);
  };

  const items = [
    {
      key: 'all',
      label: '全部',
      children: <SidebarAllPanel paper={paper} paperId={paperId} onGoTab={goTab} />
    },
    { key: 'info', label: '信息', children: <SidebarInfoPanel paper={paper} paperId={paperId} /> },
    { key: 'qa', label: '问答', children: <SidebarQaPanel paperId={paperId} /> },
    { key: 'assist', label: '辅助', children: <SidebarAssistPanel paper={paper} /> },
    { key: 'notes', label: '笔记', children: <SidebarNotesPanel paperId={paperId} /> },
    { key: 'compare', label: '对比', children: <SidebarComparePanel paperId={paperId} /> }
  ];

  return (
    <Card className="section-card paper-sidebar-card">
      <Tabs activeKey={activeKey} onChange={setActiveKey} size="small" items={items} className="sidebar-tabs" />
    </Card>
  );
}
