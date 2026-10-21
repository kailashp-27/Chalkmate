ALTER TABLE chalkmate.files ADD CONSTRAINT uq_files_workspace_id_classroom_id_id
  UNIQUE(workspace_id,classroom_id,id);
ALTER TABLE chalkmate.enrollments ADD CONSTRAINT uq_enrollments_workspace_id_classroom_id_student_id
  UNIQUE(workspace_id,classroom_id,student_id);

CREATE TABLE chalkmate.assessments (
	title VARCHAR(140) NOT NULL,
	instructions VARCHAR(4000) NOT NULL,
	status VARCHAR(20) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_assessments PRIMARY KEY (id),
	CONSTRAINT fk_assessments_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT uq_assessments_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id),
	CONSTRAINT ck_assessments_valid_status CHECK (status IN ('draft','active'))
)

;
CREATE INDEX ix_assessments_class ON chalkmate.assessments (classroom_id);

CREATE TABLE chalkmate.rubrics (
	assessment_id UUID NOT NULL,
	version INTEGER NOT NULL,
	questions JSONB NOT NULL,
	maximum NUMERIC(8, 2) NOT NULL,
	approved_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_rubrics PRIMARY KEY (id),
	CONSTRAINT fk_rubrics_workspace_id_assessments FOREIGN KEY(workspace_id, classroom_id, assessment_id) REFERENCES chalkmate.assessments (workspace_id, classroom_id, id),
	CONSTRAINT uq_rubrics_assessment_id_version UNIQUE (assessment_id, version),
	CONSTRAINT uq_rubrics_assessment_id_id UNIQUE (assessment_id, id)
)

;
CREATE INDEX ix_rubrics_class ON chalkmate.rubrics (classroom_id);

CREATE TABLE chalkmate.submissions (
	assessment_id UUID NOT NULL,
	student_id UUID NOT NULL,
	file_id UUID NOT NULL,
	rubric_id UUID NOT NULL,
	page_count INTEGER NOT NULL,
	status VARCHAR(30) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_submissions PRIMARY KEY (id),
	CONSTRAINT fk_submissions_workspace_id_assessments FOREIGN KEY(workspace_id, classroom_id, assessment_id) REFERENCES chalkmate.assessments (workspace_id, classroom_id, id),
	CONSTRAINT fk_submissions_assessment_id_rubrics FOREIGN KEY(assessment_id, rubric_id) REFERENCES chalkmate.rubrics (assessment_id, id),
	CONSTRAINT fk_submissions_workspace_id_files FOREIGN KEY(workspace_id, classroom_id, file_id) REFERENCES chalkmate.files (workspace_id, classroom_id, id),
	CONSTRAINT fk_submissions_workspace_id_enrollments FOREIGN KEY(workspace_id, classroom_id, student_id) REFERENCES chalkmate.enrollments (workspace_id, classroom_id, student_id),
	CONSTRAINT uq_submissions_assessment_id_student_id UNIQUE (assessment_id, student_id),
	CONSTRAINT uq_submissions_assessment_id_file_id UNIQUE (assessment_id, file_id),
	CONSTRAINT uq_submissions_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id),
	CONSTRAINT ck_submissions_valid_status CHECK (status IN ('uploaded','extraction_review','teacher_review','approved','released')),
	CONSTRAINT ck_submissions_page_limit CHECK (page_count BETWEEN 1 AND 30)
)

;
CREATE INDEX ix_submissions_class ON chalkmate.submissions (classroom_id);

