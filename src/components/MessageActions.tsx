/**
 * @file        訊息操作按鈕列元件
 * @description AI 訊息下方的操作按鈕：複製、重新生成等
 */

import { Button, message } from 'antd';
import { CopyOutlined, ReloadOutlined } from '@ant-design/icons';

interface MessageActionsProps {
  messageId: string;
  messageContent: string;
  onRegenerate?: () => void;
}

export default function MessageActions({ messageContent, onRegenerate }: MessageActionsProps) {
  const handleCopy = () => {
    void navigator.clipboard.writeText(messageContent).then(() => {
      message.success('已複製到剪貼簿');
    });
  };

  return (
    <div style={{
      display: 'flex',
      gap: 4,
      marginTop: 8,
      opacity: 0.6,
    }}>
      <Button
        type="text"
        size="small"
        icon={<CopyOutlined />}
        onClick={handleCopy}
        style={{ fontSize: 11, color: 'inherit', height: 24, padding: '0 4px' }}
      >
        複製
      </Button>
      {onRegenerate && (
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined />}
          onClick={onRegenerate}
          style={{ fontSize: 11, color: 'inherit', height: 24, padding: '0 4px' }}
        >
          重新生成
        </Button>
      )}
    </div>
  );
}
