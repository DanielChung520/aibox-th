/**
 * @file        Data Agent Schema 資料預覽
 * @description Schema 頁面的資料預覽 Modal — DuckDB-WASM 驅動，本地篩選/排序/翻頁
 * @lastUpdate  2026-04-16 11:36:00
 * @author      Daniel Chung
 * @version     2.2.0
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Modal, Table, App, Input, Button, Space, DatePicker, InputNumber, Select, Tooltip, Segmented } from 'antd';
import { SearchOutlined, FilterOutlined, ReloadOutlined, DatabaseOutlined, FileOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import type { InputRef, TableColumnType } from 'antd';
import type { FilterDropdownProps } from 'antd/es/table/interface';
import dayjs from 'dayjs';
import { dataAgentApi, FieldInfo } from '../../services/dataAgentApi';
import { duckdbWasm } from '../../services/duckdbWasm';
import { useEffectiveTheme } from '../../contexts/AppThemeProvider';
import { actionTrail } from '../../services/actionTrail';

interface SchemaDataPreviewModalProps {
  visible: boolean;
  tableId: string;
  tableName: string;
  previewMode?: 'paged' | 'all';
  onPreviewModeChange?: (mode: 'paged' | 'all') => void;
  onCancel: () => void;
}

const PAGE_SIZE_OPTIONS = [20, 50, 100];
const RAGIC_BATCH_SIZE = 1000;

export default function SchemaDataPreviewModal({
  visible,
  tableId,
  tableName,
  previewMode: externalMode,
  onPreviewModeChange,
  onCancel,
}: SchemaDataPreviewModalProps) {
  const { message } = App.useApp();
  const effectiveTheme = useEffectiveTheme();
  const warningColor = (() => {
    const root = document.documentElement;
    const cssVar = effectiveTheme === 'dark'
      ? root.style.getPropertyValue('--fa-warning-color-dark').trim()
      : root.style.getPropertyValue('--fa-warning-color-light').trim();
    if (cssVar) return cssVar;
    return effectiveTheme === 'dark' ? '#ff4d4f' : '#1677ff';
  })();
  const [displayRows, setDisplayRows] = useState<Record<string, unknown>[]>([]);
  const [dataFields, setDataFields] = useState<FieldInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [totalRows, setTotalRows] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchText, setSearchText] = useState('');
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [loadingProgress, setLoadingProgress] = useState('');
  const [fetchMode, setFetchMode] = useState<'paged' | 'all'>(externalMode ?? 'paged');
  const searchInputRef = useRef<InputRef>(null);
  const tableRef = useRef<HTMLDivElement>(null);

  const handleColHover = (colIdx: number | null) => {
    const container = tableRef.current;
    if (!container) return;
    container.querySelectorAll('.crosshair-col-active').forEach(el => el.classList.remove('crosshair-col-active'));
    if (colIdx == null) return;
    const colN = colIdx + 1;
    container.querySelectorAll(
      `.ant-table-thead > tr > th:nth-child(${colN}), .ant-table-tbody > tr > td:nth-child(${colN})`
    ).forEach(el => el.classList.add('crosshair-col-active'));
  };

  /** 分頁模式：僅從 Ragic 拉取當頁資料（不走 DuckDB cache） */
  const fetchPagedFromRagic = useCallback(async (p: number, ps: number) => {
    if (!tableId) return;
    setLoading(true);
    try {
      const offset = (p - 1) * ps;
      const res = await dataAgentApi.ragicProxyData(tableId, offset, ps);
      const resData = res.data;

      if (resData.code !== 0 && resData.message) {
        message.error(`Ragic API 錯誤: ${resData.message}`);
        return;
      }

      if (resData.fields?.length > 0) setDataFields(resData.fields);

      const rows = resData.rows || [];
      setDisplayRows(rows);
      // Ragic 不回傳 total，用啟發式推算：若回傳量 < pageSize 表示已到底
      setTotalRows(prev => {
        if (rows.length < ps) return offset + rows.length;
        // 若剛好等於 pageSize，至少有下一頁
        return Math.max(prev, offset + rows.length + 1);
      });
      setCachedAt(null);
    } catch {
      message.error('載入資料失敗');
      setDisplayRows([]);
    } finally {
      setLoading(false);
    }
  }, [tableId, message]);

  /** 從 Ragic 拉全量資料並載入 DuckDB-WASM */
  const fetchAndCacheAll = useCallback(async () => {
    if (!tableId) return;
    setLoading(true);
    setLoadingProgress('正在從 Ragic 載入資料...');

    try {
      let allRows: Record<string, unknown>[] = [];
      let fields: FieldInfo[] = [];
      let offset = 0;
      let hasMore = true;

      while (hasMore) {
        setLoadingProgress(`正在載入... 已取得 ${allRows.length} 筆`);
        const res = await dataAgentApi.ragicProxyData(tableId, offset, RAGIC_BATCH_SIZE);
        const resData = res.data;

        if (resData.code !== 0 && resData.message) {
          message.error(`Ragic API 錯誤: ${resData.message}`);
          break;
        }

        if (offset === 0 && resData.fields?.length > 0) {
          fields = resData.fields;
        }

        const batch = resData.rows || [];
        allRows = allRows.concat(batch);

        if (batch.length < RAGIC_BATCH_SIZE) {
          hasMore = false;
        } else {
          offset += RAGIC_BATCH_SIZE;
        }
      }

      setDataFields(fields);

      setLoadingProgress(`正在建立本地 Cache（${allRows.length} 筆）...`);
      await duckdbWasm.loadTable(tableId, allRows);

      const meta = duckdbWasm.getTableMeta(tableId);
      setCachedAt(meta?.cachedAt ? dayjs(meta.cachedAt).format('YYYY-MM-DD HH:mm:ss') : null);

      setPage(1);
      await queryPage(1, pageSize);
    } catch {
      message.error('載入資料失敗');
      setDisplayRows([]);
      setDataFields([]);
      setTotalRows(0);
    } finally {
      setLoading(false);
      setLoadingProgress('');
    }
  }, [tableId, pageSize, message]);

  /** 從 DuckDB-WASM 查詢當前頁面資料 */
  const queryPage = useCallback(async (
    p: number,
    ps: number,
  ) => {
    const safeName = `t_${tableId.replace(/[^a-zA-Z0-9_]/g, '_')}`;

    try {
      const countResult = await duckdbWasm.query<{ cnt: number }>(
        `SELECT COUNT(*)::INTEGER AS cnt FROM ${safeName}`
      );
      const total = countResult[0]?.cnt ?? 0;
      setTotalRows(total);

      const offset = (p - 1) * ps;
      const rows = await duckdbWasm.query<Record<string, unknown>>(
        `SELECT * FROM ${safeName} LIMIT ${ps} OFFSET ${offset}`
      );
      setDisplayRows(rows);
    } catch (err) {
      console.error('[DuckDB-WASM] query error:', err);
      setDisplayRows([]);
      setTotalRows(0);
    }
  }, [tableId]);

  useEffect(() => {
    if (externalMode) setFetchMode(externalMode);
  }, [externalMode]);

  useEffect(() => {
    if (visible && tableId) {
      actionTrail.record('modal_open', { tableId, tableName, fetchMode });
      if (fetchMode === 'all') {
        if (duckdbWasm.hasTable(tableId)) {
          const meta = duckdbWasm.getTableMeta(tableId);
          setCachedAt(meta?.cachedAt ? dayjs(meta.cachedAt).format('YYYY-MM-DD HH:mm:ss') : null);
          setPage(1);
          setLoading(true);
          dataAgentApi.ragicProxyData(tableId, 0, 1).then(res => {
            if (res.data.fields?.length > 0) setDataFields(res.data.fields);
          }).catch(() => {}).finally(() => {
            queryPage(1, pageSize).finally(() => setLoading(false));
          });
        } else {
          fetchAndCacheAll();
        }
      } else {
        setPage(1);
        setTotalRows(0);
        fetchPagedFromRagic(1, pageSize);
      }
    } else {
      if (tableId) actionTrail.record('modal_close', { tableId });
      setDisplayRows([]);
      setDataFields([]);
      setTotalRows(0);
      setPage(1);
      setSearchText('');
      setCachedAt(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, tableId, fetchMode]);

  const handlePageChange = (newPage: number, newPageSize: number) => {
    setPage(newPage);
    setPageSize(newPageSize);
    actionTrail.record('page_change', { tableId, page: newPage, pageSize: newPageSize, fetchMode });
    if (fetchMode === 'all') {
      queryPage(newPage, newPageSize);
    } else {
      fetchPagedFromRagic(newPage, newPageSize);
    }
  };

  const handleRefresh = () => {
    actionTrail.record('refresh', { tableId, fetchMode });
    if (fetchMode === 'all') {
      duckdbWasm.dropTable(tableId).then(() => fetchAndCacheAll());
    } else {
      setPage(1);
      setTotalRows(0);
      fetchPagedFromRagic(1, pageSize);
    }
  };

  const filteredRows = searchText
    ? displayRows.filter(row =>
      Object.values(row).some(v =>
        v != null && String(v).toLowerCase().includes(searchText.toLowerCase())
      )
    )
    : displayRows;

  const getColumnSearchProps = (field: FieldInfo): Partial<TableColumnType<Record<string, unknown>>> => {
    const fieldType = field.field_type || '文字';
    const isNumeric = ['數字', '貨幣', '百分比', 'number'].includes(fieldType);
    const isDate = fieldType.startsWith('日期') || fieldType === 'date';

    if (isNumeric) {
      return {
        filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }: FilterDropdownProps) => {
          const filterState = selectedKeys[0] ? JSON.parse(selectedKeys[0] as string) : { op: '=', value: null, max: null };

          return (
            <div style={{ padding: 8 }} onKeyDown={e => e.stopPropagation()}>
              <Space style={{ marginBottom: 8, display: 'flex', flexDirection: 'column' }}>
                <Select
                  value={filterState.op}
                  onChange={op => setSelectedKeys([JSON.stringify({ ...filterState, op })])}
                  style={{ width: 120 }}
                  options={[
                    { value: '=', label: '等於' },
                    { value: '!=', label: '不等於' },
                    { value: '>', label: '大於' },
                    { value: '>=', label: '大於等於' },
                    { value: '<', label: '小於' },
                    { value: '<=', label: '小於等於' },
                    { value: 'between', label: '介於' },
                  ]}
                />
                {filterState.op === 'between' ? (
                  <Space>
                    <InputNumber
                      placeholder="數值"
                      value={filterState.value}
                      onChange={val => setSelectedKeys([JSON.stringify({ ...filterState, value: val })])}
                      onPressEnter={() => confirm()}
                    />
                    <span>-</span>
                    <InputNumber
                      placeholder="數值"
                      value={filterState.max}
                      onChange={val => setSelectedKeys([JSON.stringify({ ...filterState, max: val })])}
                      onPressEnter={() => confirm()}
                    />
                  </Space>
                ) : (
                  <InputNumber
                    placeholder="數值"
                    value={filterState.value}
                    onChange={val => setSelectedKeys([JSON.stringify({ ...filterState, value: val })])}
                    onPressEnter={() => confirm()}
                    style={{ width: '100%' }}
                  />
                )}
              </Space>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <Button onClick={() => { clearFilters?.(); confirm(); }} size="small" style={{ width: 80 }}>清除</Button>
                <Button type="primary" onClick={() => confirm()} size="small" style={{ width: 80 }}>篩選</Button>
              </div>
            </div>
          );
        },
        filterIcon: (filtered: boolean) => (
          <FilterOutlined style={{ color: filtered ? '#1677ff' : undefined }} />
        ),
        onFilter: (value, record) => {
          const cellVal = record[field.field_id];
          if (cellVal == null || cellVal === '') return false;
          const numVal = Number(cellVal);
          if (isNaN(numVal)) return false;

          try {
            const { op, value: val1, max: val2 } = JSON.parse(value as string);
            if (op === 'between') {
              if (val1 != null && numVal < val1) return false;
              if (val2 != null && numVal > val2) return false;
              return val1 != null || val2 != null;
            } else {
              if (val1 == null) return true;
              switch (op) {
                case '=': return numVal === val1;
                case '!=': return numVal !== val1;
                case '>': return numVal > val1;
                case '>=': return numVal >= val1;
                case '<': return numVal < val1;
                case '<=': return numVal <= val1;
                default: return true;
              }
            }
          } catch {
            return true;
          }
        },
      };
    }

    if (isDate) {
      return {
        filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }: FilterDropdownProps) => {
          const filterState = selectedKeys[0] ? JSON.parse(selectedKeys[0] as string) : null;
          const dates = filterState ? [dayjs(filterState.start), dayjs(filterState.end)] : null;

          return (
            <div style={{ padding: 8 }} onKeyDown={e => e.stopPropagation()}>
              <div style={{ marginBottom: 8 }}>
                <DatePicker.RangePicker
                  value={dates as [dayjs.Dayjs, dayjs.Dayjs] | null}
                  onChange={dates => {
                    if (dates && dates[0] && dates[1]) {
                      setSelectedKeys([JSON.stringify({ start: dates[0].toISOString(), end: dates[1].toISOString() })]);
                    } else {
                      setSelectedKeys([]);
                    }
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <Button onClick={() => { clearFilters?.(); confirm(); }} size="small" style={{ width: 80 }}>清除</Button>
                <Button type="primary" onClick={() => confirm()} size="small" style={{ width: 80 }}>篩選</Button>
              </div>
            </div>
          );
        },
        filterIcon: (filtered: boolean) => (
          <FilterOutlined style={{ color: filtered ? '#1677ff' : undefined }} />
        ),
        onFilter: (value, record) => {
          const cellVal = record[field.field_id];
          if (!cellVal) return false;

          try {
            const filterState = JSON.parse(value as string);
            if (!filterState || !filterState.start || !filterState.end) return true;

            const cellDate = dayjs(String(cellVal));
            if (!cellDate.isValid()) return false;

            const start = dayjs(filterState.start).startOf('day');
            const end = dayjs(filterState.end).endOf('day');

            return (cellDate.isAfter(start) || cellDate.isSame(start)) &&
              (cellDate.isBefore(end) || cellDate.isSame(end));
          } catch {
            return true;
          }
        },
      };
    }

    return {
      filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }: FilterDropdownProps) => (
        <div style={{ padding: 8 }} onKeyDown={e => e.stopPropagation()}>
          <Input
            ref={searchInputRef}
            placeholder="搜尋..."
            value={selectedKeys[0]}
            onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
            onPressEnter={() => confirm()}
            style={{ marginBottom: 8, display: 'block' }}
          />
          <Space>
            <Button
              type="primary"
              onClick={() => confirm()}
              icon={<SearchOutlined />}
              size="small"
              style={{ width: 80 }}
            >
              篩選
            </Button>
            <Button onClick={() => { clearFilters?.(); confirm(); }} size="small" style={{ width: 80 }}>
              清除
            </Button>
          </Space>
        </div>
      ),
      filterIcon: (filtered: boolean) => (
        <FilterOutlined style={{ color: filtered ? '#1677ff' : undefined }} />
      ),
      onFilter: (value, record) => {
        const cellVal = record[field.field_id];
        if (cellVal == null) return false;
        return String(cellVal).toLowerCase().includes(String(value).toLowerCase());
      },
      onFilterDropdownOpenChange: (open: boolean) => {
        if (open) setTimeout(() => searchInputRef.current?.select(), 100);
      },
    };
  };

  const tableColumns = dataFields.map((f, colIdx) => ({
    title: f.field_name || f.field_id,
    dataIndex: f.field_id,
    key: f.field_id,
    ellipsis: true,
    width: 160,
    onCell: (_record: Record<string, unknown>, rowIdx: number | undefined) => ({
      onMouseEnter: () => handleColHover(colIdx),
      onMouseLeave: () => handleColHover(null),
      onClick: () => actionTrail.record('cell_click', { tableId, field: f.field_id, fieldName: f.field_name, rowIdx }),
    }),
    onHeaderCell: () => ({
      onMouseEnter: () => handleColHover(colIdx),
      onMouseLeave: () => handleColHover(null),
    }),
    sorter: (a: Record<string, unknown>, b: Record<string, unknown>) => {
      const va = a[f.field_id];
      const vb = b[f.field_id];
      if (va == null && vb == null) return 0;
      if (va == null) return -1;
      if (vb == null) return 1;
      return String(va).localeCompare(String(vb), 'zh-Hant');
    },
    render: (v: unknown) => v == null ? '-' : String(v),
    ...getColumnSearchProps(f),
  }));

  return (
    <Modal
      title={tableName}
      open={visible}
      onCancel={onCancel}
      footer={null}
      width="90%"
      centered
      classNames={{ root: 'schema-preview-modal' }}
      styles={{
        root: { zIndex: 10001 },
        body: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' },
      }}
      zIndex={10001}
    >
      <style>{`
        .schema-preview-modal .ant-modal-content {
          height: 90%;
          display: flex;
          flex-direction: column;
        }
        .crosshair-table .ant-table-tbody > tr:hover > td {
          background: rgba(22, 119, 255, 0.12) !important;
        }
        .crosshair-table .crosshair-col-active {
          background: rgba(22, 119, 255, 0.12) !important;
        }
        .crosshair-table .ant-table-tbody > tr:hover > td.crosshair-col-active {
          background: rgba(22, 119, 255, 0.28) !important;
        }
        .crosshair-table .ant-table-thead > tr > th.crosshair-col-active {
          background: rgba(22, 119, 255, 0.12) !important;
        }
      `}</style>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Input.Search
          placeholder="全域搜尋資料內容"
          allowClear
          onSearch={(v) => { setSearchText(v); if (v) actionTrail.record('global_search', { tableId, keyword: v }); }}
          onChange={(e) => { if (!e.target.value) setSearchText(''); }}
          style={{ width: 300 }}
        />
        <Space size="middle">
          <Space size={4}>
            <Segmented
              size="small"
              value={fetchMode}
              onChange={v => { const m = v as 'paged' | 'all'; setFetchMode(m); onPreviewModeChange?.(m); actionTrail.record('mode_switch', { tableId, mode: m }); }}
              options={[
                { value: 'paged', icon: <FileOutlined />, label: '分頁' },
                { value: 'all', icon: <DatabaseOutlined />, label: '全部' },
              ]}
            />
            <Tooltip title="此設定為表級別共用，若多人使用同一張表，將以最後切換的模式為主。選擇「全部」時將載入整張表資料至本地 Cache，若資料量大將影響載入速度。">
              <QuestionCircleOutlined style={{ fontSize: 14, opacity: 0.45, cursor: 'pointer' }} />
            </Tooltip>
          </Space>
          {loadingProgress && (
            <span style={{ fontSize: 12, color: '#1677ff' }}>{loadingProgress}</span>
          )}
          {cachedAt && (
            <span style={{ fontSize: 12, opacity: 0.65 }}>
              本地 Cache 時間：<span style={{ color: warningColor }}>{cachedAt}</span>
            </span>
          )}
          {!cachedAt && fetchMode === 'paged' && !loading && (
            <span style={{ fontSize: 12, opacity: 0.5 }}>即時分頁查詢</span>
          )}
          <Tooltip title="重新從 Ragic 拉取資料">
            <Button
              icon={<ReloadOutlined />}
              size="small"
              onClick={handleRefresh}
              loading={loading}
            />
          </Tooltip>
        </Space>
      </div>
      <div ref={tableRef} style={{ flex: 1, overflow: 'hidden' }}>
        <Table
          className="crosshair-table"
          dataSource={filteredRows}
          rowKey={(_record, idx) => `row_${idx ?? 0}`}
          loading={loading}
          size="small"
          scroll={{ x: 'max-content', y: 'calc(80vh - 180px)' }}
          onRow={(_record, rowIdx) => ({
            onMouseEnter: () => actionTrail.startDwell(`${tableId}_row_${rowIdx}`, { tableId, rowIdx }),
            onMouseLeave: () => actionTrail.clearDwell(`${tableId}_row_${rowIdx}`),
          })}
          onChange={(_pagination, filters, sorter) => {
            if (sorter && !Array.isArray(sorter) && sorter.field) {
              actionTrail.record('column_sort', { tableId, field: sorter.field, order: sorter.order });
            }
            const activeFilters = Object.entries(filters).filter(([, v]) => v && v.length > 0);
            if (activeFilters.length > 0) {
              actionTrail.record('filter_apply', { tableId, filters: Object.fromEntries(activeFilters) });
            }
          }}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: totalRows,
            showSizeChanger: true,
            pageSizeOptions: PAGE_SIZE_OPTIONS,
            showTotal: (total) => fetchMode === 'all' ? `共 ${total} 筆（本地 Cache）` : `共約 ${total} 筆`,
            onChange: handlePageChange,
          }}
          columns={tableColumns}
        />
      </div>
    </Modal>
  );
}
