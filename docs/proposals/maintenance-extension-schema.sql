-- Relocation preflight verified: pg_net 0.20.4 matches the available version,
-- the queue is empty, and pg_depend reports no external dependencies.
-- Only our PL/pgSQL dispatcher and Supabase's grant event trigger reference
-- net.http_get. Both use qualified net names; the dispatcher is recompiled below.
-- Atomic transaction + no CASCADE: any failure restores the original extension,
-- grants and dispatcher. No profile, application or catalogue data is changed.
begin;
set local lock_timeout='5s';
set local statement_timeout='20s';
lock table net.http_request_queue in access exclusive mode;
do $$ begin
 if exists(select 1 from net.http_request_queue) then raise exception 'Queue is not empty; retry after delivery'; end if;
 if (select extversion from pg_extension where extname='pg_net')<>'0.20.4' then raise exception 'Unexpected pg_net version'; end if;
end $$;
drop extension pg_net;
create extension pg_net with schema extensions version '0.20.4';
-- Recreate the only application wrapper against the replacement net functions.
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
do $$ begin
 if to_regprocedure('net.http_get(text,jsonb,jsonb,integer)') is null then raise exception 'Replacement HTTP function missing'; end if;
end $$;
-- Queue a read-only protected status check; no email or catalogue writes.
select app_private.dispatch_maintenance('check');
commit;
