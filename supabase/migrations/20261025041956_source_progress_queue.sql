begin;
alter table public.catalogue_refresh
  add column source_progress jsonb not null default '{}'::jsonb,
  add constraint catalogue_source_progress_object check (jsonb_typeof(source_progress) = 'object'),
  add constraint catalogue_source_progress_size check (octet_length(source_progress::text) <= 1048576);
comment on column public.catalogue_refresh.source_progress is
  'Private bounded public-detail retry queues and publisher Retry-After state. No source bodies, secrets or user records.';
commit;
