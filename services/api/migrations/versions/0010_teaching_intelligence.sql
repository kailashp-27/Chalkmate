
CREATE TABLE chalkmate.intelligence_runs (
	assessment_id UUID NOT NULL,
	rubric_id UUID NOT NULL,
	requested_by UUID NOT NULL,
	kind VARCHAR(20) NOT NULL,
	model VARCHAR(160) NOT NULL,
	model_digest VARCHAR(100) NOT NULL,
	prompt_version VARCHAR(50) NOT NULL,
	request JSONB NOT NULL,
	snapshot JSONB NOT NULL,
	input_digest VARCHAR(64) NOT NULL,
	status VARCHAR(20) NOT NULL,
	attempts INTEGER NOT NULL,
	lease_until TIMESTAMP WITH TIME ZONE,
	error VARCHAR(500),
	result JSONB,
	usage JSONB NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_intelligence_runs PRIMARY KEY (id),
	CONSTRAINT fk_intelligence_runs_workspace_id_assessments FOREIGN KEY(workspace_id, classroom_id, assessment_id) REFERENCES chalkmate.assessments (workspace_id, classroom_id, id),
	CONSTRAINT fk_intelligence_runs_workspace_id_rubrics FOREIGN KEY(workspace_id, classroom_id, rubric_id) REFERENCES chalkmate.rubrics (workspace_id, classroom_id, id),
	CONSTRAINT uq_intelligence_runs_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id),
	CONSTRAINT ck_intelligence_runs_valid_kind CHECK (kind IN ('analysis','material')),
	CONSTRAINT ck_intelligence_runs_valid_status CHECK (status IN ('queued','running','succeeded','failed','canceled')),
	CONSTRAINT fk_intelligence_runs_requested_by_users FOREIGN KEY(requested_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_intelligence_runs_class ON chalkmate.intelligence_runs (classroom_id);

CREATE TABLE chalkmate.finding_reviews (
	run_id UUID NOT NULL,
	finding_index INTEGER NOT NULL,
	version INTEGER NOT NULL,
	disposition VARCHAR(20) NOT NULL,
	reason VARCHAR(2000) NOT NULL,
	reviewed_by UUID NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_finding_reviews PRIMARY KEY (id),
	CONSTRAINT fk_finding_reviews_workspace_id_intelligence_runs FOREIGN KEY(workspace_id, classroom_id, run_id) REFERENCES chalkmate.intelligence_runs (workspace_id, classroom_id, id),
	CONSTRAINT uq_finding_reviews_run_id_finding_index_version UNIQUE (run_id, finding_index, version),
	CONSTRAINT ck_finding_reviews_valid_disposition CHECK (disposition IN ('accepted','dismissed')),
	CONSTRAINT fk_finding_reviews_reviewed_by_users FOREIGN KEY(reviewed_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_finding_reviews_class ON chalkmate.finding_reviews (classroom_id);

CREATE TABLE chalkmate.teaching_materials (
	run_id UUID NOT NULL,
	version INTEGER NOT NULL,
	created_by UUID NOT NULL,
	content JSONB NOT NULL,
	reason VARCHAR(2000) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_teaching_materials PRIMARY KEY (id),
	CONSTRAINT fk_teaching_materials_workspace_id_intelligence_runs FOREIGN KEY(workspace_id, classroom_id, run_id) REFERENCES chalkmate.intelligence_runs (workspace_id, classroom_id, id),
	CONSTRAINT uq_teaching_materials_run_id_version UNIQUE (run_id, version),
	CONSTRAINT uq_teaching_materials_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id),
	CONSTRAINT fk_teaching_materials_created_by_users FOREIGN KEY(created_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_teaching_materials_class ON chalkmate.teaching_materials (classroom_id);

CREATE TABLE chalkmate.material_approvals (
	material_id UUID NOT NULL,
	assignment_version_id UUID NOT NULL,
	approved_by UUID NOT NULL,
	reason VARCHAR(2000) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_material_approvals PRIMARY KEY (id),
	CONSTRAINT fk_material_approvals_workspace_id_teaching_materials FOREIGN KEY(workspace_id, classroom_id, material_id) REFERENCES chalkmate.teaching_materials (workspace_id, classroom_id, id),
	CONSTRAINT fk_material_approvals_workspace_id_assignment_versions FOREIGN KEY(workspace_id, classroom_id, assignment_version_id) REFERENCES chalkmate.assignment_versions (workspace_id, classroom_id, id),
	CONSTRAINT uq_material_approvals_material_id UNIQUE (material_id),
	CONSTRAINT fk_material_approvals_approved_by_users FOREIGN KEY(approved_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_material_approvals_class ON chalkmate.material_approvals (classroom_id);
ALTER TABLE chalkmate.intelligence_runs ADD CONSTRAINT fk_intelligence_runs_assessment_rubric
 FOREIGN KEY(assessment_id,rubric_id) REFERENCES chalkmate.rubrics(assessment_id,id);
ALTER TABLE chalkmate.intelligence_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE chalkmate.finding_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE chalkmate.teaching_materials ENABLE ROW LEVEL SECURITY;
ALTER TABLE chalkmate.material_approvals ENABLE ROW LEVEL SECURITY;
CREATE POLICY intelligence_runs_read ON chalkmate.intelligence_runs FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY intelligence_runs_create ON chalkmate.intelligence_runs FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true) AND requested_by=chalkmate.actor());
CREATE POLICY intelligence_runs_change ON chalkmate.intelligence_runs FOR UPDATE USING(chalkmate.staff(classroom_id,true)) WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.intelligence_runs TO chalkmate_app;
GRANT UPDATE(status,error) ON chalkmate.intelligence_runs TO chalkmate_app;
GRANT UPDATE(model_digest,attempts,lease_until,result,usage) ON chalkmate.intelligence_runs TO chalkmate_worker;
CREATE POLICY finding_reviews_read ON chalkmate.finding_reviews FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY finding_reviews_create ON chalkmate.finding_reviews FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true) AND reviewed_by=chalkmate.actor());
GRANT SELECT,INSERT ON chalkmate.finding_reviews TO chalkmate_app;
CREATE POLICY teaching_materials_read ON chalkmate.teaching_materials FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY teaching_materials_create ON chalkmate.teaching_materials FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true) AND created_by=chalkmate.actor());
GRANT SELECT,INSERT ON chalkmate.teaching_materials TO chalkmate_app;
CREATE POLICY material_approvals_read ON chalkmate.material_approvals FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY material_approvals_create ON chalkmate.material_approvals FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true) AND approved_by=chalkmate.actor());
GRANT SELECT,INSERT ON chalkmate.material_approvals TO chalkmate_app;
CREATE FUNCTION chalkmate.intelligence_authorized(r chalkmate.intelligence_runs) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM chalkmate.classrooms c WHERE c.id=r.classroom_id AND NOT c.archived
 AND (EXISTS(SELECT 1 FROM chalkmate.workspaces w WHERE w.id=r.workspace_id AND w.owner_id=r.requested_by)
 OR EXISTS(SELECT 1 FROM chalkmate.classroom_teachers t WHERE t.classroom_id=c.id AND t.user_id=r.requested_by AND t.role='teacher')))
