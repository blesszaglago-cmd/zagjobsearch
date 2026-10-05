import hmac
import os
import smtplib
from datetime import date,datetime,timezone
from email.message import EmailMessage
from fastapi import APIRouter,Header,HTTPException
from database.supabase_client import supabase
router=APIRouter()
@router.get('/cron/reminders')
def send_reminders(authorization: str = Header(default='')):
    secret=os.getenv('CRON_SECRET')
    if not secret or not hmac.compare_digest(authorization,'Bearer '+secret): raise HTTPException(401,'Not authorised')
    if not all(os.getenv(k) for k in ['SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM']):
        return {'sent':0,'configured':False}
    today=date.today().isoformat()
    due=supabase.table('applications').select('*').eq('email_reminder',True).eq('status','started').lte('reminder_date',today).is_('email_reminder_sent_at','null').limit(5).execute().data
    due=[a for a in due if not a.get('deadline') or a['deadline']>=today]
    sent=0
    with smtplib.SMTP_SSL(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','465')),timeout=10) as smtp:
        smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
        for item in due:
            claimed=supabase.table('applications').update({'email_reminder_sent_at':datetime.now(timezone.utc).isoformat()}).eq('id',item['id']).is_('email_reminder_sent_at','null').execute().data
            if not claimed: continue
            try:
                profile=supabase.table('profiles').select('email').eq('id',item['user_id']).single().execute().data
                mail=EmailMessage();mail['From']=os.environ['SMTP_FROM'];mail['To']=profile['email'];mail['Subject']='Your ZagJobSearch application reminder'
                mail.set_content(f"Your reminder for {item['job_title']} at {item['company_name']} is due.\n"+(f"Application deadline: {item['deadline']}\n" if item.get('deadline') else '')+f"\nReview your tracker: {os.getenv('FRONTEND_URL','https://zagjobsearch.vercel.app')}/tracker\n\nYou requested this reminder in your application record. You can turn off email reminders there.")
                smtp.send_message(mail);sent+=1
            except Exception:
                supabase.table('applications').update({'email_reminder_sent_at':None}).eq('id',item['id']).execute()
    return {'sent':sent,'configured':True}
