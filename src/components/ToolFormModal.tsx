/**
 * @file        工具表單組件
 * @description 工具創建/編輯 Modal，包含基本資訊、執行配置、模型配置、授權配置
 * @lastUpdate  2026-03-28 10:22:08
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useEffect, useState } from 'react';
import { Modal, Form, Input, Select, InputNumber, Tabs, Button, Space, App, Radio } from 'antd';
import { SyncOutlined } from '@ant-design/icons';
import { iconMap } from '../utils/icons';
import IconPicker from './IconPicker';
import { Tool, roleApi } from '../services/api';

const { TextArea } = Input;

const toolTypeOptions = [
  { value: 'tool', label: '外部工具' },
  { value: 'advisor', label: '顧問代理' },
  { value: 'oracle', label: '深度顧問 (Oracle)' },
  { value: 'mcp', label: 'MCP 工具' },
  { value: 'builtin', label: '內建工具' },
  { value: 'custom', label: '自訂工具' },
];

const statusOptions = [
  { value: 'online', label: '在線' },
  { value: 'maintenance', label: '維修中' },
  { value: 'deprecated', label: '已作廢' },
  { value: 'registering', label: '審查中' },
];

interface ToolFormModalProps {
  open: boolean;
  tool?: Tool | null;
  mode: 'create' | 'edit';
  readOnly?: boolean;
  onCancel: () => void;
  onSubmit: (values: Partial<Tool>) => void;
  onDelete?: (toolKey: string) => void;
  onSyncIntents?: (toolKey: string, data: { intent_tags: string[]; nl_examples: string[] }) => Promise<void>;
}

export default function ToolFormModal({
  open,
  tool,
  mode,
  readOnly = false,
  onCancel,
  onSubmit,
  onDelete,
  onSyncIntents,
}: ToolFormModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [iconPickerVisible, setIconPickerVisible] = useState(false);
  const [roles, setRoles] = useState<{ value: string; label: string }[]>([]);
  const [visibility, setVisibility] = useState<'public' | 'role' | 'account'>('public');
  const [syncing, setSyncing] = useState(false);
  const [nlExamples, setNlExamples] = useState<string[]>([]);
  const [newExample, setNewExample] = useState('');

  useEffect(() => {
    roleApi.list().then((res: { data?: { data?: { _key: string; name: string }[] } }) => {
      const opts = (res?.data?.data || []).map((r) => ({ value: r._key, label: r.name }));
      setRoles(opts);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (open && tool && mode === 'edit') {
      const inputSchemaStr = tool.input_schema ? JSON.stringify(tool.input_schema, null, 2) : '';
      const outputSchemaStr = tool.output_schema ? JSON.stringify(tool.output_schema, null, 2) : '';

      form.setFieldsValue({
        ...tool,
        tool_type: tool.tool_type || 'custom',
        status: tool.status || 'online',
        group_key: tool.group_key || '',
        intent_tags: tool.intent_tags || [],
        endpoint_url: tool.endpoint_url || '',
        timeout_ms: tool.timeout_ms ?? 30000,
        input_schema_str: inputSchemaStr,
        output_schema_str: outputSchemaStr,
        llm_model: tool.llm_model || 'gemma4:31b',
        temperature: tool.temperature ?? 0.7,
        max_tokens: tool.max_tokens ?? 32000,
        visibility: tool.visibility || 'public',
        visibility_roles: tool.visibility_roles || [],
        visibility_accounts: tool.visibility_accounts || [],
      });
      setVisibility(tool.visibility || 'public');
      setNlExamples((tool as any).nl_examples || []);
    } else if (open && mode === 'create') {
      form.resetFields();
      form.setFieldsValue({
        status: 'online',
        tool_type: 'custom',
        visibility: 'public',
        llm_model: 'gemma4:31b',
        temperature: 0.7,
        max_tokens: 32000,
        timeout_ms: 30000,
        intent_tags: [],
        visibility_roles: [],
        visibility_accounts: [],
      });
      setVisibility('public');
      setNlExamples([]);
    }
  }, [open, tool, mode, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      let parsedInputSchema = undefined;
      if (values.input_schema_str && values.input_schema_str.trim() !== '') {
        try {
          parsedInputSchema = JSON.parse(values.input_schema_str);
        } catch (e) {
          message.warning('輸入 Schema 格式不正確，將以字串儲存');
          parsedInputSchema = values.input_schema_str;
        }
      }

      let parsedOutputSchema = undefined;
      if (values.output_schema_str && values.output_schema_str.trim() !== '') {
        try {
          parsedOutputSchema = JSON.parse(values.output_schema_str);
        } catch (e) {
          message.warning('輸出 Schema 格式不正確，將以字串儲存');
          parsedOutputSchema = values.output_schema_str;
        }
      }

      const submitData: Partial<Tool> = {
        ...values,
        input_schema: parsedInputSchema,
        output_schema: parsedOutputSchema,
      };

      delete (submitData as Record<string, unknown>).input_schema_str;
      delete (submitData as Record<string, unknown>).output_schema_str;

      onSubmit(submitData);
    } catch (err) {
      message.error('請填寫必填欄位');
    }
  };

  const handleDelete = () => {
    if (tool?._key && onDelete) {
      Modal.confirm({
        title: '確認刪除',
        content: `確定要刪除工具「${tool.name}」嗎？此操作無法復原。`,
        okText: '刪除',
        okType: 'danger',
        cancelText: '取消',
        onOk: () => onDelete(tool._key as string),
      });
    }
  };

  const IconPreview = () => {
    const iconValue = form.getFieldValue('icon');
    const IconComp = iconValue ? iconMap[iconValue] : null;
    return IconComp ? <IconComp style={{ fontSize: 20 }} /> : null;
  };

  const basicTab = (
    <>
      <Form.Item label="圖標">
        <Space>
          {readOnly ? (
            <IconPreview />
          ) : (
            <Button onClick={() => setIconPickerVisible(true)}>
              <Space>
                <IconPreview />
                選擇圖標
              </Space>
            </Button>
          )}
          <span>{form.getFieldValue('icon') || '未設置'}</span>
        </Space>
      </Form.Item>
      <Form.Item name="icon" hidden>
        <Input />
      </Form.Item>
      <Form.Item name="name" label="名稱" rules={[{ required: true, message: '請輸入名稱' }]}>
        <Input placeholder="例如：網路搜尋工具" disabled={readOnly} />
      </Form.Item>
      <Form.Item name="code" label="代碼 (Code)" rules={[{ required: true, message: '請輸入代碼' }]}>
        <Input placeholder="例如：web_search" disabled={readOnly} />
      </Form.Item>
      <Form.Item name="description" label="描述">
        <TextArea rows={3} placeholder="描述這個工具的用途..." disabled={readOnly} />
      </Form.Item>
      <Form.Item name="tool_type" label="工具類型">
        <Select options={toolTypeOptions} disabled={readOnly} />
      </Form.Item>
      <Form.Item name="status" label="狀態">
        <Select options={statusOptions} disabled={readOnly} />
      </Form.Item>
      <Form.Item name="group_key" label="分組 Key">
        <Input placeholder="例如：search, data, utility" disabled={readOnly} />
      </Form.Item>
      <Form.Item name="intent_tags" label="意圖標籤">
        <Select mode="tags" placeholder="輸入意圖標籤，按 Enter 確認" disabled={readOnly} />
      </Form.Item>
    </>
  );

  const executionTab = (
    <>
      <Form.Item name="endpoint_url" label="Endpoint URL">
        <Input placeholder="http://localhost:8004/execute" disabled={readOnly} />
      </Form.Item>
      <Form.Item name="timeout_ms" label="超時設定 (ms)">
        <InputNumber min={1000} max={300000} step={1000} addonAfter="ms" style={{ width: '100%' }} disabled={readOnly} />
      </Form.Item>
      <Form.Item name="input_schema_str" label="輸入 Schema (JSON)">
        <TextArea rows={4} placeholder={'{"type":"object","properties":{...}}'} disabled={readOnly} />
      </Form.Item>
      <Form.Item name="output_schema_str" label="輸出 Schema (JSON)">
        <TextArea rows={4} placeholder={'{"type":"object","properties":{...}}'} disabled={readOnly} />
      </Form.Item>
    </>
  );

  const modelTab = (
    <>
      <Form.Item name="llm_model" label="LLM 模型">
        <Input placeholder="例如：llama3, gpt-4" disabled={readOnly} />
      </Form.Item>
      <Form.Item name="temperature" label="Temperature">
        <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} disabled={readOnly} />
      </Form.Item>
      <Form.Item name="max_tokens" label="最大 Tokens">
        <InputNumber min={100} max={32000} step={100} style={{ width: '100%' }} disabled={readOnly} />
      </Form.Item>
    </>
  );

  const permissionTab = (
    <>
      <Form.Item label="可見性" name="visibility">
        <Radio.Group value={visibility} onChange={(e) => setVisibility(e.target.value)} disabled={readOnly}>
          <Radio.Button value="public">公開</Radio.Button>
          <Radio.Button value="role">按角色</Radio.Button>
          <Radio.Button value="account">按帳號</Radio.Button>
        </Radio.Group>
      </Form.Item>
      {visibility === 'role' && (
        <Form.Item label="可見角色" name="visibility_roles">
          <Select mode="multiple" placeholder="選擇可見的角色" options={roles} disabled={readOnly} />
        </Form.Item>
      )}
      {visibility === 'account' && (
        <Form.Item label="可見帳號" name="visibility_accounts">
          <Select mode="tags" placeholder="輸入用戶帳號，按 Enter 確認" disabled={readOnly} />
        </Form.Item>
      )}
    </>
  );

  const intentsTab = (
    <>
      <Form.Item label="意圖標籤">
        <Form.Item name="intent_tags" noStyle>
          <Select mode="tags" placeholder="輸入意圖標籤，按 Enter 確認" disabled={readOnly} />
        </Form.Item>
      </Form.Item>
      <Form.Item label="自然語言範例" tooltip="這些範例會同步到 Qdrant，用於語意匹配">
        <div style={{ border: '1px solid #d9d9d9', borderRadius: 8, padding: 16, background: '#fafafa' }}>
          {nlExamples.map((example, index) => (
            <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ color: '#666', minWidth: 24 }}>{index + 1}.</span>
              <Input value={example} disabled />
              {!readOnly && (
                <Button
                  type="text"
                  danger
                  size="small"
                  onClick={() => {
                    const newExamples = [...nlExamples];
                    newExamples.splice(index, 1);
                    setNlExamples(newExamples);
                    form.setFieldValue('nl_examples', newExamples);
                  }}
                >
                  刪除
                </Button>
              )}
            </div>
          ))}
          {nlExamples.length === 0 && (
            <div style={{ color: '#999', textAlign: 'center', padding: '16px 0' }}>
              暫無範例，點擊下方按鈕新增
            </div>
          )}
          {!readOnly && (
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <Input
                placeholder="輸入新的自然語言範例..."
                value={newExample}
                onChange={(e) => setNewExample(e.target.value)}
                onPressEnter={() => {
                  if (newExample.trim()) {
                    const updated = [...nlExamples, newExample.trim()];
                    setNlExamples(updated);
                    form.setFieldValue('nl_examples', updated);
                    setNewExample('');
                  }
                }}
              />
              <Button
                onClick={() => {
                  if (newExample.trim()) {
                    const updated = [...nlExamples, newExample.trim()];
                    setNlExamples(updated);
                    form.setFieldValue('nl_examples', updated);
                    setNewExample('');
                  }
                }}
              >
                新增
              </Button>
            </div>
          )}
        </div>
      </Form.Item>
      <Form.Item name="nl_examples" hidden>
        <Input />
      </Form.Item>
      {mode === 'edit' && tool?._key && onSyncIntents && (
        <Form.Item>
          <Button
            type="default"
            icon={<SyncOutlined />}
            loading={syncing}
            onClick={async () => {
              const values = await form.validateFields();
              const intentTags = values.intent_tags || [];
              const nlExamplesList = values.nl_examples || nlExamples;
              try {
                setSyncing(true);
                await onSyncIntents(tool._key as string, {
                  intent_tags: intentTags,
                  nl_examples: nlExamplesList,
                });
                message.success('已同步到 Qdrant');
              } catch {
                message.error('同步失敗');
              } finally {
                setSyncing(false);
              }
            }}
          >
            {syncing ? '同步中...' : '同步到 Qdrant'}
          </Button>
        </Form.Item>
      )}
    </>
  );

  return (
    <>
      <Modal
        title={mode === 'create' ? '新增工具' : '編輯工具'}
        open={open}
        onCancel={onCancel}
        width={720}
        forceRender
        footer={
          <Space>
            {readOnly ? (
              <Button onClick={onCancel}>關閉</Button>
            ) : (
              <>
                {mode === 'edit' && onDelete && (
                  <Button danger onClick={handleDelete}>
                    刪除
                  </Button>
                )}
                <Button onClick={onCancel}>取消</Button>
                <Button type="primary" onClick={handleSubmit}>
                  {mode === 'create' ? '建立' : '儲存'}
                </Button>
              </>
            )}
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Tabs
            defaultActiveKey="basic"
            items={[
              {
                key: 'basic',
                label: '基本資訊',
                children: basicTab,
              },
              {
                key: 'execution',
                label: '執行配置',
                children: executionTab,
              },
              {
                key: 'model',
                label: '模型配置',
                children: modelTab,
              },
              {
                key: 'intents',
                label: '意圖範例',
                children: intentsTab,
              },
              {
                key: 'permission',
                label: '授權配置',
                children: permissionTab,
              },
            ]}
          />
        </Form>
      </Modal>
      <IconPicker
        open={iconPickerVisible}
        onCancel={() => setIconPickerVisible(false)}
        onSelect={(icon) => form.setFieldValue('icon', icon)}
      />
    </>
  );
}
