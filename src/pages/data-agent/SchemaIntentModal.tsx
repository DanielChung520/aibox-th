/**
 * @file        資料字典意圖 Modal
 * @description 嵌入 DataAgentTables 組件，展示 da_tables / da_intents 意圖管理
 * @lastUpdate  2026-04-13 12:00:00
 * @author      Daniel Chung
 * @version     4.0.0
 */

import { Modal } from 'antd';
import DataAgentTables from '../DataAgentTables';

interface SchemaIntentModalProps {
  open: boolean;
  onClose: () => void;
}

export default function SchemaIntentModal({ open, onClose }: SchemaIntentModalProps) {
  return (
    <Modal
      title="DataAgent 意圖表管理"
      open={open}
      onCancel={onClose}
      footer={null}
      width="94vw"
      styles={{ body: { height: '85vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 } }}
      destroyOnHidden
    >
      <DataAgentTables fillHeight />
    </Modal>
  );
}
