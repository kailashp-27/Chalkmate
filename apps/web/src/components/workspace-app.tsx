"use client";

import { useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  Compass,
  Gauge,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  FileText,
  FolderOpen,
  GraduationCap,
  Layers3,
  LayoutDashboard,
  LogOut,
  Mail,
  Plus,
  ShieldCheck,
  Upload,
  Users,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { InfoTip, Modal, Notice } from "./ui";
import { AppearanceSettings } from "./appearance-settings";
import { AssessmentWorkspace, StudentResults } from "./assessment-workspace";
import { AssignmentsWorkspace, AssignmentLink } from "./assignments-workspace";
import { PlanningWorkspace } from "./planning-workspace";
import { CommandBox, ReadinessWorkspace } from "./workspace-tools";
import { IntelligenceWorkspace } from "./intelligence-workspace";
import { FollowupWorkspace } from "./followup-workspace";
import { ClassroomOverview } from "./classroom-overview";
import { supabase, localInboxUrl } from "../lib/supabase";
import type { components } from "../lib/api-schema";

type Schema = components["schemas"];
type CurrentSession = Schema["SessionOutput"];
type Classroom = Schema["ClassroomOutput"];
type Student = Schema["StudentOutput"];
type Preview = Schema["ImportOutput"];
type FileRecord = Schema["FileOutput"];
type Invitation = Schema["InvitationOutput"];
type Audit = Schema["AuditOutput"];

function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark">
        <Layers3 size={23} strokeWidth={2} />
      </span>
      chalkmate<span className="brand-dot">.</span>
    </span>
  );
}

const credentials = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(10, "Use at least 10 characters"),
});

function Auth({ recovery }: { recovery?: boolean }) {
  const [mode, setMode] = useState<"signin" | "signup" | "reset">("signin");
  const [message, setMessage] = useState("");
  const form = useForm({
    resolver: zodResolver(
      recovery ? credentials.extend({ email: z.string() }) : credentials,
    ),
    defaultValues: { email: "", password: "" },
  });
  const action = useMutation({
    mutationFn: async (values: z.infer<typeof credentials>) => {
      const result = recovery
        ? await supabase!.auth.updateUser({ password: values.password })
        : mode === "signup"
          ? await supabase!.auth.signUp({
              ...values,
              options: { emailRedirectTo: window.location.origin },
            })
          : mode === "reset"
            ? await supabase!.auth.resetPasswordForEmail(values.email, {
                redirectTo: `${window.location.origin}/reset-password`,
              })
            : await supabase!.auth.signInWithPassword(values);
      if (result.error) throw result.error;
      if (recovery) window.location.assign("/");
      if (mode === "signup")
        setMessage(
          localInboxUrl
            ? "Open the local email inbox below to verify your account, then sign in."
            : "Check your inbox to verify your email, then sign in.",
        );
      if (mode === "reset")
        setMessage(
          localInboxUrl
            ? "If this email has an account, open the local email inbox below for the recovery link."
            : "If this email has an account, a recovery link is on its way.",
        );
    },
  });
  const submit = form.handleSubmit((values) => action.mutate(values));
  return (
    <div className="auth-page">
      <div className="auth-story">
        <Brand />
        <div>
          <span className="eyebrow">A LITTLE MORE ROOM TO TEACH</span>
          <h1>
            Your classroom.
            <br />
            All together.
          </h1>
          <p>
            Bring your students, your subjects, and your everyday teaching work
            into one thoughtful workspace.
          </p>
          <div className="story-lines">
            <span />
            <span />
            <span />
          </div>
        </div>
        <span className="quiet">Built around the work that matters.</span>
      </div>
      <main className="auth-form">
        <div className="auth-appearance">
          <AppearanceSettings authenticated={false} />
        </div>
        <div className="auth-form-inner">
          <span className="eyebrow">WELCOME TO CHALKMATE</span>
          <h2>
            {recovery
              ? "Choose a new password"
              : mode === "signup"
                ? "Make space for your teaching"
                : mode === "reset"
                  ? "Let’s get you back in"
                  : "Good to see you."}
          </h2>
          <p className="muted">
            {mode === "signup"
              ? "Create your account, then set up your workspace."
              : recovery
                ? "Use a strong password of at least 10 characters."
                : "A calmer start to your teaching day."}
          </p>
          <form
            onSubmit={
              mode === "reset" && !recovery
                ? (event) => {
                    event.preventDefault();
                    const email = form.getValues("email");
                    if (!z.email().safeParse(email).success)
                      form.setError("email", {
                        message: "Enter a valid email address",
                      });
                    else action.mutate({ email, password: "" });
                  }
                : submit
            }
          >
            {!recovery && (
              <label>
                Email address
                <input
                  type="email"
                  autoComplete="email"
                  placeholder="you@university.edu"
                  {...form.register("email")}
                  aria-invalid={!!form.formState.errors.email}
                />
                <span className="field-error">
                  {form.formState.errors.email?.message}
                </span>
              </label>
            )}
            {(recovery || mode !== "reset") && (
              <label>
                Password
                <input
                  type="password"
                  autoComplete={
                    mode === "signup" || recovery
                      ? "new-password"
                      : "current-password"
                  }
                  {...form.register("password")}
                  aria-invalid={!!form.formState.errors.password}
                />
                <span className="field-error">
                  {form.formState.errors.password?.message}
                </span>
              </label>
            )}
            <Notice error={action.error}>{message}</Notice>
            <button className="button primary wide" disabled={action.isPending}>
              {action.isPending
                ? "One moment…"
                : recovery
                  ? "Save password"
                  : mode === "signup"
                    ? "Create account"
                    : mode === "reset"
                      ? "Send recovery link"
                      : "Sign in"}
              <ArrowRight size={17} />
            </button>
          </form>
          {!recovery && (
            <>
              <button
                className="text-button"
                onClick={() => {
                  setMode(mode === "signin" ? "signup" : "signin");
                  setMessage("");
                  action.reset();
                }}
              >
                {mode === "signin"
                  ? "New here? Create an account"
                  : "Already have an account? Sign in"}
              </button>
              {mode === "signin" && (
                <button
                  className="text-button muted"
                  onClick={() => {
                    setMode("reset");
                    action.reset();
                  }}
                >
                  Forgot your password?
                </button>
              )}
            </>
          )}
          {localInboxUrl && (
            <aside className="local-inbox" aria-label="Local email inbox">
              <strong>Testing on this computer</strong>
              <p>
                Verification and password recovery emails stay in the local
                inbox. They won’t arrive in Gmail.
              </p>
              <a href={localInboxUrl} target="_blank" rel="noopener noreferrer">
                Open local email inbox <span aria-hidden="true">↗</span>
              </a>
            </aside>
          )}
        </div>
      </main>
    </div>
  );
}

