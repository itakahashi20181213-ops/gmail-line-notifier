-- Supabase SQL Editor で実行してください
-- エラー: new row violates row-level security policy の修正用

alter table users enable row level security;
alter table gmail_tokens enable row level security;
alter table oauth_sessions enable row level security;
alter table processed_emails enable row level security;

-- users
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

-- gmail_tokens
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

-- oauth_sessions
drop policy if exists "Allow all oauth_sessions" on oauth_sessions;
create policy "Allow all oauth_sessions"
  on oauth_sessions for all
  using (true)
  with check (true);

-- processed_emails
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
