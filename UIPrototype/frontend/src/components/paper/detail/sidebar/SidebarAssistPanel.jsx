import { Tag, Typography, Segmented } from 'antd';
import { useApp } from '../../../../context/AppContext';
import { MODE_ASSIST, PERSONAS } from '../../../../data/papers';

const { Paragraph, Text } = Typography;

export default function SidebarAssistPanel({ paper }) {
  const { persona, setPersona } = useApp();

  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12 }}>默认模式在学习空间设置 · 此处可快捷切换</Text>
      <Segmented
        block
        options={PERSONAS}
        value={persona}
        onChange={setPersona}
        style={{ margin: '12px 0' }}
      />
      <Text className="block-label">个性化总结 · <Tag>{persona}模式</Tag></Text>
      <Paragraph style={{ fontSize: 12, whiteSpace: 'pre-wrap', background: '#fafafa', padding: 12, borderRadius: 4 }}>
        {MODE_ASSIST[persona](paper)}
      </Paragraph>
    </div>
  );
}
