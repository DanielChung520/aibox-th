/**
 * @file        追蹤結果表格
 * @description 以表格形式展示資料深度追蹤結果，支援排序/篩選/展開/分頁
 * @lastUpdate  2026-05-17
 * @author      Daniel Chung
 * @version     1.0.0
 */
import { useMemo } from 'react';
import { Table, Tag, Tooltip, Empty } from 'antd';
import type { ColumnsType } from 'antd/es/table';

/* =================== 型別定義 =================== */

export interface TraceNodeData {
  ragic_id: string;
  table_name: string;
  depth: number;
  fields: Record<string, unknown>;
  table_key?: string;
}

export interface TraceResultTableProps {
  /** 追蹤結果節點資料 */
  nodes: TraceNodeData[];
  /** 點擊列回呼 */
  onRowClick?: (ragicId: string) => void;
  /** 載入中狀態 */
  loading?: boolean;
  /** 目前選取的節點 ragic_id（用於行高亮） */
  activeRagicId?: string | null;
}

/* =================== 工具函式 =================== */

/** 深度層級對應的色彩與標籤 */
const DEPTH_TAG_CONFIG: Record<number, { color: string; label: string }> = {
  0: { color: 'magenta', label: 'Root' },
  1: { color: 'red', label: 'Lv.1' },
  2: { color: 'volcano', label: 'Lv.2' },
  3: { color: 'orange', label: 'Lv.3' },
  4: { color: 'gold', label: 'Lv.4' },
  5: { color: 'lime', label: 'Lv.5' },
};

function getDepthTag(depth: number): { color: string; label: string } {
  return DEPTH_TAG_CONFIG[depth] ?? { color: 'geekblue', label: `Lv.${depth}` };
}

/** 從 fields 中 heuristic 找出「批號」相關欄位值 */
function extractBatchNo(fields: Record<string, unknown>): string {
  const batchKeys = ['batch', 'Batch', '批號', '批号', '批号/序号', 'lot', 'Lot', 'LOT'];
  for (const key of batchKeys) {
    for (const [k, v] of Object.entries(fields)) {
      if (k.includes(key) && v != null && String(v).trim()) return String(v).trim();
    }
  }
  return '';
}

/** 從 fields 中 heuristic 找出「名稱/描述」相關欄位值 */
function extractNameOrDesc(fields: Record<string, unknown>): string {
  const nameKeys = ['name', 'Name', '名稱', '名稱', '品名', '品項', '料號', '編號', 'description', 'Description', '描述'];
  for (const key of nameKeys) {
    for (const [k, v] of Object.entries(fields)) {
      if (k.includes(key) && v != null && String(v).trim()) return String(v).trim();
    }
  }
  return '';
}

/** 從 fields 中 heuristic 找出「往來對象」相關欄位值（客戶/供應商/廠商） */
function extractBusinessPartner(fields: Record<string, unknown>): string {
  const bpKeys = ['客戶', '客戶名稱', '客戶代碼', '供應商', '廠商', 'vendor', 'Vendor', 'customer', 'Customer', 'partner', 'Partner'];
  for (const key of bpKeys) {
    for (const [k, v] of Object.entries(fields)) {
      if (k.includes(key) && v != null && String(v).trim()) return String(v).trim();
    }
  }
  return '';
}

/** 從 fields 中 heuristic 找出「日期」相關欄位值 */
function extractDate(fields: Record<string, unknown>): string {
  const dateKeys = ['date', 'Date', '日期', '日期', 'created_at', 'createdAt', 'updated_at'];
  for (const key of dateKeys) {
    for (const [k, v] of Object.entries(fields)) {
      if (k.includes(key) && v != null && String(v).trim()) return String(v).trim();
    }
  }
  return '';
}

/* =================== 主元件 =================== */

const PAGE_SIZE_OPTIONS = [25, 50, 100];

