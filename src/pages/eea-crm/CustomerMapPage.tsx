import { useEffect } from 'react';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { pageContextManager } from '../../services/PageContextManager';
import CustomerMapComponent from '../../components/crm/CustomerMap';

export default function CustomerMapPage() {
  const contentTokens = useContentTokens();

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/customer-map',
      pageName: 'EEA-CRM 客戶地圖',
      entityType: 'dashboard',
      action: 'view',
    });
  }, []);

  return (
    <div style={{
      padding: 0,
      background: contentTokens.contentBg,
      height: 'calc(100vh - 64px)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <CustomerMapComponent />
    </div>
  );
}