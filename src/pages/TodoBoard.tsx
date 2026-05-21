/**
 * @file        待辦事項看板
 * @description Todo 引擎前端頁面，支援 CRUD、步驟管理、狀態流
 * @lastUpdate  2026-05-11 00:00:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Select, Tag, Space, App, Spin, Descriptions, Progress, Drawer, Rate, Divider, Popconfirm } from 'antd';
import { PlusOutlined, DeleteOutlined, PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, FileTextOutlined, CheckCircleOutlined, CloseCircleOutlined, ForwardOutlined, RetweetOutlined } from '@ant-design/icons';
import { todoApi } from '../services/api';
import type { TodoItem, TodoStep } from '../services/api';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';

const statusConfig: Record<string, { label: string; color: string }> = {
  pending: { label: '待處理', color: 'default' },
  running: { label: '執行中', color: 'processing' },
  paused: { label: '已暫停', color: 'warning' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失敗', color: 'error' },
  cancelled: { label: '已取消', color: 'default' },
};

const stepStatusConfig: Record<string, { label: string; color: string }> = {
  pending: { label: '待處理', color: 'default' },
  running: { label: '執行中', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失敗', color: 'error' },
  skipped: { label: '已跳過', color: 'warning' },
};

const stepTypeOptions = [
  { value: 'manual', label: '手動' },
  { value: 'agent', label: 'Agent' },
  { value: 'tool', label: '工具' },
  { value: 'sub_skill', label: '子技能' },
  { value: 'decision', label: '決策' },
  { value: 'api', label: 'API' },
];

const priorityLabels: Record<number, string> = {
  0: '最低',
  1: '低',
  2: '中',
  3: '高',
  4: '最高',
};

export default function TodoBoard() {
  const { message } = App.useApp();
  const { dispatchEntity } = useEntityPerception({ defaultEntityType: 'todo', defaultAction: 'list' });
  void dispatchEntity; // Reserved for future event handler use

  useEffect(() => {
    pageContextManager.report({ component: 'TodoBoard', entityType: 'todo', action: 'list' });
    return () => { pageContextManager.report({ component: undefined, entityType: undefined, action: undefined }); };
  }, []);

  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TodoItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<number | null>(null);
  const [searchText, setSearchText] = useState('');
  const [detailOpen, setDetailOpen] = useState(false);
  const [selected, setSelected] = useState<TodoItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [createSteps, setCreateSteps] = useState<{ title: string; step_type: string }[]>([]);
  const [form] = Form.useForm();

  const fetchList = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (priorityFilter !== null) params.priority = String(priorityFilter);
      const res = await todoApi.list(params);
      setData(res.data.data || []);
    } catch {
      message.error('載入待辦事項失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchList(); }, [statusFilter, priorityFilter]);

  const filteredData = searchText
    ? data.filter((item) =>
        item.title.toLowerCase().includes(searchText.toLowerCase()) ||
        item.todo_no.toLowerCase().includes(searchText.toLowerCase()) ||
        (item.assigned_to || '').toLowerCase().includes(searchText.toLowerCase())
      )
    : data;

  const openDetail = async (record: TodoItem) => {
    setDetailOpen(true);
    setDetailLoading(true);
    setSelected(null);
    try {
      const res = await todoApi.get(record._key!);
      setSelected(res.data.data);
    } catch {
      message.error('載入待辦詳情失敗');
      setSelected(record);
    } finally {
      setDetailLoading(false);
    }
  };

  const openCreate = () => {
    form.resetFields();
    setCreateSteps([{ title: '', step_type: 'manual' }]);
    setCreateOpen(true);
  };

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const validSteps = createSteps.filter((s) => s.title.trim());
      if (validSteps.length === 0) {
        message.warning('請至少新增一個步驟');
        return;
      }
      setConfirmLoading(true);
      const payload = {
        title: values.title,
        description: values.description || '',
        priority: values.priority ?? 2,
        tags: values.tags || [],
        steps: validSteps.map((s) => ({
          title: s.title.trim(),
          step_type: s.step_type,
        })),
      };
      await todoApi.create(payload as any);
      message.success('待辦事項已建立');
      setCreateOpen(false);
      fetchList();
    } catch (err: any) {
      const errMsg = err?.response?.data?.message || err?.message || '建立失敗';
      message.error(errMsg);
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleDelete = async (key: string) => {
    try {
      await todoApi.delete(key);
      message.success('已刪除');
      fetchList();
      if (selected?._key === key) setDetailOpen(false);
    } catch {
      message.error('刪除失敗');
    }
  };

  const handleAction = async (action: string, key: string) => {
    try {
      const actionMap: Record<string, () => Promise<any>> = {
        start: () => todoApi.start(key),
        pause: () => todoApi.pause(key),
        restart: () => todoApi.restart(key),
      };
      await actionMap[action]();
      message.success('操作成功');
      fetchList();
      if (selected?._key === key) {
        const res = await todoApi.get(key);
        setSelected(res.data.data);
      }
    } catch {
      message.error('操作失敗');
    }
  };

  const handleStepAction = async (action: string, stepIndex: number) => {
    if (!selected?._key) return;
    try {
      const actionMap: Record<string, () => Promise<any>> = {
        complete: () => todoApi.completeStep(selected._key!, stepIndex),
        fail: () => todoApi.failStep(selected._key!, stepIndex, 'manual fail'),
        skip: () => todoApi.skipStep(selected._key!, stepIndex),
        retry: () => todoApi.retryStep(selected._key!, stepIndex),
        plan: () => todoApi.plan(selected._key!, stepIndex),
        check: () => todoApi.check(selected._key!, stepIndex),
      };
      await actionMap[action]();
      message.success('步驟操作成功');
      const res = await todoApi.get(selected._key!);
      setSelected(res.data.data);
      fetchList();
    } catch {
      message.error('步驟操作失敗');
    }
  };

  const columns = [
    {
      title: '編號',
      dataIndex: 'todo_no',
      width: 90,
      render: (no: string, record: TodoItem) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => openDetail(record)}>
          {no}
        </Button>
      ),
    },
    {
      title: '標題',
      dataIndex: 'title',
      ellipsis: true,
      render: (t: string, record: TodoItem) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => openDetail(record)}>
          {t}
        </Button>
      ),
    },
    {
      title: '狀態',
      dataIndex: 'status',
      width: 90,
      render: (s: string) => {
        const cfg = statusConfig[s] || { label: s, color: 'default' };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '優先級',
      dataIndex: 'priority',
      width: 120,
      render: (p: number) => (
        <Rate disabled value={p} count={4} character={({ index }) => index! + 1} style={{ fontSize: 14 }} tooltips={['最低', '低', '中', '高']} />
      ),
    },
    {
      title: '進度',
      dataIndex: 'progress',
      width: 140,
      render: (p: number, record: TodoItem) => (
        <Progress percent={Math.round(p * 100)} size="small" style={{ margin: 0 }}
          format={() => `${record.current_step_index ?? 0}/${record.total_steps ?? 0}`}
        />
      ),
    },
    {
      title: '負責人',
      dataIndex: 'assigned_to',
      width: 100,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '建立時間',
      dataIndex: 'created_at',
      width: 80,
      ellipsis: true,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-',
    },
    {
      title: '操作',
      width: 100,
      render: (_: any, record: TodoItem) => (
        <Space size={4}>
          {record.status === 'pending' && (
            <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction('start', record._key!)} />
          )}
          {record.status === 'running' && (
            <Button type="link" size="small" icon={<PauseCircleOutlined />} onClick={() => handleAction('pause', record._key!)} />
          )}
          {record.status === 'paused' && (
            <Button type="link" size="small" icon={<ReloadOutlined />} onClick={() => handleAction('restart', record._key!)} />
          )}
          <Popconfirm title="確定刪除？" onConfirm={() => handleDelete(record._key!)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const renderStepActions = (step: TodoStep) => {
    const actions: { icon: React.ReactNode; label: string; action: string; show: boolean }[] = [
      { icon: <CheckCircleOutlined />, label: '完成', action: 'complete', show: step.status === 'running' },
      { icon: <CloseCircleOutlined />, label: '失敗', action: 'fail', show: step.status === 'running' },
      { icon: <ForwardOutlined />, label: '跳過', action: 'skip', show: step.status === 'pending' || step.status === 'running' },
      { icon: <RetweetOutlined />, label: '重試', action: 'retry', show: step.status === 'failed' || step.status === 'skipped' },
      { icon: <FileTextOutlined />, label: 'Plan', action: 'plan', show: step.status === 'pending' || step.status === 'running' },
      { icon: <CheckCircleOutlined />, label: 'Check', action: 'check', show: step.status === 'completed' },
    ];
    return (
      <Space size={4}>
        {actions.filter(a => a.show).map(a => (
          <Button key={a.action} type="link" size="small" icon={a.icon} onClick={() => handleStepAction(a.action, step.step_index)}>
            {a.label}
          </Button>
        ))}
      </Space>
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>待辦事項</h2>
        <Space>
          <Select
            placeholder="狀態篩選"
            allowClear
            style={{ width: 120 }}
            value={statusFilter || undefined}
            onChange={(v) => setStatusFilter(v || '')}
            options={Object.entries(statusConfig).map(([k, v]) => ({ value: k, label: v.label }))}
          />
          <Select
            placeholder="優先級"
            allowClear
            style={{ width: 100 }}
            value={priorityFilter !== null ? priorityFilter : undefined}
            onChange={(v) => setPriorityFilter(v ?? null)}
            options={[0, 1, 2, 3, 4].map((p) => ({ value: p, label: priorityLabels[p] }))}
          />
          <Input.Search
            placeholder="搜尋標題/編號..."
            style={{ width: 200 }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={() => {}}
            allowClear
          />
          <Button onClick={fetchList}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增待辦</Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={filteredData}
          rowKey="_key"
          size="small"
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 筆` }}
          scroll={{ x: 900 }}
        />
      </Spin>

      <Drawer
        title={selected ? `待辦詳情 - ${selected.todo_no}` : '待辦詳情'}
        open={detailOpen}
        onClose={() => { setDetailOpen(false); setSelected(null); }}
        width={640}
        extra={
          selected && (
            <Space>
              {selected.status === 'pending' && (
                <Button type="primary" size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction('start', selected._key!)}>開始</Button>
              )}
              {selected.status === 'running' && (
                <Button size="small" icon={<PauseCircleOutlined />} onClick={() => handleAction('pause', selected._key!)}>暫停</Button>
              )}
              {selected.status === 'paused' && (
                <Button size="small" icon={<ReloadOutlined />} onClick={() => handleAction('restart', selected._key!)}>繼續</Button>
              )}
            </Space>
          )
        }
      >
        <Spin spinning={detailLoading}>
          {selected && (
            <>
              <Descriptions column={2} size="small" bordered>
                <Descriptions.Item label="狀態">
                  <Tag color={statusConfig[selected.status]?.color}>{statusConfig[selected.status]?.label || selected.status}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="優先級">
                  <Rate disabled value={selected.priority} count={4} character={({ index }) => index! + 1} style={{ fontSize: 14 }} />
                </Descriptions.Item>
                <Descriptions.Item label="編號">{selected.todo_no}</Descriptions.Item>
                <Descriptions.Item label="標題">{selected.title}</Descriptions.Item>
                <Descriptions.Item label="描述" span={2}>{selected.description || '-'}</Descriptions.Item>
                <Descriptions.Item label="進度" span={2}>
                  <Progress percent={Math.round(selected.progress * 100)} format={() => `${selected.current_step_index ?? 0}/${selected.total_steps ?? 0} 步驟`} />
                </Descriptions.Item>
                <Descriptions.Item label="PDCA 判定">{selected.pdca_verdict || '-'}</Descriptions.Item>
                <Descriptions.Item label="PDCA 摘要">{selected.pdca_summary || '-'}</Descriptions.Item>
                <Descriptions.Item label="負責人">{selected.assigned_to || '-'}</Descriptions.Item>
                <Descriptions.Item label="角色">{selected.assigned_role || '-'}</Descriptions.Item>
                <Descriptions.Item label="標籤">{(selected.tags || []).join(', ') || '-'}</Descriptions.Item>
                <Descriptions.Item label="錯誤訊息" span={2}>{selected.error_message || '-'}</Descriptions.Item>
                <Descriptions.Item label="建立者">{selected.created_by || '-'}</Descriptions.Item>
                <Descriptions.Item label="建立時間">{selected.created_at ? new Date(selected.created_at).toLocaleString('zh-TW') : '-'}</Descriptions.Item>
                <Descriptions.Item label="開始時間">{selected.started_at ? new Date(selected.started_at).toLocaleString('zh-TW') : '-'}</Descriptions.Item>
                <Descriptions.Item label="完成時間">{selected.completed_at ? new Date(selected.completed_at).toLocaleString('zh-TW') : '-'}</Descriptions.Item>
              </Descriptions>

              <Divider titlePlacement="left" style={{ fontSize: 14 }}>執行步驟</Divider>
              {selected.steps && selected.steps.length > 0 ? (
                <Table
                  dataSource={selected.steps}
                  columns={[
                    { title: '#', dataIndex: 'step_index', width: 40, render: (i: number) => i + 1 },
                    { title: '步驟', dataIndex: 'step_title', ellipsis: true },
                    { title: '類型', dataIndex: 'step_type', width: 80, render: (t: string) => <Tag>{t}</Tag> },
                    {
                      title: '狀態', dataIndex: 'status', width: 80,
                      render: (s: string) => {
                        const cfg = stepStatusConfig[s] || { label: s, color: 'default' };
                        return <Tag color={cfg.color}>{cfg.label}</Tag>;
                      },
                    },
                    {
                      title: '操作', width: 200,
                      render: (_: any, record: TodoStep) => renderStepActions(record),
                    },
                  ]}
                  rowKey="step_index"
                  size="small"
                  pagination={false}
                />
              ) : (
                <div style={{ textAlign: 'center', padding: 24, color: '#999' }}>暫無步驟</div>
              )}
            </>
          )}
        </Spin>
      </Drawer>

      <Modal title="新增待辦" open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate} confirmLoading={confirmLoading}
        okText="建立" width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="標題" rules={[{ required: true, message: '請輸入標題' }]}>
            <Input placeholder="待辦事項標題" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="描述（選填）" />
          </Form.Item>
          <Space style={{ width: '100%' }}>
            <Form.Item name="priority" label="優先級" initialValue={2} style={{ width: 120 }}>
              <Select options={[
                { value: 0, label: '最低' },
                { value: 1, label: '低' },
                { value: 2, label: '中' },
                { value: 3, label: '高' },
                { value: 4, label: '最高' },
              ]} />
            </Form.Item>
            <Form.Item name="tags" label="標籤" style={{ flex: 1 }}>
              <Select mode="tags" tokenSeparators={[',', '，', ' ']} placeholder="輸入標籤" />
            </Form.Item>
          </Space>

          <Divider style={{ margin: '12px 0' }}>執行步驟</Divider>
          {createSteps.map((step, index) => (
            <Space key={index} style={{ width: '100%', marginBottom: 8 }} align="start">
              <Form.Item label={index === 0 ? '步驟標題' : ''} style={{ flex: 1, marginBottom: 0 }}>
                <Input
                  placeholder="步驟名稱"
                  value={step.title}
                  onChange={(e) => {
                    const updated = [...createSteps];
                    updated[index] = { ...updated[index], title: e.target.value };
                    setCreateSteps(updated);
                  }}
                />
              </Form.Item>
              <Form.Item label={index === 0 ? '類型' : ''} style={{ width: 120, marginBottom: 0 }}>
                <Select
                  value={step.step_type}
                  onChange={(v) => {
                    const updated = [...createSteps];
                    updated[index] = { ...updated[index], step_type: v };
                    setCreateSteps(updated);
                  }}
                  options={stepTypeOptions}
                />
              </Form.Item>
              {createSteps.length > 1 && (
                <Button type="text" danger icon={<DeleteOutlined />} style={{ marginTop: index === 0 ? 32 : 0 }}
                  onClick={() => setCreateSteps(createSteps.filter((_, i) => i !== index))} />
              )}
            </Space>
          ))}
          <Button type="dashed" block icon={<PlusOutlined />} onClick={() => setCreateSteps([...createSteps, { title: '', step_type: 'manual' }])}>
            新增步驟
          </Button>
        </Form>
      </Modal>
    </div>
  );
}
