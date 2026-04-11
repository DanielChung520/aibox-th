/**
 * @file        Data Agent Schema 編輯 Modal
 * @description Schema 頁面的編輯資料表 Modal 元件
 * @lastUpdate  2026-04-11 18:13:37
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { Modal, Form, Input, Select, FormInstance } from 'antd';
import { TableInfo } from '../../services/dataAgentApi';
import { TAB_LABELS } from './schemaConstants';

const { Option } = Select;

interface SchemaEditModalProps {
  visible: boolean;
  form: FormInstance;
  editingTable: Partial<TableInfo> | null;
  onSave: () => void;
  onCancel: () => void;
}

export default function SchemaEditModal({
  visible,
  form,
  editingTable,
  onSave,
  onCancel,
}: SchemaEditModalProps) {
  return (
    <Modal
      title="編輯資料表"
      open={visible}
      onOk={onSave}
      width={600}
      forceRender
      onCancel={onCancel}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="table_id" label="Table ID" rules={[{ required: true }]}>
          <Input disabled={!!editingTable?.table_id} placeholder="如: DATABASE_1" />
        </Form.Item>
        <Form.Item name="table_name" label="表名" rules={[{ required: true }]}>
          <Input placeholder="如: 鄉鎮區+郵遞區號" />
        </Form.Item>
        <Form.Item name="module" label="模組" rules={[{ required: true }]}>
          <Select placeholder="選擇模組">
            <Option value="BASE">BASE - 基礎資料</Option>
            <Option value="TRADE">TRADE - 進銷存</Option>
            <Option value="MFG">MFG - 生產製造</Option>
            <Option value="QC">QC - 品質/ISO</Option>
            <Option value="CRM_SCM">CRM_SCM - 客戶/供應商</Option>
            <Option value="MGMT">MGMT - 管理</Option>
          </Select>
        </Form.Item>
        <Form.Item name="tab" label="Tab Slug" rules={[{ required: true }]}>
          <Select placeholder="選擇頁籤" showSearch>
            {Object.entries(TAB_LABELS).map(([slug, label]) => (
              <Option key={slug} value={slug}>{label} ({slug})</Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item name="sheet_key" label="主表單 Key">
          <Input placeholder="如: 1015369" />
        </Form.Item>
        <Form.Item name="sheet_url" label="表單網址">
          <Input placeholder="如: https://ap15.ragic.com/2025shianyong/database/1" />
        </Form.Item>
        <Form.Item name="api_url" label="API 網址">
          <Input placeholder="如: https://ap15.ragic.com/2025shianyong/database/1?api" />
        </Form.Item>
        <Form.Item name="data_source" label="資料來源" initialValue="ragic">
          <Select disabled>
            <Option value="ragic">Ragic</Option>
          </Select>
        </Form.Item>
        <Form.Item name="status" label="狀態" initialValue="enabled">
          <Select>
            <Option value="enabled">啟用</Option>
            <Option value="disabled">停用</Option>
            <Option value="deprecated">已廢棄</Option>
          </Select>
        </Form.Item>
      </Form>
    </Modal>
  );
}
