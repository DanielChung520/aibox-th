import { useState, useEffect } from 'react';
import { Modal, Form, Input, Select, Button, Space, App, Tag } from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import { crmApi, type CRMContact, type CreateContactPayload, type UpdateContactPayload, type ContactTitle, type ContactPhone, type ContactEmail, type ContactSocialAccount, type ContactOrganization, type ContactCardImage } from '../../services/api';
import { authStore } from '../../stores/auth';

const { TextArea } = Input;

const SOCIAL_PLATFORMS = [
  { value: 'line', label: 'LINE' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'wechat', label: 'WeChat' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'slack', label: 'Slack' },
  { value: 'messenger', label: 'Messenger' },
  { value: 'other', label: '其他' },
];

const PHONE_TYPES = [
  { value: 'mobile', label: '手機' },
  { value: 'office', label: '辦公室' },
  { value: 'fax', label: '傳真' },
  { value: 'other', label: '其他' },
];

const SECTION_STYLE: React.CSSProperties = {
  border: '1px solid #334155',
  borderRadius: 6,
  padding: '8px 10px',
  marginBottom: 12,
};

const SECTION_TITLE_STYLE: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, color: '#8892a0',
  textTransform: 'uppercase', letterSpacing: '0.5px',
  marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
};

interface Props {
  open: boolean;
  contact: CRMContact | null;
  defaultCustomerKey?: string;
  onClose: () => void;
  onSaved: () => void;
}

function Row({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
      {children}
    </div>
  );
}

function RemoveBtn({ onClick }: { onClick: () => void }) {
  return (
    <MinusCircleOutlined style={{ color: '#ef4444', cursor: 'pointer', fontSize: 14, flexShrink: 0 }} onClick={onClick} />
  );
}