CREATE TABLE chalkmate.extractions (
	submission_id UUID NOT NULL,
	version INTEGER NOT NULL,
	source VARCHAR(100) NOT NULL,
	pages JSONB NOT NULL,
	answers JSONB NOT NULL,
	reviewed_by UUID,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_extractions PRIMARY KEY (id),
	CONSTRAINT fk_extractions_workspace_id_submissions FOREIGN KEY(workspace_id, classroom_id, submission_id) REFERENCES chalkmate.submissions (workspace_id, classroom_id, id),
	CONSTRAINT uq_extractions_submission_id_version UNIQUE (submission_id, version),
	CONSTRAINT uq_extractions_submission_id_id UNIQUE (submission_id, id),
	CONSTRAINT fk_extractions_reviewed_by_users FOREIGN KEY(reviewed_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_extractions_class ON chalkmate.extractions (classroom_id);

CREATE TABLE chalkmate.processing_jobs (
	submission_id UUID NOT NULL,
	requested_by UUID NOT NULL,
	kind VARCHAR(20) NOT NULL,
	input_version VARCHAR(80) NOT NULL,
	model VARCHAR(160) NOT NULL,
	status VARCHAR(20) NOT NULL,
	attempts INTEGER NOT NULL,
	error VARCHAR(500),
	lease_until TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_processing_jobs PRIMARY KEY (id),
	CONSTRAINT fk_processing_jobs_workspace_id_submissions FOREIGN KEY(workspace_id, classroom_id, submission_id) REFERENCES chalkmate.submissions (workspace_id, classroom_id, id),
	CONSTRAINT uq_processing_jobs_submission_id_kind_input_version UNIQUE (submission_id, kind, input_version),
	CONSTRAINT ck_processing_jobs_valid_kind CHECK (kind IN ('extract','grade')),
	CONSTRAINT ck_processing_jobs_valid_status CHECK (status IN ('queued','running','succeeded','failed','canceled')),
	CONSTRAINT fk_processing_jobs_requested_by_users FOREIGN KEY(requested_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_processing_jobs_class ON chalkmate.processing_jobs (classroom_id);

CREATE TABLE chalkmate.proposals (
	submission_id UUID NOT NULL,
	extraction_id UUID NOT NULL,
	rubric_id UUID NOT NULL,
	model VARCHAR(160) NOT NULL,
	model_digest VARCHAR(100) NOT NULL,
	prompt_version VARCHAR(50) NOT NULL,
	output JSONB NOT NULL,
	usage JSONB NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_proposals PRIMARY KEY (id),
	CONSTRAINT fk_proposals_workspace_id_submissions FOREIGN KEY(workspace_id, classroom_id, submission_id) REFERENCES chalkmate.submissions (workspace_id, classroom_id, id),
	CONSTRAINT fk_proposals_submission_id_extractions FOREIGN KEY(submission_id, extraction_id) REFERENCES chalkmate.extractions (submission_id, id),
	CONSTRAINT uq_proposals_submission_id_id UNIQUE (submission_id, id),
	CONSTRAINT fk_proposals_rubric_id_rubrics FOREIGN KEY(rubric_id) REFERENCES chalkmate.rubrics (id)
)

;
CREATE INDEX ix_proposals_class ON chalkmate.proposals (classroom_id);

CREATE TABLE chalkmate.decisions (
	submission_id UUID NOT NULL,
	extraction_id UUID NOT NULL,
	rubric_id UUID NOT NULL,
	proposal_id UUID,
	approved_by UUID NOT NULL,
	marks JSONB NOT NULL,
	total NUMERIC(8, 2) NOT NULL,
	maximum NUMERIC(8, 2) NOT NULL,
	feedback VARCHAR(8000) NOT NULL,
	reason VARCHAR(2000) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_decisions PRIMARY KEY (id),
	CONSTRAINT fk_decisions_workspace_id_submissions FOREIGN KEY(workspace_id, classroom_id, submission_id) REFERENCES chalkmate.submissions (workspace_id, classroom_id, id),
	CONSTRAINT fk_decisions_submission_id_extractions FOREIGN KEY(submission_id, extraction_id) REFERENCES chalkmate.extractions (submission_id, id),
	CONSTRAINT fk_decisions_submission_id_proposals FOREIGN KEY(submission_id, proposal_id) REFERENCES chalkmate.proposals (submission_id, id),
	CONSTRAINT uq_decisions_submission_id_id UNIQUE (submission_id, id),
	CONSTRAINT ck_decisions_score_bounds CHECK (total >= 0 AND total <= maximum),
	CONSTRAINT fk_decisions_rubric_id_rubrics FOREIGN KEY(rubric_id) REFERENCES chalkmate.rubrics (id),
	CONSTRAINT fk_decisions_approved_by_users FOREIGN KEY(approved_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_decisions_class ON chalkmate.decisions (classroom_id);

CREATE TABLE chalkmate.releases (
	submission_id UUID NOT NULL,
	decision_id UUID NOT NULL,
	released_by UUID NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_releases PRIMARY KEY (id),
	CONSTRAINT fk_releases_workspace_id_submissions FOREIGN KEY(workspace_id, classroom_id, submission_id) REFERENCES chalkmate.submissions (workspace_id, classroom_id, id),
	CONSTRAINT fk_releases_submission_id_decisions FOREIGN KEY(submission_id, decision_id) REFERENCES chalkmate.decisions (submission_id, id),
	CONSTRAINT uq_releases_submission_id UNIQUE (submission_id),
	CONSTRAINT fk_releases_released_by_users FOREIGN KEY(released_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_releases_class ON chalkmate.releases (classroom_id);
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='chalkmate_worker') THEN
    CREATE ROLE chalkmate_worker LOGIN NOSUPERUSER NOBYPASSRLS INHERIT;
  END IF;
END $$;
GRANT chalkmate_app TO chalkmate_worker;

CREATE FUNCTION chalkmate.job_authorized(j chalkmate.processing_jobs) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
  SELECT EXISTS(SELECT 1 FROM chalkmate.classrooms c WHERE c.id=j.classroom_id
    AND NOT c.archived AND (EXISTS(SELECT 1 FROM chalkmate.workspaces w
      WHERE w.id=j.workspace_id AND w.owner_id=j.requested_by) OR
    EXISTS(SELECT 1 FROM chalkmate.classroom_teachers t WHERE t.classroom_id=c.id
      AND t.user_id=j.requested_by AND t.role='teacher')))
$$;
CREATE FUNCTION chalkmate.pending_jobs() RETURNS SETOF uuid
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
  SELECT j.id FROM chalkmate.processing_jobs j WHERE j.attempts<3
    AND (j.status='queued' OR (j.status='running' AND j.lease_until<now()))
    AND chalkmate.job_authorized(j) ORDER BY j.created_at LIMIT 50
$$;
CREATE FUNCTION chalkmate.claim_job(target uuid) RETURNS TABLE(job_id uuid, actor_id uuid, email text)
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
  WITH claimed AS (UPDATE chalkmate.processing_jobs j SET status='running', attempts=attempts+1,
      lease_until=now()+interval '20 minutes', error=NULL
    WHERE j.id=target AND j.attempts<3 AND chalkmate.job_authorized(j)
      AND (j.status='queued' OR (j.status='running' AND j.lease_until<now()))
    RETURNING j.id,j.requested_by)
  SELECT c.id,c.requested_by,u.email::text FROM claimed c JOIN chalkmate.users u ON u.id=c.requested_by
$$;
REVOKE ALL ON FUNCTION chalkmate.job_authorized(chalkmate.processing_jobs) FROM PUBLIC;
REVOKE ALL ON FUNCTION chalkmate.pending_jobs() FROM PUBLIC;
REVOKE ALL ON FUNCTION chalkmate.claim_job(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.pending_jobs(),chalkmate.claim_job(uuid) TO chalkmate_worker;

CREATE FUNCTION chalkmate.my_results(target_class uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'assessment_title',a.title,'submission_id',s.id,'total',d.total::text,
    'maximum',d.maximum::text,'feedback',d.feedback,'marks',d.marks,
    'questions',(SELECT jsonb_agg(q-'model_answer') FROM jsonb_array_elements(b.questions) q),
    'released_at',r.created_at) ORDER BY r.created_at DESC),'[]'::jsonb)
  FROM chalkmate.releases r JOIN chalkmate.decisions d ON d.id=r.decision_id
    JOIN chalkmate.submissions s ON s.id=r.submission_id
    JOIN chalkmate.assessments a ON a.id=s.assessment_id
    JOIN chalkmate.rubrics b ON b.id=s.rubric_id
    JOIN chalkmate.students st ON st.id=s.student_id
    JOIN chalkmate.enrollments e ON e.student_id=st.id AND e.classroom_id=s.classroom_id
  WHERE s.classroom_id=target_class AND st.user_id=chalkmate.actor() AND e.status='active'
$$;
REVOKE ALL ON FUNCTION chalkmate.my_results(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.my_results(uuid) TO chalkmate_app;

-- All raw assessment records are teacher/reviewer only. Student access uses the
-- narrow released-feedback function above, never the raw extraction/proposal tables.

ALTER TABLE chalkmate.assessments ENABLE ROW LEVEL SECURITY;
CREATE POLICY assessments_read ON chalkmate.assessments FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY assessments_create ON chalkmate.assessments FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.assessments TO chalkmate_app;

ALTER TABLE chalkmate.submissions ENABLE ROW LEVEL SECURITY;
CREATE POLICY submissions_read ON chalkmate.submissions FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY submissions_create ON chalkmate.submissions FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.submissions TO chalkmate_app;

ALTER TABLE chalkmate.processing_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY processing_jobs_read ON chalkmate.processing_jobs FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY processing_jobs_create ON chalkmate.processing_jobs FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.processing_jobs TO chalkmate_app;

ALTER TABLE chalkmate.extractions ENABLE ROW LEVEL SECURITY;
CREATE POLICY extractions_read ON chalkmate.extractions FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY extractions_create ON chalkmate.extractions FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.extractions TO chalkmate_app;

ALTER TABLE chalkmate.rubrics ENABLE ROW LEVEL SECURITY;
CREATE POLICY rubrics_read ON chalkmate.rubrics FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY rubrics_create ON chalkmate.rubrics FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.rubrics TO chalkmate_app;

ALTER TABLE chalkmate.decisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY decisions_read ON chalkmate.decisions FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY decisions_create ON chalkmate.decisions FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.decisions TO chalkmate_app;

ALTER TABLE chalkmate.releases ENABLE ROW LEVEL SECURITY;
CREATE POLICY releases_read ON chalkmate.releases FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY releases_create ON chalkmate.releases FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.releases TO chalkmate_app;

ALTER TABLE chalkmate.proposals ENABLE ROW LEVEL SECURITY;
CREATE POLICY proposals_read ON chalkmate.proposals FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY proposals_create ON chalkmate.proposals FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.proposals TO chalkmate_app;

CREATE POLICY assessments_change ON chalkmate.assessments FOR UPDATE USING(chalkmate.staff(classroom_id,true))
 WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT UPDATE(status) ON chalkmate.assessments TO chalkmate_app;

CREATE POLICY rubrics_change ON chalkmate.rubrics FOR UPDATE USING(chalkmate.staff(classroom_id,true))
 WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT UPDATE(approved_at) ON chalkmate.rubrics TO chalkmate_app;

CREATE POLICY submissions_change ON chalkmate.submissions FOR UPDATE USING(chalkmate.staff(classroom_id,true))
 WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT UPDATE(status) ON chalkmate.submissions TO chalkmate_app;

CREATE POLICY processing_jobs_change ON chalkmate.processing_jobs FOR UPDATE USING(chalkmate.staff(classroom_id,true))
 WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT UPDATE(status,attempts,error,lease_until) ON chalkmate.processing_jobs TO chalkmate_app;
