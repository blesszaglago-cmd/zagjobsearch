import { timingSafeEqual } from "node:crypto";
import { API_URL } from "@/lib/api";
export async function GET(request:Request){
 const expected=`Bearer ${process.env.CRON_SECRET||''}`,actual=request.headers.get('authorization')||'';
 if(!process.env.CRON_SECRET||actual.length!==expected.length||!timingSafeEqual(Buffer.from(actual),Buffer.from(expected)))return new Response('Unauthorised',{status:401});
 try{const r=await fetch(`${API_URL}/cron/reminders`,{headers:{Authorization:expected},cache:'no-store',signal:AbortSignal.timeout(45000)});return new Response(await r.text(),{status:r.status,headers:{'Content-Type':'application/json'}})}catch{return Response.json({error:'Reminder service unavailable'},{status:503})}
}
export const maxDuration=60;
