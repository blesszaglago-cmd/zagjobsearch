import {NextRequest} from 'next/server';
import {searchJobs} from '@/lib/jobs-server';
export async function GET(request:NextRequest){try{return Response.json(await searchJobs(request.nextUrl.searchParams));}catch{return Response.json({detail:'The Ghana catalogue is temporarily unavailable. Please try again shortly.'},{status:503});}}