$$;
CREATE FUNCTION chalkmate.pending_intelligence() RETURNS SETOF uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 UPDATE chalkmate.intelligence_runs r SET status='canceled',error='Teaching access changed or classroom archived',lease_until=NULL
 WHERE r.status IN ('queued','running') AND NOT chalkmate.intelligence_authorized(r);
 UPDATE chalkmate.intelligence_runs SET status='failed',error='Worker lease expired; inspect sources before retrying',lease_until=NULL
 WHERE status='running' AND lease_until<now();
 RETURN QUERY SELECT r.id FROM chalkmate.intelligence_runs r WHERE r.status='queued' AND r.attempts<3
 AND chalkmate.intelligence_authorized(r) ORDER BY r.created_at LIMIT 20;
END $$;
CREATE FUNCTION chalkmate.claim_intelligence(target uuid) RETURNS TABLE(run_id uuid,actor_id uuid,email text)
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
 WITH claimed AS (UPDATE chalkmate.intelligence_runs r SET status='running',attempts=r.attempts+1,
 lease_until=now()+interval '12 minutes',error=NULL WHERE r.id=target AND r.status='queued'
 AND r.attempts<3 AND chalkmate.intelligence_authorized(r) RETURNING r.id,r.requested_by)
 SELECT c.id,c.requested_by,u.email::text FROM claimed c JOIN chalkmate.users u ON u.id=c.requested_by
$$;
REVOKE ALL ON FUNCTION chalkmate.intelligence_authorized(chalkmate.intelligence_runs),chalkmate.pending_intelligence(),chalkmate.claim_intelligence(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.pending_intelligence(),chalkmate.claim_intelligence(uuid) TO chalkmate_worker;
