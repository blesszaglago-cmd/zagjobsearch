begin;
create or replace function public.consume_account_token(digest text, token_purpose text, new_password_hash text default null) returns uuid language plpgsql security invoker set search_path='' as $$
declare tok public.account_tokens; owner_id uuid;
begin
 select * into tok from public.account_tokens where token_hash=digest and purpose=token_purpose and used_at is null and expires_at>now() for update;
 if not found then return null; end if;
 if token_purpose='reset' then
  if new_password_hash is null then return null; end if;
  update public.profiles set password_hash=new_password_hash,email_verified_at=now(),requires_verification=false,session_version=session_version+1 where id=tok.user_id and lower(email)=lower(tok.target_email) returning id into owner_id;
 elsif token_purpose='verify' then
  update public.profiles set email_verified_at=now(),requires_verification=false where id=tok.user_id and lower(email)=lower(tok.target_email) returning id into owner_id;
 elsif token_purpose='change_email' then
  update public.profiles set email=lower(tok.target_email),email_verified_at=now(),requires_verification=false,session_version=session_version+1 where id=tok.user_id returning id into owner_id;
 end if;
 if owner_id is not null then
  update public.account_tokens set used_at=now() where user_id=owner_id and used_at is null and (token_hash=digest or token_purpose in ('reset','change_email'));
 end if;
 return owner_id;
end; $$;
revoke execute on function public.consume_account_token(text,text,text) from public,anon,authenticated;
grant execute on function public.consume_account_token(text,text,text) to service_role;
commit;
