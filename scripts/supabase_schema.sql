-- Supabase SQL Editor で実行してください

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  line_user_id text not null,
  gmail_email text,
  send_hour int not null check (send_hour between 0 and 23),
  created_at timestamptz default now()
);

create table if not exists gmail_tokens (
  user_id uuid primary key references users(id) on delete cascade,
  refresh_token text not null,
  gmail_email text not null,
  updated_at timestamptz default now(),
  last_relink_notice_at timestamptz
);

create table if not exists oauth_sessions (
  state text primary key,
  user_id uuid not null references users(id) on delete cascade,
  code_verifier text not null,
  redirect_uri text not null,
  created_at timestamptz default now(),
  expires_at timestamptz not null
);

create index if not exists idx_oauth_sessions_expires_at on oauth_sessions (expires_at);

create table if not exists processed_emails (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  gmail_message_id text not null,
  summary text,
  line_user_id text,
  notified boolean default false,
  created_at timestamptz default now(),
  unique (user_id, gmail_message_id)
);

-- Row Level Security (RLS)
alter table users enable row level security;
alter table gmail_tokens enable row level security;
alter table oauth_sessions enable row level security;
alter table processed_emails enable row level security;

drop policy if exists "Allow read users" on users;
drop policy if exists "Allow insert users" on users;
drop policy if exists "Allow update users" on users;

create policy "Allow read users"
  on users for select
  using (true);

create policy "Allow insert users"
  on users for insert
  with check (true);

create policy "Allow update users"
  on users for update
  using (true);

drop policy if exists "Allow read gmail_tokens" on gmail_tokens;
drop policy if exists "Allow insert gmail_tokens" on gmail_tokens;
drop policy if exists "Allow update gmail_tokens" on gmail_tokens;

create policy "Allow read gmail_tokens"
  on gmail_tokens for select
  using (true);

create policy "Allow insert gmail_tokens"
  on gmail_tokens for insert
  with check (true);

create policy "Allow update gmail_tokens"
  on gmail_tokens for update
  using (true);

drop policy if exists "Allow all oauth_sessions" on oauth_sessions;
create policy "Allow all oauth_sessions"
  on oauth_sessions for all
  using (true)
  with check (true);

drop policy if exists "Allow read processed_emails" on processed_emails;
drop policy if exists "Allow insert processed_emails" on processed_emails;
drop policy if exists "Allow update processed_emails" on processed_emails;

create policy "Allow read processed_emails"
  on processed_emails for select
  using (true);

create policy "Allow insert processed_emails"
  on processed_emails for insert
  with check (true);

create policy "Allow update processed_emails"
  on processed_emails for update
  using (true);

-- テスト用サンプルデータ（任意）
insert into users (line_user_id, gmail_email, send_hour)
values ('U_sample_user', 'sample@example.com', 9)
on conflict do nothing;
