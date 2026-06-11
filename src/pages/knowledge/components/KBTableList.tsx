/**
 * @file        知識庫表格列表視圖
 * @description Table 列表式佈局，展示知識庫結構化資訊與多欄位排序
 * @lastUpdate  2026-03-25 13:00:17
 * @author      Daniel Chung
 * @version     1.1.0
 * @history
 * - 2026-03-25 13:00:17 | Daniel Chung | 1.1.0 | 新增 onAuthorize 授權、tags 標籤欄位；移除向量/圖譜狀態欄位
 */

import { Table, Button, Space, Tag, Popconfirm, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  HeartFilled,
  HeartOutlined,
  FileSearchOutlined,
  EditOutlined,
  CopyOutlined,
  DeleteOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import { KnowledgeRoot } from '../../../services/api';
import { useContentTokens } from '../../../contexts/AppThemeProvider';

export interface KBTableListProps {
  data: KnowledgeRoot[];
  loading: boolean;
  onEdit: (id: string) => void;
  onEditMeta: (id: string) => void;
  onCopy: (id: string) => void;
  onDelete: (id: string) => void;
  onFavoriteToggle: (id: string) => void;
  onAuthorize: (id: string) => void;
}

export default function KBTableList({
  data,
  loading,
  onEdit,
  onEditMeta,
  onCopy,
  onDelete,
  onFavoriteToggle,
  onAuthorize,
}: KBTableListProps) {
  const contentTokens = useContentTokens();

  const columns: ColumnsType<KnowledgeRoot> = [
    {
      title: '',
      dataIndex: 'is_favorite',
      key: 'is_favorite',
      width: 50,
      render: (is_favorite: boolean, record: KnowledgeRoot) => (
        <span
          onClick={(e) => {
            e.stopPropagation();
            onFavoriteToggle(record._key);
          }}
          style={{ cursor: 'pointer' }}
        >
          {is_favorite ? (
            <HeartFilled style={{ color: contentTokens.colorError, fontSize: 16 }} />
          ) : (
            <HeartOutlined style={{ color: contentTokens.textSecondary, fontSize: 16 }} />
          )}
        </span>
      ),
    },
    {
      title: '知識庫名稱',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <strong style={{ color: contentTokens.colorPrimary }}>{text}</strong>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '領域',
      dataIndex: 'ontology_domain',
      key: 'ontology_domain',
      width: 120,
      render: (text: string) => <Tag color={contentTokens.colorPrimary}>{text}</Tag>,
    },
    {
      title: '標籤',
      dataIndex: 'tags',
      key: 'tags',
      width: 200,
      render: (tags: string[]) => (
        <Space size={[4, 4]} wrap>
          {tags?.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '來源數量',
      dataIndex: 'source_count',
      key: 'source_count',
      width: 100,
    },
    {
      title: '操作',
      key: 'action',
      width: 210,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="詳情">
            <Button type="text" icon={<FileSearchOutlined />} onClick={() => onEdit(record._key)} />
          </Tooltip>
          <Tooltip title="編輯">
            <Button type="text" icon={<EditOutlined />} onClick={() => onEditMeta(record._key)} />
          </Tooltip>
          <Tooltip title="複製">
            <Button type="text" icon={<CopyOutlined />} onClick={() => onCopy(record._key)} />
          </Tooltip>
          <Tooltip title="授權">
            <Button type="text" icon={<SafetyOutlined />} onClick={() => onAuthorize(record._key)} />
          </Tooltip>
          <Popconfirm
            title="確定要刪除此知識庫嗎？"
            description="刪除後將無法恢復"
            onConfirm={() => onDelete(record._key)}
            okText="確定"
            cancelText="取消"
          >
            <Tooltip title="刪除">
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={data}
      rowKey="_key"
      loading={loading}
      pagination={{ pageSize: 10 }}
      onRow={(record) => ({
        onDoubleClick: () => onEdit(record._key),
        style: { cursor: 'pointer' },
      })}
      style={{ boxShadow: contentTokens.tableShadow, borderRadius: contentTokens.borderRadius }}
    />
  );
}
