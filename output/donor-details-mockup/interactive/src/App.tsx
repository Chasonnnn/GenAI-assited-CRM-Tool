import React, { useState } from 'react';
import { Home, Inbox, HandHeart, Users, CheckSquare, BarChart3, Settings, ChevronsUpDown, Bell, Zap, Bot, Sparkles, ChevronRight, HeartHandshake, Search, PanelLeft, Heart, Sun, MoreVertical, User, ChevronLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { TooltipProvider } from '@/components/ui/tooltip';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSub, DropdownMenuSubTrigger, DropdownMenuSubContent } from '@/components/ui/dropdown-menu';
import { DonorOverviewTab, type PrototypeDonorRecord } from './DonorOverviewTab';
import { EntityActivityTimeline } from '@/components/activity/EntityActivityTimeline';
import { EntityNotes } from '@/components/notes/EntityNotes';
import { EntityDocuments } from '@/components/documents/EntityDocuments';
import { SurrogateHistoryTab } from '@/components/surrogates/detail/SurrogateHistoryTab';
import { SurrogateTasksCalendarHeader } from '@/components/surrogates/SurrogateTasksCalendarHeader';
import { SurrogateTasksListView } from '@/components/surrogates/SurrogateTasksListView';
import { SurrogateTasksEmptyState } from '@/components/surrogates/SurrogateTasksEmptyState';
import { buildTaskGroups, countCompletedTasks, getOrphanedCompletedTasks } from '@/components/surrogates/surrogate-task-derivations';
import { DonorDetailHeader } from './DonorDetailHeader';
import { LocalNavigation } from './LocalLink';
import type { PipelineStage } from '@/lib/api/pipelines';
import type { TaskListItem } from '@/lib/api/tasks';
import type { EntityActivity, EntityStageHistory } from '@/lib/api/activity';
import type { Attachment } from '@/lib/api/attachments';
import { addMonths, subMonths, format, startOfMonth, endOfMonth, startOfWeek, endOfWeek, eachDayOfInterval, isSameMonth } from 'date-fns';

const NAV = [['Dashboard', Home], ['Tickets (beta)', Inbox], ['Surrogates', HandHeart], ['Intended Parents', Users], ['Donors (beta)', Heart], ['Matches', HeartHandshake], ['Tasks & Scheduling', CheckSquare], ['Automation', Zap], ['AI Studio (beta)', Sparkles], ['Reports', BarChart3], ['AI Assistant', Bot], ['Settings', Settings]] as const;
const stages: PipelineStage[] = ['New', 'Contacted', 'Pre-Screening', 'Screening', 'Available', 'Matched'].map((label, order) => ({ id: `stage-${order}`, stage_key: label.toLowerCase().replaceAll(' ', '_'), slug: label.toLowerCase(), label, color: ['#3b82f6', '#06b6d4', '#8b5cf6', '#a855f7', '#22c55e', '#10b981'][order]!, order, stage_type: 'intake', is_active: true }));
const initialActivity: EntityActivity[] = [
  { id: 'a3', activity_type: 'note_added', actor_user_id: 'alex', actor_name: 'Alex Morgan', created_at: '2026-09-13T18:00:00-04:00', details: { preview: 'Introductory call confirmed for Tuesday.' } },
  { id: 'a2', activity_type: 'assigned', actor_user_id: 'alex', actor_name: 'Alex Morgan', created_at: '2026-09-12T12:00:00-04:00', details: { owner_name: 'Alex Morgan' } },
  { id: 'a1', activity_type: 'donor_created', actor_user_id: null, actor_name: 'Website', created_at: '2026-09-10T11:00:00-04:00', details: null },
];
const stageHistory: EntityStageHistory[] = [
  { id: 'h1', from_stage_id: null, to_stage_id: 'stage-0', from_label_snapshot: null, to_label_snapshot: 'New', changed_by_user_id: 'alex', reason: 'Initial creation', changed_at: '2026-09-10T11:00:00-04:00' },
  { id: 'h2', from_stage_id: 'stage-0', to_stage_id: 'stage-1', from_label_snapshot: 'New', to_label_snapshot: 'Contacted', changed_by_user_id: 'alex', reason: null, changed_at: '2026-09-12T11:00:00-04:00' },
];
function makeTask(id: string, title: string, due_date: string | null): TaskListItem {
  return { id, title, task_type: 'follow_up', surrogate_id: null, intended_parent_id: null, donor_id: 'donor-demo', surrogate_number: null, donor_number: 'D10001', donor_type: 'egg', donor_name: 'Taylor Morgan', owner_type: 'user', owner_id: 'alex', owner_name: 'Alex Morgan', created_by_user_id: 'alex', created_by_name: 'Alex Morgan', due_date, due_time: null, duration_minutes: 30, is_completed: false, completed_at: null, completed_by_name: null, created_at: '2026-09-13T18:00:00-04:00' };
}
const initialNotes = [{ id: 'n1', author_id: 'alex', author_name: 'Alex Morgan', created_at: '2026-09-13T18:00:00-04:00', body: '<p>Introductory call confirmed for Tuesday.</p>' }];

