import { useEffect, useMemo, useState } from 'react';
import { Alert, Spin, Table, Typography, theme } from 'antd';
import { FileExcelOutlined } from '@ant-design/icons';
import * as XLSX from 'xlsx';
import { downloadFile } from '../services/api';

const { Title, Text } = Typography;

interface SheetData {
  name: string;
  data: unknown[][];
}

interface ExcelViewerProps {
  fileId: string;
  fileName: string;
  fileType: string;
}

export default function ExcelViewer({ fileId, fileName, fileType }: ExcelViewerProps) {
  const { token } = theme.useToken();
  const [sheets, setSheets] = useState<SheetData[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
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
        const wb = XLSX.read(buf, { type: 'array' });
        const sheetData: SheetData[] = wb.SheetNames.map((name) => {
          const ws = wb.Sheets[name];
          return {
            name,
            data: XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' }) as unknown[][],
          };
        });
        setSheets(sheetData);
        setActiveIndex(0);
      } catch (e: unknown) {
        if (!active) return;
        const err = e as { message?: string };
        setError(err.message || '無法載入 Excel 檔案');
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => { active = false; };
  }, [fileId]);

  const active = sheets[activeIndex];
  const headers = active?.data[0] as string[] ?? [];
  const rows = active?.data.slice(1) ?? [];

  const columns = useMemo(() =>
    headers.map((h) => ({ title: h, dataIndex: h, key: h, ellipsis: true as const, width: 180 })),
    [headers],
  );

  const dataSource = useMemo(() =>
    rows.map((row, ri) => {
      const obj: Record<string, unknown> = { key: ri };
      headers.forEach((h, ci) => { obj[h] = row[ci] ?? ''; });
      return obj;
    }),
    [rows, headers],
  );

  if (loading) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: token.paddingLG }}>
        <Alert type="error" showIcon description={<><Text strong>載入失敗</Text><br />{error}</>} />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, padding: `${token.paddingSM}px ${token.paddingLG}px` }}>
        <FileExcelOutlined style={{ fontSize: 22, color: token.colorSuccess }} />
        <div>
          <Title level={4} style={{ margin: 0 }}>{fileName}</Title>
          <Text type="secondary">{fileType}</Text>
        </div>
        {sheets.length > 1 && (
          <div style={{ marginLeft: token.margin, display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            {sheets.map((s, i) => (
              <a key={i} onClick={() => setActiveIndex(i)} style={{
                padding: '2px 8px',
                borderRadius: token.borderRadius,
                background: i === activeIndex ? token.colorPrimary : token.colorBgLayout,
                color: i === activeIndex ? '#fff' : token.colorText,
                cursor: 'pointer',
                fontSize: 12,
              }}>
                {s.name}
              </a>
            ))}
            <Text type="secondary" style={{ fontSize: 12 }}>{activeIndex + 1} / {sheets.length}</Text>
          </div>
        )}
      </div>
      <div style={{ flex: 1, minHeight: 0, padding: `0 ${token.paddingLG}px ${token.paddingSM}px` }}>
        {active && headers.length > 0 ? (
          <Table
            dataSource={dataSource}
            columns={columns}
            pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ['20', '50', '100'] }}
            size="small"
            scroll={{ x: 'max-content', y: 'calc(100vh - 400px)' }}
          />
        ) : (
          <Alert type="warning" showIcon description="此工作表為空" />
        )}
      </div>
    </div>
  );
}
