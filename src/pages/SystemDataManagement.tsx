/**
 * @file        SystemDataManagement.tsx
 * @description 系統資料管理 — SeaweedFS Bucket 檔案瀏覽/上傳/刪除
 * @lastUpdate  2026-06-20
 * @author      Sisyphus
 */

import { useState, useEffect, useCallback } from 'react';
import { Tabs, Table, Button, Upload, Modal, App, Typography, Spin, Tag, Space, Input, message } from 'antd';
import { UploadOutlined, DeleteOutlined, DownloadOutlined, SettingOutlined } from '@ant-design/icons';
import apiClient from '../services/api';
import { useContentTokens } from '../contexts/AppThemeProvider';
import { pageContextManager } from '../services/PageContextManager';

const { Text } = Typography;
const ROOT_TAB = '';
const SETTINGS_TAB = '___settings___';

export default function SystemDataManagement() {
  const contentTokens = useContentTokens();
  const [activeTab, setActiveTab] = useState(ROOT_TAB);
  const [bucketConfig, setBucketConfig] = useState<any>({});
  const [configTabs, setConfigTabs] = useState<{ group: string; path: string; buckets: string[] }[]>([]);
  const [currentDir, setCurrentDir] = useState('');
  const [files, setFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [storageStats, setStorageStats] = useState<any>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [settings, setSettings] = useState<any>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingPath, setEditingPath] = useState<Record<string, string>>({});
  const [editingVolume, setEditingVolume] = useState<Record<string, string>>({});

  // Full path for file listing: use config path for bucket tabs, or direct for root
  const fileListPath = activeTab === ROOT_TAB
    ? (currentDir || '')
    : activeTab === SETTINGS_TAB
      ? ''
      : (bucketConfig[activeTab]?.path || activeTab) + (currentDir ? `/${currentDir}` : '');

  const loadConfig = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/v1/system-params/seaweedfs.buckets');
      const raw = res.data?.data?.param_value || '{}';
      const parsed: Record<string, any> = typeof raw === 'string' ? JSON.parse(raw) : raw;
      setBucketConfig(parsed);
      // Group by status & group name
      const groups: Record<string, { path: string; buckets: string[] }> = {};
      const activeBuckets = Object.entries(parsed).filter(([_, v]) => (v as any).status === 'active');
      for (const [k, v] of activeBuckets) {
        const grp = (v as any).group || k;
        if (!groups[grp]) groups[grp] = { path: (v as any).path || '', buckets: [] };
        groups[grp].buckets.push(k);
      }
      setConfigTabs(Object.entries(groups).map(([grp, info]) => ({
        group: grp,
        path: info.path,
        buckets: info.buckets,
      })));
      // Init edit states
      const edits: Record<string, string> = {};
      const vols: Record<string, string> = {};
      for (const [k, v] of Object.entries(parsed)) {
        edits[k] = (v as any).path || '';
        vols[k] = (v as any).volume || 'default';
      }
      setEditingPath(edits);
      setEditingVolume(vols);
      setSettings(parsed);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  const loadStats = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/v1/storage/stats');
      setStorageStats(res.data?.data || null);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  const loadFiles = useCallback(async (path: string) => {
    setLoading(true);
    try {
      const apiPath = path ? `${path}/` : '';
      const apiUrl = apiPath ? `/api/v1/filer/list/${apiPath}` : '/api/v1/filer/list';
      const res = await apiClient.get(apiUrl);
      const body = res.data?.data;
      if (body?.Entries) {
        const list = body.Entries
          .filter((e: any) => {
            const name = e.FullPath?.split('/').pop() || e.Name || '';
            return name !== '.keep' && name !== '.DS_Store';
          })
          .map((e: any) => ({
            ...e,
            name: e.FullPath?.split('/').pop() || e.Name || '',
            isDir: e.FileSize === 0,
          }));
        setFiles(list);
      } else {
        setFiles([]);
      }
    } catch { setFiles([]); }
    setLoading(false);
  }, []);

  useEffect(() => {
    pageContextManager.report({ page: 'system/data-management', pageName: '系統資料管理' });
  }, []);

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    try {
      const res = await apiClient.get('/api/v1/system-params/seaweedfs.buckets');
      const raw = res.data?.data?.param_value || '{}';
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
      setSettings(parsed);
      const edits: Record<string, string> = {};
      for (const [k, v] of Object.entries(parsed)) {
        edits[k] = (v as any).path || '';
      }
      setEditingPath(edits);
    } catch { setSettings(null); }
    setSettingsLoading(false);
  }, []);

  const saveSettings = async () => {
    setSaving(true);
    try {
      const updated: Record<string, any> = {};
      for (const [key, cfg] of Object.entries(settings || {})) {
        updated[key] = {
          ...(cfg as any),
          path: editingPath[key] || (cfg as any).path,
          volume: editingVolume[key] || (cfg as any).volume || 'default',
        };
      }
      const pv = JSON.stringify(updated);
      await apiClient.put(`/api/v1/system-params/seaweedfs.buckets`, {
        param_value: pv,
      });
      message.success('設定已儲存，請重整頁面');
      setSettings(updated);
      setBucketConfig(updated);
      const groups: Record<string, { path: string; buckets: string[] }> = {};
      for (const [k, v] of Object.entries(updated)) {
        const cfg = v as any;
        if (cfg.status !== 'active') continue;
        const grp = cfg.group || k;
        if (!groups[grp]) groups[grp] = { path: cfg.path || '', buckets: [] };
        groups[grp].buckets.push(k);
      }
      setConfigTabs(Object.entries(groups).map(([grp, info]) => ({ group: grp, path: info.path, buckets: info.buckets })));
    } catch { message.error('儲存失敗'); }
    setSaving(false);
  };

  useEffect(() => {
    if (activeTab !== SETTINGS_TAB && activeTab !== ROOT_TAB) {
      loadFiles(bucketConfig[activeTab]?.path || activeTab);
    } else if (activeTab === ROOT_TAB) {
      loadFiles(currentDir || '');
    }
  }, [activeTab, currentDir, bucketConfig, loadFiles]);

  const enterDir = (dirName: string) => {
    setHistory(prev => [...prev, currentDir]);
    setCurrentDir(prev => prev ? `${prev}/${dirName}` : dirName);
  };

  const goBack = () => {
    if (history.length === 0) return;
    const prev = [...history];
    setCurrentDir(prev.pop() || '');
    setHistory(prev);
  };

  const handleDelete = (fullPath: string) => {
    Modal.confirm({
      title: '確認刪除',
      content: `確定刪除 ${fullPath} ？`,
      onOk: async () => {
        try {
          await apiClient.delete(`/api/v1/filer/${fullPath}`);
          loadFiles(fullPath);
        } catch { App.useApp().message.error('刪除失敗'); }
      },
    });
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const uploadPath = fileListPath ? `${fileListPath}/` : '';
      await apiClient.post(`/api/v1/filer/${uploadPath}${file.name}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      App.useApp().message.success('上傳成功');
      if (activeTab === ROOT_TAB) loadFiles(currentDir || '');
      else if (bucketConfig[activeTab]) loadFiles(bucketConfig[activeTab].path);
    } catch { App.useApp().message.error('上傳失敗'); }
    setUploading(false);
    return false;
  };

  const columns = [
    { title: '檔名', dataIndex: 'name', key: 'name',
      render: (name: string, record: any) => {
        const fp = record.FullPath || '';
        if (record.isDir) {
          return (
            <a onClick={() => enterDir(name)} style={{ cursor: 'pointer' }}>
              <Space><Text>📁</Text><Text>{name}</Text></Space>
            </a>
          );
        }
        const ext = name.split('.').pop()?.toLowerCase() || '';
        const iconMap: Record<string, string> = { pdf: '📄', xlsx: '📊', csv: '📋', jpg: '🖼️', png: '🖼️', mp3: '🎵', mp4: '🎬', doc: '📝' };
        return (
          <Space>
            <Text>{iconMap[ext] || '📄'}</Text>
            <a href={`http://localhost:8888${fp}`} target="_blank" rel="noopener noreferrer">{name}</a>
          </Space>
        );
      }},
    { title: '大小', dataIndex: 'FileSize', key: 'FileSize', width: 100,
      render: (size: number) => {
        if (!size) return '-';
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        return `${(size / (1024 * 1024)).toFixed(1)} MB`;
      }},
    { title: '類型', dataIndex: 'Mime', key: 'Mime', width: 100,
      render: (mime: string) => mime ? <Tag>{mime.split('/')[1] || mime}</Tag> : '-' },
    { title: '更新時間', dataIndex: 'Mtime', key: 'Mtime', width: 160,
      render: (t: string) => t?.slice(0, 16).replace('T', ' ') || '-' },
    { title: '操作', key: 'action', width: 140,
      render: (_: any, record: any) => {
        if (record.isDir) return null;
        const fp = record.FullPath || '';
        return (
          <Space>
            <Button size="small" type="link" icon={<DownloadOutlined />}
              href={`http://localhost:8888${fp}`} target="_blank">下載</Button>
            <Button size="small" type="link" danger icon={<DeleteOutlined />}
              onClick={() => handleDelete(fp)}>刪除</Button>
          </Space>
        );
      }},
  ];

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      <Tabs activeKey={activeTab} onChange={(key) => {
        setActiveTab(key);
        setCurrentDir('');
        setHistory([]);
        if (key === SETTINGS_TAB) { loadSettings(); }
        else if (key === ROOT_TAB) loadFiles('');
        else if (configTabs.find(t => t.group === key)) {
          const tab = configTabs.find(t => t.group === key);
          loadFiles(tab?.path || '');
        }
      }}
        items={[
          // Root directory tab
          { key: ROOT_TAB, label: <span>🏠 資料目錄管理</span>,
            children: (
              <div>
                {/* Dashboard cards */}
                <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
                  {[
                    { label: '📦 Volume 數量', value: storageStats?.volumes ?? '-', suffix: '個', bg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' },
                    { label: '💾 總容量', value: storageStats?.total ?? '-', suffix: '', bg: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' },
                    { label: '📀 已使用', value: storageStats?.used ?? '-', suffix: '', bg: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' },
                    { label: '📂 可用容量', value: storageStats?.avail ?? '-', suffix: '', bg: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)' },
                    { label: '🗂️ SeaweedFS 資料', value: storageStats?.size ?? '-', suffix: '', bg: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)' },
                  ].map(card => (
                    <div key={card.label} style={{
                      flex: 1, minWidth: 140, padding: '16px 12px', borderRadius: 10,
                      background: card.bg, boxShadow: '0 4px 15px rgba(0,0,0,0.1)',
                      display: 'flex', flexDirection: 'column', alignItems: 'center',
                    }}>
                      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.85)', marginBottom: 6, textAlign: 'center', fontWeight: 500 }}>{card.label}</div>
                      <div style={{ fontSize: 26, fontWeight: 700, color: '#fff', textAlign: 'center', textShadow: '0 1px 3px rgba(0,0,0,0.2)' }}>
                        {card.value}
                        {card.suffix && <span style={{ fontSize: 14, fontWeight: 400, color: 'rgba(255,255,255,0.8)', marginLeft: 2 }}>{card.suffix}</span>}
                      </div>
                    </div>
                  ))}
                </div>
                {/* Storage breakdown bar */}
                {storageStats && (() => {
                  const pct = storageStats.usage_pct || 0;
                  const totalStr = (storageStats.total || '926Gi').replace(/[^0-9.]/g, '');
                  const totalGb = parseFloat(totalStr) || 926;
                  const usedNum = parseFloat((storageStats.used || '17Gi').replace(/[^0-9.]/g, '')) || 17;
                  const bd = storageStats.breakdown || {};
                  const sw = parseFloat(bd.seaweedfs_gb) || 0;
                  const ar = parseFloat(bd.arangodb_gb) || 0;
                  const qd = parseFloat(bd.qdrant_gb) || 0;
                  const otherGb = Math.max(0, usedNum - sw - ar - qd);
                  const bar = (gb: number) => Math.max(0.3, (gb / totalGb) * 100);
                  return (
                    <div style={{ marginBottom: 16, padding: '12px 16px', borderRadius: 8, border: `1px solid ${contentTokens.tableHeaderBg || '#e8e8e8'}`, background: contentTokens.containerBg || '#fff' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: contentTokens.textSecondary }}>💾 儲存空間使用率</span>
                        <span style={{ fontSize: 12, color: contentTokens.textSecondary }}>{pct}%（{storageStats.used} / {storageStats.total}）</span>
                      </div>
                      <div style={{ height: 14, borderRadius: 6, background: contentTokens.tableHeaderBg || '#f0f0f0', overflow: 'hidden', display: 'flex', marginBottom: 8 }}>
                        {sw > 0 && <div style={{ height: '100%', width: `${bar(sw)}%`, background: '#1677ff', minWidth: 3 }} title={`SeaweedFS ${sw.toFixed(1)}G`} />}
                        {ar > 0 && <div style={{ height: '100%', width: `${bar(ar)}%`, background: '#52c41a', minWidth: 3 }} title={`ArangoDB ${ar.toFixed(1)}G`} />}
                        {qd > 0 && <div style={{ height: '100%', width: `${bar(qd)}%`, background: '#722ed1', minWidth: 3 }} title={`Qdrant ${qd.toFixed(1)}G`} />}
                        {otherGb > 0 && <div style={{ height: '100%', width: `${bar(otherGb)}%`, background: '#d9d9d9', minWidth: 3 }} title={`其他 ${otherGb.toFixed(1)}G`} />}
                      </div>
                      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                        {sw > 0 && <span style={{ fontSize: 11, color: contentTokens.textSecondary }}><span style={{ color: '#1677ff' }}>■</span> SeaweedFS {sw.toFixed(1)}G</span>}
                        {ar > 0 && <span style={{ fontSize: 11, color: contentTokens.textSecondary }}><span style={{ color: '#52c41a' }}>■</span> ArangoDB {ar.toFixed(1)}G</span>}
                        {qd > 0 && <span style={{ fontSize: 11, color: contentTokens.textSecondary }}><span style={{ color: '#722ed1' }}>■</span> Qdrant {qd.toFixed(1)}G</span>}
                        <span style={{ fontSize: 11, color: contentTokens.textSecondary }}><span style={{ color: '#d9d9d9' }}>■</span> 其他 {otherGb.toFixed(1)}G</span>
                      </div>
                    </div>
                  );
                })()}
                <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {history.length > 0 && <Button size="small" onClick={goBack}>← 上一層</Button>}
                    <Text type="secondary" style={{ fontSize: 12 }}>Filer 根目錄 {currentDir ? `/ ${currentDir}` : ''}</Text>
                  </div>
                  <Upload beforeUpload={handleUpload} showUploadList={false} accept="*/*">
                    <Button size="small" icon={<UploadOutlined />} loading={uploading}>上傳檔案</Button>
                  </Upload>
                </div>
                <Spin spinning={loading}>
                  <Table dataSource={files} columns={columns} rowKey={(r: any) => r.FullPath || r.name} pagination={false} size="middle"
                    locale={{ emptyText: '此目錄尚無檔案' }} />
                </Spin>
              </div>
            ),
          },
          // Dynamic config tabs (grouped, active only)
          ...configTabs.map(t => ({
            key: t.group,
            label: <span>{t.group}</span>,
            children: (
              <div>
                <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {history.length > 0 && <Button size="small" onClick={goBack}>← 上一層</Button>}
                    <Text type="secondary" style={{ fontSize: 12 }}>{t.path}{t.buckets.length > 1 ? ` (+${t.buckets.length - 1})` : ''}{currentDir ? `/ ${currentDir}` : ''}</Text>
                  </div>
                  <Upload beforeUpload={handleUpload} showUploadList={false} accept="*/*">
                    <Button size="small" icon={<UploadOutlined />} loading={uploading}>上傳檔案</Button>
                  </Upload>
                </div>
                <Spin spinning={loading}>
                  <Table dataSource={files} columns={columns} rowKey={(r: any) => r.FullPath || r.name} pagination={false} size="middle"
                    locale={{ emptyText: '此目錄尚無檔案' }} />
                </Spin>
              </div>
            ),
          })),
          // Settings tab
          { key: SETTINGS_TAB, label: <span><SettingOutlined /> 設置</span>,
            children: (
              <Spin spinning={settingsLoading}>
                <div style={{ marginBottom: 12 }}>
                  <Text strong>SeaweedFS Bucket 路徑配置</Text>
                  <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>所有寫入請參考此配置，禁止硬編碼路徑</Text>
                </div>
                {settings ? (
                  <Table dataSource={Object.entries(settings).map(([k, v]) => ({ key: k, ...(v as any), bucketKey: k }))}
                    columns={[
                      { title: 'Bucket', dataIndex: 'bucketKey', key: 'bucketKey', width: 140 },
                      { title: '說明', dataIndex: 'desc', key: 'desc', width: 150 },
                      { title: '路徑', dataIndex: 'path', key: 'path',
                        render: (_: any, r: any) => (
                          <Input size="small" value={editingPath[r.bucketKey] || ''}
                            onChange={e => setEditingPath(p => ({ ...p, [r.bucketKey]: e.target.value }))} />
                        )},
                      { title: '磁碟容器', dataIndex: 'volume', key: 'volume', width: 120,
                        render: (_: any, r: any) => (
                          <Input size="small" value={editingVolume[r.bucketKey] || 'default'}
                            onChange={e => setEditingVolume(p => ({ ...p, [r.bucketKey]: e.target.value }))} />
                        )},
                      { title: '狀態', dataIndex: 'status', key: 'status', width: 70,
                        render: (s: string) => <Tag color={s === 'active' ? 'green' : 'orange'}>{s}</Tag> },
                    ]}
                    rowKey="bucketKey" pagination={false} size="middle" />
                ) : <Text type="secondary">載入中...</Text>}
                <div style={{ marginTop: 16 }}>
                  <Button type="primary" loading={saving} onClick={saveSettings}>儲存設定</Button>
                </div>
              </Spin>
            ),
          },
        ]}
      />
    </div>
  );
}
