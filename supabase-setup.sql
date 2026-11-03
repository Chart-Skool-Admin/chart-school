-- Chart School: one private progress row per signed-in person
create table if not exists public.progress (
  user_id uuid primary key references auth.users(id) on delete cascade,
  s text not null,
  t bigint not null default 0,
  updated_at timestamptz not null default now()
);
alter table public.progress enable row level security;
create policy "read own progress"   on public.progress for select using (auth.uid() = user_id);
create policy "insert own progress" on public.progress for insert with check (auth.uid() = user_id);
create policy "update own progress" on public.progress for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
