export type Application = { id?: string; job_title: string; company_name: string; company_website: string; location: string; source_url: string; source: string; date_applied: string | null; status: string; notes: string; salary_min: number | null; salary_max: number | null; salary_currency: string; salary_period: string; contact_person: string; deadline: string | null; reminder_date: string | null; email_reminder: boolean; created_at?: string };
export const statuses = ["started","applied","interview","offer","rejected","ghosted"];
export const blankApplication: Application = {job_title:"",company_name:"",company_website:"",location:"",source_url:"",source:"manual",date_applied:null,status:"started",notes:"",salary_min:null,salary_max:null,salary_currency:"",salary_period:"",contact_person:"",deadline:null,reminder_date:null,email_reminder:false};
export async function accountRequest(path:string,options:RequestInit={}) {
 const response=await fetch(`/api/account/${path}`,options);
 const data=await response.json();
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:response.status===401?'Log in to use your workspace.':'Could not complete this request.');
 return data;
}
