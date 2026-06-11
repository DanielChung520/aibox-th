/**
 * @file        知識庫節點與關係側邊面板
 * @description 可折疊面板，包含「節點列表」與「關係列表」兩個頁籤
 * @lastUpdate  2026-03-25 16:03:03
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useMemo, useContext } from 'react';
import { Tabs, Table, Tag, Button, Typography, Tooltip, theme } from 'antd';
import { ThemeContext } from '../../../contexts/AppThemeProvider';
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { GraphNode, GraphEdge } from '../../../services/api';

const { Text } = Typography;

interface KBNodeRelPanelProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId?: string | null;
  onNodeClick?: (nodeId: string) => void;
  collapsed?: boolean;
  onCollapse?: (collapsed: boolean) => void;
}

export default function KBNodeRelPanel({
  nodes,
  edges,
  selectedNodeId,
  onNodeClick,
  collapsed = false,
  onCollapse,
}: KBNodeRelPanelProps) {
  const { token } = theme.useToken();
  const { contentTokens } = useContext(ThemeContext);

  const nodeColumns: ColumnsType<GraphNode> = [
    {
      title: '節點',
      key: 'node',
      render: (_: unknown, record: GraphNode) => (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text strong style={{ minWidth: 120 }}>{record.label}</Text>
            <Tag color={token.colorPrimary}>{record.type}</Tag>
          </div>
          {Object.keys(record.properties || {}).length > 0 && (
            <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {Object.entries(record.properties || {}).map(([k, v]) => (
                <Tag key={k} style={{ marginRight: 0 }}>{k}: {v}</Tag>
              ))}
            </div>
          )}
        </div>
      ),
    },
  ];

  const nodeLabelMap = useMemo(() => {
    const map = new Map<string, string>();
    nodes.forEach((n) => map.set(n.id, n.label));
    return map;
  }, [nodes]);

  const edgeColumns: ColumnsType<GraphEdge> = [
    {
      title: '起點',
      dataIndex: 'source',
      key: 'source',
      render: (src: string) => <Text>{nodeLabelMap.get(src) ?? src}</Text>,
    },
    {
      title: '關係',
      dataIndex: 'label',
      key: 'label',
      width: 80,
      render: (text: string) => <Tag color={token.colorPrimaryBorder}>{text}</Tag>,
    },
    {
      title: '終點',
      dataIndex: 'target',
      key: 'target',
      render: (tgt: string) => <Text>{nodeLabelMap.get(tgt) ?? tgt}</Text>,
    },
  ];

  const panelWidth = collapsed ? 40 : 450;

  return (
    <div
      style={{
        width: panelWidth,
        minWidth: panelWidth,
        transition: 'width 0.3s ease, min-width 0.3s ease',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderLeft: `1px solid ${token.colorBorderSecondary}`,
        backgroundColor: token.colorBgContainer,
        borderRadius: `0 ${contentTokens.borderRadius}px ${contentTokens.borderRadius}px 0`,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: collapsed ? 'center' : 'flex-end',
          padding: token.paddingXS,
          borderBottom: collapsed ? 'none' : `1px solid ${token.colorBorderSecondary}`,
        }}
      >
        <Tooltip title={collapsed ? '展開面板' : '收合面板'}>
          <Button
            type="text"
            size="small"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => onCollapse?.(!collapsed)}
          />
        </Tooltip>
      </div>

      {!collapsed && (
        <div style={{ flex: 1, overflow: 'auto', padding: `0 ${token.paddingXS}px` }}>
          <Tabs
            defaultActiveKey="nodes"
            size="small"
            items={[
              {
                key: 'nodes',
                label: '節點列表',
                children: (
                  <Table<GraphNode>
                    dataSource={nodes}
                    columns={nodeColumns}
                    rowKey="id"
                    pagination={false}
                    size="small"
                    onRow={(record) => ({
                      onClick: () => onNodeClick?.(record.id),
                      style: {
                        cursor: 'pointer',
                        backgroundColor:
                          record.id === selectedNodeId
                            ? token.controlItemBgActive
                            : undefined,
                      },
                    })}
                  />
                ),
              },
              {
                key: 'edges',
                label: '關係列表',
                children: (
                  <Table<GraphEdge>
                    dataSource={edges}
                    columns={edgeColumns}
                    rowKey={(r) => `${r.source}-${r.target}-${r.label}`}
                    pagination={false}
                    size="small"
                  />
                ),
              },
            ]}
          />
        </div>
      )}
    </div>
  );
}