export function WorkspaceApp({
  invitation = false,
  recovery = false,
  assignmentVersion,
}: {
  invitation?: boolean;
  recovery?: boolean;
  assignmentVersion?: string;
}) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
            staleTime: 15_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  const [session, setSession] = useState<Session | null>(null);
  const currentUserId = useRef<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!supabase) return;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, next) => {
      if (currentUserId.current !== (next?.user.id ?? null))
        queryClient.clear();
      currentUserId.current = next?.user.id ?? null;
      setSession(next);
      setLoading(false);
    });
    return () => subscription.unsubscribe();
  }, [queryClient]);
  if (!supabase)
    return (
      <main className="setup">
        <Brand />
        <h1>Your workspace is almost ready.</h1>
        <p>
          Run the local setup steps in the repository README, then restart the
          web server.
        </p>
      </main>
    );
  if (loading)
    return (
      <main className="setup" aria-live="polite">
        <Brand />
        <p>Opening your workspace…</p>
      </main>
    );
  return (
    <QueryClientProvider client={queryClient}>
      {!session ? (
        <Auth />
      ) : recovery ? (
        <Auth recovery />
      ) : invitation ? (
        <AcceptInvite />
      ) : assignmentVersion ? (
        <AssignmentLink versionId={assignmentVersion} />
      ) : (
        <Dashboard email={session.user.email ?? ""} />
      )}
    </QueryClientProvider>
  );
}

function AcceptInvite() {
  const [token, setToken] = useState("");
  useEffect(() => {
    setToken(
      new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "",
    );
  }, []);
  const action = useMutation({
    mutationFn: () =>
      api("/v1/invitations/accept", {
        method: "POST",
        body: JSON.stringify({ token }),
      }),
    onSuccess: () => {
      window.location.replace("/");
    },
  });
  return (
    <main className="setup">
      <Brand />
      <div className="panel invite-card">
        <ShieldCheck size={35} />
        <h1>Join your classroom.</h1>
        <p>
          Accept with the verified email address your teacher invited. This
          securely connects your account to the classroom.
        </p>
        <Notice error={action.error} />
        <button
          className="button primary"
          disabled={!token || action.isPending}
          onClick={() => action.mutate()}
        >
          {action.isPending ? "Joining…" : "Accept invitation"}
        </button>
        <button
          className="text-button"
          onClick={() => supabase!.auth.signOut()}
        >
          Use a different account
        </button>
      </div>
    </main>
  );
}

