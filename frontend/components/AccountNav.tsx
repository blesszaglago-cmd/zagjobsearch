"use client";
import { useEffect, useState } from "react";
import {useRouter} from "next/navigation";
import Link from "next/link";
export default function AccountNav() {
 const router=useRouter();
 const [signedIn,setSignedIn]=useState(false);
 useEffect(()=>{const c=new AbortController();fetch('/api/account/me',{signal:c.signal}).then(r=>{if(!c.signal.aborted)setSignedIn(r.ok)}).catch(()=>{});return()=>c.abort()},[]);
 return <div className="nav-actions">{signedIn?<><Link href="/tracker">My workspace</Link><button className="btn-outline" onClick={async()=>{await fetch('/api/account/logout',{method:'POST'});setSignedIn(false);router.push('/');router.refresh()}}>Sign out</button></>:<><Link href="/login">Log in</Link><Link href="/signup" className="btn-primary">Create account ↗</Link></>}</div>
}
