/**
 * @file        資料深度追蹤主頁面
 * @description 主要容器，整合場景選擇、輸入、圖譜、表格等子元件
 * @lastUpdate  2026-05-17
 */
import React, { useState } from 'react';
import { Typography, Layout, Card } from 'antd';

const { Title } = Typography;

const DataDepthTracking: React.FC = () => {
  const [selectedScenario, _setSelectedScenario] = useState<string | null>(null);
  return (
    <Layout style={{ padding: 24, background: 'transparent' }}>
      <Title level={3} style={{ marginBottom: 24 }}>資料深度追蹤</Title>
      <Card>
        <p>場景選擇與追蹤功能將在此處實作</p>
        <p>已選場景: {selectedScenario || '無'}</p>
      </Card>
    </Layout>
  );
};

export default DataDepthTracking;