function ClassForm({
  workspaceId,
  current,
  close,
}: {
  workspaceId: string;
  current?: Classroom;
  close: () => void;
}) {
  const query = useQueryClient();
  const action = useMutation({
    mutationFn: (values: Record<string, FormDataEntryValue>) =>
      api(
        current
          ? `/v1/classrooms/${current.id}`
          : `/v1/workspaces/${workspaceId}/classrooms`,
        { method: current ? "PATCH" : "POST", body: JSON.stringify(values) },
      ),
    onSuccess: () => {
      query.invalidateQueries();
      close();
    },
  });
  return (
    <Modal
      title={current ? "Edit classroom" : "A new place to learn"}
      close={close}
    >
      <p className="muted">
        Give your classroom a name your students will recognize.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          action.mutate(Object.fromEntries(new FormData(event.currentTarget)));
        }}
      >
        <label>
          Classroom name
          <input
            name="name"
            placeholder="e.g. Computer Science · Section A"
            required
            maxLength={120}
            defaultValue={current?.name}
          />
        </label>
        <label>
          Subject
          <input
            name="subject"
            placeholder="e.g. Data Structures"
            required
            maxLength={120}
            defaultValue={current?.subject}
          />
        </label>
        <label>
          Academic term
          <input
            name="term"
            placeholder="e.g. Fall 2026"
            required
            maxLength={80}
            defaultValue={current?.term}
          />
        </label>
        <Notice error={action.error} />
        <footer>
          <button type="button" className="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={action.isPending}>
            {action.isPending
              ? "Saving…"
              : current
                ? "Save changes"
                : "Create classroom"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function CreateWorkspace() {
  const query = useQueryClient();
  const action = useMutation({
    mutationFn: (name: string) =>
      api("/v1/workspaces", { method: "POST", body: JSON.stringify({ name }) }),
    onSuccess: () => query.invalidateQueries(),
  });
  return (
    <section className="panel onboarding">
      <span className="illustration">
        <BookOpen size={42} />
      </span>
      <span className="eyebrow">YOUR FIRST CHAPTER</span>
      <h2>A home for your teaching.</h2>
      <p className="muted">
        Create a personal workspace. Your classrooms and student records will
        stay together here.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          action.mutate(String(new FormData(event.currentTarget).get("name")));
        }}
      >
        <label>
          Workspace name
          <input
            name="name"
            placeholder="e.g. Dr. Mehta’s workspace"
            maxLength={120}
            required
          />
        </label>
        <Notice error={action.error} />
        <button className="button primary wide" disabled={action.isPending}>
          Create workspace
          <ArrowRight size={16} />
        </button>
      </form>
    </section>
  );
}

