begin;
create extension if not exists pg_cron;
create extension if not exists pg_net;
create schema if not exists app_private;
revoke all on schema app_private from public,anon,authenticated;
grant usage on schema app_private to service_role;
create table if not exists app_private.maintenance_config(id integer primary key check(id=1), secret text not null default gen_random_uuid()::text||gen_random_uuid()::text);
alter table app_private.maintenance_config enable row level security;
revoke all on app_private.maintenance_config from public,anon,authenticated;
grant select on app_private.maintenance_config to service_role;
create policy maintenance_service_read on app_private.maintenance_config for select to service_role using(true);
insert into app_private.maintenance_config(id) values(1) on conflict do nothing;
create or replace function public.verify_maintenance_key(candidate text) returns boolean language sql stable security invoker set search_path='' as $$
 select exists(select 1 from app_private.maintenance_config where id=1 and sha256(convert_to(secret,'UTF8'))=sha256(convert_to(candidate,'UTF8')));
$$;
revoke execute on function public.verify_maintenance_key(text) from public,anon,authenticated;
grant execute on function public.verify_maintenance_key(text) to service_role;
create or replace function app_private.dispatch_maintenance(task text) returns bigint language plpgsql security invoker set search_path='' as $$
declare target text; key text; request_id bigint;
begin
 target=case task when 'catalogue' then '/catalogue/refresh' when 'email' then '/cron/reminders' when 'check' then '/cron/status' else null end;
 if target is null then raise exception 'Unknown maintenance task'; end if;
 select secret into key from app_private.maintenance_config where id=1;
 select net.http_get(url:='https://zagjobsearch-api.vercel.app'||target,headers:=jsonb_build_object('Authorization','Bearer '||key),timeout_milliseconds:=200000) into request_id;
 return request_id;
end; $$;
revoke execute on function app_private.dispatch_maintenance(text) from public,anon,authenticated,service_role;
-- A light due check every 15 minutes. Successful collection sets a six-hour lease.
select cron.schedule('ghana-catalogue-refresh','*/15 * * * *',$$select app_private.dispatch_maintenance('catalogue');$$);
select cron.schedule('ghana-requested-email-worker','7,22,37,52 * * * *',$$select app_private.dispatch_maintenance('email');$$);
select cron.schedule('ghana-private-data-retention','30 3 * * *',$$
 delete from public.api_rate_limits where expires_at<now()-interval '1 day';
 delete from public.account_tokens where expires_at<now()-interval '1 day';
 delete from public.email_outbox where created_at<now()-interval '7 days';
 delete from public.applications where deleted_at<now()-interval '30 days';
$$);
commit;
