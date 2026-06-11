/**
 * @file        預訂購看板
 * @description 從前端收集的預訂購資訊列表，支援新增、查詢、狀態更新
 * @lastUpdate  2026-04-28 22:41:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, Select, Tag, Space, App, Spin, Descriptions, Empty, Popconfirm } from 'antd';
import { PlusOutlined, ShoppingCartOutlined, EyeOutlined, ArrowLeftOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { authStore } from '../stores/auth';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';

const API_BASE = '/order-secretary';

interface PreorderItem {
  _key?: string;
  line_no?: number;
  product_name: string;
  quantity: number;
  unit: string;
  spec: string;
  notes?: string;
}

interface Preorder {
  _key: string;
  preorder_id: string;
  user_id: string;
  user_name: string;
  status: string;
  source: string;
  items?: PreorderItem[];
  notes: string;
  created_at: string;
  message_date: string;
}

const statusColors: Record<string, string> = {
  '開立': 'blue',
  '預購確認中': 'orange',
  '已正式立單': 'green',
};

const statusOptions = ['開立', '預購確認中', '已正式立單'];

function ItemTable({ preorderId: _preorderId, masterKey }: { preorderId: string; masterKey: string }) {
  const [items, setItems] = useState<PreorderItem[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setLoading(true);
    fetch(`/order-secretary/preorders/${masterKey}/items`, {
      headers: { Authorization: `Bearer ${authStore.getState().token}` },
    }).then(r => r.ok ? r.json() : []).then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, [masterKey]);
  if (loading) return <Spin size="small" />;
  if (items.length === 0) return <div style={{ padding: 8, color: '#999' }}>無明細資料</div>;
  return (
    <Table dataSource={items} rowKey={(r: any) => r._key || `item_${r.line_no}`} size="small" pagination={false}
      columns={[
        { title: '項次', dataIndex: 'line_no', width: 60 },
        { title: '品名', dataIndex: 'product_name', width: 160 },
        { title: '規格', dataIndex: 'spec', width: 120, render: (s: string) => s || '-' },
        { title: '數量', dataIndex: 'quantity', width: 80, render: (q: number) => <b>{q}</b> },
        { title: '單位', dataIndex: 'unit', width: 60 },
        { title: '備註', dataIndex: 'notes', render: (n: string) => n || '-' },
      ]}
    />
  );
}

export default function PreorderBoard() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Preorder[]>([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [form] = Form.useForm();

  const API = API_BASE;
  useEntityPerception({ defaultEntityType: 'preorder', defaultAction: 'list' });

  const fetchList = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/preorders`, {
        headers: { Authorization: `Bearer ${authStore.getState().token}` },
      });
      if (res.ok) {
        const json = await res.json();
        setData(Array.isArray(json) ? json : []);
      } else {
        message.error('載入預訂購列表失敗');
      }
    } catch {
      message.error('載入預訂購列表失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, []);

  useEffect(() => {
    pageContextManager.report({ component: 'PreorderBoard', entityType: 'preorder', action: 'list' });
  }, []);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setConfirmLoading(true);
      // 透過 skill endpoint 建立預購單（統一 skills 框架入口）
      const res = await fetch(`${API}/skills/order_preorder_collect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.getState().token}`,
        },
        body: JSON.stringify({
          content: JSON.stringify({
            items: [{
              product_name: values.product_name,
              quantity: values.quantity,
              unit: values.unit || '',
              spec: values.spec || '',
            }],
            notes: values.notes || '',
          }),
          media_type: 'structured',
          user_id: values.user_id || 'frontend_user',
          user_name: values.user_name || '前端輸入',
          session_id: `web:${values.user_id || 'frontend'}`,
        }),
      });
      if (res.ok) {
        const json = await res.json();
        if (json.status === 'success') {
          message.success(`預訂購 ${json.order_id || ''} 已建立`);
          form.resetFields();
          setCreateOpen(false);
          fetchList();
        } else {
          message.error(json.message || '建立失敗');
        }
      } else {
        message.error('建立失敗');
      }
    } catch {
      message.error('請填寫完整資訊');
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleEdit = (record: any) => {
    const raw = record._raw || record;
    setEditKey(raw._key || record.orig_key);
    const item = raw.items?.[0] || record;
    form.setFieldsValue({
      user_name: raw.user_name || record.user_name,
      user_id: raw.user_id || '',
      product_name: item.product_name,
      quantity: item.quantity,
      unit: item.unit,
      spec: item.spec,
      notes: raw.notes || record.notes || '',
    });
    setCreateOpen(true);
  };

  const handleUpdate = async () => {
    if (!editKey) return;
    try {
      const values = await form.validateFields();
      setConfirmLoading(true);
      const res = await fetch(`${API}/preorders/${editKey}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.getState().token}`,
        },
        body: JSON.stringify({
          user_name: values.user_name,
          notes: values.notes,
          items: [{
            product_name: values.product_name,
            quantity: values.quantity,
            unit: values.unit || '',
            spec: values.spec || '',
          }],
        }),
      });
      if (res.ok) {
        message.success('已更新');
        form.resetFields();
        setCreateOpen(false);
        setEditKey(null);
        fetchList();
      } else {
        message.error('更新失敗');
      }
    } catch {
      message.error('請填寫完整資訊');
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleDelete = async (key: string) => {
    try {
      const res = await fetch(`${API}/preorders/${key}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authStore.getState().token}` },
      });
      if (res.ok) {
        message.success('已刪除');
        fetchList();
      } else {
        message.error('刪除失敗');
      }
    } catch {
      message.error('刪除失敗');
    }
  };

  const handleView = (record: any) => {
    setSelected(record._raw || record);
    setDetailOpen(true);
  };

  const handleStatusChange = async (key: string, newStatus: string) => {
    try {
      const res = await fetch(`${API}/preorders/${key}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.getState().token}`,
        },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        message.success('狀態已更新');
        fetchList();
      }
    } catch {
      message.error('更新失敗');
    }
  };

  const sourceMap: Record<string, string> = { chat: '聊天', phone: '電話', website: '網站' };

  const columns: any[] = [
    {
      title: '訂購單號',
      dataIndex: 'preorder_id',
      width: 160,
      render: (id: string, record: any) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => handleView(record)}>
          {id}
        </Button>
      ),
    },
    {
      title: '客戶',
      dataIndex: 'user_name',
      width: 120,
    },
    {
      title: '日期',
      dataIndex: 'message_date',
      width: 150,
      render: (d: string) => d ? new Date(d).toLocaleString('zh-TW') : '-',
    },
    {
      title: '來源',
      dataIndex: 'source',
      width: 80,
      render: (s: string) => <Tag>{sourceMap[s] || s || '聊天'}</Tag>,
    },
    {
      title: '狀態',
      dataIndex: 'status',
      width: 140,
      render: (status: string, record: any) => {
        const realKey = record.orig_key || record._key;
        return (
          <Select
            value={status}
            size="small"
            style={{ width: 120 }}
            onChange={(v) => handleStatusChange(realKey, v)}
            options={statusOptions.map(s => ({ value: s, label: s }))}
          />
        );
      },
    },
    {
      title: '備註',
      dataIndex: 'notes',
      width: 150,
      ellipsis: true,
    },
    {
      title: '操作',
      width: 180,
      render: (_: any, record: any) => {
        const realKey = record.orig_key || record._key;
        return (
          <Space>
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>編輯</Button>
            <Popconfirm title="確定刪除此預訂購？" onConfirm={() => handleDelete(realKey)}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>刪除</Button>
            </Popconfirm>
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleView(record)} />
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/app/browse-agent')}>返回</Button>
          <h2 style={{ margin: 0 }}><ShoppingCartOutlined /> 預訂購資訊</h2>
        </div>
        <Space>
          <Button onClick={fetchList}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            新增預訂購
          </Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        {data.length > 0 ? (
          <Table
            columns={columns}
            dataSource={data}
            rowKey="_key"
            pagination={{ pageSize: 15 }}
            scroll={{ x: 900 }}
            expandable={{
              expandedRowRender: (record: any) => (
                <ItemTable preorderId={record.preorder_id} masterKey={record._key} />
              ),
              rowExpandable: () => true,
            }}
          />
          ) : (
          <Empty description="暫無預訂購記錄" style={{ marginTop: 60 }}>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              建立第一筆預訂購
            </Button>
          </Empty>
        )}
      </Spin>

      <Modal title="預訂購詳情" open={detailOpen} onCancel={() => setDetailOpen(false)} footer={null} width={600}>
        {selected && (
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="編號">{selected.preorder_id}</Descriptions.Item>
            <Descriptions.Item label="狀態">
              <Tag color={statusColors[selected.status] || 'default'}>{selected.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="客戶">{selected.user_name}</Descriptions.Item>
            <Descriptions.Item label="用戶 ID">{selected.user_id}</Descriptions.Item>
            <Descriptions.Item label="日期">{new Date(selected.message_date).toLocaleString('zh-TW')}</Descriptions.Item>
            <Descriptions.Item label="備註">{selected.notes || '-'}</Descriptions.Item>
            <Descriptions.Item label="訂購產品" span={2}>
              {((selected as any).items || (selected as any)._raw?.items || []).map((item: any, i: number) => (
                <div key={i}>
                  {i + 1}. {item.product_name} × {item.quantity}{item.unit}
                  {item.spec ? `（${item.spec}）` : ''}
                </div>
              )) || '-'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      <Modal title={editKey ? '編輯預訂購' : '新增預訂購'} open={createOpen}
        onCancel={() => { setCreateOpen(false); setEditKey(null); form.resetFields(); }}
        onOk={editKey ? handleUpdate : handleCreate}
        confirmLoading={confirmLoading} okText={editKey ? '更新' : '建立'}>
        <Form form={form} layout="vertical">
          <Form.Item name="user_name" label="客戶名稱" rules={[{ required: true }]}>
            <Input placeholder="客戶名稱" />
          </Form.Item>
          <Form.Item name="user_id" label="用戶 ID">
            <Input placeholder="LINE 用戶 ID（選填）" />
          </Form.Item>
          <Form.Item name="product_name" label="產品名稱" rules={[{ required: true }]}>
            <Input placeholder="如：鋼板" />
          </Form.Item>
          <Form.Item name="quantity" label="數量" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={0.1} step={1} />
          </Form.Item>
          <Form.Item name="unit" label="單位">
            <Input placeholder="如：噸、顆、箱" />
          </Form.Item>
          <Form.Item name="spec" label="規格">
            <Input placeholder="如：厚度5mm" />
          </Form.Item>
          <Form.Item name="notes" label="備註">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
