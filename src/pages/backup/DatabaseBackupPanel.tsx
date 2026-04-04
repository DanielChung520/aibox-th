import { useState, useEffect, useCallback } from 'react';
import {
  App, Button, Card, Col, Descriptions, Empty, InputNumber,
  Modal, Progress, Row, Space, Statistic, Table, Tag, Tooltip, Typography,
} from 'antd';
import {
  CloudServerOutlined, DatabaseOutlined, DeleteOutlined, DownloadOutlined,
  ReloadOutlined, RestOutlined, WarningOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  backupApi, BackupRecord, DiskUsage,
} from '../../services/api';

const { Text } = Typography;

interface ArangoBackupRecord extends BackupRecord {
  collections_count: number;
}

interface QdrantBackupRecord extends BackupRecord {
  collections: string[];
  snapshots: Array<{
    collection: string;
    snapshot_id: string;
    snapshot_name: string;
    size_bytes: number;
    size_mb: number;
  }>;
}

export default function DatabaseBackupPanel() {
  const { message: antMessage } = App.useApp();

  const [loading, setLoading] = useState(false);
  const [arangoBacking, setArangoBacking] = useState(false);
  const [qdrantBacking, setQdrantBacking] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const [arangoHistory, setArangoHistory] = useState<ArangoBackupRecord[]>([]);
  const [qdrantHistory, setQdrantHistory] = useState<QdrantBackupRecord[]>([]);
  const [arangoDisk, setArangoDisk] = useState<DiskUsage | null>(null);
  const [qdrantDisk, setQdrantDisk] = useState<DiskUsage | null>(null);

  const [restoreModal, setRestoreModal] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState<{ type: 'arangodb' | 'qdrant'; record: BackupRecord } | null>(null);
  const [retention, setRetention] = useState(7);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ah, qh, ad, qd] = await Promise.all([
        backupApi.arangoHistory().catch(() => ({ data: { data: [] } })),
        backupApi.qdrantHistory().catch(() => ({ data: { data: [] } })),
        backupApi.arangoDiskUsage().catch(() => ({ data: { data: null } })),
        backupApi.qdrantDiskUsage().catch(() => ({ data: { data: null } })),
      ]);
        setArangoHistory((ah.data.data || []) as ArangoBackupRecord[]);
        setQdrantHistory((qh.data.data || []) as QdrantBackupRecord[]);
      setArangoDisk(ad.data.data || null);
      setQdrantDisk(qd.data.data || null);
    } catch (err) {
      console.error('Failed to fetch backup data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchAll(); }, [fetchAll]);

  const handleBackupArango = async () => {
    setArangoBacking(true);
    try {
      await backupApi.backupArango({ retention });
      antMessage.success('ArangoDB 備份已啟動');
      setTimeout(() => void fetchAll(), 2000);
    } catch (err: any) {
      antMessage.error(err.response?.data?.detail || '備份失敗');
    } finally {
      setArangoBacking(false);
    }
  };

  const handleBackupQdrant = async () => {
    setQdrantBacking(true);
    try {
      await backupApi.backupQdrant({ retention });
      antMessage.success('Qdrant 備份已啟動');
      setTimeout(() => void fetchAll(), 2000);
    } catch (err: any) {
      antMessage.error(err.response?.data?.detail || '備份失敗');
    } finally {
      setQdrantBacking(false);
    }
  };

  const openRestoreModal = (type: 'arangodb' | 'qdrant', record: BackupRecord) => {
    setRestoreTarget({ type, record });
    setRestoreModal(true);
  };

  const handleRestore = async () => {
    if (!restoreTarget) return;
    setRestoring(restoreTarget.record.backup_id);
    try {
      if (restoreTarget.type === 'arangodb') {
        await backupApi.restoreArango(restoreTarget.record.backup_id);
      } else {
        await backupApi.restoreQdrant(restoreTarget.record.backup_id);
      }
      antMessage.success('還原請求已發送，請確認操作');
    } catch (err: any) {
      antMessage.error(err.response?.data?.detail || '還原失敗');
    } finally {
      setRestoring(null);
      setRestoreModal(false);
      setRestoreTarget(null);
    }
  };

  const handleDeleteArango = async (backup_id: string) => {
    setDeleting(backup_id);
    try {
      await backupApi.deleteArangoBackup(backup_id);
      antMessage.success('備份已刪除');
      void fetchAll();
    } catch (err: any) {
      antMessage.error(err.response?.data?.detail || '刪除失敗');
    } finally {
      setDeleting(null);
    }
  };

  const handleDeleteQdrant = async (backup_id: string) => {
    setDeleting(backup_id);
    try {
      await backupApi.deleteQdrantBackup(backup_id);
      antMessage.success('備份已刪除');
      void fetchAll();
    } catch (err: any) {
      antMessage.error(err.response?.data?.detail || '刪除失敗');
    } finally {
      setDeleting(null);
    }
  };

  const arangoColumns: ColumnsType<ArangoBackupRecord> = [
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: string) => (
        <Tag color={s === 'completed' ? 'green' : s === 'failed' ? 'red' : 'blue'}>{s}</Tag>
      ),
    },
    {
      title: '備份 ID',
      dataIndex: 'backup_id',
      key: 'backup_id',
      width: 200,
      render: (v: string) => <Text code style={{ fontSize: 11 }}>{v}</Text>,
    },
    {
      title: '大小',
      dataIndex: 'size_mb',
      key: 'size_mb',
      width: 90,
      render: (v: number) => v > 0 ? `${v} MB` : '-',
      align: 'right',
    },
    {
      title: '耗時',
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      width: 80,
      render: (v: number) => `${v}s`,
      align: 'right',
    },
    {
      title: '建立時間',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString('zh-TW'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_: unknown, record: ArangoBackupRecord) => (
        <Space size="small">
          <Tooltip title="還原">
            <Button
              size="small"
              icon={<RestOutlined />}
              disabled={record.status !== 'completed'}
              loading={restoring === record.backup_id}
              onClick={() => openRestoreModal('arangodb', record)}
            />
          </Tooltip>
          <Tooltip title="刪除">
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={deleting === record.backup_id}
              onClick={() => handleDeleteArango(record.backup_id)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const qdrantColumns: ColumnsType<QdrantBackupRecord> = [
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: string) => (
        <Tag color={s === 'completed' ? 'green' : s === 'failed' ? 'red' : 'blue'}>{s}</Tag>
      ),
    },
    {
      title: '備份 ID',
      dataIndex: 'backup_id',
      key: 'backup_id',
      width: 200,
      render: (v: string) => <Text code style={{ fontSize: 11 }}>{v}</Text>,
    },
    {
      title: '集合',
      dataIndex: 'collections',
      key: 'collections',
      width: 180,
      render: (v: string[]) => v?.map(c => <Tag key={c}>{c}</Tag>) || '-',
    },
    {
      title: '大小',
      dataIndex: 'size_mb',
      key: 'size_mb',
      width: 90,
      render: (v: number) => v > 0 ? `${v} MB` : '-',
      align: 'right',
    },
    {
      title: '建立時間',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString('zh-TW'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_: unknown, record: QdrantBackupRecord) => (
        <Space size="small">
          <Tooltip title="還原">
            <Button
              size="small"
              icon={<RestOutlined />}
              disabled={record.status !== 'completed'}
              loading={restoring === record.backup_id}
              onClick={() => openRestoreModal('qdrant', record)}
            />
          </Tooltip>
          <Tooltip title="刪除">
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={deleting === record.backup_id}
              onClick={() => handleDeleteQdrant(record.backup_id)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <InputNumber min={1} max={30} value={retention} onChange={v => setRetention(v ?? 7)} addonAfter="天" />
        <Text type="secondary" style={{ fontSize: 12 }}>保留天數</Text>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void fetchAll()}>刷新</Button>
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            title={<><DatabaseOutlined /> ArangoDB 備份</>}
            extra={
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                loading={arangoBacking}
                onClick={() => void handleBackupArango()}
              >
                立即備份
              </Button>
            }
          >
            {arangoDisk && (
              <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
                <Descriptions.Item label="總容量">
                  <Statistic value={arangoDisk.total_gb} suffix="GB" valueStyle={{ fontSize: 16 }} />
                </Descriptions.Item>
                <Descriptions.Item label="使用率">
                  <Progress
                    percent={arangoDisk.usage_percent}
                    size="small"
                    format={p => `${p}%`}
                  />
                </Descriptions.Item>
                <Descriptions.Item label="已用">
                  <Text>{arangoDisk.used_gb} GB</Text>
                </Descriptions.Item>
                <Descriptions.Item label="可用">
                  <Text type="success">{arangoDisk.free_gb} GB</Text>
                </Descriptions.Item>
              </Descriptions>
            )}
            <Table
              columns={arangoColumns}
              dataSource={arangoHistory}
              rowKey="backup_id"
              size="small"
              loading={loading}
              pagination={{ pageSize: 5, size: 'small' }}
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚無 ArangoDB 備份記錄" /> }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            title={<><CloudServerOutlined /> Qdrant 備份</>}
            extra={
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                loading={qdrantBacking}
                onClick={() => void handleBackupQdrant()}
              >
                立即備份
              </Button>
            }
          >
            {qdrantDisk && (
              <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
                <Descriptions.Item label="總容量">
                  <Statistic value={qdrantDisk.total_gb} suffix="GB" valueStyle={{ fontSize: 16 }} />
                </Descriptions.Item>
                <Descriptions.Item label="使用率">
                  <Progress
                    percent={qdrantDisk.usage_percent}
                    size="small"
                    format={p => `${p}%`}
                  />
                </Descriptions.Item>
                <Descriptions.Item label="已用">
                  <Text>{qdrantDisk.used_gb} GB</Text>
                </Descriptions.Item>
                <Descriptions.Item label="可用">
                  <Text type="success">{qdrantDisk.free_gb} GB</Text>
                </Descriptions.Item>
              </Descriptions>
            )}
            <Table
              columns={qdrantColumns}
              dataSource={qdrantHistory}
              rowKey="backup_id"
              size="small"
              loading={loading}
              pagination={{ pageSize: 5, size: 'small' }}
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚無 Qdrant 備份記錄" /> }}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        title={<><WarningOutlined /> 確認還原</>}
        open={restoreModal}
        okText="確認還原"
        okButtonProps={{ danger: true, loading: !!restoring }}
        cancelText="取消"
        onCancel={() => { setRestoreModal(false); setRestoreTarget(null); }}
        onOk={() => void handleRestore()}
      >
        <div>
          <Text>確定要從以下備份還原嗎？</Text>
          <Descriptions column={1} size="small" style={{ marginTop: 12 }}>
            <Descriptions.Item label="資料庫">
              {restoreTarget?.type === 'arangodb' ? 'ArangoDB' : 'Qdrant'}
            </Descriptions.Item>
            <Descriptions.Item label="備份 ID">
              <Text code>{restoreTarget?.record.backup_id}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="建立時間">
              {restoreTarget?.record.created_at
                ? new Date(restoreTarget.record.created_at).toLocaleString('zh-TW')
                : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="大小">
              {restoreTarget?.record.size_mb ?? 0} MB
            </Descriptions.Item>
          </Descriptions>
          <div style={{ marginTop: 12, padding: '8px 12px', background: '#fffbe6', borderRadius: 6, border: '1px solid #ffe58f' }}>
            <Text type="warning">⚠️ 還原操作會覆蓋現有資料，建議在離峰時間執行。</Text>
          </div>
        </div>
      </Modal>
    </div>
  );
}
