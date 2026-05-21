import { useEffect, useState } from 'react';
import { Typography, Empty, Spin, Modal, Button, Checkbox } from 'antd';
import { MessageOutlined, DeleteOutlined, CheckOutlined, StopOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useContentTokens } from '../contexts/AppThemeProvider';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';
import { chatStore } from '../stores/chatStore';
import type { ChatSession } from '../services/api';

const { Title } = Typography;

export default function TaskSessionHistory() {
  const contentTokens = useContentTokens();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<ChatSession | null>(null);
  const [batchModalOpen, setBatchModalOpen] = useState(false);

  useEntityPerception({ defaultEntityType: 'task_session', defaultAction: 'history' });

  useEffect(() => {
    pageContextManager.report({ component: 'TaskSessionHistory', entityType: 'task_session', action: 'history' });
  }, []);

  useEffect(() => {
    setLoading(true);
    void chatStore.loadSessions().then(() => {
      const sorted = [...chatStore.getState().sessions].sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
      setSessions(sorted);
      setLoading(false);
    });
  }, []);

  const enterSelectionMode = () => {
    setSelectionMode(true);
    setSelectedKeys(new Set());
  };

  const exitSelectionMode = () => {
    setSelectionMode(false);
    setSelectedKeys(new Set());
  };

  const toggleSelect = (key: string) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleRowClick = (key: string) => {
    if (selectionMode) {
      toggleSelect(key);
    } else {
      navigate(`/app/task-session/chat/${key}`);
    }
  };

  const handleDelete = (e: React.MouseEvent, session: ChatSession) => {
    e.stopPropagation();
    setDeleteTarget(session);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await chatStore.deleteSession(deleteTarget._key);
      setSessions((prev) => prev.filter((s) => s._key !== deleteTarget._key));
    } finally {
      setDeleteTarget(null);
    }
  };

  const confirmBatchDelete = async () => {
    const keys = Array.from(selectedKeys);
    await chatStore.batchDeleteSessions(keys);
    setSessions((prev) => prev.filter((s) => !selectedKeys.has(s._key)));
    setBatchModalOpen(false);
    setSelectionMode(false);
    setSelectedKeys(new Set());
  };

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '16px 20px 12px', borderBottom: `1px solid ${contentTokens.colorBgBase}`, display: 'flex', alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <Title level={4} style={{ margin: 0, color: contentTokens.colorTextBase }}>
            歷史記錄
          </Title>
          <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginTop: 4 }}>
            {sessions.length} 個任務對話
            {selectionMode && selectedKeys.size > 0 && ` | 已選取 ${selectedKeys.size} 項`}
          </div>
        </div>
        {selectionMode ? (
          <div style={{ display: 'flex', gap: 8 }}>
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => setBatchModalOpen(true)}
              disabled={selectedKeys.size === 0}
            >
              刪除 ({selectedKeys.size})
            </Button>
            <Button size="small" icon={<StopOutlined />} onClick={exitSelectionMode}>
              取消
            </Button>
          </div>
        ) : (
          <Button size="small" icon={<CheckOutlined />} onClick={enterSelectionMode}>
            選擇
          </Button>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <Spin />
          </div>
        ) : sessions.length === 0 ? (
          <Empty description="尚無歷史記錄" style={{ marginTop: 60 }} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sessions.map((s) => (
              <div
                key={s._key}
                onClick={() => handleRowClick(s._key)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: selectedKeys.has(s._key)
                    ? `${contentTokens.colorPrimary}22`
                    : contentTokens.chatAssistantBubble,
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                  border: `1px solid ${selectedKeys.has(s._key) ? contentTokens.colorPrimary : contentTokens.colorBgBase}`,
                }}
                onMouseEnter={(e) => {
                  if (!selectedKeys.has(s._key)) {
                    e.currentTarget.style.background = `${contentTokens.colorPrimary}18`;
                  }
                }}
                onMouseLeave={(e) => {
                  if (!selectedKeys.has(s._key)) {
                    e.currentTarget.style.background = contentTokens.chatAssistantBubble;
                  }
                }}
              >
                {selectionMode && (
                  <Checkbox
                    checked={selectedKeys.has(s._key)}
                    onClick={(e) => { e.stopPropagation(); toggleSelect(s._key); }}
                    style={{ flexShrink: 0, marginRight: 10 }}
                  />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: contentTokens.colorTextBase,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {s.title || '無標題'}
                  </div>
                  <div style={{
                    fontSize: 11,
                    color: contentTokens.textSecondary,
                    marginTop: 2,
                    display: 'flex',
                    gap: 12,
                  }}>
                    <span>{new Date(s.updated_at).toLocaleString('zh-TW')}</span>
                    {s.provider && <span>{s.provider}</span>}
                    {s.model && <span>{s.model}</span>}
                  </div>
                </div>
                {!selectionMode && (
                  <DeleteOutlined
                    onClick={(e) => handleDelete(e, s)}
                    style={{
                      fontSize: 14,
                      color: contentTokens.textSecondary,
                      flexShrink: 0,
                      marginLeft: 8,
                      cursor: 'pointer',
                      padding: '0 4px',
                    }}
                  />
                )}
                {!selectionMode && (
                  <MessageOutlined
                    style={{
                      fontSize: 16,
                      color: contentTokens.colorPrimary,
                      flexShrink: 0,
                      marginLeft: 8,
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal
        title="刪除對話"
        open={deleteTarget !== null}
        onOk={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
        okText="刪除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
      >
        確定要刪除對話「{deleteTarget?.title || '無標題'}」嗎？此操作會同步刪除所有相關上傳檔案，且無法復原。
      </Modal>

      <Modal
        title="批量刪除對話"
        open={batchModalOpen}
        onOk={confirmBatchDelete}
        onCancel={() => setBatchModalOpen(false)}
        okText="刪除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
      >
        確定要刪除已選取的 {selectedKeys.size} 個對話嗎？此操作會同步刪除所有相關上傳檔案，且無法復原。
      </Modal>
    </div>
  );
}
