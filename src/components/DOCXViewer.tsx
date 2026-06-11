import { useEffect, useState } from 'react';
import { Alert, Spin, Typography, theme } from 'antd';
import { FileWordOutlined } from '@ant-design/icons';
import mammoth from 'mammoth';
import { downloadFile } from '../services/api';

const { Title, Text } = Typography;

interface DOCXViewerProps {
  fileId: string;
  fileName: string;
  fileType: string;
}

export default function DOCXViewer({ fileId, fileName, fileType }: DOCXViewerProps) {
  const { token } = theme.useToken();
  const [html, setHtml] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const blob = await downloadFile(fileId);
        if (!active) return;
        if (blob.size === 0) throw new Error('下載的檔案為空');
        const buf = await blob.arrayBuffer();
        const result = await mammoth.convertToHtml({ arrayBuffer: buf });
        setHtml(result.value);
      } catch (e: unknown) {
        if (!active) return;
        const err = e as { message?: string };
        setError(err.message || '無法載入 DOCX 檔案');
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => { active = false; };
  }, [fileId]);

  if (loading) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: 'flex', flex: 1, padding: token.paddingLG, minHeight: 0 }}>
        <Alert type="error" showIcon description={<><Text strong>載入失敗</Text><br />{error}</>} />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, padding: token.paddingLG, gap: token.marginSM }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <FileWordOutlined style={{ fontSize: 22, color: token.colorPrimary }} />
        <div>
          <Title level={4} style={{ margin: 0 }}>{fileName}</Title>
          <Text type="secondary">{fileType}</Text>
        </div>
      </div>
      <div style={{
        flex: 1, overflow: 'auto',
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: token.borderRadius,
        backgroundColor: token.colorBgContainer,
        padding: token.paddingLG,
      }}>
        {html && (
          <div
            style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        )}
      </div>
    </div>
  );
}
