begin;
alter table public.profiles alter column date_of_birth drop not null;
alter table public.profiles add column if not exists session_version integer not null default 1;
alter table public.profiles add column if not exists email_verified_at timestamptz;
alter table public.profiles add column if not exists requires_verification boolean not null default false;
alter table public.profiles add column if not exists onboarding_complete boolean not null default true;
alter table public.profiles add column if not exists auth_user_id uuid;
create unique index if not exists profiles_email_casefold on public.profiles(lower(email));
revoke all on public.profiles from anon, authenticated;
create index if not exists application_events_application_date on public.application_events(application_id,created_at desc);
alter table public.applications add column if not exists reminder_auto boolean not null default true;
alter table public.applications add column if not exists deleted_at timestamptz;
create index if not exists applications_due_reminders on public.applications(reminder_date) where email_reminder and email_reminder_sent_at is null and status='started' and deleted_at is null;

create table if not exists public.api_rate_limits (bucket text primary key, hits integer not null, expires_at timestamptz not null);
create or replace function public.consume_request_limit(bucket text, maximum integer, period_seconds integer) returns boolean language plpgsql security invoker set search_path='' as $$
declare counter integer;
begin
 insert into public.api_rate_limits as lim(bucket,hits,expires_at) values(bucket,1,now()+make_interval(secs=>greatest(1,period_seconds)))
 on conflict on constraint api_rate_limits_pkey do update set hits=case when lim.expires_at<=now() then 1 else lim.hits+1 end,
 expires_at=case when lim.expires_at<=now() then excluded.expires_at else lim.expires_at end returning hits into counter;
 return counter<=maximum;
end; $$;

create table if not exists public.account_tokens (token_hash text primary key, user_id uuid not null references public.profiles(id) on delete cascade, purpose text not null check(purpose in ('reset','verify','change_email')), target_email text not null, expires_at timestamptz not null, used_at timestamptz, created_at timestamptz not null default now());
create index if not exists account_tokens_owner on public.account_tokens(user_id);
create index if not exists account_tokens_expiry on public.account_tokens(expires_at);
create or replace function public.consume_account_token(digest text, token_purpose text, new_password_hash text default null) returns uuid language plpgsql security invoker set search_path='' as $$
declare tok public.account_tokens; owner_id uuid;
begin
 select * into tok from public.account_tokens where token_hash=digest and purpose=token_purpose and used_at is null and expires_at>now() for update;
 if not found then return null; end if;
 if token_purpose='reset' then
  if new_password_hash is null then return null; end if;
  update public.profiles set password_hash=new_password_hash, email_verified_at=now(),requires_verification=false,session_version=session_version+1 where id=tok.user_id and lower(email)=lower(tok.target_email) returning id into owner_id;
 elsif token_purpose='verify' then
  update public.profiles set email_verified_at=now(),requires_verification=false where id=tok.user_id and lower(email)=lower(tok.target_email) returning id into owner_id;
 else
  update public.profiles set email=lower(tok.target_email),email_verified_at=now(),requires_verification=false,session_version=session_version+1 where id=tok.user_id returning id into owner_id;
 end if;
 if owner_id is not null then update public.account_tokens set used_at=now() where token_hash=digest; end if;
 return owner_id;
end; $$;

