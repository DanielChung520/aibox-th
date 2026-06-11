import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// Mock all external dependencies
const mockCreate = vi.fn();
const mockGet = vi.fn();

vi.mock('../services/api', () => ({
  agentApi: {
    create: (...args: any[]) => mockCreate(...args),
    get: (key: string) => mockGet(key),
    list: vi.fn().mockResolvedValue({ data: { data: [] } }),
    delete: vi.fn(),
    toggleFavorite: vi.fn(),
  },
  knowledgeApi: { listRoots: vi.fn().mockResolvedValue({ data: { data: [] } }) },
  toolApi: { list: vi.fn().mockResolvedValue({ data: { data: [] } }) },
  daApi: { listSchemaModules: vi.fn().mockResolvedValue({ data: { data: [] } }) },
  modelProviderApi: { list: vi.fn().mockResolvedValue({ data: { data: [] } }) },
  roleApi: { list: vi.fn().mockResolvedValue({ data: { data: [] } }) },
}));

vi.mock('../stores/auth', () => ({
  authStore: {
    getState: () => ({
      user: { username: 'testuser', role_names: [] },
      token: 'test-token',
    }),
  },
}));

vi.mock('../contexts/AppThemeProvider', () => ({
  useContentTokens: () => ({
    cardShadow: 'none',
    cardShadowHover: 'none',
    colorPrimary: '#1890ff',
    textSecondary: '#666',
    colorError: '#ff4d4f',
  }),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('../hooks/useEntityPerception', () => ({
  useEntityPerception: () => {},
}));

vi.mock('../services/PageContextManager', () => ({
  pageContextManager: { report: vi.fn() },
}));

describe('BrowseAgent - Create flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render the BrowseAgent page without crashing', async () => {
    const { default: BrowseAgent } = await import('../pages/BrowseAgent');
    const { container } = render(<BrowseAgent />);
    expect(container).toBeTruthy();
  });

  it('should show tabs with group labels', async () => {
    const { default: BrowseAgent } = await import('../pages/BrowseAgent');
    render(<BrowseAgent />);

    // Verify the page renders with known tab labels
    expect(screen.getByText('全部')).toBeTruthy();
    expect(screen.getByText('進銷存')).toBeTruthy();
  });
});
