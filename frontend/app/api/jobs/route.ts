import {NextRequest} from 'next/server';
import {searchJobs} from '@/lib/jobs-server';
export async function GET(request:NextRequest){return Response.json(await searchJobs(request.nextUrl.searchParams));}
