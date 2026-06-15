/**
 * @file        EEA-CRM 機構分類標籤頁面
 * @description 標籤管理表格，含分類分頁、新增/編輯/刪除 Modal、顏色選擇器
 * @lastUpdate  2026-06-08 12:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Tabs,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  App,
  Space,
  Typography,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { pageContextManager } from '../../services/PageContextManager';
import { useContentTokens } from '../../contexts/AppThemeProvider';

const { Text } = Typography;

/* ---------- Mock data ---------- */

interface TagRecord {
  id: string;
  name: string;
  category: string;
  color: string;
  usageCount: number;
}

const PRESET_COLORS = [
  '#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911',
  '#f5222d', '#1890ff', '#fa541c', '#7cb305', '#08979c',
];

const MOCK_TAGS: TagRecord[] = [
  { id: 'T01', name: '養護機構', category: '產業別', color: '#1677ff', usageCount: 15 },
  { id: 'T02', name: '居家服務', category: '產業別', color: '#52c41a', usageCount: 12 },
  { id: 'T03', name: '護理之家', category: '產業別', color: '#722ed1', usageCount: 8 },
  { id: 'T04', name: '大型機構', category: '規模', color: '#ff4d4f', usageCount: 6 },
  { id: 'T05', name: '中小型', category: '規模', color: '#faad14', usageCount: 10 },
  { id: 'T06', name: 'A級客戶', category: '需求類型', color: '#52c41a', usageCount: 20 },
  { id: 'T07', name: 'B級客戶', category: '需求類型', color: '#faad14', usageCount: 18 },
  { id: 'T08', name: '高成長潛力', category: '需求類型', color: '#eb2f96', usageCount: 7 },
  { id: 'T09', name: '需關懷', category: '服務狀態', color: '#fa8c16', usageCount: 5 },
  { id: 'T10', name: '合約議約中', category: '服務狀態', color: '#13c2c2', usageCount: 4 },
  { id: 'T11', name: '已簽約', category: '服務狀態', color: '#1677ff', usageCount: 9 },
  { id: 'T12', name: 'VIP客戶', category: '自訂', color: '#722ed1', usageCount: 3 },
];

const CATEGORIES = ['全部', '產業別', '規模', '需求類型', '服務狀態', '自訂'];

/* ========== Main Component ========== */

export default function TagsPage() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();

  const [activeCategory, setActiveCategory] = useState<string>('全部');
  const [modalVisible, setModalVisible] = useState(false);
  const [editingTag, setEditingTag] = useState<TagRecord | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/tags',
      pageName: 'EEA-CRM 機構分類標籤',
      entityType: 'tag',
      action: 'list',
    });
  }, []);

  const filtered = activeCategory === '全部'
    ? MOCK_TAGS
    : MOCK_TAGS.filter(t => t.category === activeCategory);

  const openAdd = () => {
    setEditingTag(null);
    form.resetFields();
    setModalVisible(true);
  };

  const openEdit = (tag: TagRecord) => {
    setEditingTag(tag);
    form.setFieldsValue(tag);
    setModalVisible(true);
  };

  const handleSave = () => {
    form.validateFields().then(values => {
      if (editingTag) {
        message.success(`標籤「${editingTag.name}」已更新`);
      } else {
        message.success(`標籤「${values.name}」已建立`);
      }
      setModalVisible(false);
    });
  };

  const handleDelete = (tag: TagRecord) => {
    message.success(`標籤「${tag.name}」已刪除`);
  };

  const columns = [
    {
      title: '名稱', dataIndex: 'name', key: 'name', width: 150,
      render: (v: string, record: TagRecord) => (
        <Tag color={record.color} style={{ borderRadius: 12, padding: '2px 12px' }}>{v}</Tag>
      ),
    },
    { title: '分類', dataIndex: 'category', key: 'category', width: 100 },
    {
      title: '顏色', dataIndex: 'color', key: 'color', width: 80,
      render: (v: string) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            width: 16, height: 16, borderRadius: '50%',
            background: v, display: 'inline-block', border: '1px solid #e8e8e8',
          }} />
          <Text style={{ fontSize: 11, fontFamily: 'monospace' }}>{v}</Text>
        </div>
      ),
    },
    { title: '使用次數', dataIndex: 'usageCount', key: 'usageCount', width: 90 },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: unknown, record: TagRecord) => (
        <Space size={4}>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            編輯
          </Button>
          <Popconfirm title={`確定刪除標籤「${record.name}」？`} onConfirm={() => handleDelete(record)}>
            <Button size="small" type="link" danger icon={<DeleteOutlined />}>
              刪除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Text strong style={{ fontSize: 16 }}>🏷️ 機構分類標籤</Text>
        <Button type="primary" icon={<PlusOutlined />} size="small" onClick={openAdd}>
          新增標籤
        </Button>
      </div>

      {/* Category tabs */}
      <Tabs
        activeKey={activeCategory}
        onChange={setActiveCategory}
        items={CATEGORIES.map(cat => ({
          key: cat,
          label: cat,
        }))}
        size="small"
        style={{ marginBottom: 0 }}
      />

      {/* Table */}
      <Table
        dataSource={filtered}
        columns={columns}
        rowKey="id"
        pagination={false}
        scroll={{ x: 600 }}
        size="middle"
      />

      {/* Add/Edit Modal */}
      <Modal
        title={editingTag ? `編輯標籤：${editingTag.name}` : '新增標籤'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSave}
        okText={editingTag ? '儲存' : '建立'}
        width={480}
      >
        <Form form={form} layout="vertical" initialValues={{ category: '自訂', color: '#1677ff' }}>
          <Form.Item name="name" label="標籤名稱" rules={[{ required: true, message: '請輸入標籤名稱' }]}>
            <Input placeholder="請輸入標籤名稱" />
          </Form.Item>
          <Form.Item name="category" label="分類" rules={[{ required: true }]}>
            <Select
              options={CATEGORIES.filter(c => c !== '全部').map(c => ({ label: c, value: c }))}
            />
          </Form.Item>
          <Form.Item name="color" label="顏色">
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {PRESET_COLORS.map(color => (
                <div
                  key={color}
                  style={{
                    width: 28, height: 28, borderRadius: 6,
                    background: color, cursor: 'pointer',
                    border: form.getFieldValue('color') === color
                      ? '3px solid #333'
                      : '2px solid transparent',
                    transition: 'border-color 0.15s',
                  }}
                  onClick={() => form.setFieldsValue({ color })}
                />
              ))}
            </div>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
