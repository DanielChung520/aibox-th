import { Button, Tag, Tooltip, Space, Typography } from 'antd';
import { EditOutlined, MessageOutlined, StarFilled } from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import type { CRMContact } from '../../services/api';

const { Text } = Typography;

const LINE_STATUS_META: Record<string, { label: string; color: string }> = {
  connected: { label: '連線中', color: 'green' },
  disconnected: { label: '未連結', color: 'default' },
  expired: { label: '已過期', color: 'red' },
  none: { label: '無', color: 'default' },
};

function initials(s: string): string {
  return s ? s.slice(0, 2) : '??';
}

function primaryOf<T extends { is_primary?: boolean }>(items: T[] | undefined): T | undefined {
  if (!items || items.length === 0) return undefined;
  return items.find(i => i.is_primary) || items[0];
}

interface Props {
  contact: CRMContact;
  onEdit: (contact: CRMContact) => void;
  onSendLine: (contact: CRMContact) => void;
  onClick: (contact: CRMContact) => void;
}

export default function ContactCard({ contact, onEdit, onSendLine, onClick }: Props) {
  const tokens = useContentTokens();
  const displayName = contact.name_cn || contact.name_en || '—';
  const lineMeta = LINE_STATUS_META[contact.line_status || 'none'] || { label: '無', color: 'default' };
  const primaryPhone = primaryOf(contact.phones);
  const primaryEmail = primaryOf(contact.emails);
  const primaryOrg = primaryOf(contact.organizations);

  return (
    <div
      style={{
        width: 240,
        background: tokens.containerBg,
        borderRadius: 8,
        border: `1px solid #334155`,
        padding: 16,
        cursor: 'pointer',
        transition: 'box-shadow 0.2s, transform 0.2s',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
        position: 'relative',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.3)';
        e.currentTarget.style.transform = 'translateY(-2px)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = 'none';
        e.currentTarget.style.transform = 'none';
      }}
      onClick={() => onClick(contact)}
    >
      {contact.is_primary && (
        <StarFilled style={{ position: 'absolute', top: 8, right: 8, color: '#faad14', fontSize: 14 }} />
      )}
      {contact.card_images && contact.card_images.length > 0 && (
        <div style={{ position: 'absolute', top: 8, left: 8, fontSize: 16, lineHeight: 1 }} title={`${contact.card_images.length} 張名片圖檔`}>
          📇
        </div>
      )}

      {/* Avatar */}
      <div
        style={{
          width: 50,
          height: 50,
          borderRadius: '50%',
          background: `linear-gradient(135deg, ${tokens.colorPrimary || '#3b82f6'}, #764ba2)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: 18,
          fontWeight: 600,
          flexShrink: 0,
          overflow: 'hidden',
        }}
      >
        {initials(displayName)}
      </div>

      {/* Name */}
      <Text strong style={{ fontSize: 16, textAlign: 'center', lineHeight: 1.3 }}>
        {displayName}
      </Text>
      {contact.name_en && contact.name_cn && (
        <Text type="secondary" style={{ fontSize: 11, textAlign: 'center' }}>
          {contact.name_en}
        </Text>
      )}

      {/* Primary title */}
      {primaryOf(contact.titles) && (
        <Text type="secondary" style={{ fontSize: 12, textAlign: 'center' }}>
          {primaryOf(contact.titles)!.title}
        </Text>
      )}

      <div style={{ width: '80%', height: 1, background: '#334155', opacity: 0.5 }} />

      {/* Contact Info */}
      <div style={{ width: '100%', fontSize: 12, lineHeight: 1.8 }}>
        {primaryPhone && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
            <span>📞</span>
            <Text style={{ fontSize: 12 }}>
              {primaryPhone.code ? `${primaryPhone.code} ` : ''}{primaryPhone.number}
            </Text>
          </div>
        )}
        {primaryEmail && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
            <span>✉️</span>
            <Tooltip title={primaryEmail.address}>
              <Text ellipsis style={{ fontSize: 12, maxWidth: 160 }}>{primaryEmail.address}</Text>
            </Tooltip>
          </div>
        )}
        {primaryOrg && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
            <span>🏢</span>
            <Text ellipsis style={{ fontSize: 12, maxWidth: 160 }}>{primaryOrg.name}</Text>
          </div>
        )}
      </div>

      {/* LINE Status */}
      <Tag color={lineMeta.color} style={{ margin: 0, fontSize: 11 }}>
        {lineMeta.label}
      </Tag>

      {/* Actions */}
      <Space size={4} style={{ marginTop: 4 }}>
        {contact.is_primary && <Tag color="gold" style={{ fontSize: 10, margin: 0 }}>主要</Tag>}
        <Button
          type="text"
          size="small"
          icon={<EditOutlined />}
          onClick={e => { e.stopPropagation(); onEdit(contact); }}
        />
        <Button
          type="text"
          size="small"
          icon={<MessageOutlined />}
          onClick={e => { e.stopPropagation(); onSendLine(contact); }}
        />
      </Space>
    </div>
  );
}
