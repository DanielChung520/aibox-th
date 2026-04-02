/**
 * @file        數據湖表結構及數據檢視頁面
 * @description 左側顯示所有資料表列表，點擊後右側顯示欄位結構與資料預覽（分頁模式）
 * @lastUpdate  2026-04-02 19:30:00
 * @author      Daniel Chung
 * @version     1.3.0
 */

import { useState, useEffect, useMemo } from 'react';
import { Table, Card, Typography, Tag, Space, Spin, Empty, Descriptions, Alert, Tabs, theme, Input } from 'antd';
import { DatabaseOutlined, TableOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { dataAgentApi, TableInfo, FieldInfo } from '../../services/dataAgentApi';

const { Text } = Typography;
type DataSourceType = 'sap' | 'ragic' | 'ALL';

const MODULE_COLORS: Record<string, string> = {
  MM: 'blue',
  SD: 'green',
  FI: 'orange',
  PP: 'purple',
  QM: 'cyan',
  OTHER: 'default',
};

export default function DataLakePage() {
  const { token } = theme.useToken();
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [dataSourceFilter] = useState<DataSourceType>(
    () => (localStorage.getItem('app.system_type') as DataSourceType) || 'ALL'
  );
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableInfo, setTableInfo] = useState<TableInfo | null>(null);
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingData, setLoadingData] = useState(false);
  const [loadingRows, setLoadingRows] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [dataError, setDataError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('schema');
  const pageSize = 20;

  const loadTables = async () => {
    setLoadingTables(true);
    try {
      const res = await dataAgentApi.listTables();
      setTables(res.data.data || []);
    } catch {
      setTables([]);
    } finally {
      setLoadingTables(false);
    }
  };

  useEffect(() => {
    loadTables();
  }, []);

  const filteredTables = useMemo(() => {
    if (dataSourceFilter === 'ALL') return tables;
    return tables.filter(t => t.data_source === dataSourceFilter);
  }, [tables, dataSourceFilter]);

  const loadTableData = async (tableName: string, page = 1, size = 20) => {
    const isNewTable = tableName !== selectedTable;
    if (isNewTable) {
      setLoadingData(true);
      setSelectedTable(tableName);
    } else {
      setLoadingRows(true);
    }
    setDataError(null);
    try {
      const offset = (page - 1) * size;
      const res = await dataAgentApi.previewTable(tableName, offset, size);
      const data = res.data;
      if (isNewTable) {
        setTableInfo(data.table_info || null);
        setFields(data.fields || []);
      }
      setRows(data.rows || []);
      setTotal(data.total || 0);
      setCurrentPage(page);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = e?.response?.data?.detail || e?.message || '載入失敗';
      setDataError(
        msg.includes('404') || msg.includes('Not Found')
          ? '此資料表的實際資料集合尚未建立，請先執行資料湖資料填充腳本'
          : msg,
      );
      if (isNewTable) {
        setTableInfo(null);
        setFields([]);
      }
      setRows([]);
      setTotal(0);
    } finally {
      setLoadingData(false);
      setLoadingRows(false);
    }
  };

  const handlePageChange = (page: number) => {
    if (selectedTable) loadTableData(selectedTable, page, pageSize);
  };

  const fieldColumns = [
    {
      title: '欄位名',
      dataIndex: 'field_name',
      key: 'field_name',
      width: 200,
      render: (name: string, record: FieldInfo) => (
        <Space>
          <Text code style={{ fontSize: 12 }}>{name}</Text>
          {record.is_pk && <Tag color="gold" style={{ fontSize: 10 }}>PK</Tag>}
          {record.is_fk && <Tag color="blue" style={{ fontSize: 10 }}>FK</Tag>}
        </Space>
      ),
    },
    {
      title: '類型',
      dataIndex: 'field_type',
      key: 'field_type',
      width: 100,
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: '可空',
      dataIndex: 'nullable',
      key: 'nullable',
      width: 70,
      align: 'center' as const,
      render: (v: boolean) => (v ? 'Y' : 'N'),
    },
    {
      title: '說明',
      dataIndex: 'description',
      key: 'description',
      render: (desc: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>{desc || '-'}</Text>
      ),
    },
  ];

  const rowColumns = fields.map(field => ({
    title: field.field_name,
    dataIndex: field.field_name,
    key: field.field_name,
    ellipsis: true,
    width: 150,
    render: (value: unknown) => {
      if (value === null || value === undefined) return <Text type="secondary">NULL</Text>;
      if (typeof value === 'object') return <Text type="secondary">{JSON.stringify(value)}</Text>;
      return String(value);
    },
  }));

  const tabItems = useMemo(() => [
    {
      key: 'schema',
      label: (
        <Space>
          <TableOutlined />
          <span>欄位結構</span>
          <Tag>{fields.length}</Tag>
        </Space>
      ),
      children: (
        <div style={{ height: '100%', overflow: 'auto', padding: '8px 0' }}>
          {fields.length > 0 ? (
            <Table
              columns={fieldColumns}
              dataSource={fields}
              rowKey="field_id"
              size="small"
              pagination={false}
              scroll={{ x: 600 }}
            />
          ) : (
            <Empty description="尚無欄位結構" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </div>
      ),
    },
    {
      key: 'data',
      label: (
        <Space>
          <DatabaseOutlined />
          <span>資料預覽</span>
          <Tag>{total > 0 ? total.toLocaleString() : '-'}</Tag>
        </Space>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
          {dataError ? (
            <Alert
              message="資料載入失敗"
              description={dataError}
              type="warning"
              showIcon
              action={
                <Tag
                  color="warning"
                  style={{ cursor: 'pointer' }}
                  onClick={() => selectedTable && loadTableData(selectedTable, 1, pageSize)}
                >
                  重試
                </Tag>
              }
            />
          ) : rows.length > 0 ? (
            <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
              {total > pageSize && (
                <Alert
                  message={`顯示第 ${(currentPage - 1) * pageSize + 1}–${Math.min(currentPage * pageSize, total)} 筆記錄，共 ${total.toLocaleString()} 筆記錄`}
                  type="info"
                  showIcon
                  style={{ marginBottom: 8 }}
                />
              )}
              <Table
                columns={rowColumns}
                dataSource={rows.map((r, i) => ({ ...r, key: (r._key as string) || i }))}
                rowKey="key"
                size="small"
                loading={loadingRows}
                pagination={{
                  current: currentPage,
                  pageSize,
                  total,
                  showSizeChanger: false,
                  onChange: handlePageChange,
                  showTotal: t => `${t} 筆記錄`,
                }}
                scroll={{ x: Math.max(fields.length * 150, 600) }}
              />
            </div>
          ) : (
            <Empty description="此資料表尚無實際資料" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </div>
      ),
    },
  ], [fields, rows, total, currentPage, pageSize, dataError, selectedTable]);

  return (
    <div style={{ display: 'flex', height: '100%', gap: 16 }}>
      <Card
        title={
          <Space>
            <DatabaseOutlined />
            <span>資料表列表</span>
            <Tag>{filteredTables.length}</Tag>
          </Space>
        }
        style={{ width: 300, flexShrink: 0 }}
        styles={{ body: { padding: 0 } }}
      >
        <div style={{ padding: '12px 12px 4px' }}>
          <Input
            placeholder="搜尋資料表..."
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            allowClear
          />
        </div>
        <div style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
          <Table
            dataSource={filteredTables.filter(t =>
              !searchText ||
              t.table_name.toLowerCase().includes(searchText.toLowerCase()) ||
              t.description?.toLowerCase().includes(searchText.toLowerCase()) ||
              t.module.toLowerCase().includes(searchText.toLowerCase()) ||
              t.table_id.toLowerCase().includes(searchText.toLowerCase())
            )}
            rowKey="table_id"
            size="small"
            pagination={false}
            onRow={t => ({
              onClick: () => loadTableData(t.table_id, 1, pageSize),
              style: {
                cursor: 'pointer',
                background: selectedTable === t.table_id ? token.controlItemBgActive : 'transparent',
              },
            })}
            columns={[
              {
                title: '資料表',
                key: 'name',
                render: (_: unknown, t: TableInfo) => (
                  <Space orientation="vertical" size={2}>
                    <Space>
                      <Text strong style={{ fontSize: 13 }}>{t.table_name}</Text>
                      <Tag color={MODULE_COLORS[t.module] || 'default'} style={{ fontSize: 10 }}>
                        {t.module}
                      </Tag>
                      {t.data_source && (
                        <Tag color={t.data_source === 'sap' ? 'blue' : 'green'} style={{ fontSize: 10 }}>
                          {t.data_source.toUpperCase()}
                        </Tag>
                      )}
                    </Space>
                    <Text type="secondary" style={{ fontSize: 10 }}>
                      {t.table_id}
                    </Text>
                    {(t.row_count_estimate ?? t.record_count) !== undefined && (
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        ~{(t.row_count_estimate ?? t.record_count)?.toLocaleString()} rows
                      </Text>
                    )}
                    {t.description && (
                      <Text type="secondary" style={{ fontSize: 11 }} ellipsis>
                        {t.description}
                      </Text>
                    )}
                  </Space>
                ),
              },
            ]}
            loading={loadingTables}
            locale={{ emptyText: <Empty description="暫無資料表" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          />
        </div>
      </Card>

      <Card style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {!selectedTable ? (
          <Empty
            description="點擊左側資料表以查看結構與資料"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : loadingData ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300 }}>
            <Spin size="large" description="載入資料中..." />
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 12, overflow: 'hidden' }}>
            {tableInfo && (
              <Card size="small" title={
                <Space><InfoCircleOutlined /><span>資料表資訊</span></Space>
              } styles={{ body: { flex: 'none' } }}>
                <Descriptions size="small" column={3} bordered>
                  <Descriptions.Item label="表名">
                    <Text strong>{tableInfo.table_name}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Table ID">
                    <Text code>{tableInfo.table_id}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="模組">
                    <Tag color={MODULE_COLORS[tableInfo.module] || 'default'}>{tableInfo.module}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="來源">
                    {tableInfo.data_source ? (
                      <Tag color={tableInfo.data_source === 'sap' ? 'blue' : 'green'}>
                        {tableInfo.data_source.toUpperCase()}
                      </Tag>
                    ) : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="主鍵">
                    {tableInfo.primary_keys?.join(', ') || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="分割鍵">
                    {tableInfo.partition_keys?.join(', ') || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="狀態">
                    <Tag color={tableInfo.status === 'enabled' ? 'green' : 'default'}>
                      {tableInfo.status}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="預估列數">
                    {tableInfo.row_count_estimate
                      ? tableInfo.row_count_estimate.toLocaleString()
                      : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="描述" span={3}>
                    {tableInfo.description || '-'}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            )}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} className="datalake-tabs" />
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
