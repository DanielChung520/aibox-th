import { useEffect } from 'react';
import { Typography } from 'antd';
import { useContentTokens } from '../contexts/AppThemeProvider';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';

const { Title } = Typography;

export default function TaskSessionScheduled() {
  const contentTokens = useContentTokens();

  useEntityPerception({ defaultEntityType: 'task_session', defaultAction: 'scheduled' });

  useEffect(() => {
    pageContextManager.report({ component: 'TaskSessionScheduled', entityType: 'task_session', action: 'scheduled' });
  }, []);

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100%',
      flexDirection: 'column',
    }}>
      <Title level={3} style={{ color: contentTokens.textSecondary }}>定期任務</Title>
      <Title level={5} type="secondary">功能開發中</Title>
    </div>
  );
}
