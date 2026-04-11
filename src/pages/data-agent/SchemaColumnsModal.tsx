/**
 * @file        Data Agent Schema 欄位定義 Modal
 * @description Schema 頁面的欄位定義 Modal 元件
 * @lastUpdate  2026-04-11 18:13:37
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { Modal, Table, Tag } from 'antd';
import { FieldInfo } from '../../services/dataAgentApi';

interface SchemaColumnsModalProps {
  visible: boolean;
  tableName: string;
  columns: FieldInfo[];
  loading: boolean;
  onCancel: () => void;
}

export default function SchemaColumnsModal({
  visible,
  tableName,
  columns,
  loading,
  onCancel,
}: SchemaColumnsModalProps) {
  return (
    <Modal
      title={`欄位定義 — ${tableName}`}
      open={visible}
      onCancel={onCancel}
      footer={null}
      width="80%"
    >
      <Table
        dataSource={columns}
        rowKey="field_id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 20 }}
        columns={[
          { title: 'Field ID', dataIndex: 'field_id', key: 'field_id', width: 100 },
          { title: 'Field Name', dataIndex: 'field_name', key: 'field_name', ellipsis: true },
          { title: 'Type', dataIndex: 'field_type', key: 'field_type', width: 120 },
          { 
            title: 'Writable', 
            dataIndex: 'writable', 
            key: 'writable', 
            width: 90, 
            render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? 'Yes' : 'No'}</Tag> 
          },
          { title: 'Write Format', dataIndex: 'write_format', key: 'write_format', width: 140, ellipsis: true },
          { title: 'Memo', dataIndex: 'memo', key: 'memo', ellipsis: true },
        ]}
      />
    </Modal>
  );
}
