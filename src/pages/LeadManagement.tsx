import { useState, useEffect, useCallback } from 'react';
import { Table, Button, Modal, Form, Input, Select, Popconfirm, Switch, Tag, App } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import { leadApi, Lead } from '../services/api';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';

export default function LeadManagement() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [noteForm] = Form.useForm();
  const { message } = App.useApp();
  const { dispatchEntity } = useEntityPerception({ defaultEntityType: 'lead', defaultAction: 'list' });

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const params: { status?: string; page: number; page_size: number } = { page, page_size: 20 };
      if (statusFilter) params.status = statusFilter;
      const resp = await leadApi.list(params);
      setLeads(resp.data.data?.leads || []);
      setTotal(resp.data.data?.total || 0);
    } catch {
      message.error('獲取名單失敗');
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  useEffect(() => {
    pageContextManager.report({ component: 'LeadManagement', entityType: 'lead', action: 'list' });
  }, []);

  const openDetail = (lead: Lead) => {
    setSelectedLead(lead);
    noteForm.setFieldsValue({ note: lead.note || '', can_download: lead.can_download, open_github: lead.open_github });
    setDetailVisible(true);
  };

  const handleSaveDetail = async () => {
    if (!selectedLead) return;
    try {
      const values = noteForm.getFieldsValue();
      await leadApi.update(selectedLead._key, {
        note: values.note,
        can_download: values.can_download,
        open_github: values.open_github,
      });
      message.success('已儲存');
      setDetailVisible(false);
      fetchLeads();
    } catch {
      message.error('儲存失敗');
    }
  };

  const handleApprove = async (lead: Lead) => {
    try {
      await leadApi.approve(lead._key, { can_download: lead.can_download, open_github: lead.open_github });
      message.success(`已核准 ${lead.name}`);
      fetchLeads();
    } catch {
      message.error('操作失敗');
    }
  };

  const handleReject = async (key: string) => {
    try {
      await leadApi.reject(key, {});
      message.success('已婉拒');
      fetchLeads();
    } catch {
      message.error('操作失敗');
    }
  };

  const handleDelete = async (key: string) => {
    try {
      await leadApi.delete(key);
      message.success('已刪除');
      fetchLeads();
    } catch {
      message.error('刪除失敗');
    }
  };

  const statusColor = (s: string) => s === 'approved' ? 'success' : s === 'rejected' ? 'error' : 'warning';
  const statusLabel = (s: string) => s === 'approved' ? '已核准' : s === 'rejected' ? '已婉拒' : '待審核';

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name', width: 120 },
    { title: '公司', dataIndex: 'company', key: 'company', width: 160 },
    { title: 'Email', dataIndex: 'email', key: 'email', width: 200 },
    { title: '電話', dataIndex: 'phone', key: 'phone', width: 140 },
    { title: '預算', dataIndex: 'budget', key: 'budget', width: 140 },
    {
      title: 'GitHub', dataIndex: 'github', key: 'github', width: 140,
      render: (v: string | null) => v ? <a href={`https://github.com/${v}`} target="_blank" rel="noopener">{v}</a> : '-',
    },
    {
      title: '狀態', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => <Tag color={statusColor(s)}>{statusLabel(s)}</Tag>,
    },
    {
      title: '可下載', dataIndex: 'can_download', key: 'can_download', width: 90,
      render: (v: boolean) => v ? <Tag color="blue">可下載</Tag> : <span style={{ color: '#999' }}>無</span>,
    },
    {
      title: '開放 GitHub', dataIndex: 'open_github', key: 'open_github', width: 110,
      render: (v: boolean) => v ? <Tag color="purple">已開放</Tag> : <span style={{ color: '#999' }}>無</span>,
    },
    {
      title: '申請時間', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => new Date(v).toLocaleString('zh-TW'),
    },
    {
      title: '操作', key: 'action', width: 200,
      render: (_: unknown, record: Lead) => (
        <>
          <Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(record)} style={{ marginRight: 4 }}>檢視</Button>
          <Popconfirm title="確定刪除？" onConfirm={() => handleDelete(record._key)}>
            <Button size="small" danger icon={<DeleteOutlined />}>刪</Button>
          </Popconfirm>
        </>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>聯繫名單管理</h2>
        <Select
          value={statusFilter}
          onChange={(v) => { setStatusFilter(v); setPage(1); }}
          style={{ width: 140 }}
          options={[
            { label: '全部', value: '' },
            { label: '待審核', value: 'pending' },
            { label: '已核准', value: 'approved' },
            { label: '已婉拒', value: 'rejected' },
          ]}
        />
      </div>

      <Table
        dataSource={leads}
        columns={columns}
        rowKey="_key"
        loading={loading}
        onRow={(record) => ({
          onClick: () => dispatchEntity(record._key, 'view'),
        })}
        pagination={{ current: page, total, pageSize: 20, showTotal: (t) => `共 ${t} 筆`, onChange: (p) => setPage(p) }}
        scroll={{ x: 1400 }}
      />

      <Modal
        title={`審核：${selectedLead?.name}`}
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        onOk={handleSaveDetail}
        width={560}
        okText="儲存"
      >
        {selectedLead && (
          <Form form={noteForm} layout="vertical" initialValues={{
            note: selectedLead.note || '',
            can_download: selectedLead.can_download,
            open_github: selectedLead.open_github,
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
              <div><div style={{ color: '#666', fontSize: 12 }}>公司</div><div style={{ fontWeight: 500 }}>{selectedLead.company}</div></div>
              <div><div style={{ color: '#666', fontSize: 12 }}>Email</div><div>{selectedLead.email}</div></div>
              <div><div style={{ color: '#666', fontSize: 12 }}>電話</div><div>{selectedLead.phone || '-'}</div></div>
              <div>
                <div style={{ color: '#666', fontSize: 12 }}>GitHub</div>
                <div>{selectedLead.github
                  ? <a href={`https://github.com/${selectedLead.github}`} target="_blank" rel="noopener">{selectedLead.github}</a>
                  : '-'}</div>
              </div>
              <div><div style={{ color: '#666', fontSize: 12 }}>預算</div><div>{selectedLead.budget || '-'}</div></div>
              <div><div style={{ color: '#666', fontSize: 12 }}>申請時間</div><div>{new Date(selectedLead.created_at).toLocaleString('zh-TW')}</div></div>
            </div>
            {selectedLead.message && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: '#666', fontSize: 12 }}>留言內容</div>
                <div style={{ background: '#f5f5f5', padding: 12, borderRadius: 6, whiteSpace: 'pre-wrap' }}>{selectedLead.message}</div>
              </div>
            )}
            <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
              <Form.Item name="can_download" valuePropName="checked" style={{ margin: 0 }}>
                <Switch checkedChildren="可下載 App" unCheckedChildren="不可下載" />
              </Form.Item>
              <Form.Item name="open_github" valuePropName="checked" style={{ margin: 0 }}>
                <Switch checkedChildren="開放 GitHub" unCheckedChildren="未開放" />
              </Form.Item>
            </div>
            <Form.Item name="note" label="管理員備註">
              <Input.TextArea rows={3} placeholder="填寫審核備註或內部說明" />
            </Form.Item>
            {selectedLead.status === 'pending' && (
              <div style={{ display: 'flex', gap: 8 }}>
                <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => handleApprove(selectedLead)}>核准</Button>
                <Button danger icon={<CloseCircleOutlined />} onClick={() => handleReject(selectedLead._key)}>婉拒</Button>
              </div>
            )}
          </Form>
        )}
      </Modal>
    </div>
  );
}
