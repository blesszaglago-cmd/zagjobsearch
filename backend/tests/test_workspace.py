import io,os,sys,types,unittest
from datetime import date
from unittest.mock import MagicMock,patch,call
from fastapi import HTTPException,UploadFile
fake_database=types.ModuleType('database.supabase_client');fake_database.supabase=MagicMock()
with patch.dict(sys.modules,{'database.supabase_client':fake_database}):import workspace_api as workspace
import sessions
class WorkspaceTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):self.env=patch.dict(os.environ,{'SESSION_SECRET':'test-secret'});self.env.start()
 def tearDown(self):self.env.stop()
 def test_sessions(self):
  token=sessions.issue_session('owner');self.assertEqual(sessions.verify_session(token),'owner')
  for invalid in [token+'x','abc','x.y']:
   with self.assertRaises(HTTPException):sessions.verify_session(invalid)
  with patch('sessions.time.time',return_value=10):old=sessions.issue_session('owner')
  with self.assertRaises(HTTPException):sessions.verify_session(old)
  with self.assertRaises(HTTPException):sessions.current_user(None)
 def test_status_and_reminder(self):
  a=workspace.Application(job_title='Analyst',company_name='Example',deadline=date(2026,10,20))
  self.assertIsNone(a.record()['date_applied']);self.assertEqual(a.record()['reminder_date'],'2026-10-18')
  self.assertEqual(a.model_copy(update={'status':'applied'}).record()['date_applied'],date.today().isoformat())
  with self.assertRaises(ValueError):workspace.Application(job_title='Analyst',company_name='Example',source_url='javascript:alert(1)')
 def test_cross_account_access(self):
  db=MagicMock();db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data=[];db.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data=[]
  with patch.object(workspace,'supabase',db):
   with self.assertRaises(HTTPException):workspace.update_application('record',workspace.Application(job_title='Analyst',company_name='Example'),'other')
   with self.assertRaises(HTTPException):workspace.events('record','other')
   with self.assertRaises(HTTPException):workspace.delete_application('record','other')
  self.assertIn(call('user_id','other'),db.table.return_value.select.return_value.eq.return_value.eq.call_args_list)
 def test_cv_truth(self):
  d=workspace.CVRequest(verified_text='Ama Mensah\nBuilt reports with Excel and SQL for a student project.',job_description='Python and SQL are required',confirmed=True)
  r=workspace.prepare_cv(d);self.assertEqual(r['matched'],['sql']);self.assertEqual(r['missing'],['python']);self.assertNotIn('Python',r['document']);self.assertIn(d.verified_text,r['document'])
  with self.assertRaises(HTTPException):workspace.prepare_cv(d.model_copy(update={'confirmed':False}))
 async def test_upload(self):
  u=UploadFile(filename='cv.txt',file=io.BytesIO(b'Ama Mensah: SQL and Excel student projects in Accra.'));r=await workspace.extract(u,'owner');self.assertIn('Ama',r['text']);self.assertTrue(u.file.closed)
  with self.assertRaises(HTTPException):await workspace.extract(UploadFile(filename='cv.exe',file=io.BytesIO(b'bad')),'owner')
 def test_downloads(self):
  pdf=workspace.export(workspace.Export(text='Ama Mensah\nSQL and Excel',format='pdf'),'owner');word=workspace.export(workspace.Export(text='Ama Mensah\nSQL and Excel',format='docx'),'owner');self.assertTrue(pdf.body.startswith(b'%PDF'))
  from docx import Document
  self.assertIn('Ama Mensah','\n'.join(p.text for p in Document(io.BytesIO(word.body)).paragraphs));self.assertEqual(pdf.headers['cache-control'],'no-store')
