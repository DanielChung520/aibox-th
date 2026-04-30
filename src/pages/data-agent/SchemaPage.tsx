/**
 * @file        Data Agent Schema 管理頁面
 * @description 管理 DA 的資料表結構與模組分類
 * @lastUpdate  2026-04-16 11:16:02
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Card, Table, Form, Tabs, App, Typography, Input, Button, Space, theme } from 'antd';
import { DatabaseOutlined, SettingOutlined } from '@ant-design/icons';
import { dataAgentApi, TableInfo, FieldInfo } from '../../services/dataAgentApi';

import { TAB_LABELS, TAB_CATEGORIES } from './schemaConstants';
import { getSchemaTableColumns } from './schemaTableColumns';
import SchemaFilterTags from './SchemaFilterTags';
import SchemaDataPreviewModal from './SchemaDataPreviewModal';
import SchemaImportSection from './SchemaImportSection';
import SchemaColumnsModal from './SchemaColumnsModal';
import SchemaEditModal from './SchemaEditModal';
import SchemaSettingsDrawer from './SchemaSettingsDrawer';
import SchemaReportModal from './SchemaReportModal';
import { useEntityPerception } from '../../hooks/useEntityPerception';

const { Title, Text } = Typography;

export default function SchemaPage() {
  const { message } = App.useApp();
  const { token: antToken } = theme.useToken();
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [tableModalVisible, setTableModalVisible] = useState(false);
  const [editingTable, setEditingTable] = useState<Partial<TableInfo> | null>(null);
  
  const [selectedCategory, setSelectedCategory] = useState<string>('全部');
  const [selectedTab, setSelectedTab] = useState<string>('ALL');
  
  const [form] = Form.useForm();

  const [columnsModalVisible, setColumnsModalVisible] = useState(false);
  const [columnsTableName, setColumnsTableName] = useState('');
  const [columns, setColumns] = useState<FieldInfo[]>([]);
  const [columnsLoading, setColumnsLoading] = useState(false);

  const [searchText, setSearchText] = useState('');

  const [dataModalVisible, setDataModalVisible] = useState(false);
  const [dataModalTitle, setDataModalTitle] = useState('');
  const [dataTableId, setDataTableId] = useState('');
  const [dataPreviewMode, setDataPreviewMode] = useState<'paged' | 'all'>('paged');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [reportTableInfo, setReportTableInfo] = useState<TableInfo | null>(null);
  const { dispatchEntity } = useEntityPerception({ defaultEntityType: 'table', defaultAction: 'list' });

  const loadTables = async () => {
    setLoading(true);
    try {
      const res = await dataAgentApi.listTables();
      setTables((res.data.data || []).filter((t: TableInfo) => t.data_source !== 'sap'));
    } catch {
      message.error('載入資料表失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTables();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDeleteTable = async (tableId: string) => {
    try {
      await dataAgentApi.deleteTable(tableId);
      message.success('刪除成功');
      loadTables();
    } catch {
      message.error('刪除失敗');
    }
  };

  const handleSaveTable = async () => {
    try {
      const values = await form.validateFields();
      if (editingTable?.table_id) {
        await dataAgentApi.updateTable(editingTable.table_id, values);
        message.success('更新成功');
      } else {
        await dataAgentApi.createTable(values);
        message.success('建立成功');
      }
      setTableModalVisible(false);
      form.resetFields();
      setEditingTable(null);
      loadTables();
    } catch {
      message.error('操作失敗');
    }
  };

  const openDataModal = (record: TableInfo) => {
    setDataModalTitle(record.table_name);
    setDataTableId(record.table_id);
    setDataPreviewMode(record.preview_mode ?? 'paged');
    setDataModalVisible(true);
    dispatchEntity(record.table_id, 'view', { table_name: record.table_name, type: 'data_preview' });
  };

  const openReportModal = (record: TableInfo) => {
    setReportTableInfo(record);
    setReportModalOpen(true);
    dispatchEntity(record.table_id, 'create', { table_name: record.table_name, action_type: 'open_report' });
  };

  const handlePreviewModeChange = async (mode: 'paged' | 'all') => {
    setDataPreviewMode(mode);
    if (!dataTableId) return;
    try {
      await dataAgentApi.updateTable(dataTableId, { preview_mode: mode } as Partial<TableInfo>);
      setTables(prev => prev.map(t => t.table_id === dataTableId ? { ...t, preview_mode: mode } : t));
    } catch {
      message.error('儲存預覽模式失敗');
    }
  };

  const openColumnsModal = async (record: TableInfo) => {
    setColumnsTableName(`${record.table_name}（${record.table_id}）`);
    setColumnsModalVisible(true);
    dispatchEntity(record.table_id, 'view', { table_name: record.table_name, action_type: 'view_columns' });
    setColumnsLoading(true);
    try {
      const res = await dataAgentApi.listFields(record.table_id);
      setColumns(res.data.data || []);
    } catch {
      message.error('載入欄位資訊失敗');
      setColumns([]);
    } finally {
      setColumnsLoading(false);
    }
  };

  const knownTabs = TAB_CATEGORIES.flatMap(c => c.tabs);
  const filteredTables = tables.filter(t => {
    if (selectedCategory !== '全部') {
      if (selectedCategory === '其他') {
        if (knownTabs.includes(t.tab || '')) return false;
      } else {
        const category = TAB_CATEGORIES.find(c => c.label === selectedCategory);
        if (category && !category.tabs.includes(t.tab || '')) return false;
      }
    }
    if (selectedTab !== 'ALL' && t.tab !== selectedTab) return false;
    if (searchText) {
      const s = searchText.toLowerCase();
      if (!t.table_name.toLowerCase().includes(s) && !t.table_id.toLowerCase().includes(s)) return false;
    }
    return true;
  });

  const enabledCount = tables.filter(t => t.status === 'enabled').length;
  const disabledCount = tables.filter(t => t.status !== 'enabled').length;

  const categoryOptions = [
    { label: `全部 (${tables.length})`, value: '全部' },
    ...TAB_CATEGORIES.map(c => ({
      label: `${c.label} (${tables.filter(t => c.tabs.includes(t.tab || '')).length})`, 
      value: c.label
    })),
  ];
  
  const otherCount = tables.filter(t => !knownTabs.includes(t.tab || '')).length;
  if (otherCount > 0) categoryOptions.push({ label: `其他 (${otherCount})`, value: '其他' });

  let availableTabs: string[] = [];
  if (selectedCategory === '全部') {
    availableTabs = Array.from(new Set(tables.map(t => t.tab || ''))).filter(Boolean);
  } else if (selectedCategory === '其他') {
    availableTabs = Array.from(new Set(tables.filter(t => !knownTabs.includes(t.tab || '')).map(t => t.tab || ''))).filter(Boolean);
  } else {
    const category = TAB_CATEGORIES.find(c => c.label === selectedCategory);
    if (category) availableTabs = category.tabs.filter(tab => tables.some(t => t.tab === tab));
  }

  const tabItems = [
    {
      key: 'ALL',
      label: `全部 (${tables.filter(t => {
        if (selectedCategory === '全部') return true;
        if (selectedCategory === '其他') return !knownTabs.includes(t.tab || '');
        const cat = TAB_CATEGORIES.find(c => c.label === selectedCategory);
        return cat?.tabs.includes(t.tab || '');
      }).length})`
    },
    ...availableTabs.map(tab => ({
      key: tab,
      label: `${TAB_LABELS[tab] || tab} (${tables.filter(t => t.tab === tab).length})`
    }))
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <DatabaseOutlined /> Data Agent Schema 管理
          <Text type="secondary" style={{ fontSize: 14, marginLeft: 12 }}>
            有效 {enabledCount} / 無效 {disabledCount}
          </Text>
        </Title>
        <Space>
          <Button type="text" icon={<SettingOutlined />} onClick={() => setSettingsOpen(true)} title="模型設置" />
          <SchemaImportSection onImportSuccess={loadTables} />
        </Space>
      </div>

      <Card style={{ flex: 1, display: 'flex', flexDirection: 'column' }} styles={{ body: { padding: '12px 24px 0', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' } }}>
        <SchemaFilterTags 
          categoryOptions={categoryOptions} 
          selectedCategory={selectedCategory} 
          onSelect={(val) => { setSelectedCategory(val); setSelectedTab('ALL'); }} 
        />

        <div style={{ marginBottom: 8 }}>
          <Input.Search
            placeholder="搜尋表名或 Table ID"
            allowClear
            onSearch={(v) => setSearchText(v)}
            onChange={(e) => { if (!e.target.value) setSearchText(''); }}
            style={{ width: 260 }}
          />
        </div>
        
        {availableTabs.length > 0 && (
          <>
            <style>{`
              .schema-tabs .ant-tabs-tab:not(.ant-tabs-tab-active):hover {
                background: rgba(255,255,255,0.18) !important;
                border-color: rgba(53,114,212,0.5) !important;
              }
              /* 深色模式下提高非選中 tab 的預設可見度 */
              .schema-tabs[data-dark="true"] .ant-tabs-tab:not(.ant-tabs-tab-active) {
                background: rgba(255,255,255,0.06) !important;
              }
            `}</style>
            <Tabs
              type="card"
              size="small"
              activeKey={selectedTab}
              onChange={setSelectedTab}
              items={tabItems}
              style={{ marginBottom: 8 }}
              className="schema-tabs"
              data-dark={antToken.colorBgBase === '#0f172a' ? 'true' : 'false'}
            />
          </>
        )}

        <div className="schema-table-fill">
          <Table 
            columns={getSchemaTableColumns({
              onOpenColumnsModal: openColumnsModal,
              onOpenDataModal: openDataModal,
              onOpenReportModal: openReportModal,
              onEditTable: (record) => {
                setEditingTable(record);
                form.setFieldsValue(record);
                setTableModalVisible(true);
              },
              onDeleteTable: handleDeleteTable
            })} 
            dataSource={filteredTables} 
            rowKey="table_id"
            loading={loading} 
            pagination={{ pageSize: 15 }} 
            size="small"
            onRow={(record) => ({ 
              onClick: () => dispatchEntity(record.table_id, 'view', { table_name: record.table_name, tab: record.tab }),
              onDoubleClick: () => openDataModal(record), 
              style: { cursor: 'pointer' } 
            })}
          />
        </div>
      </Card>

      <SchemaEditModal
        visible={tableModalVisible}
        form={form}
        editingTable={editingTable}
        onSave={handleSaveTable}
        onCancel={() => { setTableModalVisible(false); form.resetFields(); setEditingTable(null); }}
      />

      <SchemaColumnsModal
        visible={columnsModalVisible}
        tableName={columnsTableName}
        columns={columns}
        loading={columnsLoading}
        onCancel={() => setColumnsModalVisible(false)}
      />

      <SchemaDataPreviewModal
        visible={dataModalVisible}
        tableId={dataTableId}
        tableName={dataModalTitle}
        previewMode={dataPreviewMode}
        onPreviewModeChange={handlePreviewModeChange}
        onCancel={() => setDataModalVisible(false)}
      />

      <SchemaSettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />

      {reportTableInfo && (
        <SchemaReportModal
          open={reportModalOpen}
          tableInfo={reportTableInfo}
          onClose={() => { setReportModalOpen(false); setReportTableInfo(null); }}
        />
      )}
    </div>
  );
}
