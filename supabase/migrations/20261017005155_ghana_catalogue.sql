create table public.job_catalogue (
 id text primary key, source_key text not null, payload jsonb not null,
 status text not null default 'active' check(status in ('active','closed')),
 first_seen_at timestamptz not null default now(), last_checked_at timestamptz not null,
 deadline timestamptz
);
create index catalogue_active_source on public.job_catalogue(source_key,last_checked_at) where status='active';
alter table public.job_catalogue enable row level security;
revoke all on public.job_catalogue from anon, authenticated;
grant all on public.job_catalogue to service_role;
create table public.catalogue_refresh (
 id integer primary key check(id=1), next_refresh_at timestamptz not null default now(),
 completed_at timestamptz, summary jsonb not null default '[]'
);
insert into public.catalogue_refresh(id) values(1);
alter table public.catalogue_refresh enable row level security;
revoke all on public.catalogue_refresh from anon, authenticated;
grant all on public.catalogue_refresh to service_role;
create function public.claim_catalogue_refresh() returns boolean
language plpgsql security invoker set search_path='' as $$
declare claimed integer;
begin
 update public.catalogue_refresh set next_refresh_at=now()+interval '10 hours'
 where id=1 and next_refresh_at<=now();
 get diagnostics claimed=row_count;
 return claimed=1;
end; $$;
revoke execute on function public.claim_catalogue_refresh() from public, anon, authenticated;
grant execute on function public.claim_catalogue_refresh() to service_role;
