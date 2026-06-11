/**
 * @file        LiffAuthGate.tsx
 * @description v1 stub — will integrate LINE LIFF SDK in future phase to gate content behind LINE login
 * @lastUpdate  2026-05-21 16:35:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import type { ReactNode } from 'react';

interface LiffAuthGateProps {
  children: ReactNode;
}

export default function LiffAuthGate({ children }: LiffAuthGateProps) {
  return <>{children}</>;
}
