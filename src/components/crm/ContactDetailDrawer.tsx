import { useState, useEffect, ReactNode } from 'react';
import { Drawer, Tag, Typography } from 'antd';
import { StarFilled, LoadingOutlined } from '@ant-design/icons';
import { crmApi, type CRMContact } from '../../services/api';
import { useContentTokens } from '../../contexts/AppThemeProvider';

const { Text } = Typography;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: '#8892a0', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Dash() {
  return <Text type="secondary" style={{ fontSize: 12 }}>—</Text>;
}

const SOURCE_LABEL: Record<string, string> = {
  manual: '手動新增', line_card: 'LINE 名片', line_photo: 'LINE 拍照',
  assignment: '指派', import: '匯入',
};

const PLATFORM_LABELS: Record<string, string> = {
  line: 'LINE', whatsapp: 'WhatsApp', wechat: 'WeChat',
  facebook: 'Facebook', telegram: 'Telegram', slack: 'Slack',
  messenger: 'Messenger', other: '',
};

function initials(s: string): string {
  return s ? s.slice(0, 2) : '??';
}

interface Props {
  contactKey: string | null;
  onClose: () => void;
}

export default function ContactDetailDrawer({ contactKey, onClose }: Props) {
  const tokens = useContentTokens();
  const [contact, setContact] = useState<CRMContact | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!contactKey) { setContact(null); return; }
    setLoading(true);
    crmApi.getContact(contactKey)
      .then(res => setContact(res.data.data))
      .catch(() => setContact(null))
      .finally(() => setLoading(false));
  }, [contactKey]);

  const displayName = contact?.name_cn || contact?.name_en || '';

  return (
    <Drawer
      title={displayName || '聯絡人詳情'}
      placement="right"
      width={520}
      open={!!contactKey}
      onClose={onClose}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <LoadingOutlined style={{ fontSize: 24 }} />
        </div>
      ) : contact ? (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
            <div style={{
              width: 60, height: 60, borderRadius: '50%',
              background: `linear-gradient(135deg, ${tokens.colorPrimary || '#3b82f6'}, #764ba2)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontSize: 22, fontWeight: 600, flexShrink: 0, overflow: 'hidden',
            }}>
              {initials(displayName)}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text strong style={{ fontSize: 20 }}>{displayName}</Text>
                {contact.is_primary && <StarFilled style={{ color: '#faad14', fontSize: 16 }} />}
                {contact.line_status === 'connected' && (
                  <Tag color="green" style={{ margin: 0, fontSize: 11 }}>LINE</Tag>
                )}
              </div>
              {contact.name_en && contact.name_cn && (
                <Text type="secondary" style={{ fontSize: 13 }}>{contact.name_en}</Text>
              )}
              <div style={{ marginTop: 4 }}>
                <Tag color="blue" style={{ fontSize: 10 }}>{SOURCE_LABEL[contact.source] || contact.source}</Tag>
              </div>
            </div>
          </div>

          {/* Titles */}
          <Section title="職稱">
            {contact.titles && contact.titles.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {contact.titles.map((t, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                    <span>{t.title}</span>
                    {t.department && <span style={{ color: '#8892a0' }}>{t.department}</span>}
                    {t.is_primary && <Tag color="blue" style={{ fontSize: 9, margin: 0, lineHeight: '14px' }}>主要</Tag>}
                  </div>
                ))}
              </div>
            ) : <Dash />}
          </Section>

          {/* Phones */}
          <Section title="電話">
            {contact.phones && contact.phones.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {contact.phones.map((p, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                    <span>📞</span>
                    <span>{p.code ? `${p.code} ` : ''}{p.number}</span>
                    {p.type && <span style={{ color: '#8892a0', fontSize: 12 }}>({p.type})</span>}
                    {p.is_primary && <Tag color="blue" style={{ fontSize: 9, margin: 0, lineHeight: '14px' }}>主要</Tag>}
                  </div>
                ))}
              </div>
            ) : <Dash />}
          </Section>

          {/* Emails */}
          <Section title="Email">
            {contact.emails && contact.emails.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {contact.emails.map((e, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                    <span>✉️</span>
                    <span>{e.address}</span>
                    {e.type && <span style={{ color: '#8892a0', fontSize: 12 }}>({e.type})</span>}
                    {e.is_primary && <Tag color="blue" style={{ fontSize: 9, margin: 0, lineHeight: '14px' }}>主要</Tag>}
                  </div>
                ))}
              </div>
            ) : <Dash />}
          </Section>

          {/* Social */}
          <Section title="社群帳號">
            {contact.social_accounts && contact.social_accounts.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {contact.social_accounts.map((s, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                    <span style={{ width: 70, color: '#8892a0', fontSize: 12 }}>
                      {PLATFORM_LABELS[s.platform] || s.label || s.platform}
                    </span>
                    <span>{s.account}</span>
                  </div>
                ))}
              </div>
            ) : <Dash />}
          </Section>

          {/* Organizations */}
          <Section title="公司/組織">
            {contact.organizations && contact.organizations.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {contact.organizations.map((o, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                    <span>{o.name}</span>
                    {o.title && <span style={{ color: '#8892a0' }}>/ {o.title}</span>}
                    {o.is_primary && <Tag color="blue" style={{ fontSize: 9, margin: 0, lineHeight: '14px' }}>主要</Tag>}
                  </div>
                ))}
              </div>
            ) : <Dash />}
          </Section>

          {/* Card images */}
          {contact.card_images && contact.card_images.length > 0 && (
            <Section title="名片圖片">
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {contact.card_images.map((img, i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{
                      width: 200, height: 126, borderRadius: 6, overflow: 'hidden',
                      border: '1px solid #334155', background: '#0f172a',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {img.url.startsWith('data:') || img.url.startsWith('http') ? (
                        <img src={img.url} alt={`名片${img.side === 'front' ? '正面' : '背面'}`}
                          style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                      ) : (
                        <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>
                          {img.side === 'front' ? '正面' : '背面'} #{i + 1}
                        </Tag>
                      )}
                    </div>
                    <span style={{ fontSize: 11, textAlign: 'center', color: '#8892a0' }}>
                      {img.side === 'front' ? '正面' : '背面'}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Notes */}
          {contact.notes && (
            <Section title="備註">
              <Text style={{ fontSize: 13 }}>{contact.notes}</Text>
            </Section>
          )}

          {/* System info */}
          <Section title="系統資訊">
            <div style={{ fontSize: 12, lineHeight: 2 }}>
              <div><span style={{ color: '#8892a0' }}>來源：</span>{SOURCE_LABEL[contact.source] || contact.source}</div>
              <div><span style={{ color: '#8892a0' }}>建立：</span>{contact.created_at}</div>
              <div><span style={{ color: '#8892a0' }}>更新：</span>{contact.updated_at}</div>
            </div>
          </Section>
        </>
      ) : (
        <Text type="secondary">找不到聯絡人資料</Text>
      )}
    </Drawer>
  );
}
