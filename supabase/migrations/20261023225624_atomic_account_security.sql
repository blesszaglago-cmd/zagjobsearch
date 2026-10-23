begin;

-- A provider identity belongs to one workspace. Never replace another binding.
create unique index if not exists profiles_auth_identity_unique
  on public.profiles(auth_user_id) where auth_user_id is not null;

alter table public.account_tokens add column if not exists issued_session_version integer;
update public.account_tokens t set issued_session_version=p.session_version
  from public.profiles p where t.user_id=p.id and t.issued_session_version is null;

-- Keep token issuance compatible while the old and new API deployments overlap.
create or replace function public.stamp_account_token_version() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
  if new.issued_session_version is null then
    select session_version into new.issued_session_version from public.profiles where id=new.user_id;
  end if;
  return new;
end; $$;
create trigger account_token_version before insert on public.account_tokens
  for each row execute function public.stamp_account_token_version();
alter table public.account_tokens alter column issued_session_version set not null;

create or replace function public.bind_google_account(
  provider_id uuid, verified_email text, display_name text, unusable_password_hash text
) returns jsonb language plpgsql security invoker set search_path='' as $$
declare p public.profiles; address text := lower(verified_email);
begin
  if provider_id is null or address is null or length(address)>320 or position('@' in address)<2
     or unusable_password_hash is null or unusable_password_hash !~ '^!google:[a-f0-9]{64}$' then
    raise exception 'Invalid provider identity';
  end if;
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(provider_id::text,0));
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(address,1));
  select * into p from public.profiles where auth_user_id=provider_id for update;
  if not found then
    select * into p from public.profiles where lower(email)=address for update;
    if found then
      if p.auth_user_id is not null then raise exception 'Identity already linked'; end if;
      -- An unverified signup may have been created by someone who does not own
      -- the mailbox. Do not retain that person's password, sessions or links.
      update public.profiles set
        password_hash=case when email_verified_at is null then unusable_password_hash else password_hash end,
        email_verified_at=now(), requires_verification=false, auth_user_id=provider_id,
        session_version=session_version+1
        where id=p.id returning * into p;
      update public.account_tokens set used_at=now() where user_id=p.id and used_at is null;
    else
      insert into public.profiles(email,full_name,country,date_of_birth,password_hash,
        auth_user_id,email_verified_at,requires_verification,onboarding_complete)
        values(address,left(coalesce(nullif(trim(display_name),''),'Job seeker'),100),'GH',null,
          unusable_password_hash,provider_id,now(),false,false) returning * into p;
    end if;
  end if;
  return jsonb_build_object('id',p.id,'session_version',p.session_version,'onboarding_complete',p.onboarding_complete);
end; $$;

create or replace function public.rotate_account_session(
  owner_id uuid, request_version integer, expected_password_hash text default null,
  replacement_password_hash text default null
) returns integer language plpgsql security invoker set search_path='' as $$
declare p public.profiles; next_version integer;
begin
  select * into p from public.profiles where id=owner_id for update;
  if not found or p.session_version<>request_version then return null; end if;
  if replacement_password_hash is not null and
     (expected_password_hash is null or p.password_hash<>expected_password_hash) then return null; end if;
  update public.profiles set session_version=session_version+1,
    password_hash=coalesce(replacement_password_hash,password_hash)
    where id=owner_id returning session_version into next_version;
  if replacement_password_hash is not null then
    update public.account_tokens set used_at=now() where user_id=owner_id and used_at is null;
  end if;
  return next_version;
end; $$;

create or replace function public.consume_account_token(
  digest text, token_purpose text, new_password_hash text default null
) returns uuid language plpgsql security invoker set search_path='' as $$
declare tok public.account_tokens; p public.profiles; owner_id uuid;
begin
  -- All credential changes lock the profile first, then re-read the token.
  -- Two different reset links cannot both win a concurrent request.
  select user_id into owner_id from public.account_tokens where token_hash=digest;
  if not found then return null; end if;
  select * into p from public.profiles where id=owner_id for update;
  if not found then return null; end if;
  select * into tok from public.account_tokens
    where token_hash=digest and purpose=token_purpose and used_at is null and expires_at>now()
      and issued_session_version=p.session_version for update;
  if not found then return null; end if;
  owner_id := null;
  if token_purpose='reset' then
    if new_password_hash is null then return null; end if;
    update public.profiles set password_hash=new_password_hash,email_verified_at=now(),
      requires_verification=false,session_version=session_version+1
      where id=tok.user_id and lower(email)=lower(tok.target_email) returning id into owner_id;
  elsif token_purpose='verify' then
    update public.profiles set email_verified_at=now(),requires_verification=false
      where id=tok.user_id and lower(email)=lower(tok.target_email) returning id into owner_id;
  elsif token_purpose='change_email' then
    update public.profiles set email=lower(tok.target_email),email_verified_at=now(),
      requires_verification=false,session_version=session_version+1
      where id=tok.user_id returning id into owner_id;
  end if;
  if owner_id is not null then
    update public.account_tokens set used_at=now() where user_id=owner_id and used_at is null
      and (token_hash=digest or token_purpose in ('reset','change_email'));
  end if;
  return owner_id;
end; $$;

revoke execute on function public.bind_google_account(uuid,text,text,text) from public,anon,authenticated;
revoke execute on function public.rotate_account_session(uuid,integer,text,text) from public,anon,authenticated;
revoke execute on function public.consume_account_token(text,text,text) from public,anon,authenticated;
revoke execute on function public.stamp_account_token_version() from public,anon,authenticated;
grant execute on function public.bind_google_account(uuid,text,text,text) to service_role;
grant execute on function public.rotate_account_session(uuid,integer,text,text) to service_role;
grant execute on function public.consume_account_token(text,text,text) to service_role;
grant execute on function public.stamp_account_token_version() to service_role;

commit;
