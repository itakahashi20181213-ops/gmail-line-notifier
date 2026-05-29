-- Phase 2: Vercel / serverless 向けマイグレーション
-- Supabase SQL Editor で実行してください

create table if not exists oauth_sessions (
  state text primary key,
  user_id uuid not null references users(id) on delete cascade,
  code_verifier text not null,
  redirect_uri text not null,
  created_at timestamptz default now(),
  expires_at timestamptz not null
);

create index if not exists idx_oauth_sessions_expires_at on oauth_sessions (expires_at);

alter table gmail_tokens
  add column if not exists last_relink_notice_at timestamptz;

alter table oauth_sessions enable row level security;

drop policy if exists "Allow all oauth_sessions" on oauth_sessions;
create policy "Allow all oauth_sessions"
  on oauth_sessions for all
  using (true)
  with check (true);
