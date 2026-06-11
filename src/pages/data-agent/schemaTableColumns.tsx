/**
 * @file        Data Agent Schema 列表欄位設定
 * @description Schema 頁面的列表欄位
 * @lastUpdate  2026-04-11 18:13:37
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { Button, Space, Tag, Popconfirm } from 'antd';
import { EditOutlined, DeleteOutlined, UnorderedListOutlined, TableOutlined, FileTextOutlined } from '@ant-design/icons';
import { TableInfo } from '../../services/dataAgentApi';
import { TAB_LABELS } from './schemaConstants';

interface SchemaTableColumnsProps {
  onOpenColumnsModal: (record: TableInfo) => void;
  onOpenDataModal: (record: TableInfo) => void;
  onEditTable: (record: TableInfo) => void;
  onDeleteTable: (tableId: string) => void;
  onOpenReportModal: (record: TableInfo) => void;
}

export const getSchemaTableColumns = ({
  onOpenColumnsModal,
  onOpenDataModal,
  onEditTable,
  onDeleteTable,
  onOpenReportModal,
}: SchemaTableColumnsProps) => [
  { 
    title: '來源', dataIndex: 'data_source', key: 'data_source', width: 80,
    render: (ds: 'ragic' | undefined) => (
      <Tag color={ds === 'ragic' ? 'green' : 'default'}>{ds?.toUpperCase() || 'N/A'}</Tag>
    )
  },
  { title: 'Table ID', dataIndex: 'table_id', key: 'table_id', width: 220 },
  { title: '表名', dataIndex: 'table_name', key: 'table_name', ellipsis: true },
  { 
    title: '模組', dataIndex: 'module', key: 'module', width: 100,
    render: (module: string) => {
      const colors: Record<string, string> = {
        'BASE': 'blue', 'TRADE': 'green', 'MFG': 'orange',
        'QC': 'red', 'CRM_SCM': 'purple', 'MGMT': 'cyan',
      };
      return <Tag color={colors[module] || 'default'}>{module}</Tag>;
    }
  },
  { 
    title: '頁籤', dataIndex: 'tab', key: 'tab', width: 140, ellipsis: true,
    render: (tab: string) => TAB_LABELS[tab] || tab
  },
  { title: 'Sheet Key', dataIndex: 'sheet_key', key: 'sheet_key', width: 110 },
  { 
    title: '表單連結', dataIndex: 'sheet_url', key: 'sheet_url', width: 80,
    render: (url: string) => url ? <a href={url} target="_blank" rel="noopener noreferrer">開啟</a> : '-'
  },
  { 
    title: '狀態', dataIndex: 'status', key: 'status', width: 80,
    render: (status: string) => <Tag color={status === 'enabled' ? 'success' : 'default'}>{status}</Tag>
  },
  {
    title: '操作', key: 'actions', width: 200,
    render: (_: unknown, record: TableInfo) => (
      <Space>
        <Button type="link" icon={<UnorderedListOutlined />} onClick={() => onOpenColumnsModal(record)} title="查看欄位" />
        <Button type="link" icon={<TableOutlined />} onClick={() => onOpenDataModal(record)} title="查看資料" />
        <Button type="link" icon={<FileTextOutlined />} onClick={() => onOpenReportModal(record)} title="智慧報表" />
        <Button type="link" icon={<EditOutlined />} onClick={() => onEditTable(record)} />
        <Popconfirm title="確定要刪除此資料表嗎？" onConfirm={() => onDeleteTable(record.table_id)}>
          <Button type="link" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    )
  }
];
