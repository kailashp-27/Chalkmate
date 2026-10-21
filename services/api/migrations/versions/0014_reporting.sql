
CREATE TABLE chalkmate.marks_exports (
	assessment_id UUID NOT NULL,
	template_id UUID NOT NULL,
	created_by UUID NOT NULL,
	snapshot JSONB NOT NULL,
	digest VARCHAR(64) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_marks_exports PRIMARY KEY (id),
	CONSTRAINT fk_marks_exports_workspace_id_assessments FOREIGN KEY(workspace_id, classroom_id, assessment_id) REFERENCES chalkmate.assessments (workspace_id, classroom_id, id),
	CONSTRAINT fk_marks_exports_workspace_id_planning_documents FOREIGN KEY(workspace_id, classroom_id, template_id) REFERENCES chalkmate.planning_documents (workspace_id, classroom_id, id),
	CONSTRAINT fk_marks_exports_created_by_users FOREIGN KEY(created_by) REFERENCES chalkmate.users (id)
)

;

CREATE TABLE chalkmate.question_links (
	document_id UUID NOT NULL,
	version INTEGER NOT NULL,
	question_index INTEGER NOT NULL,
	assessment_id UUID NOT NULL,
	rubric_id UUID NOT NULL,
	question_id UUID NOT NULL,
	disposition VARCHAR(10) NOT NULL,
	reason VARCHAR(1000) NOT NULL,
	created_by UUID NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_question_links PRIMARY KEY (id),
	CONSTRAINT fk_question_links_workspace_id_assessments FOREIGN KEY(workspace_id, classroom_id, assessment_id) REFERENCES chalkmate.assessments (workspace_id, classroom_id, id),
	CONSTRAINT fk_question_links_workspace_id_planning_documents FOREIGN KEY(workspace_id, classroom_id, document_id) REFERENCES chalkmate.planning_documents (workspace_id, classroom_id, id),
	CONSTRAINT uq_question_links_document_id_version UNIQUE (document_id, version),
	CONSTRAINT fk_question_links_workspace_id_rubrics FOREIGN KEY(workspace_id, classroom_id, rubric_id) REFERENCES chalkmate.rubrics (workspace_id, classroom_id, id),
	CONSTRAINT fk_question_links_assessment_id_rubrics FOREIGN KEY(assessment_id, rubric_id) REFERENCES chalkmate.rubrics (assessment_id, id),
	CONSTRAINT ck_question_links_valid_disposition CHECK (disposition IN ('linked','revoked')),
	CONSTRAINT ck_question_links_valid_index CHECK (question_index BETWEEN 0 AND 39),
	CONSTRAINT fk_question_links_created_by_users FOREIGN KEY(created_by) REFERENCES chalkmate.users (id)
)

;
ALTER TABLE chalkmate.marks_exports ENABLE ROW LEVEL SECURITY;
CREATE POLICY marks_exports_read ON chalkmate.marks_exports FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY marks_exports_create ON chalkmate.marks_exports FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true) AND created_by=chalkmate.actor());
GRANT SELECT,INSERT ON chalkmate.marks_exports TO chalkmate_app;
ALTER TABLE chalkmate.question_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY question_links_read ON chalkmate.question_links FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY question_links_create ON chalkmate.question_links FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true) AND created_by=chalkmate.actor());
GRANT SELECT,INSERT ON chalkmate.question_links TO chalkmate_app;
CREATE FUNCTION chalkmate.record_marks_download(eid uuid,fmt text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE item chalkmate.marks_exports;
BEGIN
 SELECT * INTO item FROM chalkmate.marks_exports WHERE id=eid;
 IF NOT FOUND OR NOT chalkmate.staff(item.classroom_id) OR fmt NOT IN ('csv','xlsx') THEN RETURN false; END IF;
 INSERT INTO chalkmate.audit_events(id,workspace_id,classroom_id,actor_id,action,details)
 VALUES(gen_random_uuid(),item.workspace_id,item.classroom_id,chalkmate.actor(),'marks_export.downloaded',jsonb_build_object('export_id',eid,'format',fmt));
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION chalkmate.record_marks_download(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.record_marks_download(uuid,text) TO chalkmate_app;
