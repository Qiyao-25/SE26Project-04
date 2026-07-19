import { Modal, Tag, Typography, message } from 'antd';
import { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { PERSONAS } from '../../data/papers';
import { updateLearningProfile } from '../../services/learningService';
import { USE_MOCK } from '../../services/runtimeConfig';

const { Text } = Typography;

const TOPICS = ['cs.CL', 'cs.LG', 'cs.CV', 'cs.AI'];

export default function OnboardingModal({ open, onDone }) {
  const { userId, setTopics, setPersona } = useApp();
  const [selectedTopics, setSelectedTopics] = useState(['cs.CL']);
  const [persona, setLocalPersona] = useState('研究');
  const [saving, setSaving] = useState(false);

  const toggleTopic = (t) => {
    setSelectedTopics((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  };

  const handleDone = async () => {
    const nextTopics = selectedTopics.length ? selectedTopics : ['cs.CL'];
    setSaving(true);
    try {
      if (!USE_MOCK) await updateLearningProfile(userId, { persona, topics: nextTopics, preferences: {} });
      setTopics(nextTopics);
      setPersona(persona);
      onDone();
    } catch (error) {
      message.error(error.message || '画像保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="首次登录引导" open={open} onOk={handleDone} confirmLoading={saving} okText="完成，进入工作空间" cancelButtonProps={{ style: { display: 'none' } }} closable={false}>
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
