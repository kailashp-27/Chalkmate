CREATE SCHEMA chalkmate;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='chalkmate_app') THEN
    CREATE ROLE chalkmate_app LOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;

CREATE TABLE chalkmate.users (
	id UUID NOT NULL,
	email VARCHAR(320) NOT NULL,
	CONSTRAINT pk_users PRIMARY KEY (id)
)

;

CREATE TABLE chalkmate.workspaces (
	id UUID NOT NULL,
	owner_id UUID NOT NULL,
	name VARCHAR(120) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_workspaces PRIMARY KEY (id),
	CONSTRAINT fk_workspaces_owner_id_users FOREIGN KEY(owner_id) REFERENCES chalkmate.users (id)
)

;

CREATE TABLE chalkmate.classrooms (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	created_by UUID NOT NULL,
	name VARCHAR(120) NOT NULL,
	subject VARCHAR(120) NOT NULL,
	term VARCHAR(80) NOT NULL,
	archived BOOLEAN DEFAULT 'false' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_classrooms PRIMARY KEY (id),
	CONSTRAINT uq_classrooms_workspace_id_id UNIQUE (workspace_id, id),
	CONSTRAINT fk_classrooms_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES chalkmate.workspaces (id),
	CONSTRAINT fk_classrooms_created_by_users FOREIGN KEY(created_by) REFERENCES chalkmate.users (id)
)

;

CREATE TABLE chalkmate.memberships (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	user_id UUID NOT NULL,
	role VARCHAR(20) NOT NULL,
	CONSTRAINT pk_memberships PRIMARY KEY (id),
	CONSTRAINT uq_memberships_workspace_id_user_id UNIQUE (workspace_id, user_id),
	CONSTRAINT ck_memberships_valid_role CHECK (role IN ('owner','teacher','reviewer','student')),
	CONSTRAINT fk_memberships_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES chalkmate.workspaces (id),
	CONSTRAINT fk_memberships_user_id_users FOREIGN KEY(user_id) REFERENCES chalkmate.users (id)
)

;

CREATE TABLE chalkmate.students (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	registration_number VARCHAR(80) NOT NULL,
	name VARCHAR(160) NOT NULL,
	email VARCHAR(320),
	user_id UUID,
	CONSTRAINT pk_students PRIMARY KEY (id),
	CONSTRAINT uq_students_workspace_id_id UNIQUE (workspace_id, id),
	CONSTRAINT uq_students_workspace_id_registration_number UNIQUE (workspace_id, registration_number),
	CONSTRAINT uq_students_workspace_id_user_id UNIQUE (workspace_id, user_id),
	CONSTRAINT fk_students_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES chalkmate.workspaces (id),
	CONSTRAINT fk_students_user_id_users FOREIGN KEY(user_id) REFERENCES chalkmate.users (id)
)

;

CREATE TABLE chalkmate.audit_events (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID,
	actor_id UUID NOT NULL,
	action VARCHAR(80) NOT NULL,
	details JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_audit_events PRIMARY KEY (id),
	CONSTRAINT fk_audit_events_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT fk_audit_events_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES chalkmate.workspaces (id),
	CONSTRAINT fk_audit_events_actor_id_users FOREIGN KEY(actor_id) REFERENCES chalkmate.users (id)
)

;

CREATE TABLE chalkmate.classroom_teachers (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	user_id UUID NOT NULL,
	role VARCHAR(20) NOT NULL,
	CONSTRAINT pk_classroom_teachers PRIMARY KEY (id),
	CONSTRAINT fk_classroom_teachers_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT uq_classroom_teachers_classroom_id_user_id UNIQUE (classroom_id, user_id),
	CONSTRAINT ck_classroom_teachers_valid_role CHECK (role IN ('teacher','reviewer')),
	CONSTRAINT fk_classroom_teachers_user_id_users FOREIGN KEY(user_id) REFERENCES chalkmate.users (id)
)

;

