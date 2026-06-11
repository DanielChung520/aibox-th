/**
 * @file        知識庫檔案列表元件
 * @description 顯示並管理知識庫內的文件清單
 * @lastUpdate  2026-04-05 22:00:00
 * @author      Daniel Chung
 * @version     1.1.0
 */

import { Input, Button, Popconfirm, Typography, Table, theme, Tag, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { SearchOutlined, UploadOutlined, DeleteOutlined, FilePdfOutlined, FileMarkdownOutlined, FileTextOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { KnowledgeFile } from '../../../services/api';

const { Text } = Typography;

interface KBFileListProps {
  rootId: string;
  files: KnowledgeFile[];
  selectedFileId?: string;
  onSelectFile: (fileId: string) => void;
  onUpload: () => void;
  onDeleteFile: (fileId: string) => void;
  loading?: boolean;
}


export default function KBFileList({ files, selectedFileId, onSelectFile, onUpload, onDeleteFile, loading }: KBFileListProps) {
  const [searchText, setSearchText] = useState('');
  const { token } = theme.useToken();

  const filteredFiles = files.filter(f => f.filename.toLowerCase().includes(searchText.toLowerCase()));

  const columns: ColumnsType<KnowledgeFile> = [
    {
      title: '文件名稱',
      dataIndex: 'filename',
      key: 'filename',
      render: (filename: string, record) => {
        const isPdf = record.file_type?.includes('pdf');
        const isMd = record.file_type?.includes('markdown');
        const isSelected = record._key === selectedFileId;
        const textColor = isSelected ? '#fff' : token.colorText;
        const iconColor = isSelected ? '#fff' : (
          isPdf ? token.colorError : isMd ? token.colorPrimary : token.colorSuccess
        );

        const tooltipContent = (
          <div style={{ maxWidth: 300 }}>
            {record.ontology_major && (
              <div style={{ marginBottom: 6 }}>
                <span style={{ color: '#94a3b8', fontSize: 11 }}>領域: </span>
                <Tag color="blue" style={{ fontSize: 10, marginLeft: 4 }}>{record.ontology_major}</Tag>
              </div>
            )}
            {record.document_type?.length ? (
              <div style={{ marginBottom: 6 }}>
                <span style={{ color: '#94a3b8', fontSize: 11 }}>類型: </span>
                <div style={{ marginTop: 4 }}>
                  {record.document_type.map(t => (
                    <Tag key={t} style={{ fontSize: 10 }}>{t}</Tag>
                  ))}
                </div>
              </div>
            ) : null}
            {record.document_summary ? (
              <div style={{ marginTop: 4 }}>
                <span style={{ color: '#94a3b8', fontSize: 11 }}>摘要: </span>
                <div style={{ fontSize: 11, color: '#e2e8f0', marginTop: 4, lineHeight: 1.5 }}>
                  {record.document_summary}
                </div>
              </div>
            ) : null}
            {!record.ontology_major && !record.document_type?.length && !record.document_summary ? (
              <span style={{ color: '#64748b', fontSize: 11 }}>尚無分析資料</span>
            ) : null}
          </div>
        );

        return (
          <Tooltip title={tooltipContent} placement="right" styles={{ root: { maxWidth: 340 } }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {isPdf ? <FilePdfOutlined style={{ color: iconColor, fontSize: 14 }} /> :
               isMd ? <FileMarkdownOutlined style={{ color: iconColor, fontSize: 14 }} /> :
               <FileTextOutlined style={{ color: iconColor, fontSize: 14 }} />}
              <Text ellipsis style={{ color: textColor, fontWeight: isSelected ? 500 : 400, fontSize: 12, flex: 1 }}>
                {filename}
              </Text>
              {record.document_type?.length ? (
                <span style={{ color: isSelected ? 'rgba(255,255,255,0.5)' : '#94a3b8', fontSize: 10 }}>
                  <InfoCircleOutlined />
                </span>
              ) : null}
            </div>
          </Tooltip>
        );
      },
    },
    {
      title: '',
      key: 'action',
      width: 40,
      render: (_: unknown, record: KnowledgeFile) => {
        const isSelected = record._key === selectedFileId;
        return (
          <Popconfirm
            title="確定要刪除此文件嗎？"
            onConfirm={() => onDeleteFile(record._key)}
          >
            <Button
              type="text"
              danger
              size="small"
              icon={<DeleteOutlined />}
              style={isSelected ? { color: '#fff' } : undefined}
            />
          </Popconfirm>
        );
      },
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ padding: token.padding, borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
        <Button type="primary" icon={<UploadOutlined />} block onClick={onUpload} style={{ marginBottom: token.margin }}>
          上傳文件
        </Button>
        <Input
          placeholder="搜尋文件..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
        />
      </div>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Table
          dataSource={filteredFiles}
          columns={columns}
          rowKey="_key"
          size="small"
          loading={loading}
          pagination={false}
          scroll={{ y: 'calc(100vh - 220px)' }}
          onRow={(record) => ({
            onClick: () => onSelectFile(record._key),
            style: {
              cursor: 'pointer',
              backgroundColor: record._key === selectedFileId
                ? token.controlItemBgActive
                : 'transparent',
            },
          })}
          locale={{ emptyText: '尚無文件' }}
        />
      </div>
    </div>
  );
}
