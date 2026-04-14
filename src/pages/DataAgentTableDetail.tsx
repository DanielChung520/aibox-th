/**
 * @file        Data Agent 表格詳細資訊視圖
 * @description 顯示 da_tables 欄位、關聯及 da_expressions 意圖管理
 * @lastUpdate  2026-04-13 12:00:00
 * @author      Daniel Chung
 * @version     2.0.0
 */

import { useState, useEffect } from 'react';
import { Tabs, Table, Button, Space, Modal, Form, Input, Tag, Popconfirm, App, Select, Tooltip, Switch } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { daExpressionsApi, DaExpression, DaTable } from '../services/daTablesApi';

interface Props {
  tableData: DaTable;
}

const ACTION_OPTIONS = [
  { label: 'Query 查詢', value: 'query' },
  { label: 'Count 計數', value: 'count' },
  { label: 'Sum 加總', value: 'sum' },
  { label: 'Update 更新', value: 'update' },
];

const QUERY_TYPE_OPTIONS = [
  { label: 'Simple Filter (Path A)', value: 'simple_filter' },
  { label: 'Aggregate (Path B)', value: 'aggregate' },
];

const DOMAIN_OPTIONS = [
  { label: 'Sales 銷售', value: 'sales' },
  { label: 'CRM 客戶', value: 'crm' },
  { label: 'Contract 合約', value: 'contract' },
  { label: 'Inventory 庫存', value: 'inventory' },
  { label: 'Finance 財務', value: 'finance' },
  { label: 'Marketing 行銷', value: 'marketing' },
  { label: 'Manufacturing 生產', value: 'manufacturing' },
  { label: 'Quality 品管', value: 'quality' },
  { label: 'Trade 貿易', value: 'trade' },
  { label: 'Base 基礎', value: 'base' },
  { label: 'Management 管理', value: 'management' },
];

const DIFFICULTY_OPTIONS = [
  { label: 'Easy 簡單', value: 'easy' },
  { label: 'Medium 中等', value: 'medium' },
  { label: 'Hard 困難', value: 'hard' },
];

