import { useEffect, useRef, useState } from 'react';
import { Button, Modal, message } from 'antd';
import { FullscreenOutlined, FileTextOutlined, InsertRowAboveOutlined, CopyOutlined, CheckOutlined, ZoomInOutlined, AimOutlined } from '@ant-design/icons';
import mermaid from 'mermaid';
import { useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';

function sanitizeMermaidCode(code: string): string {
  return code
    .replace(/【/g, '[')
    .replace(/】/g, ']')
    .replace(/（/g, '(')
    .replace(/）/g, ')')
    .replace(/《/g, '<')
    .replace(/》/g, '>')
    .replace(/「/g, "'")
    .replace(/」/g, "'")
    .replace(/"/g, "'")
    .replace(/"/g, "'");
}

const DARK_MERMAID_VARS = {
  primaryColor: '#3b82f6',
  primaryTextColor: '#f1f5f9',
  primaryBorderColor: '#3b82f6',
  lineColor: '#8892a0',
  secondaryColor: '#1e293b',
  tertiaryColor: '#0f172a',
  background: '#1e293b',
  mainBkg: '#1e293b',
  nodeBorder: '#3b82f6',
  clusterBkg: '#0f172a',
  titleColor: '#f1f5f9',
  edgeLabelBackground: '#1e293b',
};

const LIGHT_MERMAID_VARS = {
  primaryColor: '#3b82f6',
  primaryTextColor: '#1e293b',
  primaryBorderColor: '#3b82f6',
  lineColor: '#64748b',
  secondaryColor: '#f1f5f9',
  tertiaryColor: '#e2e8f0',
  background: '#ffffff',
  mainBkg: '#f8fafc',
  nodeBorder: '#3b82f6',
  clusterBkg: '#f1f5f9',
  titleColor: '#1e293b',
  edgeLabelBackground: '#ffffff',
};

mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: DARK_MERMAID_VARS,
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
});

interface MermaidToggleProps {
  code: string;
}

export default function MermaidToggle({ code }: MermaidToggleProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const modalSvgRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [viewMode, setViewMode] = useState<'diagram' | 'code'>('diagram');
  const [error, setError] = useState(false);
  const [copied, setCopied] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalSvgCopied, setModalSvgCopied] = useState(false);
  const [modalScale, setModalScale] = useState(1);
  const [id] = useState(() => `mermaid-${Math.random().toString(36).slice(2, 9)}`);
  const contentTokens = useContentTokens();
  const effectiveTheme = useEffectiveTheme();
  const isDark = effectiveTheme === 'dark';

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'base',
      themeVariables: isDark ? DARK_MERMAID_VARS : LIGHT_MERMAID_VARS,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    });
  }, [isDark]);

  useEffect(() => {
    let cancelled = false;

    async function render() {
      const sanitized = sanitizeMermaidCode(code.trim());
      try {
        await mermaid.parse(sanitized);
      } catch {
        if (!cancelled) {
          setError(true);
          setSvg('');
        }
        return;
      }

      try {
        const { svg: rendered } = await mermaid.render(id, sanitized);
        if (!cancelled) {
          setSvg(rendered);
          setError(false);
        }
      } catch (e) {
        if (!cancelled) {
          setError(true);
          setSvg('');
        }
        const div = document.getElementById(`dmermaid-${id}`);
        div?.remove();
      }
    }

    void render();

    return () => { cancelled = true; };
  }, [code, id]);

  useEffect(() => {
    setModalScale(1);
  }, [modalOpen]);

  const handleCopy = () => {
    void navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      message.success('已複製到剪貼簿');
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (error) {
    return (
      <div style={{
        borderRadius: 8,
        border: '1px solid rgba(239,68,68,0.4)',
        background: contentTokens.chatAssistantBubble,
        padding: '12px 16px',
        marginTop: 8,
        marginBottom: 8,
        fontSize: 13,
        color: '#ef4444',
        fontFamily: 'monospace',
      }}>
        <strong>Mermaid 解析錯誤</strong>
        <pre style={{ margin: '8px 0 0', whiteSpace: 'pre-wrap', fontSize: 12 }}>{code}</pre>
      </div>
    );
  }

  const borderColor = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)';
  const labelColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.45)';
  const btnColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.45)';
  const activeColor = '#3b82f6';
  const successColor = '#22c55e';
  const headerBg = isDark ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.06)';
  const codeBg = isDark ? 'rgba(0,0,0,0.3)' : 'rgba(0,0,0,0.06)';
  const codeColor = isDark ? '#e2e8f0' : '#334155';

  const handleModalCopySvg = () => {
    void navigator.clipboard.writeText(svg).then(() => {
      setModalSvgCopied(true);
      message.success('已複製 SVG 到剪貼簿');
      setTimeout(() => setModalSvgCopied(false), 2000);
    });
  };

  return (
    <>
      <div style={{
        borderRadius: 8,
        border: `1px solid ${borderColor}`,
        background: contentTokens.chatAssistantBubble,
        marginTop: 8,
        marginBottom: 8,
        overflow: 'hidden',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 12px',
          background: headerBg,
          borderBottom: `1px solid ${borderColor}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 11, color: labelColor, fontFamily: 'monospace' }}>
              Mermaid 圖表
            </span>
            <Button
              type="text"
              size="small"
              icon={<InsertRowAboveOutlined />}
              onClick={() => setViewMode('diagram')}
              style={{ fontSize: 11, height: 22, padding: '0 6px', color: viewMode === 'diagram' ? activeColor : btnColor }}
            >
              圖形
            </Button>
            <Button
              type="text"
              size="small"
              icon={<FileTextOutlined />}
              onClick={() => setViewMode('code')}
              style={{ fontSize: 11, height: 22, padding: '0 6px', color: viewMode === 'code' ? activeColor : btnColor }}
            >
              程式碼
            </Button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Button
              type="text"
              size="small"
              icon={copied ? <CheckOutlined /> : <CopyOutlined />}
              onClick={handleCopy}
              style={{ color: copied ? successColor : btnColor, fontSize: 11, height: 22, padding: '0 6px' }}
            >
              {copied ? '已複製' : '複製'}
            </Button>
            <Button
              type="text"
              size="small"
              icon={<FullscreenOutlined />}
              onClick={() => setModalOpen(true)}
              style={{ color: btnColor, fontSize: 11, height: 22, padding: '0 6px' }}
            >
              全螢幕
            </Button>
          </div>
        </div>

        {viewMode === 'diagram' ? (
          !svg ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px', fontSize: 12, color: labelColor }}>
              <span style={{ animation: 'dotBounce 1.4s ease-in-out infinite' }}>●</span>
              正在渲染 Mermaid 圖表...
            </div>
          ) : (
            <div
              ref={containerRef}
              style={{ padding: '8px 16px', overflow: 'auto', maxHeight: 400, overflowX: 'auto' }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          )
        ) : (
          <div style={{ padding: '12px 16px' }}>
            <pre style={{
              margin: 0, background: codeBg, borderRadius: 6, padding: '12px 16px',
              fontSize: 12, lineHeight: 1.6,
              fontFamily: '"Fira Code", "Cascadia Code", Consolas, monospace',
              color: codeColor, whiteSpace: 'pre-wrap', wordBreak: 'break-all', overflow: 'hidden', maxHeight: 300,
            }}>
              {code}
            </pre>
          </div>
        )}
      </div>

      <Modal
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setModalScale(1); }}
        footer={null}
        width="80vw"
        style={{ top: 40 }}
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 13 }}>Mermaid 圖表</span>
            <span style={{ fontSize: 11, color: labelColor, fontFamily: 'monospace' }}>{Math.round(modalScale * 100)}%</span>
            <Button type="text" size="small" icon={<ZoomInOutlined />} onClick={() => setModalScale((s) => Math.min(s + 0.2, 5))} style={{ color: btnColor, fontSize: 12, height: 24, padding: '0 4px' }} />
            <Button type="text" size="small" icon={<AimOutlined />} onClick={() => setModalScale(1)} style={{ color: btnColor, fontSize: 12, height: 24, padding: '0 4px' }} />
            <Button type="text" size="small" icon={<ZoomInOutlined style={{ transform: 'scaleY(-1)' }} />} onClick={() => setModalScale((s) => Math.max(s - 0.2, 0.2))} style={{ color: btnColor, fontSize: 12, height: 24, padding: '0 4px' }} />
            <span style={{ width: 1, height: 16, background: labelColor, margin: '0 4px' }} />
            <Button type="text" size="small" icon={<CopyOutlined />} onClick={handleModalCopySvg} style={{ color: modalSvgCopied ? successColor : btnColor, fontSize: 12, height: 24, padding: '0 4px' }}>
              {modalSvgCopied ? '已複製' : '複製 SVG'}
            </Button>
            <Button type="text" size="small" icon={<FileTextOutlined />} onClick={() => { void navigator.clipboard.writeText(code).then(() => { message.success('已複製程式碼'); }); }} style={{ color: btnColor, fontSize: 12, height: 24, padding: '0 4px' }}>
              程式碼
            </Button>
          </div>
        }
        styles={{ body: { background: contentTokens.chatAssistantBubble, padding: 24 } }}
      >
        {svg ? (
          <div
            ref={modalSvgRef}
            style={{ overflow: 'auto', maxHeight: 'calc(80vh - 120px)', cursor: modalScale !== 1 ? 'grab' : 'default', userSelect: 'none' }}
          >
            <div style={{ transform: `scale(${modalScale})`, transformOrigin: 'top left', transition: 'transform 0.1s ease' }} dangerouslySetInnerHTML={{ __html: svg }} />
          </div>
        ) : (
          <pre style={{
            margin: 0, background: codeBg, borderRadius: 6, padding: '16px 24px',
            fontSize: 13, lineHeight: 1.6,
            fontFamily: '"Fira Code", "Cascadia Code", Consolas, monospace',
            color: codeColor, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          }}>
            {code}
          </pre>
        )}
      </Modal>
    </>
  );
}
