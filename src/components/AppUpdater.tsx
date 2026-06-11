/**
 * @file        應用自動更新檢查元件
 * @description 啟動時靜默檢查 Tauri 殼更新，有新版本時彈窗提示下載安裝
 * @lastUpdate  2026-03-25 13:03:52
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useEffect, useRef, useState } from 'react';
import { Modal, Progress, Typography, App as AntApp } from 'antd';
import { check, type Update } from '@tauri-apps/plugin-updater';
import { relaunch } from '@tauri-apps/plugin-process';

const { Text } = Typography;

const CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000;

export default function AppUpdater() {
  const { modal } = AntApp.useApp();
  const [downloading, setDownloading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [contentLength, setContentLength] = useState(0);
  const downloaded = useRef(0);
  const checking = useRef(false);

  useEffect(() => {
    const doCheck = async () => {
      if (checking.current) return;
      checking.current = true;

      try {
        const update: Update | null = await check();
        if (!update) {
          checking.current = false;
          return;
        }

        modal.confirm({
          title: '發現新版本',
          content: (
            <div>
              <Text>版本 <Text strong>{update.version}</Text> 已可用。</Text>
              {update.body && (
                <div style={{ marginTop: 8, maxHeight: 200, overflow: 'auto' }}>
                  <Text type="secondary">{update.body}</Text>
                </div>
              )}
            </div>
          ),
          okText: '立即更新',
          cancelText: '稍後提醒',
          onOk: async () => {
            setDownloading(true);
            downloaded.current = 0;

            await update.downloadAndInstall((event) => {
              if (event.event === 'Started' && event.data.contentLength) {
                setContentLength(event.data.contentLength);
              } else if (event.event === 'Progress') {
                downloaded.current += event.data.chunkLength;
                if (contentLength > 0) {
                  setProgress(Math.round((downloaded.current / contentLength) * 100));
                }
              } else if (event.event === 'Finished') {
                setProgress(100);
              }
            });

            await relaunch();
          },
        });
      } catch {
        // silent fail — updater should never block the app
      } finally {
        checking.current = false;
      }
    };

    doCheck();
    const timer = setInterval(doCheck, CHECK_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [modal, contentLength]);

  if (!downloading) return null;

  return (
    <Modal
      open
      title="正在更新..."
      footer={null}
      closable={false}
      maskClosable={false}
    >
      <Progress percent={progress} status="active" />
      {contentLength > 0 && (
        <Text type="secondary">
          {(downloaded.current / 1024 / 1024).toFixed(1)} / {(contentLength / 1024 / 1024).toFixed(1)} MB
        </Text>
      )}
    </Modal>
  );
}
