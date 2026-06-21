import { Segmented } from 'antd';
import { AppstoreOutlined, UnorderedListOutlined } from '@ant-design/icons';
import { useCrmStore } from '../../stores/crmStore';

export default function ContactViewToggle() {
  const { contactViewMode, setContactViewMode } = useCrmStore();

  return (
    <Segmented
      size="small"
      value={contactViewMode}
      onChange={v => setContactViewMode(v as 'grid' | 'list')}
      options={[
        { value: 'grid', icon: <AppstoreOutlined />, label: '卡片' },
        { value: 'list', icon: <UnorderedListOutlined />, label: '列表' },
      ]}
    />
  );
}