function Sidebar({ collapsed }: { collapsed: boolean }) {
  return <aside className={`mock-sidebar bg-sidebar text-sidebar-foreground border-r border-sidebar-border ${collapsed ? 'collapsed' : ''}`}>
    <div className="flex h-full flex-col">
      <div className="p-2"><div className="flex items-center gap-2 rounded-lg p-2"><div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground"><Users className="size-4" /></div>{!collapsed && <div className="grid flex-1 text-left text-sm leading-tight"><span className="truncate font-semibold">Surrogacy Force</span><span className="truncate text-xs text-muted-foreground">Design QA Agency</span></div>}</div></div>
      <div className="px-2"><div className="flex h-9 items-center gap-2 rounded-md bg-secondary px-3 text-sm text-muted-foreground"><Search className="size-4" />{!collapsed && 'Search'}</div></div>
      <nav className="flex-1 px-2 pt-3" aria-label="Navigation">{!collapsed && <div className="mb-2 text-xs font-medium text-muted-foreground">Navigation</div>}<div className="flex flex-col gap-1">{NAV.map(([label, Icon]) => <div key={label} className={`flex min-h-9 items-center gap-2 rounded-md p-2 text-sm ${label==='Donors (beta)' ? 'bg-sidebar-accent text-sidebar-accent-foreground' : ''}`}><Icon className="size-4 shrink-0" />{!collapsed && <><span className="flex-1">{label}</span>{['Tasks & Scheduling','Automation','Settings'].includes(label) && <ChevronRight className="size-4" />}</>}</div>)}</div></nav>
      <div className="p-2"><div className="flex items-center gap-2 rounded-lg p-2"><div className="flex size-8 items-center justify-center rounded-full bg-muted"><User className="size-5 text-muted-foreground" /></div>{!collapsed && <><div className="grid flex-1 text-left text-sm leading-tight"><span className="font-semibold">Alex Morgan</span><span className="text-xs text-muted-foreground">designer@example.com</span></div><ChevronsUpDown className="size-4" /></>}</div></div>
    </div>
  </aside>;
}