CREATE TABLE chalkmate.enrollments (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	student_id UUID NOT NULL,
	status VARCHAR(20) DEFAULT 'active' NOT NULL,
	CONSTRAINT pk_enrollments PRIMARY KEY (id),
	CONSTRAINT fk_enrollments_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT fk_enrollments_workspace_id_students FOREIGN KEY(workspace_id, student_id) REFERENCES chalkmate.students (workspace_id, id),
	CONSTRAINT uq_enrollments_classroom_id_student_id UNIQUE (classroom_id, student_id),
	CONSTRAINT ck_enrollments_valid_status CHECK (status IN ('active','withdrawn'))
)

;

CREATE TABLE chalkmate.files (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	uploaded_by UUID NOT NULL,
	filename VARCHAR(180) NOT NULL,
	object_path VARCHAR(250) NOT NULL,
	content_type VARCHAR(80) NOT NULL,
	size INTEGER NOT NULL,
	checksum VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_files PRIMARY KEY (id),
	CONSTRAINT fk_files_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT fk_files_uploaded_by_users FOREIGN KEY(uploaded_by) REFERENCES chalkmate.users (id),
	CONSTRAINT uq_files_object_path UNIQUE (object_path)
)

;

CREATE TABLE chalkmate.import_batches (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_by UUID NOT NULL,
	rows JSONB NOT NULL,
	issues JSONB NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	confirmed_at TIMESTAMP WITH TIME ZONE,
	CONSTRAINT pk_import_batches PRIMARY KEY (id),
	CONSTRAINT fk_import_batches_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT fk_import_batches_created_by_users FOREIGN KEY(created_by) REFERENCES chalkmate.users (id)
)

;

CREATE TABLE chalkmate.invitations (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	student_id UUID,
	email VARCHAR(320) NOT NULL,
	role VARCHAR(20) NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	accepted_at TIMESTAMP WITH TIME ZONE,
	revoked BOOLEAN DEFAULT 'false' NOT NULL,
	CONSTRAINT pk_invitations PRIMARY KEY (id),
	CONSTRAINT fk_invitations_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT fk_invitations_workspace_id_students FOREIGN KEY(workspace_id, student_id) REFERENCES chalkmate.students (workspace_id, id),
	CONSTRAINT ck_invitations_valid_role CHECK (role IN ('teacher','reviewer','student')),
	CONSTRAINT ck_invitations_student_target CHECK ((role = 'student') = (student_id IS NOT NULL)),
	CONSTRAINT uq_invitations_token_hash UNIQUE (token_hash)
)

