import { Tag, Typography, Dropdown } from 'antd';
import {
  StarFilled,
  MoreOutlined,
  EditOutlined,
  DeleteOutlined,
  MessageOutlined,
  SwapOutlined,
  StarOutlined,
} from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import type { CRMContact } from '../../services/api';

const { Text } = Typography;

const LINE_META: Record<string, { label: string; color: string }> = {
  connected: { label: '連線中', color: 'green' },
  disconnected: { label: '未連結', color: 'default' },
  expired: { label: '已過期', color: 'red' },
  none: { label: '無', color: 'default' },
};

function initials(s: string): string {
  return s ? s.slice(0, 1) : '?';
}

function primaryPhone(phones: any[] | undefined): string {
  if (!phones || phones.length === 0) return '-';
  const p = phones.find((ph: any) => ph.is_primary) || phones[0];
  return `${p.code || ''}${p.number}`;
}

function primaryTitle(titles: any[] | undefined): string {
  if (!titles || titles.length === 0) return '-';
  const t = titles.find((x: any) => x.is_primary) || titles[0];
  return t.title;
}

function primaryOrg(orgs: any[] | undefined): string {
  if (!orgs || orgs.length === 0) return '-';
  const o = orgs.find((x: any) => x.is_primary) || orgs[0];
  return o.name;
}

interface Props {
  contact: CRMContact;
  onEdit: (contact: CRMContact) => void;
  onDelete: (contact: CRMContact) => void;
  onSetPrimary: (contact: CRMContact) => void;
  onAssign: (contact: CRMContact) => void;
  onSendLine: (contact: CRMContact) => void;
}

export default function ContactListItem({ contact, onEdit, onDelete, onSetPrimary, onAssign, onSendLine }: Props) {
  const tokens = useContentTokens();
  const lineInfo = LINE_META[contact.line_status || 'none'] || { label: '未知', color: 'default' };

  const menuItems = [
    { key: 'edit', icon: <EditOutlined />, label: '編輯' },
    { key: 'delete', icon: <DeleteOutlined />, label: '刪除', danger: true },
    { key: 'set-primary', icon: contact.is_primary ? <StarFilled /> : <StarOutlined />, label: contact.is_primary ? '取消主要聯絡人' : '設為主要聯絡人' },
    { key: 'assign', icon: <SwapOutlined />, label: '指派' },
    { key: 'send-line', icon: <MessageOutlined />, label: '發送LINE訊息' },
  ];

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        height: 56,
        padding: '0 12px',
        borderBottom: `1px solid #334155`,
        gap: 12,
        transition: 'background 0.15s',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = tokens.tableRowHoverBg || '#1a2744'; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
    >
      {/* Avatar */}
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          background: `linear-gradient(135deg, ${tokens.colorPrimary || '#3b82f6'}, #764ba2)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: 13,
          fontWeight: 600,
          flexShrink: 0,
          overflow: 'hidden',
        }}
      >
        {contact.line_picture_url ? (
          <img src={contact.line_picture_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          initials(contact.name_cn || contact.name_en || '')
        )}
      </div>

      {/* Name */}
      <div style={{ width: 120, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4 }}>
        <Text strong style={{ fontSize: 13 }}>{contact.name_cn || contact.name_en || '-'}</Text>
        {contact.is_primary && <StarFilled style={{ color: '#faad14', fontSize: 11 }} />}
      </div>

      {/* Title */}
      <Text style={{ width: 100, fontSize: 12, flexShrink: 0 }} type="secondary">
        {primaryTitle(contact.titles)}
      </Text>

      {/* Phone */}
      <Text style={{ width: 140, fontSize: 12, flexShrink: 0 }}>{primaryPhone(contact.phones)}</Text>

      {/* LINE Status */}
      <Tag color={lineInfo.color} style={{ width: 70, textAlign: 'center', fontSize: 11, margin: 0 }}>
        {lineInfo.label}
      </Tag>

      {/* Organization */}
      <Text ellipsis style={{ flex: 1, fontSize: 12 }} type="secondary">
        {primaryOrg(contact.organizations)}
      </Text>

      {/* Actions Menu */}
      <Dropdown
        menu={{
          items: menuItems,
          onClick: ({ key }) => {
            switch (key) {
              case 'edit': onEdit(contact); break;
              case 'delete': onDelete(contact); break;
              case 'set-primary': onSetPrimary(contact); break;
              case 'assign': onAssign(contact); break;
              case 'send-line': onSendLine(contact); break;
            }
          },
        }}
        trigger={['click']}
      >
        <div style={{ cursor: 'pointer', padding: '4px 8px', borderRadius: 4 }}
          onClick={e => e.stopPropagation()}>
          <MoreOutlined style={{ fontSize: 16, color: tokens.textSecondary }} />
        </div>
      </Dropdown>
    </div>
  );
}