export function App() {
  const [tab, setTab] = useState('overview');
  const [collapsed, setCollapsed] = useState(false);
  const [modal, setModal] = useState<string|null>(null);
  const [draft, setDraft] = useState('');
  const [stage, setStage] = useState('stage-1');
  const [owner, setOwner] = useState('Alex Morgan');
  const [notes, setNotes] = useState(initialNotes);
  const [tasks, setTasks] = useState([makeTask('t1', 'Review donor questionnaire', '2026-09-14'), makeTask('t2', 'Introductory call', '2026-09-15')]);
  const [activities, setActivities] = useState(initialActivity);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploadedFiles] = useState(() => new Map<string, File>());
  const [viewMode, setViewMode] = useState<'list'|'calendar'>('list');
  const [calendarMonth, setCalendarMonth] = useState(new Date(2026, 8, 14));
  const [record, setRecord] = useState<PrototypeDonorRecord>({ id:'donor-demo', full_name:'Taylor Morgan', email:'taylor.morgan@example.com', phone:'(202) 555-0142', state:'CA', source:'website', created_at:'2026-09-10T15:00:00Z', donor_type:'egg', education:"Bachelor’s degree", date_of_birth:'2000-05-14', race:'asian', height_ft:5.5, weight_lb:135, bmi:null, marital_status:'Single', ssn_masked:null, address_line1:'100 Sample Avenue', address_line2:null, address_city:'Sacramento', address_state:'CA', address_postal:'95814', partner_ssn_masked:null, college:'Example University', nicotine:'No', cannabis:'No', infectious_disease:'Prefer to discuss with the team', previous_donation:'No',   clinic_name: 'Example Fertility Clinic', clinic_address_line1: '100 Example Avenue', clinic_city: 'Sacramento', clinic_state: 'CA', clinic_postal: '95814', clinic_phone: '(202) 555-0156', clinic_fax: null, clinic_email: 'clinic@example.com', lab_clinic_name: 'Example Lab', lab_clinic_address_line1: '200 Sample Street', lab_clinic_city: 'Sacramento', lab_clinic_state: 'CA', lab_clinic_postal: '95814', lab_clinic_phone: '(202) 555-0182', lab_clinic_fax: null, lab_clinic_email: 'lab@example.com'  } as PrototypeDonorRecord);
  const selectedStage = stages.find(s => s.id === stage)!;
  const groups = buildTaskGroups(tasks);
  const dateFormat = (value: string) => new Date(value).toLocaleString('en-US', { year:'numeric', month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' });
  const openModal = (title: string, value='') => { setDraft(value); setModal(title); };
  const activity = (activity_type: string, details: Record<string, string> = {}) => setActivities(a => [{ id: crypto.randomUUID(), activity_type, actor_user_id:'alex', actor_name:'Alex Morgan', created_at:new Date().toISOString(), details }, ...a]);
  const save = () => { if (!draft.trim()) return; if(modal==='Add Task') setTasks(t => [...t, makeTask(crypto.randomUUID(),draft,'2026-09-15')]); setModal(null); };
  return <LocalNavigation.Provider value={setTab}><TooltipProvider><div className="flex min-h-svh w-full bg-sidebar">
    <Sidebar collapsed={collapsed}/>
    <div className="flex min-w-0 flex-1 flex-col bg-background">
      <header className="flex h-16 shrink-0 items-center justify-between gap-2 border-b px-4"><Button variant="ghost" size="icon" onClick={()=>setCollapsed(c=>!c)} aria-label="Toggle sidebar"><PanelLeft className="size-4"/></Button><div className="flex items-center gap-3"><span className="prototype-marker">Mockup · sample data</span><Button variant="ghost" size="sm" onClick={()=>setModal('Surrogate reference')}>Surrogate reference</Button><Button variant="ghost" size="icon" aria-label="Notifications" onClick={()=>setModal('Notifications')}><Bell className="size-4"/></Button><Button variant="ghost" size="icon" aria-label="Toggle theme" onClick={()=>document.documentElement.classList.toggle('dark')}><Sun className="size-4"/></Button></div></header>
      <main className="min-w-0 flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col">
          <DonorDetailHeader surrogateNumber="D10001" statusLabel={selectedStage.label} statusColor={selectedStage.color} isArchived={false} onBack={()=>setTab('overview')}>
            <Button variant="outline" size="sm" onClick={()=>{setDraft(stage);setModal('Change Stage')}}>Change Stage</Button>
            <DropdownMenu><DropdownMenuTrigger aria-label="Donor actions" render={<Button variant="ghost" size="icon-sm"/>}><MoreVertical className="size-4"/></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuSub><DropdownMenuSubTrigger>Assign</DropdownMenuSubTrigger><DropdownMenuSubContent><DropdownMenuItem onClick={()=>setOwner('Unassigned')} disabled={owner==='Unassigned'}>Unassign</DropdownMenuItem>{['Alex Morgan','Jamie Lee'].map(name=><DropdownMenuItem key={name} disabled={owner===name} onClick={()=>setOwner(name)}>{name}</DropdownMenuItem>)}</DropdownMenuSubContent></DropdownMenuSub><DropdownMenuItem onClick={()=>{setTab('overview');setModal('Edit Donor')}}>Edit Donor</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
          </DonorDetailHeader>
          <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
            <Tabs value={tab} onValueChange={setTab} className="w-full">
              <TabsList className="mb-4 overflow-x-auto print:hidden"><TabsTrigger value="overview">Overview</TabsTrigger><TabsTrigger value="notes">Notes {notes.length>0&&`(${notes.length})`}</TabsTrigger><TabsTrigger value="tasks">Tasks {tasks.length>0&&`(${tasks.length})`}</TabsTrigger><TabsTrigger value="history">History</TabsTrigger></TabsList>
              <DonorOverviewTab record={record} onUpdate={async data=>setRecord(current=>({...current,...data}))} activityPanel={<EntityActivityTimeline currentStageId={stage} stages={stages} stageHistory={stageHistory} activities={activities} tasks={tasks} status="ready" historyHref="#history" notesHref="#notes" />}/>
              <TabsContent value="notes"><Card><div className="grid grid-cols-1 divide-y divide-border lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:divide-x lg:divide-y-0">
                <div className="order-last min-w-0 p-6 lg:order-first"><EntityNotes notes={notes} isSubmitting={false} editorLabel="New donor note" currentUser={{id:'alex',name:'Alex Morgan'}} onAddNote={async body=>{setNotes(n=>[{id:crypto.randomUUID(),body,author_id:'alex',author_name:'Alex Morgan',created_at:new Date().toISOString()},...n]);activity('note_added')}} onDeleteNote={async id=>setNotes(n=>n.filter(note=>note.id!==id))}/></div>
                <div className="order-first min-w-0 p-6 lg:sticky lg:top-4 lg:self-start lg:order-last"><div className="mb-4 flex items-center justify-between"><h3 className="text-lg font-semibold">Attachments</h3></div><EntityDocuments attachments={attachments} isLoading={false} isUploading={false} isDownloading={false} isDeleting={false} onRetry={()=>{}} onUpload={async file=>{const id=crypto.randomUUID();uploadedFiles.set(id,file);setAttachments(a=>[...a,{id,filename:file.name,content_type:file.type,file_size:file.size,scan_status:'pending',quarantined:false,uploaded_by_user_id:'alex',created_at:new Date().toISOString()}]);}} onDelete={async id=>{uploadedFiles.delete(id);setAttachments(a=>a.filter(f=>f.id!==id));}} onDownload={id=>{const file=uploadedFiles.get(id);if(file){const url=URL.createObjectURL(file);const a=document.createElement('a');a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}} /></div>
              </div></Card></TabsContent>
              <TabsContent value="tasks" className="space-y-4"><SurrogateTasksCalendarHeader taskCount={tasks.length} viewMode={viewMode} onViewModeChange={setViewMode} onAddTask={()=>openModal('Add Task')}/>{viewMode==='list'?(tasks.length?<SurrogateTasksListView taskGroups={groups} orphanedCompletedTasks={getOrphanedCompletedTasks(groups,tasks)} completedTaskCount={countCompletedTasks(tasks)} onTaskToggle={id=>setTasks(t=>t.map(x=>x.id===id?{...x,is_completed:!x.is_completed}:x))}/>:<SurrogateTasksEmptyState onAddTask={()=>openModal('Add Task')}/>):<Card><CardHeader><div className="flex items-center justify-between"><CardTitle>{format(calendarMonth,'MMMM yyyy')}</CardTitle><div className="flex gap-1"><Button variant="outline" size="icon-sm" aria-label="Previous month" onClick={()=>setCalendarMonth(m=>subMonths(m,1))}><ChevronLeft className="size-4"/></Button><Button variant="outline" size="icon-sm" aria-label="Next month" onClick={()=>setCalendarMonth(m=>addMonths(m,1))}><ChevronRight className="size-4"/></Button></div></div></CardHeader><CardContent><div className="grid grid-cols-7 border-l border-t">{['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(day=><div key={day} className="border-b border-r p-2 text-center text-xs font-medium text-muted-foreground">{day}</div>)}{eachDayOfInterval({start:startOfWeek(startOfMonth(calendarMonth)),end:endOfWeek(endOfMonth(calendarMonth))}).map(day=><div key={day.toISOString()} className={`min-h-24 border-b border-r p-2 text-xs ${!isSameMonth(day,calendarMonth)?'bg-muted/30 text-muted-foreground':''}`}><span>{format(day,'d')}</span>{tasks.filter(t=>t.due_date===format(day,'yyyy-MM-dd')).map(t=><button key={t.id} className="mt-1 block w-full truncate rounded bg-purple-100 p-1 text-left text-purple-800" onClick={()=>openModal('Task Details',t.title)}>{t.title}</button>)}</div>)}</div></CardContent></Card>}</TabsContent>
              <TabsContent value="history"><SurrogateHistoryTab activities={activities} formatDateTime={dateFormat}/></TabsContent>
            </Tabs>
          </div>
        </div>
      </main>
    </div>
    <Dialog open={modal!==null} onOpenChange={open=>{if(!open)setModal(null)}}><DialogContent className={modal==='Surrogate reference'?'sm:max-w-[95vw] max-h-[92vh] overflow-auto':'sm:max-w-lg'}><DialogHeader><DialogTitle>{modal}</DialogTitle></DialogHeader>
      {modal==='Surrogate reference'?<img src="/surrogate-notes-reference.png" alt="Existing surrogate Notes tab, using synthetic test data" className="w-full"/>:modal==='Change Stage'?<><label htmlFor="stage-picker" className="text-sm">Stage</label><select id="stage-picker" className="h-9 rounded-md border bg-background px-3 text-sm" value={draft} onChange={e=>setDraft(e.target.value)}>{stages.map(s=><option key={s.id} value={s.id}>{s.label}</option>)}</select><DialogFooter><Button variant="outline" onClick={()=>setModal(null)}>Cancel</Button><Button onClick={()=>{setStage(draft);setModal(null)}}>Save</Button></DialogFooter></>:modal==='Edit Donor'?<><div className="space-y-3">{(['full_name','email','phone','state'] as const).map(key=><label key={key} className="grid gap-1 text-sm capitalize">{key==='full_name'?'Name':key}<Input value={record[key] ?? ''} onChange={e=>setRecord(p=>({...p,[key]:e.target.value}))}/></label>)}</div><DialogFooter><Button onClick={()=>setModal(null)}>Done</Button></DialogFooter></>:modal==='Notifications'?<p className="text-sm text-muted-foreground">No notifications.</p>:modal==='Task Details'?<p className="text-sm">{draft}</p>:<form onSubmit={e=>{e.preventDefault();save()}}><label htmlFor="mock-value" className="mb-2 block text-sm">Title</label><Input id="mock-value" value={draft} onChange={e=>setDraft(e.target.value)} required/><DialogFooter className="mt-5"><Button type="button" variant="outline" onClick={()=>setModal(null)}>Cancel</Button><Button type="submit">{modal==='Add Task'?'Add Task':'Save'}</Button></DialogFooter></form>}
    </DialogContent></Dialog>
  </div></TooltipProvider></LocalNavigation.Provider>;
}