export default function DataAgentTableDetail({ tableData }: Props) {
  const { message } = App.useApp();
  const [expressions, setExpressions] = useState<DaExpression[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingExp, setEditingExp] = useState<DaExpression | null>(null);
  const [form] = Form.useForm();

  const fetchExpressions = async () => {
    setLoading(true);
    try {
      const res = await daExpressionsApi.list({ table_key: tableData._key, page_size: 100 });
      setExpressions(res.data.data.records || []);
    } catch (err: unknown) {
      message.error('載入表達式失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExpressions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableData._key]);

  const handleAdd = () => {
    setEditingExp(null);
    form.resetFields();
    form.setFieldsValue({
      status: 'enabled',
      action: 'query',
      domain: tableData.domain || 'base',
      query_type: tableData.capabilities?.aggregate ? 'aggregate' : 'simple_filter',
      is_template: true,
    });
    setModalOpen(true);
  };

  const handleEdit = (record: DaExpression) => {
    setEditingExp(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleDelete = async (key: string) => {
    try {
      await daExpressionsApi.delete(key);
      message.success('刪除成功');
      fetchExpressions();
    } catch (err: unknown) {
      message.error('刪除失敗');
    }
  };

  const handleToggleStatus = async (key: string, checked: boolean) => {
    try {
      await daExpressionsApi.update(key, { status: checked ? 'enabled' : 'disabled' });
      message.success(checked ? '已啟用' : '已停用');
      fetchExpressions();
    } catch (err: unknown) {
      message.error('狀態更新失敗');
    }
  };

  const handleSave = async () => {
    try {
      const vals = await form.validateFields();
      if (editingExp) {
        await daExpressionsApi.update(editingExp._key, vals);
        message.success('更新成功');
      } else {
        const key = `${tableData._key}_${vals.angle || 'custom'}`;
        await daExpressionsApi.create({ ...vals, _key: key, table_key: tableData._key });
        message.success('新增成功');
      }
      setModalOpen(false);
      fetchExpressions();
    } catch (err: unknown) {
      message.error('儲存失敗');
    }
  };

  const expCols = [
    { title: 'Angle', dataIndex: 'angle', key: 'angle' },
    { title: '名稱', dataIndex: 'name', key: 'name' },
    { title: '動作', dataIndex: 'action', key: 'action', render: (v: string) => <Tag color={v === 'query' ? 'green' : v === 'sum' ? 'orange' : 'purple'}>{v}</Tag> },
    { title: '領域', dataIndex: 'domain', key: 'domain', render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: '查詢類型', dataIndex: 'query_type', key: 'query_type', render: (v: string) => <Tag color={v === 'aggregate' ? 'cyan' : 'geekblue'}>{v}</Tag> },
    { title: '難度', dataIndex: 'difficulty_level', key: 'difficulty_level', render: (v: string) => <Tag color={v === 'hard' ? 'red' : v === 'medium' ? 'orange' : 'green'}>{v}</Tag> },
    { title: '模板', dataIndex: 'is_template', key: 'is_template', render: (v: boolean) => <Tag color={v ? 'purple' : 'default'}>{v ? '是' : '否'}</Tag> },
    { title: '狀態', dataIndex: 'status', key: 'status', render: (v: string, r: DaExpression) => <Switch checked={v === 'enabled'} checkedChildren="啟" unCheckedChildren="停" onChange={(checked) => handleToggleStatus(r._key, checked)} size="small" /> },
    {
      title: 'NL Examples',
      key: 'nl_examples',
      render: (_: unknown, r: DaExpression) => (
        <Tooltip title={r.nl_examples?.join('\n')}>
          <span>{r.nl_examples?.length || 0} 個範例</span>
        </Tooltip>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: DaExpression) => (
        <Space size="middle">
          <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)}>編輯</Button>
          <Popconfirm title="確認刪除？" onConfirm={() => handleDelete(record._key)}>
            <Button type="text" danger icon={<DeleteOutlined />}>刪除</Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  const fieldCols = [
    { title: '欄位 ID', dataIndex: 'field_id', key: 'field_id' },
    { title: '名稱', dataIndex: 'name', key: 'name' },
    { title: '類型', dataIndex: 'type', key: 'type' },
    { title: '可過濾', dataIndex: 'filterable', key: 'filterable', render: (v: boolean) => (v ? '是' : '否') }
  ];

  const relCols = [
    { title: '目標表', dataIndex: 'target_table', key: 'target_table' },
    { title: '關係', dataIndex: 'cardinality', key: 'cardinality' },
    {
      title: '連接鍵',
      dataIndex: 'join_keys',
      key: 'join_keys',
      render: (arr: {source_field: string, target_field: string}[]) =>
        arr?.map(j => `${j.source_field} = ${j.target_field}`).join(', ')
    }
  ];

  return (
    <div style={{ padding: '0 16px 16px', background: 'var(--ant-color-fill-quaternary)', height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <Tabs
        style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
        tabBarStyle={{ flexShrink: 0 }}
        items={[
          {
            key: 'fields',
            label: '欄位',
            children: <Table size="small" columns={fieldCols} dataSource={tableData.fields} rowKey="field_id" pagination={false} scroll={{ y: 240 }} style={{ flex: 1 }} />
          },
          {
            key: 'rels',
            label: '關聯',
            children: <Table size="small" columns={relCols} dataSource={tableData.relationships} rowKey={(r) => r.target_table} pagination={false} scroll={{ y: 240 }} style={{ flex: 1 }} />
          },
          {
            key: 'expr',
            label: '表達式',
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
                <div style={{ marginBottom: 12, textAlign: 'right', flexShrink: 0 }}>
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleAdd}>新增表達</Button>
                </div>
                <Table size="small" columns={expCols} dataSource={expressions} rowKey="_key" loading={loading} pagination={false} scroll={{ y: 280 }} style={{ flex: 1 }} />
              </div>
            )
          }
        ]}
      />
      <Modal title={editingExp ? '編輯表達' : '新增表達'} open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)} width={700}>
        <Form form={form} layout="vertical">
          <Form.Item name="angle" label="Angle" rules={[{ required: true }]}><Input placeholder="如：default, summary, filter" /></Form.Item>
          <Form.Item name="name" label="名稱" rules={[{ required: true }]}><Input placeholder="如：潛在交易對象查詢" /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} placeholder="描述此意圖的用途" /></Form.Item>
          <Space style={{ display: 'flex' }}>
            <Form.Item name="action" label="動作" rules={[{ required: true }]}>
              <Select options={ACTION_OPTIONS} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="domain" label="領域" rules={[{ required: true }]}>
              <Select options={DOMAIN_OPTIONS} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="query_type" label="查詢類型" rules={[{ required: true }]}>
              <Select options={QUERY_TYPE_OPTIONS} style={{ width: 180 }} />
            </Form.Item>
          </Space>
          <Form.Item name="nl_examples" label="NL Examples (場景範例)">
            <Select mode="tags" placeholder="輸入自然語言查詢範例" />
          </Form.Item>
          <Form.Item name="aliases" label="別名"><Select mode="tags" placeholder="別名" /></Form.Item>
          <Space style={{ display: 'flex' }}>
            <Form.Item name="difficulty_level" label="難度">
              <Select allowClear options={DIFFICULTY_OPTIONS} style={{ width: 120 }} placeholder="難度" />
            </Form.Item>
            <Form.Item name="is_template" label="是否為模板" valuePropName="checked" initialValue={true}>
              <Select options={[{ label: '是', value: true }, { label: '否', value: false }]} style={{ width: 80 }} />
            </Form.Item>
            <Form.Item name="status" label="狀態" initialValue="enabled">
              <Select options={[{ label: '啟用', value: 'enabled' }, { label: '停用', value: 'disabled' }]} style={{ width: 100 }} />
            </Form.Item>
          </Space>
          <Form.Item name="golden_sql" label="Golden SQL">
            <Input.TextArea rows={2} placeholder="經驗證的標準 SQL 範本（可選）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
