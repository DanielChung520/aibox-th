/**
 * @file        EEA-CRM 聯絡人管理頁面
 * @description 聯絡人資料表格，含 LINE 狀態標籤、主要聯絡人識別、Agent K 整合
 * @lastUpdate  2026-06-08 12:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Input,
  Select,
  Tag,
  App,
  Space,
  Typography,
} from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  StarFilled,
  MessageOutlined,
} from '@ant-design/icons';
import { pageContextManager } from '../../services/PageContextManager';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { useCrmStore } from '../../stores/crmStore';

const { Text } = Typography;

/* ---------- Mock data ---------- */

interface ContactRecord {
  id: string;
  name: string;
  title: string;
  phone: string;
  email: string;
  lineStatus: 'connected' | 'disconnected' | 'expired';
  organization: string;
  isPrimary: boolean;
}

const MOCK_CONTACTS: ContactRecord[] = [
  { id: 'K001', name: '張淑芬', title: '院長', phone: '0912-345-678', email: 'sfchang@sunny.com', lineStatus: 'connected', organization: '陽光老人養護中心', isPrimary: true },
  { id: 'K002', name: '李志明', title: '護理長', phone: '0923-456-789', email: 'cmlee@sunny.com', lineStatus: 'connected', organization: '陽光老人養護中心', isPrimary: false },
  { id: 'K003', name: '王雅慧', title: '執行長', phone: '0934-567-890', email: 'yhwang@renai.com', lineStatus: 'disconnected', organization: '仁愛居家長照機構', isPrimary: true },
  { id: 'K004', name: '陳建宏', title: '個案管理師', phone: '0945-678-901', email: 'jhchen@renai.com', lineStatus: 'connected', organization: '仁愛居家長照機構', isPrimary: false },
  { id: 'K005', name: '林美玲', title: '主任', phone: '0956-789-012', email: 'mllin@tzuchi.com', lineStatus: 'connected', organization: '慈濟護理之家', isPrimary: true },
  { id: 'K006', name: '黃志強', title: '社工師', phone: '0967-890-123', email: 'cghuang@tzuchi.com', lineStatus: 'expired', organization: '慈濟護理之家', isPrimary: false },
  { id: 'K007', name: '吳佩珊', title: '營運長', phone: '0978-901-234', email: 'pswu@pingan.com', lineStatus: 'connected', organization: '平安社區服務中心', isPrimary: true },
  { id: 'K008', name: '劉怡君', title: '護理部主任', phone: '0989-012-345', email: 'yjliu@pingan.com', lineStatus: 'disconnected', organization: '平安社區服務中心', isPrimary: false },
  { id: 'K009', name: '趙自強', title: '負責人', phone: '0911-223-344', email: 'zqjhao@kangfu.com', lineStatus: 'connected', organization: '康復長照中心', isPrimary: true },
  { id: 'K010', name: '楊雅婷', title: '行政組長', phone: '0922-334-455', email: 'ytyang@kangfu.com', lineStatus: 'connected', organization: '康復長照中心', isPrimary: false },
  { id: 'K011', name: '蔡明宏', title: '院長', phone: '0933-445-566', email: 'mhtsai@engrace.com', lineStatus: 'expired', organization: '恩典護理之家', isPrimary: true },
  { id: 'K012', name: '鄧惠文', title: '公關經理', phone: '0944-556-677', email: 'hwteng@hope.com', lineStatus: 'disconnected', organization: '希望居家服務', isPrimary: false },
  { id: 'K013', name: '周杰倫', title: '資訊長', phone: '0955-667-788', email: 'jlzhou@shuanglian.com', lineStatus: 'connected', organization: '雙連安養中心', isPrimary: false },
  { id: 'K014', name: '孫燕姿', title: '護理長', phone: '0966-778-899', email: 'yzsun@xile.com', lineStatus: 'connected', organization: '喜樂居家長照', isPrimary: true },
  { id: 'K015', name: '陶喆', title: '執行副院長', phone: '0977-889-900', email: 'ztao@rongzong.com', lineStatus: 'connected', organization: '榮總護理之家', isPrimary: false },
];

