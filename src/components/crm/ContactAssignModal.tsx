import { useState, useEffect } from 'react';
import { Modal, Select, App, Typography } from 'antd';
import { crmApi, type CRMContact, type UserRoleItem } from '../../services/api';

const { Text } = Typography;

interface Props {
  open: boolean;
  contact: CRMContact | null;
  onClose: () => void;
  onAssigned: () => void;
}

export default function ContactAssignModal({ open, contact, onClose, onAssigned }: Props) {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<UserRoleItem[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>('');

  useEffect(() => {
    if (open) {
      setSelectedUser('');
      setLoading(true);
      crmApi.getUsersAndRoles()
        .then(res => setUsers((res.data.data?.users || []) as UserRoleItem[]))
        .catch(() => message.error('載入使用者列表失敗'))
        .finally(() => setLoading(false));
    }
  }, [open, message]);

  const handleAssign = async () => {
    if (!contact || !selectedUser) return;
    try {
      await crmApi.assignContact(contact._key, selectedUser);
      message.success('已指派');
      onAssigned();
      onClose();
    } catch {
      message.error('指派失敗');
    }
  };

  return (
    <Modal
      title={`指派聯絡人 — ${contact?.name_cn || contact?.name_en || ''}`}
      open={open}
      onCancel={onClose}
      onOk={handleAssign}
      confirmLoading={loading}
      width={420}
    >
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">將此聯絡人指派給業務員：</Text>
      </div>
      <Select
        style={{ width: '100%' }}
        placeholder="選擇業務員"
        value={selectedUser || undefined}
        onChange={v => setSelectedUser(v)}
        showSearch
        filterOption={(input, option) =>
          (option?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
        }
        options={users.map(u => ({
          value: u._key,
          label: `${u.name}（${u.username || ''}）`,
        }))}
        loading={loading}
      />
      {contact?.customer_name && (
        <div style={{ marginTop: 12 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            所屬機構：{contact.customer_name}
          </Text>
        </div>
      )}
    </Modal>
  );
}
