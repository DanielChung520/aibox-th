/**
 * @file        chatStoreFiles.ts
 * @description ChatStore 的檔案管理邏輯（上傳、刪除、狀態更新）
 * @lastUpdate  2026-04-18 22:12:08
 * @author      AI Agent
 * @version     1.0.0
 */

import type { FileStatusPayload, SessionFile } from '../services/api';
import { sessionFilesApi } from '../services/api';

export async function loadSessionFiles(
  sessionKey: string,
  setState: (next: { uploadedFiles: SessionFile[] }) => void,
): Promise<void> {
  try {
    const response = await sessionFilesApi.list(sessionKey);
    setState({ uploadedFiles: response.data.data || [] });
  } catch (err) {
    console.warn('[chatStore] loadSessionFiles failed:', err);
  }
}

export async function uploadFile(
  sessionKey: string,
  file: File,
  currentFiles: SessionFile[],
  setState: (next: { uploadedFiles: SessionFile[] }) => void,
): Promise<void> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await sessionFilesApi.upload(sessionKey, formData);
  const uploaded = response.data.data;
  setState({ uploadedFiles: [...currentFiles, uploaded] });
}

export async function deleteFile(
  sessionKey: string,
  fileKey: string,
  currentFiles: SessionFile[],
  setState: (next: { uploadedFiles: SessionFile[] }) => void,
): Promise<void> {
  await sessionFilesApi.delete(sessionKey, fileKey);
  setState({ uploadedFiles: currentFiles.filter((f) => f.file_key !== fileKey) });
}

export function applyFileStatusUpdate(
  payload: FileStatusPayload,
  currentFiles: SessionFile[],
  setState: (next: { uploadedFiles: SessionFile[] }) => void,
): void {
  const files = currentFiles.map((f) => {
    if (f.file_key !== payload.file_key) return f;
    return {
      ...f,
      ...(payload.vector_status !== undefined && { vector_status: payload.vector_status }),
      ...(payload.graph_status !== undefined && { graph_status: payload.graph_status }),
      ...(payload.failed_reason !== undefined && { failed_reason: payload.failed_reason }),
      ...(payload.graph_stats !== undefined && { graph_stats: payload.graph_stats }),
    };
  });
  setState({ uploadedFiles: files });
}
