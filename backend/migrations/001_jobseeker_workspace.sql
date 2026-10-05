-- Apply in the Supabase SQL editor. Existing profiles and login records are preserved.
begin;
create table if not exists public.applications (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references public.profiles(id) on delete cascade,
 job_title text not null, company_name text not null, company_website text not null default '', location text not null default '',
 source_url text not null default '', source text not null default 'manual', date_applied date,
 status text not null default 'started' check(status in ('started','applied','interview','offer','rejected','ghosted')),
 notes text not null default '', salary_min numeric, salary_max numeric, salary_currency text not null default '', salary_period text not null default '',
 contact_person text not null default '', deadline date, reminder_date date, email_reminder boolean not null default false,
 email_reminder_sent_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index if not exists applications_user_date on public.applications(user_id,date_applied desc);
create table if not exists public.application_events (
 id uuid primary key default gen_random_uuid(), application_id uuid not null references public.applications(id) on delete cascade,
 event_type text not null, old_value text, new_value text, note text, created_at timestamptz not null default now()
);
create table if not exists public.career_profiles (
 user_id uuid primary key references public.profiles(id) on delete cascade, verified_text text not null default '', updated_at timestamptz not null default now()
);
alter table public.applications enable row level security;
alter table public.application_events enable row level security;
alter table public.career_profiles enable row level security;
-- Access is through the authenticated FastAPI service. No browser anon/authenticated table grants.
revoke all on public.applications,public.application_events,public.career_profiles from anon,authenticated;
grant all on public.applications,public.application_events,public.career_profiles to service_role;
create or replace function public.record_application_event() returns trigger language plpgsql set search_path=public as $$
begin
 if TG_OP='INSERT' then
  insert into public.application_events(application_id,event_type,new_value) values(new.id,'created',new.status);
 else
  if old.status is distinct from new.status then
   insert into public.application_events(application_id,event_type,old_value,new_value) values(new.id,'status_change',old.status,new.status);
  end if;
  if old.notes is distinct from new.notes then
   insert into public.application_events(application_id,event_type,note) values(new.id,'note',new.notes);
  end if;
 end if;
 return new;
end $$;
drop trigger if exists application_event_log on public.applications;
create trigger application_event_log after insert or update on public.applications for each row execute function public.record_application_event();
commit;
