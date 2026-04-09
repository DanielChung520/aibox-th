/**
 * @file        知識庫詳情頁面
 * @description 三欄佈局：左側文件列表、中間圖譜/源文件/向量、右側節點與關係面板
 * @lastUpdate  2026-03-26 21:22:20
 * @author      Daniel Chung
 * @version     2.0.2
 */

import { useState, useCallback, useRef, useEffect, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Space, Typography, Empty, App, theme } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import type { Graph } from '@antv/g6';
import { GraphNode, GraphEdge, KnowledgeFile, knowledgeApi } from '../../services/api';
import { ThemeContext } from '../../contexts/AppThemeProvider';
import FileContentViewer from '../../components/FileContentViewer';
import KBFileList from './components/KBFileList';
import KBFileUpload from './components/KBFileUpload';
import KBNodeRelPanel from './components/KBNodeRelPanel';
import KBSettingsModal from './components/KBSettingsModal';

const { Title, Text } = Typography;

export default function KnowledgeBaseDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const { contentTokens } = useContext(ThemeContext);

  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [selectedFileId, setSelectedFileId] = useState<string | undefined>(undefined);
  const [activeTab, setActiveTab] = useState('source');
  const [uploadMode, setUploadMode] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const graphInstanceRef = useRef<Graph | null>(null);

  const selectedFile = files.find(f => f._key === selectedFileId);

  const loadFiles = useCallback(async () => {
    if (!id) return;
    setFilesLoading(true);
    try {
      const res = await knowledgeApi.listFiles(id);
      setFiles(res.data.data || []);
    } catch {
      message.error('載入文件列表失敗');
      setFiles([]);
    } finally {
      setFilesLoading(false);
    }
  }, [id, message]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  // Poll file statuses while any file is still pending/processing
  useEffect(() => {
    const hasPending = files.some(f =>
      ['pending', 'processing', 'queued'].includes(f.vector_status || '') ||
      ['pending', 'processing', 'queued'].includes(f.graph_status || '')
    );
    if (!hasPending || !id) return;
    const timer = setInterval(() => { loadFiles(); }, 5000);
    return () => clearInterval(timer);
  }, [files, id, loadFiles]);

  useEffect(() => {
    if (!selectedFileId && files.length > 0) {
      setSelectedFileId(files[0]._key);
    }
  }, [files, selectedFileId]);

  const handleSelectFile = (fileId: string) => {
    setSelectedFileId(fileId);
    setUploadMode(false);
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      await knowledgeApi.deleteFile(fileId);
      message.success('文件已刪除');
      setFiles(files.filter(f => f._key !== fileId));
      if (selectedFileId === fileId) setSelectedFileId(undefined);
    } catch (e: any) {
      message.error(e.response?.data?.message || '刪除失敗');
    }
  };

  const handleUploadComplete = () => {
    message.success('文件上傳成功');
    setUploadMode(false);
    loadFiles();
  };

  const handleGraphReady = useCallback((graph: Graph) => {
    graphInstanceRef.current = graph;
  }, []);

  const handleNodeSelect = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
  }, []);

  const handleDataLoaded = useCallback((nodes: GraphNode[], edges: GraphEdge[]) => {
    setGraphNodes(nodes);
    setGraphEdges(edges);
  }, []);

  const handleRightPanelNodeClick = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
    const graph = graphInstanceRef.current;
    if (!graph) return;
    if (typeof graph.setElementState === 'function' && typeof graph.focusElement === 'function') {
      graph.setElementState(nodeId, 'selected', true);
      graph.focusElement(nodeId, { duration: 500 });
    }
  }, []);

  const showRightPanel = activeTab === 'graph' && selectedFile && !uploadMode;

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      <div style={{
        width: 280, minWidth: 280, flexShrink: 0,
        backgroundColor: token.colorBgContainer,
        borderRight: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: `${contentTokens.borderRadius}px 0 0 ${contentTokens.borderRadius}px`,
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{
          padding: 16,
          borderRadius: 16,
          borderBottomWidth: 1,
          borderBottomStyle: 'solid',
          borderBottomColor: 'rgba(255, 255, 255, 0.89)',
          display: 'flex', alignItems: 'center', gap: 16,
          flexShrink: 0,
        }}>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/app/knowledge/management')} />
          <Space orientation="vertical" size={0}>
            <Title level={4} style={{ margin: 0, color: token.colorText }}>知識庫</Title>
            <Text style={{ color: token.colorTextSecondary, fontSize: token.fontSizeSM }}>ID: {id}</Text>
          </Space>
        </div>
        <KBFileList
          rootId={id || 'kb1'} files={files} selectedFileId={selectedFileId}
          onSelectFile={handleSelectFile} onUpload={() => setUploadMode(true)}
          onDeleteFile={handleDeleteFile} loading={filesLoading}
        />
      </div>

      <div style={{
        flex: 1, minWidth: 0, flexShrink: 0,
        overflow: 'hidden',
        backgroundColor: token.colorBgLayout,
        display: 'flex', flexDirection: 'column',
        height: '100%', alignItems: 'stretch',
        paddingLeft: token.padding,
        paddingRight: token.padding,
      }}>
        {uploadMode ? (
          <div style={{ padding: token.paddingXL, maxWidth: 600, margin: '0 auto', width: '100%' }}>
            <KBFileUpload rootId={id || 'kb1'} onUploadComplete={handleUploadComplete} />
          </div>
        ) : !selectedFile ? (
          <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
            <Empty description={<Text style={{ color: token.colorTextSecondary }}>請在左側選擇文件以查看詳情</Text>} />
          </div>
        ) : (
          <FileContentViewer
            fileId={selectedFile._key}
            fileName={selectedFile.filename}
            fileType={selectedFile.file_type}
            activeTab={activeTab}
            graphStatus={selectedFile.graph_status}
            vectorStatus={selectedFile.vector_status}
            onActiveTabChange={setActiveTab}
            onGraphReady={handleGraphReady}
            onNodeSelect={handleNodeSelect}
            onDataLoaded={handleDataLoaded}
            onSettingsClick={() => setSettingsOpen(true)}
          />
        )}
      </div>

      {showRightPanel && (
        <KBNodeRelPanel
          nodes={graphNodes} edges={graphEdges}
          selectedNodeId={selectedNodeId} onNodeClick={handleRightPanelNodeClick}
          collapsed={rightPanelCollapsed} onCollapse={setRightPanelCollapsed}
        />
      )}

      <KBSettingsModal open={settingsOpen} onCancel={() => setSettingsOpen(false)} />
    </div>
  );
}
