/**
 * @file        Data Agent Schema 資料預覽
 * @description Schema 頁面的資料預覽 Modal 元件
 * @lastUpdate  2026-04-11 18:13:37
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Modal, Table, App } from 'antd';
import { dataAgentApi, FieldInfo } from '../../services/dataAgentApi';

interface SchemaDataPreviewModalProps {
  visible: boolean;
  tableId: string;
  tableName: string;
  onCancel: () => void;
}

export default function SchemaDataPreviewModal({
  visible,
  tableId,
  tableName,
  onCancel,
}: SchemaDataPreviewModalProps) {
  const { message } = App.useApp();
  const [dataRows, setDataRows] = useState<Record<string, unknown>[]>([]);
  const [dataFields, setDataFields] = useState<FieldInfo[]>([]);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataTotal, setDataTotal] = useState(0);
  const [dataPage, setDataPage] = useState(1);
  const [dataPageSize, setDataPageSize] = useState(20);

  const loadData = async (page: number, pageSize: number) => {
    if (!tableId || !visible) return;
    
    setDataLoading(true);
    setDataPage(page);
    setDataPageSize(pageSize);
    try {
      const res = await dataAgentApi.ragicProxyData(tableId, (page - 1) * pageSize, pageSize);
      const resData = res.data;
      if (resData.code !== 0 && resData.message) {
        message.error(`Ragic API 錯誤: ${resData.message}`);
      }
      setDataRows(resData.rows || []);
      // Only update fields on first load (or whenever)
      if (resData.fields && resData.fields.length > 0) {
        setDataFields(resData.fields);
      }
      setDataTotal(resData.total || 0);
    } catch {
      message.error('載入資料失敗');
      setDataRows([]);
      if (page === 1) setDataFields([]);
      setDataTotal(0);
    } finally {
      setDataLoading(false);
    }
  };

  useEffect(() => {
    if (visible && tableId) {
      loadData(1, 20);
    } else {
      setDataRows([]);
      setDataFields([]);
      setDataTotal(0);
      setDataPage(1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, tableId]);

  const handlePageChange = (page: number, pageSize: number) => {
    loadData(page, pageSize);
  };

  return (
    <Modal
      title={tableName}
      open={visible}
      onCancel={onCancel}
      footer={null}
      width="80%"
    >
      <Table
        dataSource={dataRows}
        rowKey={(_record, idx) => `row_${idx ?? 0}`}
        loading={dataLoading}
        size="small"
        scroll={{ x: 'max-content' }}
        pagination={{
          current: dataPage,
          pageSize: dataPageSize,
          total: dataTotal,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 筆`,
          onChange: handlePageChange,
        }}
        columns={dataFields.map(f => ({
          title: f.field_name || f.field_id,
          dataIndex: f.field_id,
          key: f.field_id,
          ellipsis: true,
          width: 160,
          render: (v: unknown) => v == null ? '-' : String(v),
        }))}
      />
    </Modal>
  );
}