;
-- These helpers run as the migration owner, bypassing recursive RLS lookups.
-- They accept only scoped identifiers and use the API's transaction-local identity.
CREATE FUNCTION chalkmate.actor() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;
CREATE FUNCTION chalkmate.actor_email() RETURNS text LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.email', true), '')
$$;
CREATE FUNCTION chalkmate.owns(w uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT EXISTS(SELECT 1 FROM chalkmate.workspaces
    WHERE id=w AND owner_id=chalkmate.actor())
$$;
CREATE FUNCTION chalkmate.member(w uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT EXISTS(SELECT 1 FROM chalkmate.memberships
    WHERE workspace_id=w AND user_id=chalkmate.actor()) OR chalkmate.owns(w)
$$;
CREATE FUNCTION chalkmate.teaches(w uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT EXISTS(SELECT 1 FROM chalkmate.memberships
    WHERE workspace_id=w AND user_id=chalkmate.actor() AND role IN ('teacher','owner'))
$$;
CREATE FUNCTION chalkmate.staff(c uuid, edit boolean DEFAULT false) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT EXISTS(SELECT 1 FROM chalkmate.classrooms r WHERE r.id=c AND
    (chalkmate.owns(r.workspace_id) OR EXISTS(
      SELECT 1 FROM chalkmate.classroom_teachers t WHERE t.classroom_id=c
      AND t.user_id=chalkmate.actor() AND (NOT edit OR t.role='teacher'))))
$$;
CREATE FUNCTION chalkmate.attends(c uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT EXISTS(SELECT 1 FROM chalkmate.enrollments e
    JOIN chalkmate.students s ON s.id=e.student_id
    WHERE e.classroom_id=c AND e.status='active' AND s.user_id=chalkmate.actor())
$$;
CREATE FUNCTION chalkmate.student_visible(sid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT EXISTS(SELECT 1 FROM chalkmate.students s WHERE s.id=sid AND
    (s.user_id=chalkmate.actor() OR chalkmate.owns(s.workspace_id) OR EXISTS(
      SELECT 1 FROM chalkmate.enrollments e
      WHERE e.student_id=sid AND chalkmate.staff(e.classroom_id))))
$$;
CREATE FUNCTION chalkmate.invited(w uuid, c uuid, r text, s uuid DEFAULT NULL) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT EXISTS(SELECT 1 FROM chalkmate.invitations i WHERE i.workspace_id=w
    AND (c IS NULL OR i.classroom_id=c) AND i.email=chalkmate.actor_email()
    AND i.role=r AND (s IS NULL OR i.student_id=s) AND NOT i.revoked
    AND i.accepted_at IS NULL AND i.expires_at > now())
$$;

ALTER TABLE chalkmate.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_self ON chalkmate.users USING(id=chalkmate.actor())
  WITH CHECK(id=chalkmate.actor() AND email=chalkmate.actor_email());

ALTER TABLE chalkmate.workspaces ENABLE ROW LEVEL SECURITY;
CREATE POLICY workspace_read ON chalkmate.workspaces FOR SELECT
  USING(chalkmate.member(id));
CREATE POLICY workspace_create ON chalkmate.workspaces FOR INSERT
  WITH CHECK(owner_id=chalkmate.actor());

ALTER TABLE chalkmate.memberships ENABLE ROW LEVEL SECURITY;
CREATE POLICY membership_read ON chalkmate.memberships FOR SELECT
  USING(user_id=chalkmate.actor() OR chalkmate.owns(workspace_id));
CREATE POLICY membership_create ON chalkmate.memberships FOR INSERT WITH CHECK(
  user_id=chalkmate.actor() AND (
    (role='owner' AND chalkmate.owns(workspace_id)) OR
    (role='teacher' AND chalkmate.invited(workspace_id,NULL,'teacher')) OR
    (role='reviewer' AND chalkmate.invited(workspace_id,NULL,'reviewer')) OR
    (role='student' AND chalkmate.invited(workspace_id,NULL,'student'))));

ALTER TABLE chalkmate.classrooms ENABLE ROW LEVEL SECURITY;
CREATE POLICY classroom_read ON chalkmate.classrooms FOR SELECT
  USING(chalkmate.staff(id) OR chalkmate.attends(id) OR created_by=chalkmate.actor());
CREATE POLICY classroom_create ON chalkmate.classrooms FOR INSERT
  WITH CHECK(created_by=chalkmate.actor() AND chalkmate.teaches(workspace_id));
CREATE POLICY classroom_change ON chalkmate.classrooms FOR UPDATE
  USING(chalkmate.staff(id,true)) WITH CHECK(chalkmate.staff(id,true));

ALTER TABLE chalkmate.classroom_teachers ENABLE ROW LEVEL SECURITY;
CREATE POLICY teachers_read ON chalkmate.classroom_teachers FOR SELECT
  USING(chalkmate.staff(classroom_id) OR user_id=chalkmate.actor());
CREATE POLICY teachers_create ON chalkmate.classroom_teachers FOR INSERT WITH CHECK(
  user_id=chalkmate.actor() AND (
    EXISTS(SELECT 1 FROM chalkmate.classrooms c WHERE c.id=classroom_id
           AND c.created_by=chalkmate.actor() AND role='teacher') OR
    chalkmate.invited(workspace_id,classroom_id,role)));

ALTER TABLE chalkmate.students ENABLE ROW LEVEL SECURITY;
CREATE POLICY students_read ON chalkmate.students FOR SELECT
  USING(chalkmate.student_visible(id));
CREATE POLICY students_create ON chalkmate.students FOR INSERT
  WITH CHECK(chalkmate.teaches(workspace_id) AND user_id IS NULL);
CREATE POLICY students_link ON chalkmate.students FOR UPDATE
  USING(user_id IS NULL AND email=chalkmate.actor_email()
    AND chalkmate.invited(workspace_id,NULL,'student',id))
  WITH CHECK(user_id=chalkmate.actor() AND email=chalkmate.actor_email());
-- Intended invitees must see the unlinked record during acceptance.
CREATE POLICY invited_student_read ON chalkmate.students FOR SELECT
  USING(email=chalkmate.actor_email() AND chalkmate.invited(workspace_id,NULL,'student',id));

ALTER TABLE chalkmate.enrollments ENABLE ROW LEVEL SECURITY;
CREATE POLICY enrollment_read ON chalkmate.enrollments FOR SELECT
  USING(chalkmate.staff(classroom_id) OR
    (status='active' AND chalkmate.invited(workspace_id,classroom_id,'student',student_id)) OR EXISTS(
    SELECT 1 FROM chalkmate.students s WHERE s.id=student_id AND s.user_id=chalkmate.actor()));
CREATE POLICY enrollment_create ON chalkmate.enrollments FOR INSERT
  WITH CHECK(chalkmate.staff(classroom_id,true));
CREATE POLICY enrollment_change ON chalkmate.enrollments FOR UPDATE
  USING(chalkmate.staff(classroom_id,true)) WITH CHECK(chalkmate.staff(classroom_id,true));

ALTER TABLE chalkmate.import_batches ENABLE ROW LEVEL SECURITY;
CREATE POLICY import_read ON chalkmate.import_batches FOR SELECT
  USING(chalkmate.staff(classroom_id,true) AND created_by=chalkmate.actor());
CREATE POLICY import_create ON chalkmate.import_batches FOR INSERT
  WITH CHECK(chalkmate.staff(classroom_id,true) AND created_by=chalkmate.actor());
CREATE POLICY import_change ON chalkmate.import_batches FOR UPDATE
  USING(chalkmate.staff(classroom_id,true) AND created_by=chalkmate.actor());

ALTER TABLE chalkmate.invitations ENABLE ROW LEVEL SECURITY;
CREATE POLICY invitation_read ON chalkmate.invitations FOR SELECT
  USING(chalkmate.staff(classroom_id,true) OR email=chalkmate.actor_email());
CREATE POLICY invitation_create ON chalkmate.invitations FOR INSERT
  WITH CHECK(chalkmate.staff(classroom_id,true));
CREATE POLICY invitation_change ON chalkmate.invitations FOR UPDATE
  USING(chalkmate.staff(classroom_id,true) OR email=chalkmate.actor_email());

ALTER TABLE chalkmate.files ENABLE ROW LEVEL SECURITY;
CREATE POLICY files_read ON chalkmate.files FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY files_create ON chalkmate.files FOR INSERT
  WITH CHECK(chalkmate.staff(classroom_id,true) AND uploaded_by=chalkmate.actor());

ALTER TABLE chalkmate.audit_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_read ON chalkmate.audit_events FOR SELECT
  USING(chalkmate.owns(workspace_id) OR chalkmate.staff(classroom_id));
CREATE POLICY audit_create ON chalkmate.audit_events FOR INSERT
  WITH CHECK(actor_id=chalkmate.actor() AND (chalkmate.owns(workspace_id)
    OR chalkmate.staff(classroom_id,true)
    OR (action='invitation.accepted' AND chalkmate.member(workspace_id))));

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA chalkmate FROM PUBLIC;
GRANT USAGE ON SCHEMA chalkmate TO chalkmate_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA chalkmate TO chalkmate_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA chalkmate TO chalkmate_app;
GRANT UPDATE(email) ON chalkmate.users TO chalkmate_app;
GRANT UPDATE(name,subject,term,archived) ON chalkmate.classrooms TO chalkmate_app;
GRANT UPDATE(user_id) ON chalkmate.students TO chalkmate_app;
GRANT UPDATE(status) ON chalkmate.enrollments TO chalkmate_app;
GRANT UPDATE(confirmed_at) ON chalkmate.import_batches TO chalkmate_app;
GRANT UPDATE(accepted_at,revoked) ON chalkmate.invitations TO chalkmate_app;
