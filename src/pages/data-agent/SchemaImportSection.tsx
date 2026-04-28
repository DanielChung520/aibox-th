/**
 * @file        Data Agent Schema 導入區塊
 * @description Schema 頁面的資料表導入按鈕與上傳邏輯，含圖譜與意圖 Modal
 * @lastUpdate  2026-04-24 12:17:42
 * @author      Daniel Chung
 * @version     2.1.0
 */

import { useState, useRef } from 'react';
import { Button, Modal, Space, Typography, App } from 'antd';
import { ImportOutlined, ExclamationCircleOutlined, ApartmentOutlined, BookOutlined } from '@ant-design/icons';
import { dataAgentApi } from '../../services/dataAgentApi';
import SchemaGraphModal from './SchemaGraphModal';
import SchemaIntentModal from './SchemaIntentModal';

const { Text } = Typography;

const DEFAULT_ACCOUNT = 'dawnlink';

interface SchemaImportSectionProps {
  onImportSuccess: () => void;
}

export default function SchemaImportSection({ onImportSuccess }: SchemaImportSectionProps) {
  const { message } = App.useApp();
  const [importConfirmVisible, setImportConfirmVisible] = useState(false);
  const [importing, setImporting] = useState(false);
  const [graphOpen, setGraphOpen] = useState(false);
  const [intentOpen, setIntentOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImportClick = () => {
    setImportConfirmVisible(true);
  };

  const handleImportConfirm = () => {
    setImportConfirmVisible(false);
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImporting(true);
    const loadingMessage = message.loading('正在導入 Ragic 資料表定義...', 0);
    try {
      const content = await file.text();
      const res = await dataAgentApi.importRagicMd({
        account: DEFAULT_ACCOUNT,
        content
      });

      if (res.data.code === 0 && res.data.data) {
        const result = res.data.data;
        message.success(
          `導入完成：解析了 ${result.tables_parsed || 0} 個表單，` +
          `向量化 ${result.schemas_vectorized || 0} 個 Schema，` +
          `生成 ${result.intents_generated || 0} 個意圖`
        );
        onImportSuccess();
      } else {
        message.error(`導入失敗：${res.data.message || '未知錯誤'}`);
      }
    } catch (error: unknown) {
      if (error instanceof Error) {
        message.error(`導入失敗：${error.message}`);
      } else {
        message.error('導入失敗：檔案解析錯誤');
      }
    } finally {
      loadingMessage();
      setImporting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <>
      <Space.Compact>
        <Button icon={<ApartmentOutlined />} onClick={() => setGraphOpen(true)}>
          顯示圖譜
        </Button>
        <Button icon={<BookOutlined />} onClick={() => setIntentOpen(true)}>
          資料字典意圖
        </Button>
        <Button icon={<ImportOutlined />} onClick={handleImportClick} loading={importing}>
          導入 Ragic 資料表定義
        </Button>
      </Space.Compact>

      <input
        ref={fileInputRef}
        type="file"
        accept=".md"
        style={{ display: 'none' }}
        onChange={handleFileSelected}
      />

      <Modal
        title={
          <Space>
            <ExclamationCircleOutlined style={{ color: '#faad14' }} />
            <span>確認重新導入</span>
          </Space>
        }
        open={importConfirmVisible}
        onCancel={() => setImportConfirmVisible(false)}
        onOk={handleImportConfirm}
        okText="確認重新導入"
        cancelText="取消"
        okButtonProps={{ danger: true }}
        closable={false}
      >
        <div style={{ padding: '12px 0' }}>
          <p>此操作將會：</p>
          <ul style={{ paddingLeft: 20, margin: '8px 0' }}>
            <li><Text strong type="danger">清除</Text> 現有所有資料表定義（da_table_info_ragic）</li>
            <li><Text strong type="danger">清除</Text> 現有所有欄位定義（da_field_info_ragic）</li>
            <li>從選定的 Markdown 檔案重新解析並導入</li>
          </ul>
          <p><Text type="warning">此操作不可逆，請確認是否要繼續？</Text></p>
        </div>
      </Modal>

      <SchemaGraphModal open={graphOpen} onClose={() => setGraphOpen(false)} account={DEFAULT_ACCOUNT} />
      <SchemaIntentModal open={intentOpen} onClose={() => setIntentOpen(false)} />
    </>
  );
}
