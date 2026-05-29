-- Phase 1 マイグレーション（既存 DB 向け）
-- Supabase SQL Editor で実行してください

-- gmail_tokens: ユーザーごとの refresh_token
create table if not exists gmail_tokens (
  user_id uuid primary key references users(id) on delete cascade,
  refresh_token text not null,
  gmail_email text not null,
  updated_at timestamptz default now()
);

-- processed_emails に user_id を追加（ユーザー単位で重複判定）
alter table processed_emails
  add column if not exists user_id uuid references users(id) on delete cascade;

alter table processed_emails
  drop constraint if exists processed_emails_gmail_message_id_key;

create unique index if not exists processed_emails_user_gmail_unique
  on processed_emails (user_id, gmail_message_id);

alter table gmail_tokens enable row level security;

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