export default function ContactFormModal({ open, contact, defaultCustomerKey, onClose, onSaved }: Props) {
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [customers, setCustomers] = useState<{ key: string; name: string }[]>([]);
  const [searching, setSearching] = useState(false);

  const [titles, setTitles] = useState<ContactTitle[]>([{ title: '', department: '', is_primary: true }]);
  const [phones, setPhones] = useState<ContactPhone[]>([{ number: '', code: '+886', type: 'mobile', is_primary: true }]);
  const [emails, setEmails] = useState<ContactEmail[]>([{ address: '', type: 'work', is_primary: true }]);
  const [socials, setSocials] = useState<ContactSocialAccount[]>([]);
  const [orgs, setOrgs] = useState<ContactOrganization[]>([]);
  const [cardImages, setCardImages] = useState<ContactCardImage[]>([]);

  useEffect(() => {
    if (open) {
      form.resetFields();
      if (contact) {
        setTitles(contact.titles?.length ? contact.titles : [{ title: '', department: '', is_primary: true }]);
        setPhones(contact.phones?.length ? contact.phones : [{ number: '', code: '+886', type: 'mobile', is_primary: true }]);
        setEmails(contact.emails?.length ? contact.emails : [{ address: '', type: 'work', is_primary: true }]);
        setSocials(contact.social_accounts || []);
        setOrgs(contact.organizations || []);
        setCardImages(contact.card_images || []);
        form.setFieldsValue({ name_cn: contact.name_cn, name_en: contact.name_en, notes: contact.notes, customer_key: contact.customer_key });
      } else {
        setTitles([{ title: '', department: '', is_primary: true }]);
        setPhones([{ number: '', code: '+886', type: 'mobile', is_primary: true }]);
        setEmails([{ address: '', type: 'work', is_primary: true }]);
        setSocials([]);
        setOrgs([]);
        setCardImages([]);
        form.setFieldsValue({ customer_key: defaultCustomerKey || undefined });
      }
    }
  }, [open, contact, defaultCustomerKey, form]);

  const handleSubmit = async () => {
    try {
      await form.validateFields();
      setLoading(true);

      const payload_base = {
        name_cn: form.getFieldValue('name_cn') || undefined,
        name_en: form.getFieldValue('name_en') || undefined,
        notes: form.getFieldValue('notes') || undefined,
        customer_key: form.getFieldValue('customer_key') || undefined,
        titles: titles.filter(t => t.title.trim()),
        phones: phones.filter(p => p.number.trim()),
        emails: emails.filter(e => e.address.trim()),
        social_accounts: socials.filter(s => s.account.trim()),
        organizations: orgs.filter(o => o.name.trim()),
        card_images: cardImages.filter(img => img.url),
      };

      if (contact) {
        await crmApi.updateContact(contact._key, payload_base as UpdateContactPayload);
        message.success('已更新');
      } else {
        const user = authStore.getState().user;
        await crmApi.createContact({ ...payload_base, owner_key: user?._key } as CreateContactPayload);
        message.success('已新增');
      }
      onSaved();
      onClose();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error('操作失敗');
    } finally {
      setLoading(false);
    }
  };

  const searchCustomer = async (q: string) => {
    if (!q) return;
    setSearching(true);
    try {
      const res = await crmApi.list({ q, page_size: 10 });
      setCustomers((res.data as any).data?.map((c: any) => ({ key: c._key, name: c.name })) || []);
    } catch {}
    finally { setSearching(false); }
  };

  const setOnePrimary = <T extends { is_primary?: boolean }>(arr: T[], idx: number): T[] =>
    arr.map((item, i) => ({ ...item, is_primary: i === idx }));

  return (
    <Modal
      title={contact ? '編輯聯絡人' : '新增聯絡人'}
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      confirmLoading={loading}
      width={640}
      destroyOnClose
    >
      <Form form={form} layout="vertical" size="small">
        {/* Name row */}
        <div style={SECTION_STYLE}>
          <div style={SECTION_TITLE_STYLE}>姓名</div>
          <Space style={{ width: '100%' }} size={8}>
            <Form.Item name="name_cn" style={{ width: '50%', marginBottom: 0 }}>
              <Input placeholder="中文姓名" size="small" />
            </Form.Item>
            <Form.Item name="name_en" style={{ width: '50%', marginBottom: 0 }}>
              <Input placeholder="English Name" size="small" />
            </Form.Item>
          </Space>
        </div>

        {/* Titles */}
        <div style={SECTION_STYLE}>
          <div style={SECTION_TITLE_STYLE}>
            職稱
            <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => setTitles([...titles, { title: '', department: '', is_primary: false }])} style={{ height: 20 }} />
          </div>
          {titles.map((t, i) => (
            <Row key={i}>
              <Input size="small" placeholder="職稱" value={t.title} onChange={e => setTitles(prev => prev.map((x, j) => j === i ? { ...x, title: e.target.value } : x))} style={{ width: 130 }} />
              <Input size="small" placeholder="部門" value={t.department} onChange={e => setTitles(prev => prev.map((x, j) => j === i ? { ...x, department: e.target.value } : x))} style={{ width: 120 }} />
              <Tag color={t.is_primary ? 'blue' : 'default'} style={{ cursor: 'pointer', margin: 0, fontSize: 10, lineHeight: '18px' }} onClick={() => setTitles(setOnePrimary(titles, i))}>
                {t.is_primary ? '主要' : '次要'}
              </Tag>
              {titles.length > 1 && <RemoveBtn onClick={() => setTitles(prev => prev.filter((_, j) => j !== i))} />}
            </Row>
          ))}
        </div>

        {/* Phones */}
        <div style={SECTION_STYLE}>
          <div style={SECTION_TITLE_STYLE}>
            電話
            <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => setPhones([...phones, { number: '', code: '+886', type: 'mobile', is_primary: false }])} style={{ height: 20 }} />
          </div>
          {phones.map((p, i) => (
            <Row key={i}>
              <Select size="small" value={p.code || '+886'} onChange={v => setPhones(prev => prev.map((x, j) => j === i ? { ...x, code: v } : x))} style={{ width: 80 }} options={[{ value: '+886', label: '+886' }, { value: '+1', label: '+1' }, { value: '+81', label: '+81' }, { value: '+86', label: '+86' }, { value: '+852', label: '+852' }]} />
              <Input size="small" placeholder="號碼" value={p.number} onChange={e => setPhones(prev => prev.map((x, j) => j === i ? { ...x, number: e.target.value } : x))} style={{ width: 145 }} />
              <Select size="small" value={p.type || 'mobile'} onChange={v => setPhones(prev => prev.map((x, j) => j === i ? { ...x, type: v } : x))} style={{ width: 80 }} options={PHONE_TYPES} />
              <Tag color={p.is_primary ? 'blue' : 'default'} style={{ cursor: 'pointer', margin: 0, fontSize: 10, lineHeight: '18px' }} onClick={() => setPhones(setOnePrimary(phones, i))}>
                {p.is_primary ? '主要' : '次要'}
              </Tag>
              {phones.length > 1 && <RemoveBtn onClick={() => setPhones(prev => prev.filter((_, j) => j !== i))} />}
            </Row>
          ))}
        </div>

        {/* Emails */}
        <div style={SECTION_STYLE}>
          <div style={SECTION_TITLE_STYLE}>
            Email
            <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => setEmails([...emails, { address: '', type: 'work', is_primary: false }])} style={{ height: 20 }} />
          </div>
          {emails.map((e, i) => (
            <Row key={i}>
              <Input size="small" placeholder="email@example.com" value={e.address} onChange={ev => setEmails(prev => prev.map((x, j) => j === i ? { ...x, address: ev.target.value } : x))} style={{ width: 220 }} />
              <Select size="small" value={e.type || 'work'} onChange={v => setEmails(prev => prev.map((x, j) => j === i ? { ...x, type: v } : x))} style={{ width: 80 }} options={[{ value: 'work', label: '工作' }, { value: 'personal', label: '個人' }, { value: 'other', label: '其他' }]} />
              <Tag color={e.is_primary ? 'blue' : 'default'} style={{ cursor: 'pointer', margin: 0, fontSize: 10, lineHeight: '18px' }} onClick={() => setEmails(setOnePrimary(emails, i))}>
                {e.is_primary ? '主要' : '次要'}
              </Tag>
              {emails.length > 1 && <RemoveBtn onClick={() => setEmails(prev => prev.filter((_, j) => j !== i))} />}
            </Row>
          ))}
        </div>

        {/* Social */}
        <div style={SECTION_STYLE}>
          <div style={SECTION_TITLE_STYLE}>
            社群帳號
            <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => setSocials([...socials, { platform: 'line', account: '' }])} style={{ height: 20 }} />
          </div>
          {socials.map((s, i) => (
            <Row key={i}>
              <Select size="small" value={s.platform} onChange={v => setSocials(prev => prev.map((x, j) => j === i ? { ...x, platform: v } : x))} style={{ width: 110 }} options={SOCIAL_PLATFORMS} />
              <Input size="small" placeholder="帳號/ID" value={s.account} onChange={ev => setSocials(prev => prev.map((x, j) => j === i ? { ...x, account: ev.target.value } : x))} style={{ width: 160 }} />
              {s.platform === 'other' && <Input size="small" placeholder="平台名" value={s.label} onChange={ev => setSocials(prev => prev.map((x, j) => j === i ? { ...x, label: ev.target.value } : x))} style={{ width: 100 }} />}
              <RemoveBtn onClick={() => setSocials(prev => prev.filter((_, j) => j !== i))} />
            </Row>
          ))}
        </div>

        {/* Organizations */}
        <div style={SECTION_STYLE}>
          <div style={SECTION_TITLE_STYLE}>
            公司/組織
            <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => setOrgs([...orgs, { name: '', title: '', is_primary: false }])} style={{ height: 20 }} />
          </div>
          {orgs.map((o, i) => (
            <Row key={i}>
              <Input size="small" placeholder="公司/組織" value={o.name} onChange={e => setOrgs(prev => prev.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} style={{ width: 175 }} />
              <Input size="small" placeholder="職稱" value={o.title} onChange={e => setOrgs(prev => prev.map((x, j) => j === i ? { ...x, title: e.target.value } : x))} style={{ width: 130 }} />
              <Tag color={o.is_primary ? 'blue' : 'default'} style={{ cursor: 'pointer', margin: 0, fontSize: 10, lineHeight: '18px' }} onClick={() => setOrgs(setOnePrimary(orgs, i))}>
                {o.is_primary ? '主要' : '次要'}
              </Tag>
              <RemoveBtn onClick={() => setOrgs(prev => prev.filter((_, j) => j !== i))} />
            </Row>
          ))}
        </div>

        {/* Card Images */}
        <div style={SECTION_STYLE}>
          <div style={SECTION_TITLE_STYLE}>
            名片圖片
            <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => setCardImages([...cardImages, { url: '', side: 'front' }])} style={{ height: 20 }} />
          </div>
          {cardImages.map((img, i) => (
            <div key={i} style={{ marginBottom: 8 }}>
              <Row>
                <Select size="small" value={img.side} onChange={v => setCardImages(prev => prev.map((x, j) => j === i ? { ...x, side: v } : x))} style={{ width: 80 }} options={[{ value: 'front', label: '正面' }, { value: 'back', label: '背面' }]} />
                {img.url ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
                    <img src={img.url} alt="card" style={{ height: 40, borderRadius: 4, objectFit: 'contain', maxWidth: 140, background: '#000' }} />
                    <Button size="small" type="link" style={{ fontSize: 11, padding: 0, height: 20 }} onClick={() => {
                      const input = document.createElement('input');
                      input.type = 'file';
                      input.accept = 'image/*';
                      input.onchange = (e: any) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        const reader = new FileReader();
                        reader.onload = (ev) => {
                          const dataUrl = ev.target?.result as string;
                          setCardImages(prev => prev.map((x, j) => j === i ? { ...x, url: dataUrl } : x));
                        };
                        reader.readAsDataURL(file);
                      };
                      input.click();
                    }}>更換</Button>
                    <RemoveBtn onClick={() => setCardImages(prev => prev.filter((_, j) => j !== i))} />
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
                    <Button size="small" onClick={() => {
                      const input = document.createElement('input');
                      input.type = 'file';
                      input.accept = 'image/*';
                      input.onchange = (e: any) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        const reader = new FileReader();
                        reader.onload = (ev) => {
                          const dataUrl = ev.target?.result as string;
                          setCardImages(prev => prev.map((x, j) => j === i ? { ...x, url: dataUrl } : x));
                        };
                        reader.readAsDataURL(file);
                      };
                      input.click();
                    }} style={{ fontSize: 11 }}>
                      選擇圖片
                    </Button>
                    <RemoveBtn onClick={() => setCardImages(prev => prev.filter((_, j) => j !== i))} />
                  </div>
                )}
              </Row>
            </div>
          ))}
        </div>

        {/* Other */}
        <div style={SECTION_STYLE}>
          <div style={SECTION_TITLE_STYLE}>其他</div>
          <Form.Item name="customer_key" style={{ marginBottom: 8 }}>
            <Select size="small" placeholder="所屬機構（選填）" showSearch allowClear filterOption={false} onSearch={searchCustomer} loading={searching} notFoundContent={null}
              options={customers.map(c => ({ value: c.key, label: c.name }))} />
          </Form.Item>
          <Form.Item name="notes" style={{ marginBottom: 0 }}>
            <TextArea rows={2} placeholder="備註..." size="small" />
          </Form.Item>
        </div>
      </Form>
    </Modal>
  );
}
