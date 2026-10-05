import {NextRequest} from 'next/server';
import {getJob} from '@/lib/jobs-server';
export async function GET(request:NextRequest,{params}:{params:Promise<{id:string}>}){try{const {id}=await params;const job=await getJob(id,request.nextUrl.searchParams);return job?Response.json(job):Response.json({detail:'This listing is no longer available. Search again for current opportunities.'},{status:404})}catch{return Response.json({detail:'The source could not load this posting. Please try again.'},{status:503})}}
