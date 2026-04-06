/**
 * @file        知識庫文件上傳元件
 * @description 支援拖曳上傳文件至知識庫
 * @lastUpdate  2026-04-05 22:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { Upload, App, theme } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { authApi, knowledgeApi, paramsApi } from '../../../services/api';
import { authStore } from '../../../stores/auth';

const { Dragger } = Upload;

interface KBFileUploadProps {
  rootId: string;
  onUploadComplete: () => void;
}

async function getUserTier(): Promise<string> {
  const cachedTier = authStore.getState().user?.tier;
  if (cachedTier) return cachedTier;

  try {
    const res = await authApi.me();
    const freshUser = res.data?.data;
    if (freshUser?.tier) return freshUser.tier;
  } catch {
    // ignore
  }
  return 'general';
}

export default function KBFileUpload({ rootId, onUploadComplete }: KBFileUploadProps) {
  const { message } = App.useApp();
  const { token } = theme.useToken();

  const getUploadMaxBytes = async (): Promise<number> => {
    const tier = await getUserTier();
    const paramKey = `upload_max_size_${tier}`;
    try {
      const resp = await paramsApi.get(paramKey);
      return parseInt(resp.data?.data?.param_value ?? '0', 10) || 0;
    } catch {
      return tier === 'vip' ? 52428800 : 5242880;
    }
  };

  const beforeUpload = async (file: File) => {
    const maxBytes = await getUploadMaxBytes();
    if (maxBytes > 0 && file.size > maxBytes) {
      const maxMB = (maxBytes / (1024 * 1024)).toFixed(0);
      message.error(`檔案大小（${(file.size / (1024 * 1024)).toFixed(1)} MB）超過您的上傳限制（${maxMB} MB）`);
      return Upload.LIST_IGNORE;
    }
    return true;
  };

  const customRequest = async (options: {
    file: Blob | File | string;
    onSuccess?: (res: string) => void;
    onError?: (err: Error) => void;
    onProgress?: (event: { percent: number }) => void;
  }) => {
    try {
      options.onProgress?.({ percent: 50 });
      const formData = new FormData();
      if (options.file instanceof Blob) {
        formData.append('file', options.file);
      }
      await knowledgeApi.uploadFile(rootId, formData);
      options.onProgress?.({ percent: 100 });
      options.onSuccess?.('ok');
      message.success('文件上傳成功，正在處理中...');
      onUploadComplete();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } } };
      message.error(err.response?.data?.message || '文件上傳失敗');
      options.onError?.(error as Error);
    }
  };

  return (
    <div style={{ backgroundColor: token.colorBgContainer, padding: token.paddingXL, borderRadius: token.borderRadiusLG }}>
      <Dragger 
        customRequest={customRequest}
        beforeUpload={beforeUpload}
        showUploadList={false}
        multiple={true}
        style={{ padding: '40px 0' }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ color: token.colorPrimary, fontSize: 48 }} />
        </p>
        <p className="ant-upload-text" style={{ color: token.colorText, fontSize: 16, marginTop: 16, fontWeight: 500 }}>
          點擊或拖曳文件至此區域進行上傳
        </p>
        <p className="ant-upload-hint" style={{ color: token.colorTextSecondary, marginTop: 8 }}>
          支援 .txt, .md, .pdf 等格式文件
        </p>
      </Dragger>
    </div>
  );
}
