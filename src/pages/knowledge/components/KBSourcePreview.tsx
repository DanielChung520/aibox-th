import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, InputNumber, Spin, Table, Typography, theme, Tag, Descriptions, Divider, Tooltip } from 'antd';
import {
  LeftOutlined, RightOutlined, ZoomInOutlined, ZoomOutOutlined,
  DownloadOutlined, FilePdfOutlined, FileMarkdownOutlined,
  FileTextOutlined, InboxOutlined, InfoCircleOutlined,
} from '@ant-design/icons';
import Markdown from 'markdown-to-jsx';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { knowledgeApi, KnowledgeFile, PreviewData } from '../../../services/api';
import ExcelViewer from '../../../components/ExcelViewer';
import DOCXViewer from '../../../components/DOCXViewer';

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const { Title, Text } = Typography;

interface TableRow extends Record<string, string | number> {
  key: string;
}

interface KBSourcePreviewProps {
  fileId: string;
  fileName: string;
  fileType: string;
}

function FileMetadataPanel({ file }: { file: KnowledgeFile }) {
  const { token } = theme.useToken();

  return (
    <div style={{
      width: 260,
      flexShrink: 0,
      borderLeft: `1px solid ${token.colorBorder}`,
      background: token.colorBgContainer,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'auto',
    }}>
      <div style={{ padding: '12px 16px', borderBottom: `1px solid ${token.colorBorder}` }}>
        <Text strong style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
          <InfoCircleOutlined /> 文件屬性
        </Text>
      </div>

      <div style={{ padding: '12px 16px', flex: 1, overflow: 'auto' }}>
        {file.ontology_major ? (
          <div style={{ marginBottom: 16 }}>
            <Text style={{ fontSize: 11, color: token.colorTextSecondary, display: 'block', marginBottom: 6 }}>
              專業領域 (Major)
            </Text>
            <Tag color="blue" style={{ fontSize: 12 }}>{file.ontology_major}</Tag>
          </div>
        ) : null}

        {file.document_type?.length ? (
          <div style={{ marginBottom: 16 }}>
            <Text style={{ fontSize: 11, color: token.colorTextSecondary, display: 'block', marginBottom: 6 }}>
              文件類型
            </Text>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {file.document_type.map(t => (
                <Tag key={t} style={{ fontSize: 11 }}>{t}</Tag>
              ))}
            </div>
          </div>
        ) : null}

        {file.document_summary ? (
          <div style={{ marginBottom: 16 }}>
            <Text style={{ fontSize: 11, color: token.colorTextSecondary, display: 'block', marginBottom: 6 }}>
              文件摘要
            </Text>
            <div style={{
              fontSize: 12,
              color: token.colorText,
              lineHeight: 1.6,
              background: token.colorBgLayout,
              borderRadius: 6,
              padding: '8px 10px',
              whiteSpace: 'pre-wrap',
            }}>
              {file.document_summary}
            </div>
          </div>
        ) : null}

        <Divider style={{ margin: '12px 0' }} />

        <Descriptions column={1} size="small" style={{ fontSize: 11 }}>
          <Descriptions.Item label="檔案名稱">
            <Tooltip title={file.filename}>
              <span style={{ fontSize: 11, wordBreak: 'break-all' }}>{file.filename}</span>
            </Tooltip>
          </Descriptions.Item>
          <Descriptions.Item label="格式">
            <Tag style={{ fontSize: 10 }}>{file.file_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="大小">
            {file.file_size < 1024 * 1024
              ? `${(file.file_size / 1024).toFixed(1)} KB`
              : `${(file.file_size / (1024 * 1024)).toFixed(1)} MB`}
          </Descriptions.Item>
          <Descriptions.Item label="上傳時間">{file.upload_time}</Descriptions.Item>
          <Descriptions.Item label="向量狀態">
            <Tag color={
              file.vector_status === 'completed' ? 'success' :
              file.vector_status === 'failed' ? 'error' : 'default'
            } style={{ fontSize: 10 }}>
              {file.vector_status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="圖譜狀態">
            <Tag color={
              file.graph_status === 'completed' ? 'success' :
              file.graph_status === 'failed' ? 'error' : 'default'
            } style={{ fontSize: 10 }}>
              {file.graph_status}
            </Tag>
          </Descriptions.Item>
        </Descriptions>
      </div>
    </div>
  );
}

export default function KBSourcePreview({ fileId, fileName, fileType }: KBSourcePreviewProps) {
  const { token } = theme.useToken();
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [fileMeta, setFileMeta] = useState<KnowledgeFile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [pdfNumPages, setPdfNumPages] = useState(0);
  const [pdfPage, setPdfPage] = useState(1);
  const [pdfScale, setPdfScale] = useState(1.0);
  const [pdfData, setPdfData] = useState<string | ArrayBuffer | null>(null);

  useEffect(() => {
    let active = true;
    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      setPdfPage(1);
      setPdfNumPages(0);
      setPdfData(null);
      try {
        const [previewRes, fileMetaRes] = await Promise.all([
          knowledgeApi.getPreview(fileId),
          knowledgeApi.getFile(fileId).catch(() => null),
        ]);
        if (!active) return;

        if (fileMetaRes?.data?.data) setFileMeta(fileMetaRes.data.data);

        setPreview(previewRes.data.data);
        if (previewRes.data.data?.type === 'pdf_url' && previewRes.data.data?.url) {
          fetchPdfBlob(`/api/v1/knowledge/files/${fileId}/download`);
        }
      } catch (e: unknown) {
        if (!active) return;
        const err = e as { response?: { data?: { message?: string } } };
        setPreview(null);
        setError(err.response?.data?.message || '載入文件預覽失敗');
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchAll();
    return () => { active = false; };
  }, [fileId]);

  const fetchPdfBlob = async (url: string) => {
    try {
      const token = localStorage.getItem('token');
      const resp = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      if (blob.size === 0) throw new Error('PDF 為空');
      const buf = await blob.arrayBuffer();
      setPdfData(buf);
    } catch (err) {
      setError(`PDF 載入失敗: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const pdfOptions = useMemo(() => ({
    cMapUrl: `https://unpkg.com/pdfjs-dist@${pdfjs.version}/cmaps/`,
    cMapPacked: true,
    standardFontDataUrl: `https://unpkg.com/pdfjs-dist@${pdfjs.version}/standard_fonts/`,
  }), []);

  const tableColumns = useMemo(() => {
    return (preview?.headers || []).map((header) => ({
      title: header,
      dataIndex: header,
      key: header,
      ellipsis: true as const,
      width: 180,
    }));
  }, [preview?.headers]);

  const tableData = useMemo<TableRow[]>(() => {
    return (preview?.rows || []).map((row, index) => ({
      key: `${fileId}_${index}`,
      ...row,
    }));
  }, [fileId, preview?.rows]);

  const getIcon = () => {
    if (fileType.includes('pdf')) return <FilePdfOutlined style={{ color: token.colorError }} />;
    if (fileType.includes('markdown')) return <FileMarkdownOutlined style={{ color: token.colorPrimary }} />;
    if (fileType.includes('csv') || fileType.includes('excel') || fileType.includes('sheet')) {
      return <FileTextOutlined style={{ color: token.colorSuccess }} />;
    }
    return <InboxOutlined style={{ color: token.colorTextSecondary }} />;
  };

  const rightPanel = fileMeta ? <FileMetadataPanel file={fileMeta} /> : null;

  const containerStyle: React.CSSProperties = {
    display: 'flex', flex: 1, minHeight: 0,
    overflow: 'hidden',
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={containerStyle}>
        <div style={{ flex: 1, padding: token.paddingLG, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Alert type="error" showIcon description={<><Text strong>預覽載入失敗</Text><br />{error}</>} />
        </div>
        {rightPanel}
      </div>
    );
  }

  if (!preview) {
    return (
      <div style={containerStyle}>
        <div style={{ flex: 1, padding: token.paddingLG, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Alert type="warning" showIcon description="尚無可顯示的內容" />
        </div>
        {rightPanel}
      </div>
    );
  }

  const headerEl = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 22 }}>{getIcon()}</span>
      <div>
        <Title level={4} style={{ margin: 0 }}>{fileName}</Title>
        <Text type="secondary" style={{ fontSize: 12 }}>{fileType}</Text>
      </div>
    </div>
  );

  if (preview.type === 'markdown' || preview.type === 'text') {
    return (
      <div style={containerStyle}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: token.paddingLG, gap: token.marginSM }}>
          <div>{headerEl}</div>
          <div style={{ flex: 1, overflow: 'auto', border: `1px solid ${token.colorBorder}`, borderRadius: token.borderRadius, background: token.colorBgContainer }}>
            <div style={{ padding: token.paddingLG }}>
              <Markdown>{preview.content || ''}</Markdown>
            </div>
          </div>
        </div>
        {rightPanel}
      </div>
    );
  }

  if (preview.type === 'pdf_url') {
    return (
      <div style={containerStyle}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: token.paddingLG, gap: token.marginSM }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 22 }}>{getIcon()}</span>
            <div>
              <Title level={4} style={{ margin: 0 }}>{fileName}</Title>
              <Text type="secondary" style={{ fontSize: 12 }}>{fileType}</Text>
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
              <Button icon={<LeftOutlined />} size="small" disabled={pdfPage <= 1} onClick={() => setPdfPage((p) => Math.max(1, p - 1))} />
              <InputNumber size="small" min={1} max={pdfNumPages || 1} value={pdfPage}
                onChange={(v) => setPdfPage(Math.max(1, Math.min(pdfNumPages || 1, v || 1)))} style={{ width: 56, fontSize: 12 }} />
              <span style={{ fontSize: 12 }}>/ {pdfNumPages || '?'}</span>
              <Button icon={<RightOutlined />} size="small" disabled={pdfPage >= (pdfNumPages || 1)} onClick={() => setPdfPage((p) => Math.min(pdfNumPages || 1, p + 1))} />
              <Button icon={<ZoomOutOutlined />} size="small" disabled={pdfScale <= 0.5} onClick={() => setPdfScale((s) => Math.max(0.5, s - 0.2))} />
              <span style={{ fontSize: 12, minWidth: 44, textAlign: 'center' }}>{Math.round(pdfScale * 100)}%</span>
              <Button icon={<ZoomInOutlined />} size="small" disabled={pdfScale >= 3.0} onClick={() => setPdfScale((s) => Math.min(3.0, s + 0.2))} />
              {preview.url && (
                <Button type="primary" icon={<DownloadOutlined />} size="small"
                  onClick={() => window.open(`/api/v1/knowledge/files/${fileId}/download`, '_blank')}>
                  下載
                </Button>
              )}
            </div>
          </div>
          <div style={{ flex: 1, overflow: 'auto', border: `1px solid ${token.colorBorder}`, borderRadius: token.borderRadius, background: token.colorBgLayout, display: 'flex', justifyContent: 'center', padding: token.padding }}>
            {!pdfData ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <Spin />
              </div>
            ) : (
              <Document
                file={pdfData}
                onLoadSuccess={({ numPages: n }) => setPdfNumPages(n)}
                onLoadError={(e) => setError(`PDF 載入錯誤: ${e.message}`)}
                options={pdfOptions}
                loading={<Spin />}
                error={<Alert type="error" message="PDF 載入失敗，請嘗試下載後觀看" />}
              >
                <Page pageNumber={pdfPage} scale={pdfScale} renderTextLayer renderAnnotationLayer />
              </Document>
            )}
          </div>
        </div>
        {rightPanel}
      </div>
    );
  }

  const isExcel = /xlsx|xls|spreadsheet/i.test(fileType);
  const isDocx = /docx|doc|word/i.test(fileType);

  if (isExcel) {
    return (
      <div style={containerStyle}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: token.paddingLG, gap: token.marginSM }}>
          <div>{headerEl}</div>
          <div style={{ flex: 1, minHeight: 0 }}>
            <ExcelViewer fileId={fileId} fileName={fileName} fileType={fileType} />
          </div>
        </div>
        {rightPanel}
      </div>
    );
  }

  if (isDocx) {
    return (
      <div style={containerStyle}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: token.paddingLG, gap: token.marginSM }}>
          <div>{headerEl}</div>
          <div style={{ flex: 1, minHeight: 0 }}>
            <DOCXViewer fileId={fileId} fileName={fileName} fileType={fileType} />
          </div>
        </div>
        {rightPanel}
      </div>
    );
  }

  if (preview.type === 'table') {
    return (
      <div style={containerStyle}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: token.paddingLG, gap: token.marginSM }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <span style={{ fontSize: 22 }}>{getIcon()}</span>
            <div>
              <Title level={4} style={{ margin: 0 }}>{fileName}</Title>
              <Text type="secondary" style={{ fontSize: 12 }}>{fileType}</Text>
            </div>
            <Text type="secondary" style={{ marginLeft: 'auto' }}>{tableData.length} 筆資料</Text>
          </div>
          <div id={`table-wrap-${fileId}`} style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
            <Table<TableRow>
              columns={tableColumns}
              dataSource={tableData}
              pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ['20', '50', '100', '200'] }}
              scroll={{ x: 'max-content', y: 'calc(100vh - 400px)' }}
              size="small"
            />
          </div>
        </div>
        {rightPanel}
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: token.paddingLG, gap: token.marginSM }}>
        <div>{headerEl}</div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: token.marginSM }}>
          <Alert type="info" showIcon description={preview.message || '此檔案類型無法內嵌預覽，請下載後觀看。'} />
          <Button type="primary" icon={<DownloadOutlined />} size="large"
            href={`/api/v1/knowledge/files/${encodeURIComponent(fileId)}/download`} target="_blank">
            下載檔案
          </Button>
        </div>
      </div>
      {rightPanel}
    </div>
  );
}
