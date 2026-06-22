/**
 * @file        EEA-CRM 參數設置頁面
 * @description CRM 系統參數配置表格，支持搜尋、行內編輯、Switch 切換
 * @lastUpdate  2026-06-08 12:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Input,
  Switch,
  Tag,
  Modal,
  App,
  Space,
  Typography,
  Tooltip,
} from 'antd';
import {
  SearchOutlined,
  EditOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { pageContextManager } from '../../services/PageContextManager';
import { useContentTokens } from '../../contexts/AppThemeProvider';

const { Text } = Typography;

/* ---------- Mock data ---------- */

interface CrmParam {
  key: string;
  value: string;
  type: 'string' | 'number' | 'boolean' | 'json' | 'array';
  description: string;
  lastUpdated: string;
}

const MOCK_PARAMS: CrmParam[] = [
  {
    key: 'crm.abc.classification.rules',
    value: '{"A":">100萬","B":"50-100萬","C":"<50萬"}',
    type: 'json',
    description: 'ABC 客戶分類規則定義（依年營收）',
    lastUpdated: '2026-05-15',
  },
  {
    key: 'crm.visit.reminder.days',
    value: '30',
    type: 'number',
    description: '客戶拜訪提醒間隔天數',
    lastUpdated: '2026-05-10',
  },
  {
    key: 'crm.contract.expiry.warning',
    value: '60',
    type: 'number',
    description: '合約到期預警天數',
    lastUpdated: '2026-05-10',
  },
  {
    key: 'crm.scrape.sources',
    value: '衛福部長照機構清單,縣市立案機構,政府公開資料',
    type: 'array',
    description: '衛服部資料更新來源列表',
    lastUpdated: '2026-06-01',
  },
  {
    key: 'crm.map.default.zoom',
    value: '8',
    type: 'number',
    description: '客戶地圖預設縮放層級',
    lastUpdated: '2026-05-20',
  },
  {
    key: 'crm.agent.auto.context',
    value: 'true',
    type: 'boolean',
    description: 'AI Agent 是否自動注入當前頁面上下文',
    lastUpdated: '2026-06-05',
  },
  {
    key: 'crm.contact.line.auto.reply',
    value: 'false',
    type: 'boolean',
    description: 'LINE 訊息自動回覆啟用',
    lastUpdated: '2026-06-05',
  },
  {
    key: 'crm.dashboard.refresh.interval',
    value: '300',
    type: 'number',
    description: '看板自動刷新間隔（秒）',
    lastUpdated: '2026-05-25',
  },
  {
    key: 'crm.customer.status.definitions',
    value: '{"active":"活躍","sleeping":"沉睡","churned":"流失"}',
    type: 'json',
    description: '客戶狀態定義對照表',
    lastUpdated: '2026-05-18',
  },
  {
    key: 'crm.notification.email.recipients',
    value: 'crm@abcdesktop.com,manager@abcdesktop.com',
    type: 'array',
    description: 'CRM 通知郵件收件人列表',
    lastUpdated: '2026-06-03',
  },
];

const TYPE_COLORS: Record<string, string> = {
  string: 'blue',
  number: 'cyan',
  boolean: 'purple',
  json: 'orange',
  array: 'green',
};

/* ========== Main Component ========== */

export default function ParamsPage() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();

  const [search, setSearch] = useState('');
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingParam, setEditingParam] = useState<CrmParam | null>(null);
  const [editValue, setEditValue] = useState('');
  const [params, setParams] = useState<CrmParam[]>(MOCK_PARAMS);

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/params',
      pageName: 'EEA-CRM 參數設置',
      entityType: 'crm_param',
      action: 'list',
    });
  }, []);

  const filtered = params.filter(p =>
    p.key.toLowerCase().includes(search.toLowerCase()) ||
    p.description.includes(search),
  );

  const openEdit = (param: CrmParam) => {
    setEditingParam(param);
    setEditValue(param.value);
    setEditModalVisible(true);
  };

  const handleSaveEdit = () => {
    if (!editingParam) return;
    setParams(prev =>
      prev.map(p =>
        p.key === editingParam.key
          ? { ...p, value: editValue, lastUpdated: new Date().toISOString().slice(0, 10) }
          : p,
      ),
    );
    setEditModalVisible(false);
    message.success(`參數「${editingParam.key}」已更新`);
  };

  const handleToggle = (param: CrmParam, checked: boolean) => {
    setParams(prev =>
      prev.map(p =>
        p.key === param.key
          ? { ...p, value: String(checked), lastUpdated: new Date().toISOString().slice(0, 10) }
          : p,
      ),
    );
    message.success(`參數「${param.key}」已設為 ${checked}`);
  };

  const columns = [
    {
      title: '參數鍵', dataIndex: 'key', key: 'key', width: 260,
      render: (v: string) => (
        <Text code style={{ fontSize: 12 }}>{v}</Text>
      ),
    },
    {
      title: '參數值', dataIndex: 'value', key: 'value', width: 200,
      render: (v: string, record: CrmParam) => {
        if (record.type === 'boolean') {
          return (
            <Switch
              checked={v === 'true'}
              onChange={(checked) => handleToggle(record, checked)}
              checkedChildren="開啟"
              unCheckedChildren="關閉"
              size="small"
            />
          );
        }
        // Truncate long values
        const maxLen = 28;
        const display = v.length > maxLen ? `${v.slice(0, maxLen)}...` : v;
        return (
          <Tooltip title={v}>
            <Text style={{ fontSize: 12, fontFamily: 'monospace' }}>{display}</Text>
          </Tooltip>
        );
      },
    },
    {
      title: '類型', dataIndex: 'type', key: 'type', width: 80,
      render: (v: string) => <Tag color={TYPE_COLORS[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '說明', dataIndex: 'description', key: 'description', width: 240,
      render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '更新時間', dataIndex: 'lastUpdated', key: 'lastUpdated', width: 100,
      render: (v: string) => <Text type="secondary" style={{ fontSize: 11 }}>{v}</Text>,
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: unknown, record: CrmParam) => (
        record.type !== 'boolean' ? (
          <Button
            size="small"
            type="link"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            編輯
          </Button>
        ) : null
      ),
    },
  ];

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Text strong style={{ fontSize: 16 }}>⚙️ CRM 參數設置</Text>
        <Space size={8}>
          <Input
            placeholder="搜尋參數鍵或說明..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: 240 }}
            size="small"
            allowClear
          />
          <Button size="small" icon={<ReloadOutlined />} onClick={() => message.success('參數已重新整理')}>
            重新整理
          </Button>
        </Space>
      </div>

      {/* Table */}
      <Table
        dataSource={filtered}
        columns={columns}
        rowKey="key"
        pagination={false}
        scroll={{ x: 1000 }}
        size="middle"
      />

      {/* Edit Modal */}
      <Modal
        title={`編輯參數：${editingParam?.key}`}
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        onOk={handleSaveEdit}
        okText="儲存"
        width={560}
      >
        {editingParam && (
          <div>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>類型：</Text>
              <Tag color={TYPE_COLORS[editingParam.type]}>{editingParam.type}</Tag>
            </div>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>說明：{editingParam.description}</Text>
            </div>
            <Input.TextArea
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              rows={editingParam.type === 'json' ? 8 : 3}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
          </div>
        )}
      </Modal>
    </div>
  );
}
