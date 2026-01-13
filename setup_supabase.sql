-- 在 Supabase SQL Editor 中运行此 SQL 以创建表

create table if not exists gemini_accounts (
  alias text primary key,
  psid text not null,
  psidts text not null,
  proxy text,
  headers jsonb,
  enabled boolean default true,
  call_count bigint default 0,
  last_used timestamptz,
  last_updated timestamptz
);

-- 创建索引以优化轮询查询
create index if not exists idx_gemini_accounts_call_count on gemini_accounts (call_count);
create index if not exists idx_gemini_accounts_enabled on gemini_accounts (enabled);
