/**
 * @file        文件內容預覽元件
 * @description 文件源文件/圖譜/向量 Tab 預覽，知識庫與 AI 聊天複用
 * @lastUpdate  2026-03-26 00:00:00
 * @author      Daniel Chung
 * @version     1.1.0
 */

import { Tabs, Button, theme } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { useContext } from 'react';
import type { Graph } from '@antv/g6';
import type { GraphNode, GraphEdge } from '../services/api';
import { ThemeContext } from '../contexts/AppThemeProvider';
import KBSourcePreview from '../pages/knowledge/components/KBSourcePreview';
import KBGraphPanel from '../pages/knowledge/components/KBGraphPanel';
import KBVectorPanel from '../pages/knowledge/components/KBVectorPanel';

interface FileContentViewerProps {
  fileId: string;
  fileName: string;
  fileType: string;
  activeTab?: string;
  graphStatus?: string;
  vectorStatus?: string;
  onActiveTabChange?: (tab: string) => void;
  onSettingsClick?: () => void;
  onGraphReady?: (graph: Graph) => void;
  onNodeSelect?: (nodeId: string | null) => void;
  onDataLoaded?: (nodes: GraphNode[], edges: GraphEdge[]) => void;
}

export default function FileContentViewer({
  fileId, fileName, fileType, activeTab = 'source', graphStatus, vectorStatus,
  onActiveTabChange, onSettingsClick, onGraphReady, onNodeSelect, onDataLoaded,
}: FileContentViewerProps) {
  const { token } = theme.useToken();
  const { contentTokens } = useContext(ThemeContext);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden',
      background: token.colorBgContainer,
      borderRadius: contentTokens.borderRadius,
      border: `1px solid ${token.colorBorderSecondary}`,
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0, padding: `0 ${token.paddingMD}px`,
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
      }}>
        <Tabs
          activeKey={activeTab} onChange={onActiveTabChange}
          items={[
            { key: 'source', label: '源文件' },
            { key: 'graph', label: '圖譜' },
            { key: 'vector', label: '向量' },
          ]}
          style={{ marginBottom: 0 }}
        />
        {onSettingsClick && (
          <Button icon={<SettingOutlined />} onClick={onSettingsClick} size="small" />
        )}
      </div>
      <div style={{ flex: 1, flexShrink: 0, position: 'relative', minHeight: 0 }}>
        <div style={{ position: 'absolute', inset: 0, overflow: 'auto' }}>
          {activeTab === 'source' && (
            <KBSourcePreview fileId={fileId} fileName={fileName} fileType={fileType} />
          )}
          {activeTab === 'graph' && (
            <KBGraphPanel
              fileId={fileId} graphStatus={graphStatus}
              onNodeSelect={onNodeSelect} onGraphReady={onGraphReady} onDataLoaded={onDataLoaded}
            />
          )}
          {activeTab === 'vector' && (
            <KBVectorPanel fileId={fileId} vectorStatus={vectorStatus} />
          )}
        </div>
      </div>
    </div>
  );
}
