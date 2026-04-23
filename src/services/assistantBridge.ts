import { resolvePageContext } from '../components/FloatingAssistant/types';
import { pageContextManager, type PageContextState } from './PageContextManager';
import { ENTITY_INTERACT_EVENT } from '../hooks/useEntityPerception';
import { intentEngine } from './intentEngine';
import type { IntentGuess } from '../components/FloatingAssistant/types';

export const ASSISTANT_CHANNEL_NAME = 'aibox-assistant-bridge';

export interface AssistantBridgeState {
  pathname: string;
  pageContext: ReturnType<typeof resolvePageContext>;
  fullPageContext: PageContextState | null;
  modalContext: Record<string, unknown> | null;
  entityContext: Record<string, unknown> | null;
  intentGuesses: IntentGuess[];
  updatedAt: number;
}

const CHANNEL_SUPPORTED = typeof window !== 'undefined' && 'BroadcastChannel' in window;

function createSnapshot(pathname: string, fullPageContext: PageContextState | null, modalContext: Record<string, unknown> | null, entityContext: Record<string, unknown> | null, intentGuesses: IntentGuess[]): AssistantBridgeState {
  return {
    pathname,
    pageContext: resolvePageContext(pathname),
    fullPageContext,
    modalContext,
    entityContext,
    intentGuesses,
    updatedAt: Date.now(),
  };
}

export function setupAssistantBridge(pathnameProvider: () => string): () => void {
  if (!CHANNEL_SUPPORTED) return () => {};

  const channel = new BroadcastChannel(ASSISTANT_CHANNEL_NAME);

  let fullPageContext = pageContextManager.getContext();
  let modalContext: Record<string, unknown> | null = null;
  let entityContext: Record<string, unknown> | null = null;
  let intentGuesses: IntentGuess[] = intentEngine.getLastGuesses();

  const publish = () => {
    channel.postMessage(createSnapshot(pathnameProvider(), fullPageContext, modalContext, entityContext, intentGuesses));
  };

  const unsubscribePageContext = pageContextManager.subscribe((ctx) => {
    fullPageContext = ctx;
    publish();
  });

  const handleEntityInteract = (event: Event) => {
    entityContext = (event as CustomEvent).detail as Record<string, unknown>;
    publish();
  };

  const handleModalContextChange = (event: Event) => {
    const detail = (event as CustomEvent).detail as Record<string, unknown>;
    modalContext = detail.action === 'open' ? detail : null;
    publish();
  };

  const unsubscribeIntent = intentEngine.subscribe((guesses) => {
    intentGuesses = guesses;
    publish();
  });
  intentEngine.startListening();

  window.addEventListener(ENTITY_INTERACT_EVENT, handleEntityInteract);
  window.addEventListener('modal-context-change', handleModalContextChange);

  publish();

  return () => {
    unsubscribePageContext();
    unsubscribeIntent();
    window.removeEventListener(ENTITY_INTERACT_EVENT, handleEntityInteract);
    window.removeEventListener('modal-context-change', handleModalContextChange);
    channel.close();
  };
}

export function subscribeAssistantBridge(listener: (state: AssistantBridgeState) => void): () => void {
  if (!CHANNEL_SUPPORTED) return () => {};

  const channel = new BroadcastChannel(ASSISTANT_CHANNEL_NAME);
  const handleMessage = (event: MessageEvent<AssistantBridgeState>) => listener(event.data);
  channel.addEventListener('message', handleMessage);

  return () => {
    channel.removeEventListener('message', handleMessage);
    channel.close();
  };
}