create table if not exists public.email_outbox (
 id uuid primary key default gen_random_uuid(),dedupe_key text unique not null, user_id uuid references public.profiles(id) on delete cascade, application_id uuid references public.applications(id) on delete cascade,
 recipient text not null,subject text not null,body text not null,status text not null default 'queued' check(status in ('queued','sending','sent','failed','cancelled')),attempts integer not null default 0,next_attempt_at timestamptz not null default now(),claimed_at timestamptz,sent_at timestamptz,last_error text,expires_at timestamptz,created_at timestamptz not null default now()
);
create index if not exists email_outbox_pending on public.email_outbox(next_attempt_at,created_at) where status in ('queued','failed','sending');
create index if not exists email_outbox_user on public.email_outbox(user_id);
create index if not exists email_outbox_application on public.email_outbox(application_id);
create or replace function public.claim_email_outbox(batch_size integer default 100,wanted_id uuid default null) returns setof public.email_outbox language sql security invoker set search_path='' as $$
 update public.email_outbox set status='sending',claimed_at=now(),attempts=attempts+1
 where id in (select id from public.email_outbox where (wanted_id is null or id=wanted_id) and ((status in ('queued','failed') and next_attempt_at<=now()) or (status='sending' and claimed_at<now()-interval '15 minutes')) and attempts<8 and (expires_at is null or expires_at>now()) order by created_at for update skip locked limit least(greatest(batch_size,1),100)) returning *;
$$;

create table if not exists public.saved_searches (id uuid primary key default gen_random_uuid(),user_id uuid not null references public.profiles(id) on delete cascade,name text not null,filters jsonb not null, email_alert boolean not null default false,last_checked_at timestamptz,seen_ids jsonb not null default '[]',created_at timestamptz not null default now());
create index if not exists saved_searches_owner on public.saved_searches(user_id,created_at desc);
create table if not exists public.job_reports (id uuid primary key default gen_random_uuid(),job_id text not null references public.job_catalogue(id) on delete cascade,reason text not null check(reason in ('closed','fraud','broken_link','wrong_location','other')),details text not null default '',status text not null default 'open',created_at timestamptz not null default now());
create index if not exists job_reports_listing on public.job_reports(job_id,created_at desc);

alter table public.catalogue_refresh add column if not exists last_error text;
alter table public.catalogue_refresh add column if not exists archive_page integer not null default 9;
alter table public.catalogue_refresh add column if not exists started_at timestamptz;
create or replace function public.claim_catalogue_refresh() returns boolean language plpgsql security invoker set search_path='' as $$
declare claimed integer;
begin
 update public.catalogue_refresh set next_refresh_at=now()+interval '10 minutes',started_at=now() where id=1 and next_refresh_at<=now();
 get diagnostics claimed=row_count;
 return claimed=1;
end; $$;

-- Explicit service-only access; public clients cannot call privileged functions.
do $$ declare tab text; begin
 foreach tab in array array['api_rate_limits','account_tokens','email_outbox','saved_searches','job_reports'] loop
  execute format('alter table public.%I enable row level security',tab);
  execute format('revoke all on public.%I from anon, authenticated',tab);
  execute format('grant all on public.%I to service_role',tab);
 end loop;
end $$;
do $$ declare tab text; begin
 foreach tab in array array['profiles','applications','application_events','career_profiles','job_catalogue','catalogue_refresh','api_rate_limits','account_tokens','email_outbox','saved_searches','job_reports'] loop
  execute format('create policy app_service_only on public.%I for all to service_role using(true) with check(true)',tab);
 end loop;
