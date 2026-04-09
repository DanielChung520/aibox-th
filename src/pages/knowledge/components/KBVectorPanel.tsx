/**
 * @file        知識庫向量面板元件
 * @description 顯示文件的向量分塊結果，含「找相似」功能
 * @lastUpdate  2026-03-26 16:50:00
 * @author      Daniel Chung
 * @version     1.4.0
 */

import { useEffect, useState } from 'react';
import { Empty, Spin, Alert, Table, Button, message, Typography, theme, Modal, Progress } from 'antd';
import { ReloadOutlined, SyncOutlined } from '@ant-design/icons';
import { knowledgeApi, VectorChunk, SimilarChunk } from '../../../services/api';

const { Text, Paragraph } = Typography;

interface KBVectorPanelProps {
  fileId: string;
  vectorStatus?: string;
}

export default function KBVectorPanel({ fileId, vectorStatus }: KBVectorPanelProps) {
  const { token } = theme.useToken();
  const [chunks, setChunks] = useState<VectorChunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [similarOpen, setSimilarOpen] = useState(false);
  const [similarChunks, setSimilarChunks] = useState<SimilarChunk[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [similarError, setSimilarError] = useState<string | null>(null);
  const [selectedChunk, setSelectedChunk] = useState<VectorChunk | null>(null);

  const fetchChunks = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await knowledgeApi.getVectors(fileId, { limit: 50, offset: 0 });
      setChunks(res.data.data?.chunks || []);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } } };
      setError(e.response?.data?.message || '載入向量失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchChunks();
  }, [fileId]);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      await knowledgeApi.regenerateVector(fileId);
      message.success('已重新提交向量生成任務');
      fetchChunks();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } } };
      message.error(e.response?.data?.message || '重新向量失敗');
    } finally {
      setRegenerating(false);
    }
  };

  const handleFindSimilar = async (chunk: VectorChunk) => {
    setSelectedChunk(chunk);
    setSimilarOpen(true);
    setSimilarLoading(true);
    setSimilarError(null);
    setSimilarChunks([]);
    try {
      const res = await knowledgeApi.getSimilarChunks(fileId, chunk.chunk_id, 10);
      setSimilarChunks(res.data.data?.similar || []);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } } };
      setSimilarError(e.response?.data?.message || '查詢相似失敗');
    } finally {
      setSimilarLoading(false);
    }
  };

  const columns = [
    {
      title: '#',
      dataIndex: 'chunk_index',
      key: 'chunk_index',
      width: 52,
      render: (v: number) => <Text type="secondary">{v + 1}</Text>,
    },
    {
      title: '文字內容',
      dataIndex: 'text',
      key: 'text',
      ellipsis: { rows: 2, showTitle: false },
      render: (text: string) => (
        <span style={{ WebkitLineClamp: 2, display: '-webkit-box', WebkitBoxOrient: 'vertical' as const, overflow: 'hidden' }}>
          {text}
        </span>
      ),
    },
    {
      title: '',
      key: 'action',
      width: 80,
      render: (_: unknown, record: VectorChunk) => (
        <Button
          type="text"
          size="small"
          icon={<SyncOutlined />}
          onClick={() => handleFindSimilar(record)}
          title="找相似"
        >
          相似
        </Button>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: token.padding, gap: token.margin }}>
      <div style={{ flexShrink: 0, display: 'flex', justifyContent: 'flex-end' }}>
        {(!vectorStatus || !['pending', 'processing', 'queued'].includes(vectorStatus)) ? (
          <Button icon={<ReloadOutlined />} loading={regenerating} onClick={handleRegenerate} size="small">
            重新向量
          </Button>
        ) : (
          <Text type="secondary">向量生成中...</Text>
        )}
      </div>

      {loading && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Spin description="載入向量..." />
        </div>
      )}

      {!loading && error && (
        <Alert type="error" title={error} showIcon />
      )}

      {!loading && !error && chunks.length === 0 && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty
            description={
              <Text style={{ color: token.colorTextSecondary }}>
                向量分塊待生成
              </Text>
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </div>
      )}

      {!loading && !error && chunks.length > 0 && (
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          <Table
            dataSource={chunks}
            rowKey="chunk_id"
            columns={columns}
            size="small"
            pagination={{ pageSize: 50, size: 'small', showSizeChanger: true, pageSizeOptions: ['20', '50', '100'] }}
          />
        </div>
      )}

      <Modal
        title={`找相似 — Chunk #${(selectedChunk?.metadata?.chunk_index as unknown as number ?? 0) + 1}`}
        open={similarOpen}
        onCancel={() => setSimilarOpen(false)}
        footer={null}
        width={640}
        bodyStyle={{ maxHeight: '60vh', overflow: 'auto' }}
      >
        {selectedChunk && (
          <div style={{ marginBottom: 12, padding: 8, background: token.colorFillAlter, borderRadius: token.borderRadius }}>
            <Text type="secondary" style={{ fontSize: 11 }}>原文</Text>
            <Paragraph
              ellipsis={{ rows: 2, expandable: true, symbol: '展開' }}
              style={{ margin: 0, fontSize: 13, whiteSpace: 'pre-wrap' }}
            >
              {selectedChunk.text}
            </Paragraph>
          </div>
        )}

        {similarLoading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
            <Spin description="查詢相似中..." />
          </div>
        )}

        {similarError && (
          <Alert type="error" title={similarError} showIcon />
        )}

        {!similarLoading && !similarError && similarChunks.length === 0 && (
          <Text type="secondary">沒有找到相似的分塊</Text>
        )}

        {!similarLoading && !similarError && similarChunks.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {similarChunks.map((c, i) => (
              <div key={c.chunk_id} style={{
                padding: 10,
                border: `1px solid ${token.colorBorderSecondary}`,
                borderRadius: token.borderRadius,
                background: token.colorBgContainer,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    #{i + 1} · ID: {c.chunk_id}
                  </Text>
                  <Text style={{ fontSize: 11, color: token.colorPrimary, fontWeight: 500 }}>
                    {((c.score ?? 0) * 100).toFixed(1)}%
                  </Text>
                </div>
                <Progress
                  percent={Math.round((c.score ?? 0) * 100)}
                  size="small"
                  strokeColor={token.colorPrimary}
                  showInfo={false}
                  style={{ margin: '4px 0 6px' }}
                />
                <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
                  {c.text.length > 200 ? `${c.text.slice(0, 200)}…` : c.text}
                </Text>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
