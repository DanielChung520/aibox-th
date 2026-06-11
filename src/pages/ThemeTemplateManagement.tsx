/**
 * @file        樣板維護頁面
 * @description 主題樣板 CRUD 管理，支持外殼(shell)與內容(content)兩類樣板
 * @lastUpdate  2026-03-25 15:07:58
 * @author      Daniel Chung
 * @version     1.2.0
 */

import { useState, useEffect, useCallback } from 'react';
import { App, Table, Button, Modal, Form, Input, Select, Switch, Space, Tag, Popconfirm, Typography, theme } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { themeTemplateApi, ThemeTemplate } from '../services/api';
import { useReloadTemplates } from '../contexts/AppThemeProvider';
import { ShellTokensForm, ContentTokensForm } from '../components/ThemeTokenEditor';

const { Title } = Typography;

export default function ThemeTemplateManagement() {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const reloadTemplates = useReloadTemplates();
  const [templates, setTemplates] = useState<ThemeTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ThemeTemplate | null>(null);
  const [form] = Form.useForm();

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const response = await themeTemplateApi.list();
      setTemplates(response.data.data || []);
    } catch {
      message.error('操作失敗');
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handleAdd = () => {
    setEditingTemplate(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: ThemeTemplate) => {
    setEditingTemplate(record);
    const tokens = record.tokens as unknown as Record<string, unknown>;
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      template_type: record.template_type,
      tokens,
      is_default: record.is_default,
      status: record.status,
    });
    setModalVisible(true);
  };

  const handleDelete = async (key: string) => {
    try {
      await themeTemplateApi.delete(key);
      message.success('刪除成功');
      fetchTemplates();
    } catch {
      message.error('操作失敗');
    }
  };

  const handleActivate = async (key: string) => {
    try {
      await themeTemplateApi.activate(key);
      message.success('已啟用');
      fetchTemplates();
      reloadTemplates();
    } catch {
      message.error('操作失敗');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const { tokens, ...rest } = values;
      const finalTokens = (tokens && typeof tokens === 'object') ? tokens : {};
      const payload = { ...rest, tokens: finalTokens };

      if (editingTemplate) {
        await themeTemplateApi.update(editingTemplate._key, payload);
        message.success('更新成功');
      } else {
        await themeTemplateApi.create(payload);
        message.success('建立成功');
      }
      setModalVisible(false);
      fetchTemplates();
      reloadTemplates();
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'errorFields' in e) return;
      message.error('操作失敗');
    }
  };

  const commonColumns = [
    { title: '名稱', dataIndex: 'name', key: 'name' },
    {
      title: '預設', dataIndex: 'is_default', key: 'is_default',
      render: (isDefault: boolean) => <Tag color={isDefault ? 'green' : 'default'}>{isDefault ? '是' : '否'}</Tag>,
    },
    {
      title: '狀態', dataIndex: 'status', key: 'status',
      render: (status: string) => (
        <Tag color={status === 'enabled' ? 'green' : 'red'}>
          {status === 'enabled' ? '啟用 (enabled)' : '停用 (disabled)'}
        </Tag>
      ),
    },
    {
      title: '建立時間', dataIndex: 'created_at', key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
  ];

  const contentColumns = [
    ...commonColumns,
    {
      title: '操作', key: 'action',
      render: (_: unknown, record: ThemeTemplate) => (
        <Space>
          <Button type="link" icon={<CheckCircleOutlined />} onClick={() => handleActivate(record._key)} disabled={record.is_active}>啟用</Button>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>編輯</Button>
          <Popconfirm title="確定刪除此樣板？" onConfirm={() => handleDelete(record._key)} okText="確定" cancelText="取消" disabled={record.is_default}>
            <Button type="link" danger icon={<DeleteOutlined />} disabled={record.is_default}>刪除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const shellTemplates = templates.filter(t => t.template_type === 'shell');
  const contentTemplates = templates.filter(t => t.template_type === 'content');

  const templateType = Form.useWatch('template_type', form) || editingTemplate?.template_type || 'content';

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增樣板
        </Button>
      </div>

      <Title level={4} style={{ marginTop: 0 }}>外殼樣板 (Shell Templates)</Title>
      <Table
        columns={commonColumns}
        dataSource={shellTemplates}
        rowKey="_key"
        loading={loading}
        pagination={false}
        style={{ marginBottom: 32 }}
      />

      <Title level={4}>內容樣板 (Content Templates)</Title>
      <Table
        columns={contentColumns}
        dataSource={contentTemplates}
        rowKey="_key"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title={editingTemplate ? '編輯樣板' : '新增樣板'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={900}
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ status: 'enabled', is_default: false, template_type: 'content' }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
            <Form.Item name="name" label="名稱" rules={[{ required: true, message: '請輸入名稱' }]}>
              <Input />
            </Form.Item>
            <Form.Item name="template_type" label="類型" rules={[{ required: true, message: '請選擇類型' }]}>
              <Select
                disabled={!!editingTemplate}
                options={[
                  { value: 'shell', label: '外殼 (shell)' },
                  { value: 'content', label: '內容 (content)' },
                ]}
              />
            </Form.Item>
          </div>
          <Form.Item name="description" label="說明">
            <Input.TextArea rows={2} />
          </Form.Item>

          <hr style={{ margin: '16px 0', border: 'none', borderTop: `1px solid ${token.colorBorderSecondary}` }} />

          {templateType === 'shell' ? <ShellTokensForm /> : <ContentTokensForm />}

          <hr style={{ margin: '16px 0', border: 'none', borderTop: `1px solid ${token.colorBorderSecondary}` }} />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
            <Form.Item name="is_default" label="預設" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="status" label="狀態" rules={[{ required: true, message: '請選擇狀態' }]}>
              <Select
                options={[
                  { value: 'enabled', label: '啟用 (enabled)' },
                  { value: 'disabled', label: '停用 (disabled)' },
                ]}
              />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  );
}