export default function TraceResultTable({ nodes, onRowClick, loading, activeRagicId }: TraceResultTableProps) {
  const columns: ColumnsType<TraceNodeData> = useMemo(() => [
    {
      title: 'Depth',
      dataIndex: 'depth',
      key: 'depth',
      width: 80,
      sorter: (a, b) => a.depth - b.depth,
      defaultSortOrder: 'ascend',
      render: (depth: number) => {
        const cfg = getDepthTag(depth);
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: 'Table Name',
      dataIndex: 'table_name',
      key: 'table_name',
      width: 160,
      sorter: (a, b) => a.table_name.localeCompare(b.table_name),
    },
    {
      title: 'Record ID',
      dataIndex: 'ragic_id',
      key: 'ragic_id',
      width: 140,
      render: (id: string) => (
        <Tooltip title={id}>
          <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{id.length > 16 ? `${id.slice(0, 16)}…` : id}</span>
        </Tooltip>
      ),
    },
    {
      title: 'Batch No',
      key: 'batch_no',
      width: 140,
      render: (_: unknown, record: TraceNodeData) => {
        const val = extractBatchNo(record.fields);
        return val ? <span>{val}</span> : <span style={{ color: '#bfbfbf' }}>—</span>;
      },
    },
    {
      title: 'Name / Description',
      key: 'name_desc',
      ellipsis: true,
      render: (_: unknown, record: TraceNodeData) => {
        const val = extractNameOrDesc(record.fields);
        return val ? (
          <Tooltip title={val}>{val}</Tooltip>
        ) : (
          <span style={{ color: '#bfbfbf' }}>—</span>
        );
      },
    },
    {
      title: 'Business Partner',
      key: 'bp',
      width: 150,
      ellipsis: true,
      render: (_: unknown, record: TraceNodeData) => {
        const val = extractBusinessPartner(record.fields);
        return val ? <span>{val}</span> : <span style={{ color: '#bfbfbf' }}>—</span>;
      },
    },
    {
      title: 'Date',
      key: 'date',
      width: 130,
      sorter: (a, b) => {
        const da = extractDate(a.fields);
        const db = extractDate(b.fields);
        return da.localeCompare(db);
      },
      render: (_: unknown, record: TraceNodeData) => {
        const val = extractDate(record.fields);
        return val ? <span>{val}</span> : <span style={{ color: '#bfbfbf' }}>—</span>;
      },
    },
    {
      title: 'Depth Level',
      key: 'depth_level',
      width: 110,
      filters: [
        { text: 'Root (0)', value: 0 },
        { text: 'Level 1', value: 1 },
        { text: 'Level 2', value: 2 },
        { text: 'Level 3', value: 3 },
        { text: 'Level 4+', value: 4 },
      ],
      onFilter: (value, record) => {
        if (value === 4) return record.depth >= 4;
        return record.depth === value;
      },
      render: (_: unknown, record: TraceNodeData) => {
        const cfg = getDepthTag(record.depth);
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
  ], []);

  /** 展開列：顯示所有 fields key:value */
  const expandedRowRender = (record: TraceNodeData) => {
    const entries = Object.entries(record.fields).filter(([, v]) => v != null);
    if (entries.length === 0) {
      return <Empty description="無欄位資料" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }

    return (
      <div style={{ padding: '8px 0' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#fafafa' }}>
              <th style={{ padding: '4px 12px', borderBottom: '1px solid #f0f0f0', textAlign: 'left', fontWeight: 600, width: '30%' }}>Field</th>
              <th style={{ padding: '4px 12px', borderBottom: '1px solid #f0f0f0', textAlign: 'left', fontWeight: 600 }}>Value</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td style={{ padding: '4px 12px', borderBottom: '1px solid #f5f5f5', color: '#64748b', whiteSpace: 'nowrap' }}>{key}</td>
                <td style={{ padding: '4px 12px', borderBottom: '1px solid #f5f5f5', color: '#1e293b', wordBreak: 'break-all' }}>
                  {typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const handleRow = (record: TraceNodeData) => ({
    onClick: () => {
      onRowClick?.(record.ragic_id);
    },
    style: {
      cursor: onRowClick ? 'pointer' : undefined,
      background: activeRagicId === record.ragic_id ? '#e6f4ff' : undefined,
    },
  });

  return (
    <Table<TraceNodeData>
      columns={columns}
      dataSource={nodes}
      rowKey="ragic_id"
      loading={loading}
      size="small"
      locale={{
        emptyText: <Empty description="尚無追蹤結果" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
      }}
      pagination={{
        defaultPageSize: 25,
        pageSizeOptions: PAGE_SIZE_OPTIONS,
        showSizeChanger: true,
        showTotal: (total, range) => `${range[0]}-${range[1]} / 共 ${total} 筆`,
      }}
      expandable={{
        expandedRowRender,
        rowExpandable: () => true,
      }}
      onRow={handleRow}
      scroll={{ x: 1100 }}
      style={{ width: '100%' }}
    />
  );
}
