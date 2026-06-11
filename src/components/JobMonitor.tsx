/**
 * @file        JobMonitor - 任務監控元件
 * @description 顯示知識庫處理任務狀態（處理中/失敗/完成），支援中止、重試、刪除與日誌查看
 * @lastUpdate  2026-03-29 00:07:13
 * @author      Daniel Chung
 * @version     1.1.0
 */
import { useState, useEffect } from 'react';
import { App, Badge, Button, Drawer, Dropdown, Segmented, Tooltip } from 'antd';
import {
  CloudOutlined, DeleteOutlined, FileTextOutlined, PlayCircleOutlined,
  StopOutlined, WarningOutlined,
} from '@ant-design/icons';
import { jobsApi, JobLog, KbJobFile } from '../services/api';
import { useContentTokens, useShellTokens } from '../contexts/AppThemeProvider';

type JobStatus = 'active' | 'failed' | 'completed' | 'stuck';

interface JobMonitorProps {
  isDark: boolean;
  primaryColor: string;
  textColor: string;
}

export default function JobMonitor({ textColor }: JobMonitorProps) {
  const { modal, message } = App.useApp();
  const [jobs, setJobs] = useState<KbJobFile[]>([]);
  const [tab, setTab] = useState<JobStatus>('active');
  const [clearing, setClearing] = useState(false);
  const [abortingKey, setAbortingKey] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [retryingKey, setRetryingKey] = useState<string | null>(null);
  const [logDrawerOpen, setLogDrawerOpen] = useState(false);
  const [logJob, setLogJob] = useState<KbJobFile | null>(null);
  const [logs, setLogs] = useState<JobLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [stuckCount, setStuckCount] = useState(0);
  const tokens = useContentTokens();
  const shellTokens = useShellTokens();

  const fetchJobs = async () => {
    try {
      if (tab === 'stuck') {
        const response = await jobsApi.listStuck();
        setJobs(response.data.data || []);
      } else {
        const response = await jobsApi.list(tab);
        setJobs(response.data.data || []);
      }
    } catch (error: unknown) {
      console.error('Failed to fetch jobs:', error);
    }
  };

  useEffect(() => { void fetchJobs(); }, [tab]);

  useEffect(() => {
    const timer = setInterval(() => void fetchJobs(), 5000);
    return () => clearInterval(timer);
  }, [tab]);

  const handleClear = () => {
    if (jobs.length === 0) return;
    const label = tab === 'failed' ? '失敗' : '已完成';
    modal.confirm({
      title: `清除${label}任務`,
      content: `確定要清除 ${jobs.length} 筆${label}任務嗎？此操作無法復原。`,
      okText: '確定清除',
      cancelText: '取消',
      okButtonProps: { danger: true, loading: clearing },
      onOk: async () => {
        setClearing(true);
        try {
          const response = await jobsApi.clear(tab === 'active' || tab === 'stuck' ? 'failed' : tab);
          message.success(response.data.message || '已清除');
          void fetchJobs();
        } catch (error: unknown) {
          const err = error as { response?: { data?: { message?: string } } };
          message.error(err.response?.data?.message || '清除失敗');
        } finally {
          setClearing(false);
        }
      },
    });
  };

  const handleAbort = (job: KbJobFile) => {
    modal.confirm({
      title: '中止任務',
      content: `確定要中止「${job.filename}」嗎？`,
      okText: '確定中止',
      cancelText: '取消',
      okButtonProps: { danger: true, loading: abortingKey === job._key },
      onOk: async () => {
        if (!job._key) return;
        setAbortingKey(job._key);
        try {
          await jobsApi.abort(job._key);
          message.success('任務已中止');
          fetchJobs();
        } catch (error: unknown) {
          const err = error as { response?: { data?: { message?: string } } };
          message.error(err.response?.data?.message || '中止失敗');
        } finally {
          setAbortingKey(null);
        }
      },
    });
  };

  const handleDeleteJob = (job: KbJobFile) => {
    modal.confirm({
      title: '刪除任務',
      content: `確定要刪除「${job.filename}」及其所有相關資料嗎？此操作無法復原。`,
      okText: '確定刪除',
      cancelText: '取消',
      okButtonProps: { danger: true, loading: deletingKey === job._key },
      onOk: async () => {
        if (!job._key) return;
        setDeletingKey(job._key);
        try {
          await jobsApi.deleteJob(job._key);
          message.success('任務已刪除');
          fetchJobs();
        } catch (error: unknown) {
          const err = error as { response?: { data?: { message?: string } } };
          message.error(err.response?.data?.message || '刪除失敗');
        } finally {
          setDeletingKey(null);
        }
      },
    });
  };

  const handleRetry = async (job: KbJobFile) => {
    if (!job._key) return;
    setRetryingKey(job._key);
    try {
      await jobsApi.retry(job._key);
      message.success('任務已重新排入佇列');
      fetchJobs();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } } };
      message.error(err.response?.data?.message || '重試失敗');
    } finally {
      setRetryingKey(null);
    }
  };

  const handleViewLogs = async (job: KbJobFile) => {
    if (!job._key) return;
    setLogJob(job);
    setLogDrawerOpen(true);
    setLogs([]);
    setLoadingLogs(true);
    try {
      const response = await jobsApi.logs(job._key);
      setLogs(response.data.data?.logs || []);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } } };
      message.error(err.response?.data?.message || '取得日誌失敗');
    } finally {
      setLoadingLogs(false);
    }
  };

  const getOverallStatus = (job: KbJobFile) => {
    if (job.vector_status === 'failed' || job.graph_status === 'failed') return 'failed';
    if (job.vector_status === 'processing' || job.graph_status === 'processing') return 'processing';
    if (job.vector_status === 'completed' && job.graph_status === 'completed') return 'completed';
    return 'pending';
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'pending': return { color: tokens.colorWarning, text: '等待中' };
      case 'processing': return { color: tokens.colorPrimary, text: '處理中' };
      case 'failed': return { color: tokens.colorError, text: '失敗' };
      case 'completed': return { color: tokens.colorSuccess, text: '完成' };
      default: return { color: tokens.colorInfo, text: '未知' };
    }
  };

  const getFileIcon = (type: string | undefined) => {
    if (!type) return '📎';
    const t = type.toLowerCase();
    if (t === 'md') return '📝';
    if (t === 'pdf') return '📕';
    if (t === 'docx' || t === 'doc') return '📘';
    if (t === 'xlsx' || t === 'xls') return '📊';
    if (t === 'pptx' || t === 'ppt') return '📙';
    if (t === 'csv') return '📑';
    if (t === 'txt') return '📄';
    return '📎';
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  const activeJobs = jobs.filter((j) => {
    const s = getOverallStatus(j);
    return s === 'pending' || s === 'processing';
  });
  const badgeCount = activeJobs.length + stuckCount;

  useEffect(() => {
    void (async () => {
      try {
        const resp = await jobsApi.listStuck();
        setStuckCount(resp.data.data?.length ?? 0);
      } catch { /* empty */ }
    })();
    const t = setInterval(async () => {
      try {
        const resp = await jobsApi.listStuck();
        setStuckCount(resp.data.data?.length ?? 0);
      } catch { /* empty */ }
    }, 30_000);
    return () => clearInterval(t);
  }, []);

  const tabLabels: Record<JobStatus, string> = {
    active: '處理中',
    failed: '失敗',
    completed: '已完成',
    stuck: '卡住',
  };

  const tabBadges: Record<JobStatus, number> = {
    active: badgeCount,
    failed: tab === 'failed' ? jobs.filter((j) => getOverallStatus(j) === 'failed').length : 0,
    completed: tab === 'completed' ? jobs.filter((j) => getOverallStatus(j) === 'completed').length : 0,
    stuck: tab === 'stuck' ? jobs.length : 0,
  };

  const showClear = tab !== 'active' && tab !== 'stuck';

  return (
    <>
    <Dropdown
      placement="bottomRight"
      trigger={['click']}
      popupRender={() => (
        <div
          style={{
            width: 340,
            background: tokens.colorBgBase,
            borderRadius: tokens.borderRadius,
            boxShadow: tokens.boxShadow,
            border: `1px solid ${shellTokens.siderBorder}`,
            padding: 0,
          }}
        >
          <div
            style={{
              padding: '10px 12px 10px 16px',
              borderBottom: `1px solid ${shellTokens.siderBorder}`,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Segmented
              value={tab}
              onChange={(v) => setTab(v as JobStatus)}
              options={[
                { label: `${tabLabels.active}${tabBadges.active > 0 ? ` (${tabBadges.active})` : ''}`, value: 'active' },
                { label: `${tabLabels.failed}${tabBadges.failed > 0 ? ` (${tabBadges.failed})` : ''}`, value: 'failed' },
                { label: `${tabLabels.stuck}${tabBadges.stuck > 0 ? ` (${tabBadges.stuck})` : ''}`, value: 'stuck' },
                { label: tabLabels.completed, value: 'completed' },
              ]}
              style={{ flex: 1 }}
            />
            {showClear && jobs.length > 0 && (
              <Button
                type="text"
                size="small"
                icon={<DeleteOutlined />}
                loading={clearing}
                onClick={handleClear}
                style={{ color: tokens.colorError, flexShrink: 0 }}
                title="清除"
              />
            )}
          </div>

          {jobs.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', color: tokens.textSecondary, fontSize: 13 }}>
              {tab === 'active' ? '目前沒有處理中的任務' : tab === 'failed' ? '沒有失敗的任務' : '沒有已完成任務'}
            </div>
          ) : (
            <div style={{ maxHeight: 320, overflowY: 'auto' }}>
              {jobs.map((job, index) => {
                const overall = getOverallStatus(job);
                const vecLabel = getStatusLabel(job.vector_status);
                const graLabel = getStatusLabel(job.graph_status);
                const isLast = index === jobs.length - 1;
                return (
                  <div
                    key={job._key}
                    style={{
                      padding: '8px 16px',
                      display: 'flex',
                      gap: 12,
                      borderBottom: isLast ? 'none' : `1px solid ${shellTokens.siderBorder}`,
                    }}
                  >
                    <span style={{ fontSize: 20 }}>{getFileIcon(job.file_type)}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Tooltip title={job.filename} placement="topLeft">
                          <div
                            style={{
                              color: tokens.colorTextBase,
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              fontSize: 13,
                              fontWeight: 500,
                              flex: 1,
                            }}
                          >
                            {job.filename}
                          </div>
                        </Tooltip>
                        {overall === 'processing' && (
                          <Tooltip title="中止並重置為等待中">
                            <Button
                              type="text"
                              size="small"
                              icon={<StopOutlined />}
                              loading={abortingKey === job._key}
                              onClick={() => handleAbort(job)}
                              style={{
                                color: tokens.colorError,
                                padding: '0 2px',
                                height: 20,
                                minWidth: 0,
                              }}
                            />
                          </Tooltip>
                        )}
                        {overall === 'pending' && (
                          <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                            <Tooltip title="強制執行">
                              <Button
                                type="text"
                                size="small"
                                icon={<PlayCircleOutlined />}
                                loading={retryingKey === job._key}
                                onClick={() => handleRetry(job)}
                                style={{ color: tokens.colorSuccess, padding: '0 2px', height: 20, minWidth: 0 }}
                              />
                            </Tooltip>
                            <Tooltip title="中止任務">
                              <Button
                                type="text"
                                size="small"
                                icon={<StopOutlined />}
                                loading={abortingKey === job._key}
                                onClick={() => handleAbort(job)}
                                style={{ color: tokens.colorError, padding: '0 2px', height: 20, minWidth: 0 }}
                              />
                            </Tooltip>
                            <Tooltip title="刪除任務">
                              <Button
                                type="text"
                                size="small"
                                icon={<DeleteOutlined />}
                                loading={deletingKey === job._key}
                                onClick={() => handleDeleteJob(job)}
                                style={{ color: tokens.colorError, padding: '0 2px', height: 20, minWidth: 0 }}
                              />
                            </Tooltip>
                          </div>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: 8, marginTop: 4, fontSize: 12, color: tokens.textSecondary }}>
                        <span style={{ color: vecLabel.color }}>向量化: {vecLabel.text}</span>
                        <span style={{ color: graLabel.color }}>圖譜: {graLabel.text}</span>
                      </div>
                      <div style={{ fontSize: 11, color: tokens.textSecondary, marginTop: 2 }}>
                        {job.knowledge_root_id} | {formatSize(job.file_size)}
                      </div>
                      {overall === 'failed' && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3 }}>
                          {job.failed_reason && (
                            <div
                              style={{
                                fontSize: 11,
                                color: tokens.colorError,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                flex: 1,
                                maxWidth: 220,
                              }}
                              title={job.failed_reason}
                            >
                              <WarningOutlined style={{ marginRight: 3 }} />
                              {job.failed_reason}
                            </div>
                          )}
                          <Tooltip title="查看日誌">
                            <Button
                              type="text"
                              size="small"
                              icon={<FileTextOutlined />}
                              onClick={() => handleViewLogs(job)}
                              style={{ color: tokens.colorInfo, padding: '0 2px', height: 18, minWidth: 0, fontSize: 11 }}
                            />
                          </Tooltip>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    >
      <Badge count={badgeCount} size="small" style={{ pointerEvents: 'none' }}>
        <Button type="text" icon={<CloudOutlined />} style={{ color: textColor }} />
      </Badge>
    </Dropdown>
    <Drawer
      title={`任務日誌 — ${logJob?.filename ?? ''}`}
      placement="right"
      size="large"
      open={logDrawerOpen}
      onClose={() => setLogDrawerOpen(false)}
      styles={{ body: { padding: 0 } }}
    >
      {loadingLogs ? (
        <div style={{ padding: 20, textAlign: 'center', color: tokens.textSecondary }}>
          載入中...
        </div>
      ) : logs.length === 0 ? (
        <div style={{ padding: 20, textAlign: 'center', color: tokens.textSecondary }}>
          尚無日誌記錄
        </div>
      ) : (
        <div style={{ fontFamily: 'monospace', fontSize: 12 }}>
          {logs.map((log, i) => {
            const isError = log.event === 'error';
            const isEnd = log.event === 'end';
            return (
              <div
                key={i}
                style={{
                  padding: '8px 16px',
                  borderBottom: '1px solid rgba(0,0,0,0.06)',
                  background: isError
                    ? 'rgba(255,0,0,0.04)'
                    : isEnd
                    ? 'rgba(0,200,83,0.04)'
                    : 'transparent',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      padding: '1px 5px',
                      borderRadius: 3,
                      background: log.task_type === 'vectorize'
                        ? '#e6f4ff'
                        : '#fff7e6',
                      color: log.task_type === 'vectorize'
                        ? tokens.colorPrimary
                        : tokens.colorWarning,
                    }}
                  >
                    {log.task_type}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      padding: '1px 5px',
                      borderRadius: 3,
                      background: isError
                        ? 'rgba(255,0,0,0.1)'
                        : isEnd
                        ? 'rgba(0,200,83,0.1)'
                        : 'rgba(0,0,0,0.04)',
                      color: isError
                        ? tokens.colorError
                        : isEnd
                        ? tokens.colorSuccess
                        : '#999',
                    }}
                  >
                    {log.event}
                  </span>
                  <span style={{ color: tokens.textSecondary, fontSize: 10, marginLeft: 'auto' }}>
                    {new Date(log.timestamp).toLocaleTimeString('zh-TW')}
                  </span>
                </div>
                <div style={{ color: tokens.colorTextBase, lineHeight: 1.5 }}>{log.message}</div>
                {isError && log.detail && (
                  <pre
                    style={{
                      marginTop: 6,
                      padding: '6px 8px',
                      background: 'rgba(255,0,0,0.06)',
                      borderRadius: 4,
                      color: tokens.colorError,
                      fontSize: 11,
                      overflowX: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {log.detail}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Drawer>
    </>
  );
}
