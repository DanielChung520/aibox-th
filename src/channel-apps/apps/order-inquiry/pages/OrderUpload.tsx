/**
 * @file        OrderUpload.tsx
 * @description Order upload page — upload order sheet (image or file) for AI parsing
 * @lastUpdate  2026-05-21 17:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import ChannelShell from '../../../shell/ChannelShell';
import { uploadPreorderFile } from '../services/orderApi';
import './OrderUpload.css';

// ─── Constants ──────────────────────────────────────────────────────────

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

const ACCEPTED_TYPES = '.jpg,.jpeg,.png,.gif,.webp,.pdf,.xlsx,.xls,.csv,.docx';

// ─── Types ──────────────────────────────────────────────────────────────

type UploadState = 'idle' | 'selected' | 'uploading' | 'done' | 'error';

interface UploadResult {
  status: string;
  order_id?: string;
  message?: string;
}

// ─── Helpers ────────────────────────────────────────────────────────────

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getMediaType(file: File): 'image' | 'file' {
  return file.type.startsWith('image/') ? 'image' : 'file';
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error('無法讀取檔案'));
    reader.readAsDataURL(file);
  });
}

// ─── Upload Icon SVG ────────────────────────────────────────────────────

function UploadIcon() {
  return (
    <svg className="order-upload__dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

// ─── Component ──────────────────────────────────────────────────────────

export default function OrderUpload() {
  const [state, setState] = useState<UploadState>('idle');
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [errorMessage, setErrorMessage] = useState('');

  const inputRef = useRef<HTMLInputElement>(null);
  const isImage = file?.type.startsWith('image/') ?? false;

  // Cleanup object URLs on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const clearPreview = useCallback(() => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
  }, [previewUrl]);

  const selectFile = useCallback((selectedFile: File | null) => {
    clearPreview();

    if (!selectedFile) {
      setFile(null);
      setResult(null);
      setErrorMessage('');
      setState('idle');
      return;
    }

    if (selectedFile.size > MAX_FILE_SIZE) {
      setFile(selectedFile);
      setErrorMessage('檔案大小超過 10MB 限制，請選擇較小的檔案');
      setResult(null);
      setState('error');
      return;
    }

    setFile(selectedFile);
    setResult(null);
    setErrorMessage('');

    if (selectedFile.type.startsWith('image/')) {
      setPreviewUrl(URL.createObjectURL(selectedFile));
    }

    setState('selected');
  }, [clearPreview]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    selectFile(e.target.files?.[0] ?? null);
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    selectFile(e.dataTransfer.files?.[0] ?? null);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleRemoveFile = () => {
    clearPreview();
    setFile(null);
    setResult(null);
    setErrorMessage('');
    setState('idle');
  };

  const handleUpload = async () => {
    if (!file || state !== 'selected') return;

    setState('uploading');

    try {
      const base64 = await readFileAsBase64(file);
      const mediaType = getMediaType(file);

      const res = await uploadPreorderFile({
        fileBase64: base64,
        filename: file.name,
        mediaType,
      });

      if (res.status === 'ok' || res.status === 'success') {
        setResult(res);
        setState('done');
      } else {
        setErrorMessage(res.message || 'AI 解析失敗，請確認檔案內容後重試');
        setState('error');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '上傳發生錯誤，請稍後重試';
      setErrorMessage(msg);
      setState('error');
    }
  };

  const handleReset = () => {
    handleRemoveFile();
  };

  // ─── Render ──────────────────────────────────────────────────────────

  return (
    <ChannelShell title="上傳訂購單">
      <div className="order-upload">
        {/* ── Dropzone (idle state) ── */}
        {state === 'idle' && (
          <div
            className={`order-upload__dropzone${dragOver ? ' order-upload__dropzone--dragover' : ''}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          >
            <input
              ref={inputRef}
              type="file"
              className="order-upload__dropzone-input"
              accept={ACCEPTED_TYPES}
              onChange={handleInputChange}
            />
            <UploadIcon />
            <p className="order-upload__dropzone-text">點擊或拖曳上傳訂購單</p>
            <p className="order-upload__dropzone-hint">
              支援圖片（JPG/PNG/GIF/WebP）<br />及檔案（PDF/XLSX/XLS/CSV/DOCX）
            </p>
          </div>
        )}

        {/* ── File info + preview (when file is selected) ── */}
        {file && state !== 'idle' && (
          <>
            {isImage && previewUrl && (
              <div className="order-upload__preview">
                <img className="order-upload__preview-img" src={previewUrl} alt={file.name} />
              </div>
            )}

            <div className="order-upload__info">
              <div className="order-upload__info-icon">
                {isImage ? '🖼' : '📄'}
              </div>
              <div className="order-upload__info-details">
                <p className="order-upload__info-name">{file.name}</p>
                <p className="order-upload__info-size">{formatFileSize(file.size)}</p>
              </div>
              {state === 'selected' && (
                <button className="order-upload__info-remove" onClick={handleRemoveFile} aria-label="移除檔案">
                  ✕
                </button>
              )}
            </div>
          </>
        )}

        {/* ── Upload button (selected state) ── */}
        {state === 'selected' && (
          <button className="order-upload__btn" onClick={handleUpload}>
            上傳並解析
          </button>
        )}

        {/* ── Uploading status ── */}
        {state === 'uploading' && (
          <>
            <button className="order-upload__btn order-upload__btn--loading" disabled>
              <span className="order-upload__spinner" />
              AI 正在解析您的訂購單...
            </button>
            <div className="order-upload__status order-upload__status--loading">
              <span className="order-upload__spinner" />
              AI 正在解析您的訂購單，請稍候...
            </div>
          </>
        )}

        {/* ── Success result ── */}
        {state === 'done' && result && (
          <div className="order-upload__result order-upload__result--success">
            <div className="order-upload__result-icon">✓</div>
            <h3 className="order-upload__result-title">解析完成</h3>
            <p className="order-upload__result-message">
              {result.message || '訂購單已成功解析'}
            </p>
            {result.order_id && (
              <p className="order-upload__result-id">訂單編號：{result.order_id}</p>
            )}
            <button className="order-upload__reset-btn" onClick={handleReset}>
              繼續上傳
            </button>
          </div>
        )}

        {/* ── Error result ── */}
        {state === 'error' && (
          <div className="order-upload__result order-upload__result--error">
            <div className="order-upload__result-icon">✕</div>
            <h3 className="order-upload__result-title">解析失敗</h3>
            <p className="order-upload__result-message">{errorMessage}</p>
            <button className="order-upload__reset-btn" onClick={handleReset}>
              重新上傳
            </button>
          </div>
        )}
      </div>
    </ChannelShell>
  );
}
