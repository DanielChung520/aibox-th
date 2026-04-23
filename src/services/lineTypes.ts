export interface LINEChannel {
  _key: string;
  official_account_key: string;
  channel_name: string;
  channel_id: string;
  channel_secret?: string;
  channel_access_token?: string;
  webhook_url: string;
  webhook_enabled: boolean;
  bot_user_id?: string;
  publication_status: 'unpublished' | 'published' | 'error';
  published_bot_key?: string;
  published_bot_name?: string;
  last_connected_at?: string;
  created_at: string;
  status?: 'connected' | 'error' | 'default';
}

export interface LINEOfficialAccount {
  _key: string;
  provider_name: string;
  name: string;
  status: 'active' | 'inactive' | 'error';
  channels: LINEChannel[];
  created_at: string;
  updated_at: string;
}

export interface BotAgent {
  _key: string;
  name: string;
  description?: string;
  intents?: string[];
}
