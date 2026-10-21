
CREATE TABLE chalkmate.planning_documents (
	family_id UUID NOT NULL,
	version INTEGER NOT NULL,
	kind VARCHAR(30) NOT NULL,
	title VARCHAR(200) NOT NULL,
	content JSONB NOT NULL,
	sources JSONB NOT NULL,
	created_by UUID NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_planning_documents PRIMARY KEY (id),
	CONSTRAINT fk_planning_documents_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT uq_planning_documents_classroom_id_family_id_version UNIQUE (classroom_id, family_id, version),
	CONSTRAINT uq_planning_documents_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id),
	CONSTRAINT fk_planning_documents_created_by_users FOREIGN KEY(created_by) REFERENCES chalkmate.users (id)
)


;

CREATE TABLE chalkmate.planning_approvals (
	document_id UUID NOT NULL,
	approved_by UUID NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_planning_approvals PRIMARY KEY (id),
	CONSTRAINT fk_planning_approvals_workspace_id_planning_documents FOREIGN KEY(workspace_id, classroom_id, document_id) REFERENCES chalkmate.planning_documents (workspace_id, classroom_id, id),
	CONSTRAINT uq_planning_approvals_document_id UNIQUE (document_id),
	CONSTRAINT fk_planning_approvals_approved_by_users FOREIGN KEY(approved_by) REFERENCES chalkmate.users (id)
)


;

CREATE TABLE chalkmate.planning_jobs (
	requested_by UUID NOT NULL,
	model VARCHAR(160) NOT NULL,
	model_digest VARCHAR(100) NOT NULL,
	request JSONB NOT NULL,
	status VARCHAR(20) NOT NULL,
	attempts INTEGER NOT NULL,
 budget_day TIMESTAMP WITH TIME ZONE NOT NULL,
 budget_attempts INTEGER NOT NULL,
	lease_until TIMESTAMP WITH TIME ZONE,
	error VARCHAR(500),
	result_id UUID,
	usage JSONB NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_planning_jobs PRIMARY KEY (id),
	CONSTRAINT fk_planning_jobs_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT fk_planning_jobs_requested_by_users FOREIGN KEY(requested_by) REFERENCES chalkmate.users (id)
)

;
ALTER TABLE chalkmate.planning_documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY planning_documents_read ON chalkmate.planning_documents FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY planning_documents_create ON chalkmate.planning_documents FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true) AND created_by=chalkmate.actor());
GRANT SELECT,INSERT ON chalkmate.planning_documents TO chalkmate_app;
ALTER TABLE chalkmate.planning_approvals ENABLE ROW LEVEL SECURITY;
CREATE POLICY planning_approvals_read ON chalkmate.planning_approvals FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY planning_approvals_create ON chalkmate.planning_approvals FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true) AND approved_by=chalkmate.actor());
GRANT SELECT,INSERT ON chalkmate.planning_approvals TO chalkmate_app;
ALTER TABLE chalkmate.planning_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY planning_jobs_read ON chalkmate.planning_jobs FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY planning_jobs_create ON chalkmate.planning_jobs FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true) AND requested_by=chalkmate.actor());
GRANT SELECT,INSERT ON chalkmate.planning_jobs TO chalkmate_app;
CREATE POLICY planning_jobs_change ON chalkmate.planning_jobs FOR UPDATE USING(chalkmate.staff(classroom_id,true)) WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT UPDATE(status,error,budget_day,budget_attempts) ON chalkmate.planning_jobs TO chalkmate_app;
GRANT UPDATE(model_digest,attempts,lease_until,result_id,usage) ON chalkmate.planning_jobs TO chalkmate_worker;
CREATE FUNCTION chalkmate.planning_authorized(r chalkmate.planning_jobs) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM chalkmate.classrooms c WHERE c.id=r.classroom_id AND NOT c.archived
 AND (EXISTS(SELECT 1 FROM chalkmate.workspaces w WHERE w.id=r.workspace_id AND w.owner_id=r.requested_by)
 OR EXISTS(SELECT 1 FROM chalkmate.classroom_teachers t WHERE t.classroom_id=c.id AND t.user_id=r.requested_by AND t.role='teacher')))
$$;
CREATE FUNCTION chalkmate.pending_planning() RETURNS SETOF uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 UPDATE chalkmate.planning_jobs r SET status='canceled',error='Teaching access changed or classroom archived',lease_until=NULL
 WHERE r.status IN ('queued','running') AND NOT chalkmate.planning_authorized(r);
 UPDATE chalkmate.planning_jobs SET status='failed',error='Worker lease expired; inspect sources before retrying',lease_until=NULL
 WHERE status='running' AND lease_until<now();
 RETURN QUERY SELECT r.id FROM chalkmate.planning_jobs r WHERE r.status='queued' AND r.attempts<3
 AND chalkmate.planning_authorized(r) ORDER BY r.created_at LIMIT 20;
END $$;
CREATE FUNCTION chalkmate.claim_planning(target uuid) RETURNS TABLE(run_id uuid,actor_id uuid,email text,attempt integer)
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
 WITH claimed AS (UPDATE chalkmate.planning_jobs r SET status='running',attempts=r.attempts+1,
 lease_until=now()+interval '12 minutes',error=NULL WHERE r.id=target AND r.status='queued'
 AND r.attempts<3 AND chalkmate.planning_authorized(r) RETURNING r.id,r.requested_by,r.attempts)
 SELECT c.id,c.requested_by,u.email::text,c.attempts FROM claimed c JOIN chalkmate.users u ON u.id=c.requested_by
$$;
REVOKE ALL ON FUNCTION chalkmate.planning_authorized(chalkmate.planning_jobs),chalkmate.pending_planning(),chalkmate.claim_planning(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.pending_planning(),chalkmate.claim_planning(uuid) TO chalkmate_worker;

CREATE FUNCTION chalkmate.record_planning_export(mid uuid,with_key boolean) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE material chalkmate.planning_documents;
BEGIN
 SELECT * INTO material FROM chalkmate.planning_documents WHERE id=mid;
 IF NOT FOUND OR NOT chalkmate.staff(material.classroom_id) THEN RETURN false; END IF;
 INSERT INTO chalkmate.audit_events(id,workspace_id,classroom_id,actor_id,action,details)
 VALUES(gen_random_uuid(),material.workspace_id,material.classroom_id,chalkmate.actor(),
 'planning.exported',jsonb_build_object('document_id',mid,'answer_key',with_key));
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION chalkmate.record_planning_export(uuid,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.record_planning_export(uuid,boolean) TO chalkmate_app;
