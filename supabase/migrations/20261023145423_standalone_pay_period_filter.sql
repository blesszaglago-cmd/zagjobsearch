-- Pay-period filters also work without a numeric salary bound.
-- Preserve academic states, source filters and service-only execution.
begin;
create or replace function public.search_ghana_catalogue(filters jsonb default '{}') returns jsonb language sql stable security invoker set search_path='' as $$
 with eligible as (
  select payload,first_seen_at,
   case when lower(coalesce(payload->>'source_status',''))='closed' or deadline<now() then 'closed' when payload->>'application_window'='rolling' then 'open' when deadline is null then 'unconfirmed' else 'open' end as availability
  from public.job_catalogue where status='active' and last_checked_at>now()-interval '48 hours' and payload->>'duplicate_of' is null
   and payload->>'category'=coalesce(filters->>'category','jobs')
   and (coalesce(filters->>'source','')='' or source_key=filters->>'source')
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
   and (coalesce(filters->>'salary_period','')='' or (payload->>'salary_period'=filters->>'salary_period' and payload->>'salary_currency'=coalesce(nullif(filters->>'salary_currency',''),'GHS')))
   and ((coalesce(filters->>'salary_min','')='' and coalesce(filters->>'salary_max','')='') or (
     payload->>'salary_currency'=coalesce(nullif(filters->>'salary_currency',''),'GHS')
     and coalesce((payload->>'salary_max')::numeric,(payload->>'salary_min')::numeric)>=coalesce(nullif(filters->>'salary_min','')::numeric,0)
     and coalesce((payload->>'salary_min')::numeric,(payload->>'salary_max')::numeric)<=coalesce(nullif(filters->>'salary_max','')::numeric,1e15)))
 ), filtered as (
  select (payload-'check_url')||jsonb_build_object('first_seen_at',first_seen_at)||case when payload->>'category'='scholarships' then jsonb_build_object('listing_status',availability,'can_apply',availability='open') else '{}'::jsonb end as job
  from eligible where payload->>'category'<>'scholarships' or coalesce(filters->>'availability','open')='all' or availability=coalesce(filters->>'availability','open')
 ), page_rows as (
  select job from filtered order by coalesce(job->>'created',job->>'first_seen_at') desc,job->>'id'
  limit 20 offset ((greatest(1,coalesce(nullif(filters->>'page','')::integer,1))-1)::bigint*20)
 ) select jsonb_build_object('jobs',coalesce((select jsonb_agg(job) from page_rows),'[]'::jsonb),'scholarship_counts',(select jsonb_build_object('open',count(*) filter(where availability='open'),'unconfirmed',count(*) filter(where availability='unconfirmed'),'closed',count(*) filter(where availability='closed')) from eligible where payload->>'category'='scholarships'),'total',(select count(*)from filtered),'page',greatest(1,coalesce(nullif(filters->>'page','')::integer,1)),'has_more',greatest(1,coalesce(nullif(filters->>'page','')::integer,1))::bigint*20<(select count(*)from filtered));
$$;
revoke execute on function public.search_ghana_catalogue(jsonb) from public,anon,authenticated;
grant execute on function public.search_ghana_catalogue(jsonb) to service_role;

-- Correct the known Sr. abbreviation in existing public catalogue records.
-- Do not change source timestamps or overwrite a supplied experience level.
update public.job_catalogue
set payload=jsonb_set(payload,'{experience}','"senior"'::jsonb)
where status='active' and payload->>'category' in ('jobs','early','remote')
 and payload->>'experience'='unspecified' and payload->>'title' ~* '\msr\M';

commit;
