/**
 * @file        開發中頁面
 * @description 顯示「功能開發中」提示的通用頁面
 * @lastUpdate  2026-03-22 19:56:42
 * @author      Daniel Chung
 * @version     1.0.0
 * @history
 * - 2026-03-17 23:27:55 | Daniel Chung | 1.0.0 | 初始版本
 */

import { useEffect } from 'react';
import { Typography } from 'antd';
import { useContentTokens } from '../contexts/AppThemeProvider';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';

const { Title } = Typography;

export default function UnderDevelopment() {
  const contentTokens = useContentTokens();
  useEntityPerception({ defaultEntityType: 'placeholder', defaultAction: 'view' });

  useEffect(() => {
    pageContextManager.report({ component: 'UnderDevelopment', action: 'view' });
  }, []);

  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      height: '100%',
      flexDirection: 'column'
    }}>
      <Title level={2} style={{ color: contentTokens.colorWarning }}>🚧 開發中</Title>
      <Title level={4} type="secondary">此功能正在開發中，敬請期待...</Title>
    </div>
  );
}
