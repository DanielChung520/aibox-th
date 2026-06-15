/**
 * @file        AIAssistantDrawer.tsx
 * @description 艾企 AI 助手側邊抽屜面板 — 基於 Ant Design Drawer 的骨架元件
 *              Header: 用戶頭像 + 標題 + 新對話按鈕 + 關閉按鈕
 *              Body:   空白訊息容器（由後續 Task 實作）
 *              Footer: Input + 發送按鈕 + 附加檔案按鈕（純 UI，無邏輯）
 * @lastUpdate  2026-06-15 16:00:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { Drawer, Input, Button, Avatar, Tooltip } from 'antd';
import {
  SendOutlined,
  PlusOutlined,
  RobotOutlined,
  PaperClipOutlined,
} from '@ant-design/icons';
import './AIAssistantDrawer.css';

interface AIAssistantDrawerProps {
  /** 控制 Drawer 開關 */
  open: boolean;
  /** Drawer 關閉回呼 */
  onClose: () => void;
}

export default function AIAssistantDrawer({ open, onClose }: AIAssistantDrawerProps) {
  return (
    <Drawer
      placement="right"
      open={open}
      onClose={onClose}
      destroyOnClose={false}
      rootClassName="ai-drawer"
      styles={{
        wrapper: { width: 480 },
        body: { padding: 0, overflow: 'hidden' },
      }}
      title={
        <div className="ai-drawer__header-title">
          <Avatar
            size={28}
            icon={<RobotOutlined />}
          />
          <span className="ai-drawer__header-text">艾企 AI 助手</span>
        </div>
      }
      extra={
        <Tooltip title="開始新對話">
          <Button
            type="text"
            icon={<PlusOutlined />}
            className="ai-drawer__new-chat-btn"
          />
        </Tooltip>
      }
    >
      <div className="ai-drawer__container">
        {/* Messages area — will be populated by future tasks (T5-T8) */}
        <div className="ai-drawer__messages" />

        {/* Footer — UI only, no logic */}
        <div className="ai-drawer__footer">
          <Tooltip title="附加檔案">
            <Button
              type="text"
              icon={<PaperClipOutlined />}
              className="ai-drawer__footer-btn"
            />
          </Tooltip>
          <Input
            placeholder="輸入消息...（支援 Markdown）"
            className="ai-drawer__footer-input"
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            className="ai-drawer__footer-send"
          />
        </div>
      </div>
    </Drawer>
  );
}
