import { Modal, Tag, Typography } from 'antd';
import { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { PERSONAS } from '../../data/papers';

const { Text } = Typography;

const TOPICS = ['cs.CL', 'cs.LG', 'cs.CV', 'cs.AI'];

export default function OnboardingModal({ open, onDone }) {
  const { setTopics, setPersona } = useApp();
  const [selectedTopics, setSelectedTopics] = useState(['cs.CL']);
  const [persona, setLocalPersona] = useState('研究');

  const toggleTopic = (t) => {
    setSelectedTopics((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  };

  const handleDone = () => {
    setTopics(selectedTopics.length ? selectedTopics : ['cs.CL']);
    setPersona(persona);
    onDone();
  };

  return (
    <Modal title="首次登录引导" open={open} onOk={handleDone} okText="完成，进入工作空间" cancelButtonProps={{ style: { display: 'none' } }} closable={false}>
      <Text className="block-label">选择研究方向</Text>
      <div style={{ marginBottom: 16 }}>
        {TOPICS.map((t) => (
          <Tag.CheckableTag
            key={t}
            checked={selectedTopics.includes(t)}
            onChange={() => toggleTopic(t)}
            style={{ marginBottom: 8 }}
          >
            {t}
          </Tag.CheckableTag>
        ))}
      </div>
      <Text className="block-label">选择用户画像</Text>
      <div>
        {PERSONAS.map((p) => (
          <Tag.CheckableTag
            key={p}
            checked={persona === p}
            onChange={() => setLocalPersona(p)}
            style={{ marginBottom: 8 }}
          >
            {p}
          </Tag.CheckableTag>
        ))}
      </div>
    </Modal>
  );
}