end $$;
revoke execute on function public.consume_request_limit(text,integer,integer) from public,anon,authenticated;
revoke execute on function public.consume_account_token(text,text,text) from public,anon,authenticated;
revoke execute on function public.claim_email_outbox(integer,uuid) from public,anon,authenticated;
grant execute on function public.consume_request_limit(text,integer,integer) to service_role;
grant execute on function public.consume_account_token(text,text,text) to service_role;
grant execute on function public.claim_email_outbox(integer,uuid) to service_role;
create index if not exists catalogue_category_fresh on public.job_catalogue((payload->>'category'),last_checked_at desc) where status='active';
create index if not exists catalogue_search_terms on public.job_catalogue using gin(to_tsvector('english'::regconfig,coalesce(payload->>'title','')||' '||coalesce(payload->>'company','')||' '||coalesce(payload->>'description','')||' '||coalesce(payload->>'search_terms',''))) where status='active';
create or replace function public.search_ghana_catalogue(filters jsonb default '{}') returns jsonb language sql stable security invoker set search_path='' as $$
 with eligible as (
  select payload,first_seen_at,
   case when lower(coalesce(payload->>'source_status',''))='closed' or deadline<now() then 'closed' when deadline is null then 'unconfirmed' else 'open' end as availability
  from public.job_catalogue where status='active' and last_checked_at>now()-interval '48 hours' and payload->>'duplicate_of' is null
   and payload->>'category'=coalesce(filters->>'category','jobs')
   and (payload->>'category'='scholarships' or deadline is null or deadline>=now())
   and (coalesce(filters->>'q','')='' or to_tsvector('english'::regconfig,coalesce(payload->>'title','')||' '||coalesce(payload->>'company','')||' '||coalesce(payload->>'description','')||' '||coalesce(payload->>'search_terms','')) @@ plainto_tsquery('english'::regconfig,filters->>'q'))
   and (coalesce(filters->>'region','')='' or payload->'regions' ? (filters->>'region'))
   and (coalesce(filters->>'town','')='' or position(lower(filters->>'town') in lower(payload->>'location'))>0)
   and (coalesce(filters->>'job_type','all') in ('','all') or payload->>'job_type'=filters->>'job_type')
   and (coalesce(filters->>'experience','')='' or payload->>'experience'=filters->>'experience')
   and (coalesce(filters->>'study_level','')='' or payload->'study_levels' ? (filters->>'study_level'))
   and (coalesce(filters->>'destination','')='' or payload->>'study_destination'=filters->>'destination')
   and (coalesce(filters->>'funding','')='' or payload->>'funding'=filters->>'funding')
   and (coalesce(filters->>'industry','')='' or position(lower(filters->>'industry') in lower(coalesce(payload->>'industry','')||' '||coalesce(payload->>'title','')||' '||coalesce(payload->>'search_terms','')))>0)
   and ((coalesce(filters->>'salary_min','')='' and coalesce(filters->>'salary_max','')='') or (
     payload->>'salary_currency'=coalesce(nullif(filters->>'salary_currency',''),'GHS')
     and (coalesce(filters->>'salary_period','')='' or payload->>'salary_period'=filters->>'salary_period')
     and coalesce((payload->>'salary_max')::numeric,(payload->>'salary_min')::numeric)>=coalesce(nullif(filters->>'salary_min','')::numeric,0)
     and coalesce((payload->>'salary_min')::numeric,(payload->>'salary_max')::numeric)<=coalesce(nullif(filters->>'salary_max','')::numeric,1e15)))
 ), filtered as (
  select (payload-'check_url')||jsonb_build_object('first_seen_at',first_seen_at)||case when payload->>'category'='scholarships' then jsonb_build_object('listing_status',availability,'can_apply',availability='open') else '{}'::jsonb end as job
  from eligible where payload->>'category'<>'scholarships' or coalesce(filters->>'availability','open')='all' or availability=coalesce(filters->>'availability','open')
 ), page_rows as (
  select job from filtered order by coalesce(job->>'created',job->>'first_seen_at') desc,job->>'id'
  limit 20 offset ((greatest(1,coalesce(nullif(filters->>'page','')::integer,1))-1)::bigint*20)
 ) select jsonb_build_object('jobs',coalesce((select jsonb_agg(job) from page_rows),'[]'::jsonb),'total',(select count(*)from filtered),'page',greatest(1,coalesce(nullif(filters->>'page','')::integer,1)),'has_more',greatest(1,coalesce(nullif(filters->>'page','')::integer,1))::bigint*20<(select count(*)from filtered));
$$;
revoke execute on function public.search_ghana_catalogue(jsonb) from public,anon,authenticated;
grant execute on function public.search_ghana_catalogue(jsonb) to service_role;

update public.applications set reminder_auto=false where reminder_date is not null and (deadline is null or reminder_date<>deadline-2);
commit;
