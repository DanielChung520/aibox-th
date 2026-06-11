/**
 * @file        知識庫卡片網格視圖
 * @description Grid 卡片式佈局，展示知識庫核心狀態與操作按鈕
 * @lastUpdate  2026-03-25 13:00:17
 * @author      Daniel Chung
 * @version     1.1.0
 * @history
 * - 2026-03-25 13:00:17 | Daniel Chung | 1.1.0 | 新增 onAuthorize 授權、tags 標籤顯示；移除向量/圖譜狀態
 */

import { Card, Row, Col, Typography, Button, Tag, Space, Empty, Spin, Tooltip, Popconfirm } from 'antd';
import {
  FolderOpenOutlined,
  ProjectOutlined,
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

const { Title, Paragraph, Text } = Typography;

export interface KBCardGridProps {
  data: KnowledgeRoot[];
  loading: boolean;
  onRefresh?: () => void;
  onEdit: (id: string) => void;
  onEditMeta: (id: string) => void;
  onCopy: (id: string) => void;
  onDelete: (id: string) => void;
  onFavoriteToggle: (id: string) => void;
  onAuthorize: (id: string) => void;
}

export default function KBCardGrid({
  data,
  loading,
  onEdit,
  onEditMeta,
  onCopy,
  onDelete,
  onFavoriteToggle,
  onAuthorize,
}: KBCardGridProps) {
  const contentTokens = useContentTokens();

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return <Empty description="暫無知識庫" />;
  }

  return (
    <Row gutter={[16, 16]}>
      {data.map((item) => (
        <Col xs={24} sm={12} md={8} lg={6} xl={6} key={item._key}>
          <Card
            hoverable
            onDoubleClick={() => onEdit(item._key)}
            style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: contentTokens.cardShadow,
              borderRadius: contentTokens.borderRadius,
              border: `1px solid ${contentTokens.colorBgBase}`,
            }}
            styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column', padding: '16px' } }}
            actions={[
              <Tooltip title="詳情" key="detail">
                <Button type="text" icon={<FileSearchOutlined />} onClick={() => onEdit(item._key)} />
              </Tooltip>,
              <Tooltip title="編輯" key="edit">
                <Button type="text" icon={<EditOutlined />} onClick={() => onEditMeta(item._key)} />
              </Tooltip>,
              <Tooltip title="複製" key="copy">
                <Button type="text" icon={<CopyOutlined />} onClick={() => onCopy(item._key)} />
              </Tooltip>,
              <Tooltip title="授權" key="auth">
                <Button type="text" icon={<SafetyOutlined />} onClick={() => onAuthorize(item._key)} />
              </Tooltip>,
              <Popconfirm title="確定要刪除此知識庫嗎？" description="刪除後將無法恢復" onConfirm={() => onDelete(item._key)} okText="確定" cancelText="取消" key="delete">
                <Tooltip title="刪除">
                  <Button type="text" danger icon={<DeleteOutlined />} />
                </Tooltip>
              </Popconfirm>,
            ]}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <Space align="center">
                <FolderOpenOutlined style={{ fontSize: 20, color: contentTokens.colorPrimary }} />
                <Title level={5} style={{ margin: 0 }} ellipsis={{ tooltip: item.name }}>
                  {item.name}
                </Title>
              </Space>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  onFavoriteToggle(item._key);
                }}
                style={{ cursor: 'pointer' }}
              >
                {item.is_favorite ? (
                  <HeartFilled style={{ color: contentTokens.colorError, fontSize: 18 }} />
                ) : (
                  <HeartOutlined style={{ color: contentTokens.textSecondary, fontSize: 18 }} />
                )}
              </span>
            </div>

            <Paragraph
              type="secondary"
              ellipsis={{ rows: 2, tooltip: item.description }}
              style={{ minHeight: 44, marginBottom: 16 }}
            >
              {item.description || '無描述'}
            </Paragraph>

            <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
                <Tag color={contentTokens.colorPrimary}>{item.ontology_domain}</Tag>
                {item.tags?.map((tag) => (
                  <Tag key={tag}>{tag}</Tag>
                ))}
              </div>

              <Space orientation="vertical" size="small" style={{ width: '100%', fontSize: 13 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text type="secondary"><ProjectOutlined /> 來源數量</Text>
                  <Text strong>{item.source_count}</Text>
                </div>
              </Space>
            </div>
          </Card>
        </Col>
      ))}
    </Row>
  );
}