const LINE_STATUS_MAP: Record<string, { label: string; color: string }> = {
  connected: { label: '🟢 連線中', color: 'green' },
  disconnected: { label: '⚪ 未連結', color: 'default' },
  expired: { label: '🔴 已過期', color: 'red' },
};

const INSTITUTIONS = [...new Set(MOCK_CONTACTS.map(c => c.organization))];

/* ========== Main Component ========== */

export default function ContactListPage() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();
  const { openAgentDrawer } = useCrmStore();

  const [search, setSearch] = useState('');
  const [orgFilter, setOrgFilter] = useState<string>('');
  const [lineFilter, setLineFilter] = useState<string>('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/contacts',
      pageName: 'EEA-CRM 聯絡人管理',
      entityType: 'contact',
      action: 'list',
    });
  }, []);

  const filtered = MOCK_CONTACTS.filter(c => {
    if (search && !c.name.includes(search) && !c.phone.includes(search) && !c.email.includes(search)) return false;
    if (orgFilter && c.organization !== orgFilter) return false;
    if (lineFilter && c.lineStatus !== lineFilter) return false;
    return true;
  });

  const columns = [
    {
      title: '姓名', dataIndex: 'name', key: 'name', width: 100,
      render: (v: string, record: ContactRecord) => (
        <span>
          {v}
          {record.isPrimary && (
            <StarFilled style={{ color: '#faad14', marginLeft: 4, fontSize: 12 }} />
          )}
        </span>
      ),
    },
    { title: '職稱', dataIndex: 'title', key: 'title', width: 110 },
    { title: '電話', dataIndex: 'phone', key: 'phone', width: 130 },
    { title: 'Email', dataIndex: 'email', key: 'email', width: 180, ellipsis: true },
    {
      title: 'LINE狀態', dataIndex: 'lineStatus', key: 'lineStatus', width: 110,
      render: (v: string) => {
        const info = LINE_STATUS_MAP[v] || { label: v, color: 'default' };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    { title: '所屬機構', dataIndex: 'organization', key: 'organization', width: 150 },
    {
      title: '主要聯絡人', dataIndex: 'isPrimary', key: 'isPrimary', width: 100,
      render: (v: boolean) => v
        ? <Tag icon={<StarFilled />} color="gold">主要</Tag>
        : <Text type="secondary">-</Text>,
    },
    {
      title: '操作', key: 'action', width: 140,
      render: (_: unknown, record: ContactRecord) => (
        <Space size={4}>
          <Button
            size="small"
            type="link"
            icon={<MessageOutlined />}
            onClick={() => {
              openAgentDrawer('contacts', record.id);
              message.info(`開啟 Agent K — LINE 智慧客情助手（${record.name}）`);
            }}
          >
            發送LINE訊息
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Input
            placeholder="搜尋姓名、電話或Email..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            style={{ width: 220 }}
            size="small"
          />
          <Select
            value={orgFilter}
            onChange={v => { setOrgFilter(v); setPage(1); }}
            placeholder="機構"
            style={{ width: 150 }}
            size="small"
            allowClear
            options={INSTITUTIONS.map(o => ({ label: o, value: o }))}
          />
          <Select
            value={lineFilter}
            onChange={v => { setLineFilter(v); setPage(1); }}
            placeholder="LINE狀態"
            style={{ width: 110 }}
            size="small"
            allowClear
            options={[
              { label: '🟢 連線中', value: 'connected' },
              { label: '⚪ 未連結', value: 'disconnected' },
              { label: '🔴 已過期', value: 'expired' },
            ]}
          />
        </div>
        <Button type="primary" icon={<PlusOutlined />} size="small" onClick={() => message.info('新增聯絡人表單（開發中）')}>
          新增聯絡人
        </Button>
      </div>

      <Table
        dataSource={filtered}
        columns={columns}
        rowKey="id"
        pagination={{
          current: page,
          pageSize: 10,
          total: filtered.length,
          showTotal: (t) => `共 ${t} 筆`,
          onChange: (p) => setPage(p),
        }}
        scroll={{ x: 1000 }}
        size="middle"
      />
    </div>
  );
}