function Dashboard({ email }: { email: string }) {
  const [workspaceChoice, setWorkspaceChoice] = useState("");
  const [classChoice, setClassChoice] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const query = useQueryClient();
  const profile = useQuery({
    queryKey: ["session"],
    queryFn: () => api<CurrentSession>("/v1/session"),
  });
  const workspace =
    profile.data?.workspaces.find((item) => item.id === workspaceChoice) ??
    profile.data?.workspaces[0];
  const classes = useQuery({
    queryKey: ["classes", workspace?.id],
    queryFn: () =>
      api<Classroom[]>(`/v1/workspaces/${workspace!.id}/classrooms`),
    enabled: !!workspace,
  });
  const filtered =
    classes.data?.filter((item) => item.archived === showArchived) ?? [];
  const selected =
    filtered.find((item) => item.id === classChoice) ?? filtered[0];
  const canCreate = workspace && ["owner", "teacher"].includes(workspace.role);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspace-switch">
          <span className="workspace-avatar">
            {workspace?.name.slice(0, 1) ?? "W"}
          </span>
          <div>
            <span className="small muted">WORKSPACE</span>
            <select
              aria-label="Workspace"
              value={workspace?.id ?? ""}
              onChange={(event) => {
                setWorkspaceChoice(event.target.value);
                setClassChoice("");
              }}
            >
              {profile.data?.workspaces.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <span className="nav-caption">TEACHING</span>
        <a className="nav-item active" href="/">
          <BookOpen size={19} />
          Classrooms
          <span className="nav-count">
            {classes.data?.filter((item) => !item.archived).length ?? 0}
          </span>
        </a>
        <div className="sidebar-note">
          <span className="note-icon">
            <GraduationCap size={23} />
          </span>
          <strong>From answers to insight.</strong>
          <p>A calmer day in the classroom.</p>
          <span className="small">YOUR TEACHING WORKSPACE</span>
        </div>
        <div className="sidebar-bottom">
          <AppearanceSettings />
          <span>
            <ShieldCheck size={15} /> Private by design
          </span>
          <button
            onClick={async () => {
              query.clear();
              await supabase!.auth.signOut();
            }}
          >
            <LogOut size={17} />
            Sign out
          </button>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <span>
            Workspace <ChevronRight size={14} />
            <strong>Classrooms</strong>
          </span>
          <span className="user">
            <span className="user-email">{email}</span>
            <span className="avatar">{email.slice(0, 2).toUpperCase()}</span>
          </span>
        </header>
        <main className="main-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">YOUR TEACHING, TOGETHER</span>
              <h1>A little more room to teach.</h1>
              <p className="muted">Your classrooms, all together.</p>
            </div>
            {canCreate && (
              <button
                className="button primary"
                onClick={() => setShowCreate(true)}
              >
                <Plus size={17} />
                New classroom
              </button>
            )}
          </div>
          <Notice error={profile.error ?? classes.error} />
          {profile.isPending ? (
            <p role="status">Loading your workspace…</p>
          ) : profile.data?.workspaces.length === 0 ? (
            <CreateWorkspace />
          ) : (
            <>
              <div className="section-label">
                <span>
                  <span className="status-dot" />
                  {showArchived ? "Archived classrooms" : "Your classrooms"}
                  <span className="count">{filtered.length}</span>
                </span>
                <button
                  className="text-button"
                  onClick={() => {
                    setShowArchived(!showArchived);
                    setClassChoice("");
                  }}
                >
                  {showArchived ? "View active" : "View archived"}
                </button>
              </div>
              {classes.isPending ? (
                <p role="status">Loading classrooms…</p>
              ) : filtered.length === 0 ? (
                <section className="panel empty-class">
                  <span className="illustration">
                    <BookOpen size={37} />
                  </span>
                  <h2>
                    {showArchived
                      ? "Nothing archived."
                      : "Every class starts here."}
                  </h2>
                  <p className="muted">
                    {showArchived
                      ? "Archived classrooms will appear here."
                      : canCreate
                        ? "Create your first classroom, then bring in your student roster."
                        : "Your assigned classrooms will appear here once you accept an invitation."}
                  </p>
                  {canCreate && !showArchived && (
                    <button
                      className="button"
                      onClick={() => setShowCreate(true)}
                    >
                      <Plus size={16} />
                      Create your first classroom
                    </button>
                  )}
                </section>
              ) : (
                <div className="class-grid">
                  {filtered.map((item, index) => (
                    <button
                      key={item.id}
                      className={`class-card ${selected?.id === item.id ? "selected" : ""}`}
                      onClick={() => setClassChoice(item.id)}
                    >
                      <div className="class-card-top">
                        <span className={`class-symbol tone-${index % 3}`}>
                          <BookOpen size={21} />
                        </span>
                        <span className="term">{item.term}</span>
                      </div>
                      <h2>{item.name}</h2>
                      <p>{item.subject}</p>
                      <div className="class-card-bottom">
                        <span>
                          <Users size={14} />
                          {item.role === "student"
                            ? "Your enrollment"
                            : `${item.student_count} students`}
                        </span>
                        <ArrowRight size={16} />
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {selected && (
                <ClassDetail
                  key={selected.id}
                  classroom={selected}
                  workspaceId={workspace!.id}
                />
              )}
            </>
          )}
          <div className="page-foot">
            <span>
              <ShieldCheck size={14} />
              Your classroom records stay within your workspace.
            </span>
            <span>Made for the everyday work of teaching.</span>
          </div>
        </main>
      </div>
      {showCreate && workspace && (
        <ClassForm
          workspaceId={workspace.id}
          close={() => setShowCreate(false)}
        />
      )}
    </div>
  );
}

function ClassDetail({
  classroom,
  workspaceId,
}: {
  classroom: Classroom;
  workspaceId: string;
}) {
  const [tab, setTab] = useState("Students");
  const [editing, setEditing] = useState(false);
  const [importing, setImporting] = useState(false);
  const query = useQueryClient();
  const staff = classroom.role !== "student";
  const editable = classroom.can_edit && !classroom.archived;
  const roster = useQuery({
    queryKey: ["students", classroom.id],
    queryFn: () => api<Student[]>(`/v1/classrooms/${classroom.id}/students`),
    enabled: staff,
  });
  const archive = useMutation({
    mutationFn: () =>
      api(`/v1/classrooms/${classroom.id}`, {
        method: "PATCH",
        body: JSON.stringify({ archived: !classroom.archived }),
      }),
    onSuccess: () => query.invalidateQueries(),
  });
  return (
    <section className="panel class-detail">
      <header className="detail-header">
        <div>
          <span className="eyebrow">YOUR CLASSROOM</span>
          <h2>{classroom.name}</h2>
          <p className="muted">
            {classroom.subject}
            <span className="separator">/</span>
            {classroom.term}
            <span className="role-tag">{classroom.role}</span>
          </p>
        </div>
        {classroom.can_edit && (
          <div className="button-group">
            <button
              className="button small-button"
              onClick={() => setEditing(true)}
            >
              Edit details
            </button>
            <button
              className="text-button muted"
              disabled={archive.isPending}
              onClick={() => archive.mutate()}
            >
              {classroom.archived ? "Restore classroom" : "Archive"}
            </button>
          </div>
        )}
      </header>
      {staff && (
        <div className="class-tool-strip">
          <CommandBox classId={classroom.id} navigate={setTab} />
          <InfoTip label="Classroom guide">
            Start with Students to import your roster. Assessments handles
            review and marks. Planning helps with papers and everyday notes.
            Assignments and Follow-up keep publication and messages under your
            control.
          </InfoTip>
        </div>
      )}
      <Notice error={archive.error} />
      {classroom.archived && (
        <p className="notice">
          This classroom is archived. Restore it to make changes.
        </p>
      )}
      {!staff ? (
        <StudentPortal classroom={classroom} />
      ) : (
        <>
          <nav className="tabs" aria-label="Classroom sections">
            {[
              { name: "Overview", icon: LayoutDashboard },
              { name: "Assessments", icon: ClipboardList },
              { name: "Intelligence", icon: BrainCircuit },
              { name: "Planning", icon: Compass },
              { name: "Assignments", icon: BookOpen },
              { name: "Follow-up", icon: Mail },
              { name: "Students", icon: Users },
              { name: "Files", icon: FolderOpen },
              { name: "People", icon: ShieldCheck },
              { name: "Activity", icon: ClipboardList },
              { name: "Readiness", icon: Gauge },
            ]
              .filter((item) => item.name !== "People" || classroom.can_edit)
              .map(({ name, icon: Icon }) => (
                <button
                  key={name}
                  className={tab === name ? "tab selected" : "tab"}
                  aria-current={tab === name ? "page" : undefined}
                  onClick={() => setTab(name)}
                >
                  <Icon size={16} />
                  {name}
                  {name === "Students" && (
                    <span className="count">{roster.data?.length ?? 0}</span>
                  )}
                </button>
              ))}
          </nav>
          {tab === "Overview" && (
            <ClassroomOverview
              classId={classroom.id}
              canEdit={editable}
              navigate={setTab}
            />
          )}
          {tab === "Planning" && <PlanningWorkspace classroom={classroom} />}
          {tab === "Readiness" && <ReadinessWorkspace classId={classroom.id} />}
          {tab === "Assessments" && (
            <AssessmentWorkspace
              classroom={classroom}
              students={roster.data ?? []}
            />
          )}
          {tab === "Assignments" && (
            <AssignmentsWorkspace classroom={classroom} />
          )}
          {tab === "Follow-up" && <FollowupWorkspace classroom={classroom} />}
          {tab === "Intelligence" && (
            <IntelligenceWorkspace classroom={classroom} />
          )}
          {tab === "Students" && (
            <div className="tab-content">
              <div className="section-heading">
                <div>
                  <h3>
                    Student roster{" "}
                    <InfoTip label="About the roster">
                      Import a CSV or Excel file, review each row, then confirm.
                      Students see only their own records.
                    </InfoTip>
                  </h3>
                </div>
                {editable && (
                  <button className="button" onClick={() => setImporting(true)}>
                    <Upload size={16} />
                    Import students
                  </button>
                )}
              </div>
              <Notice error={roster.error} />
              {roster.isPending ? (
                <p role="status">Loading student records…</p>
              ) : roster.data?.length ? (
                <RosterTable students={roster.data} classroom={classroom} />
              ) : (
                <div className="roster-empty">
                  <span className="illustration">
                    <Users size={31} />
                  </span>
                  <div>
                    <h3>Bring your class together.</h3>
                    <p className="muted">
                      Import a CSV or Excel roster. You’ll review every row
                      before anything is saved.
                    </p>
                    {editable && (
                      <button
                        className="text-button"
                        onClick={() => setImporting(true)}
                      >
                        Import your first roster
                        <ArrowRight size={15} />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          {tab === "Files" && <Files classroom={classroom} />}
          {tab === "People" && classroom.can_edit && (
            <People classroom={classroom} students={roster.data ?? []} />
          )}
          {tab === "Activity" && <Activity classroomId={classroom.id} />}
        </>
      )}
      {editing && (
        <ClassForm
          workspaceId={workspaceId}
          current={classroom}
          close={() => setEditing(false)}
        />
      )}
      {importing && (
        <ImportRoster classroom={classroom} close={() => setImporting(false)} />
      )}
    </section>
  );
}

function RosterTable({
  students,
  classroom,
}: {
  students: Student[];
  classroom: Classroom;
}) {
  const [search, setSearch] = useState("");
  const query = useQueryClient();
  const action = useMutation({
    mutationFn: (student: Student) =>
      api(
        `/v1/classrooms/${classroom.id}/enrollments/${student.enrollment_id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status: student.status === "active" ? "withdrawn" : "active",
          }),
        },
      ),
    onSuccess: () => query.invalidateQueries(),
  });
  const filtered = students.filter((student) =>
    `${student.name} ${student.registration_number} ${student.email ?? ""}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <label className="search-label">
        <span className="sr-only">Search students</span>
        <input
          placeholder="Search name, registration number, or email…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <Notice error={action.error} />
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>STUDENT</th>
              <th>REGISTRATION NO.</th>
              <th>EMAIL ADDRESS</th>
              <th>STATUS</th>
              {classroom.can_edit && !classroom.archived && (
                <th>
                  <span className="sr-only">Actions</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {filtered.map((student) => (
              <tr key={student.id}>
                <td>
                  <strong>{student.name}</strong>
                  {student.linked && (
                    <span className="linked">
                      <Check size={11} />
                      Account linked
                    </span>
                  )}
                </td>
                <td className="mono">{student.registration_number}</td>
                <td>
                  {student.email ?? (
                    <span className="warning-text">No email</span>
                  )}
                </td>
                <td>
                  <span className={`status ${student.status}`}>
                    {student.status}
                  </span>
                </td>
                {classroom.can_edit && !classroom.archived && (
                  <td>
                    <button
                      className="text-button small"
                      disabled={action.isPending}
                      onClick={() => action.mutate(student)}
                    >
                      {student.status === "active" ? "Withdraw" : "Re-enroll"}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && (
          <p className="muted">No students match this search.</p>
        )}
      </div>
      <p className="table-foot">
        {filtered.length} of {students.length} students
        <span>Student identity stays separate from classroom enrollment.</span>
      </p>
    </>
  );
}

function ImportRoster({
  classroom,
  close,
}: {
  classroom: Classroom;
  close: () => void;
}) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const query = useQueryClient();
  const upload = useMutation({
    mutationFn: () => {
      const data = new FormData();
      data.set("file", file!);
      return api<Preview>(`/v1/classrooms/${classroom.id}/imports/preview`, {
        method: "POST",
        body: data,
      });
    },
    onSuccess: setPreview,
  });
  const confirm = useMutation({
    mutationFn: () =>
      api(`/v1/classrooms/${classroom.id}/imports/${preview!.id}/confirm`, {
        method: "POST",
      }),
    onSuccess: () => {
      query.invalidateQueries();
      close();
    },
  });
  const errors =
    preview?.issues.filter((issue) => issue.severity === "error") ?? [];
  return (
    <Modal
      title={preview ? "Review your roster" : "Bring in your students"}
      close={close}
    >
      <p className="muted">
        {preview
          ? "Check the preview. No student records have been saved yet."
          : "Use CSV or Excel with registration_number, name, and email columns."}
      </p>
      {!preview ? (
        <>
          <a className="template-link" href="/roster-template.csv" download>
            <ArrowDownToLine size={16} />
            Download CSV template
          </a>
          <label className="file-picker">
            Choose a roster
            <input
              type="file"
              accept=".csv,.xlsx"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                upload.reset();
              }}
            />
            <span className="small muted">
              Up to 1,000 students · 2 MB maximum
            </span>
          </label>
          <Notice error={upload.error} />
          <footer>
            <button className="button" onClick={close}>
              Cancel
            </button>
            <button
              className="button primary"
              disabled={!file || upload.isPending}
              onClick={() => upload.mutate()}
            >
              {upload.isPending ? "Checking roster…" : "Preview roster"}
              <ArrowRight size={16} />
            </button>
          </footer>
        </>
      ) : (
        <>
          <div className="preview-summary">
            <strong>{preview.rows.length} student rows</strong>
            <span>
              {errors.length} errors · {preview.issues.length - errors.length}{" "}
              warnings
            </span>
          </div>
          {preview.issues.length > 0 && (
            <ul className="issues">
              {preview.issues.map((issue, index) => (
                <li key={index} className={issue.severity}>
                  <strong>Row {issue.row}</strong> {issue.message}
                </li>
              ))}
            </ul>
          )}
          <div className="table-scroll preview-table">
            <table>
              <thead>
                <tr>
                  <th>ROW</th>
                  <th>REGISTRATION</th>
                  <th>NAME</th>
                  <th>EMAIL</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.row}>
                    <td>{row.row}</td>
                    <td>{row.registration_number}</td>
                    <td>{row.name}</td>
                    <td>{row.email ?? "No email"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="small muted">
            Missing or invalid emails are saved as blank after confirmation.
            Correct errors in your file, then preview again.
          </p>
          <Notice error={confirm.error} />
          <footer>
            <button
              className="button"
              disabled={confirm.isPending}
              onClick={() => {
                setPreview(null);
                confirm.reset();
              }}
            >
              Choose another file
            </button>
            <button
              className="button primary"
              disabled={errors.length > 0 || confirm.isPending}
              onClick={() => confirm.mutate()}
            >
              {confirm.isPending
                ? "Importing…"
                : `Confirm import · ${preview.rows.length} students`}
            </button>
          </footer>
        </>
      )}
    </Modal>
  );
}

function Files({ classroom }: { classroom: Classroom }) {
  const query = useQueryClient();
  const files = useQuery({
    queryKey: ["files", classroom.id],
    queryFn: () => api<FileRecord[]>(`/v1/classrooms/${classroom.id}/files`),
  });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.set("file", file);
      return api(`/v1/classrooms/${classroom.id}/files`, {
        method: "POST",
        body: form,
      });
    },
    onSuccess: () =>
      query.invalidateQueries({ queryKey: ["files", classroom.id] }),
  });
  const download = useMutation({
    mutationFn: (file: FileRecord) =>
      api<{ url: string }>(
        `/v1/classrooms/${classroom.id}/files/${file.id}/download`,
      ),
    onSuccess: (result) => {
      window.open(result.url, "_blank", "noopener,noreferrer");
    },
  });
  return (
    <div className="tab-content">
      <div className="section-heading">
        <div>
          <h3>Classroom files</h3>
          <p className="small muted">
            Private resources for your teaching team. PDF, JPEG, or PNG · up to
            10 MB.
          </p>
        </div>
        {classroom.can_edit && !classroom.archived && (
          <label className="button upload-label">
            <Upload size={16} />
            {upload.isPending ? "Uploading…" : "Upload file"}
            <input
              className="sr-only"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              disabled={upload.isPending}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload.mutate(file);
                event.target.value = "";
              }}
            />
          </label>
        )}
      </div>
      <Notice error={files.error ?? upload.error ?? download.error} />
      {files.isPending ? (
        <p role="status">Loading files…</p>
      ) : files.data?.length ? (
        <div className="file-list">
          {files.data.map((file) => (
            <div className="file-row" key={file.id}>
              <span className="file-icon">
                <FileText size={22} />
              </span>
              <span>
                <strong>{file.filename}</strong>
                <small>
                  {(file.size / 1024).toFixed(1)} KB ·{" "}
                  {new Date(file.created_at).toLocaleDateString()}
                </small>
              </span>
              <button
                className="icon-button"
                aria-label={`Download ${file.filename}`}
                disabled={download.isPending}
                onClick={() => download.mutate(file)}
              >
                <ArrowDownToLine size={18} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-inline">
          <FolderOpen size={30} />
          <h3>A place for your resources.</h3>
          <p>
            Upload your first classroom file. Downloads require authorized
            access.
          </p>
        </div>
      )}
    </div>
  );
}

function People({
  classroom,
  students,
}: {
  classroom: Classroom;
  students: Student[];
}) {
  const [role, setRole] = useState("teacher");
  const [studentId, setStudentId] = useState("");
  const [link, setLink] = useState("");
  const query = useQueryClient();
  const invitations = useQuery({
    queryKey: ["invitations", classroom.id],
    queryFn: () =>
      api<Invitation[]>(`/v1/classrooms/${classroom.id}/invitations`),
  });
  const create = useMutation({
    mutationFn: (email: string) =>
      api<Schema["InvitationCreated"]>(
        `/v1/classrooms/${classroom.id}/invitations`,
        {
          method: "POST",
          body: JSON.stringify({
            email,
            role,
            student_id: role === "student" ? studentId : null,
          }),
        },
      ),
    onSuccess: (result) => {
      setLink(result.url);
      query.invalidateQueries({ queryKey: ["invitations", classroom.id] });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) =>
      api(`/v1/classrooms/${classroom.id}/invitations/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () =>
      query.invalidateQueries({ queryKey: ["invitations", classroom.id] }),
  });
  const selectedStudent = students.find((student) => student.id === studentId);
  return (
    <div className="tab-content">
      <div className="section-heading">
        <div>
          <h3>Invite with intention.</h3>
          <p className="small muted">
            People join this classroom only after accepting with their verified
            email.
          </p>
        </div>
      </div>
      {!classroom.archived && (
        <form
          className="invite-form"
          onSubmit={(event) => {
            event.preventDefault();
            setLink("");
            create.mutate(
              role === "student"
                ? (selectedStudent?.email ?? "")
                : String(new FormData(event.currentTarget).get("email")),
            );
          }}
        >
          <label>
            Access
            <select
              value={role}
              onChange={(event) => {
                setRole(event.target.value);
                setLink("");
              }}
            >
              <option value="teacher">Co-teacher · edit this class</option>
              <option value="reviewer">Reviewer · read this class</option>
              <option value="student">Student · own enrollment</option>
            </select>
          </label>
          {role === "student" ? (
            <label>
              Student
              <select
                value={studentId}
                onChange={(event) => setStudentId(event.target.value)}
                required
              >
                <option value="">Choose an unlinked student</option>
                {students
                  .filter(
                    (student) =>
                      !student.linked &&
                      student.email &&
                      student.status === "active",
                  )
                  .map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.name} · {student.email}
                    </option>
                  ))}
              </select>
            </label>
          ) : (
            <label>
              Email address
              <input
                type="email"
                name="email"
                required
                placeholder="colleague@university.edu"
              />
            </label>
          )}
          <button
            className="button primary"
            disabled={
              create.isPending || (role === "student" && !selectedStudent)
            }
          >
            {create.isPending ? "Creating…" : "Create invite link"}
          </button>
        </form>
      )}
      <Notice error={create.error ?? revoke.error ?? invitations.error} />
      {link && (
        <div className="notice">
          <strong>
            Invite ready. Share this link with the intended person.
          </strong>
          <input
            aria-label="Invitation link"
            readOnly
            value={link}
            onFocus={(event) => event.target.select()}
          />
          <span className="small">
            Expires in 7 days. The recipient must verify the invited email
            address.
          </span>
        </div>
      )}
      <div className="file-list">
        {invitations.data?.map((invitation) => (
          <div className="file-row" key={invitation.id}>
            <ShieldCheck size={19} />
            <span>
              <strong>{invitation.email}</strong>
              <small>
                {invitation.role} ·{" "}
                {invitation.revoked
                  ? "Revoked"
                  : invitation.accepted_at
                    ? "Accepted"
                    : new Date(invitation.expires_at) < new Date()
                      ? "Expired"
                      : "Pending"}
              </small>
            </span>
            {!invitation.revoked && !invitation.accepted_at && (
              <button
                className="text-button"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(invitation.id)}
              >
                Revoke
              </button>
            )}
          </div>
        ))}
      </div>
      <p className="small muted">
        <CircleHelp size={13} className="inline-icon" />
        Creating a link does not send an email. Share it directly with the
        intended recipient.
      </p>
    </div>
  );
}

function Activity({ classroomId }: { classroomId: string }) {
  const events = useQuery({
    queryKey: ["audit", classroomId],
    queryFn: () => api<Audit[]>(`/v1/classrooms/${classroomId}/audit`),
  });
  return (
    <div className="tab-content">
      <h3>A record you can follow.</h3>
      <p className="muted small">
        Recent classroom actions are recorded automatically.
      </p>
      <Notice error={events.error} />
      <ol className="activity-list">
        {events.data?.map((event) => (
          <li key={event.id}>
            <span className="activity-dot" />
            <div>
              <strong>
                {event.action.replaceAll(".", " ").replaceAll("_", " ")}
              </strong>
              <time dateTime={event.created_at}>
                {new Date(event.created_at).toLocaleString()}
              </time>
            </div>
          </li>
        ))}
      </ol>
      {events.isPending && <p role="status">Loading activity…</p>}
    </div>
  );
}

function StudentPortal({ classroom }: { classroom: Classroom }) {
  const [section, setSection] = useState("Assignments");
  return (
    <>
      <nav className="tabs" aria-label="Student classroom sections">
        {["Assignments", "Results"].map((name) => (
          <button
            key={name}
            className={section === name ? "tab selected" : "tab"}
            aria-current={section === name ? "page" : undefined}
            onClick={() => setSection(name)}
          >
            {name}
          </button>
        ))}
      </nav>
      {section === "Assignments" ? (
        <AssignmentsWorkspace classroom={classroom} />
      ) : (
        <StudentResults
          classroomId={classroom.id}
          canRequest={!classroom.archived}
        />
      )}
    </>
  );
}
