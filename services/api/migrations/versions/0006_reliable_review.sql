ALTER TABLE chalkmate.rubrics ADD COLUMN reason varchar(2000) NOT NULL DEFAULT '';
ALTER TABLE chalkmate.rubrics ALTER COLUMN reason DROP DEFAULT;
ALTER TABLE chalkmate.decisions ADD COLUMN question_feedback jsonb NOT NULL DEFAULT '{}';
ALTER TABLE chalkmate.decisions ALTER COLUMN question_feedback DROP DEFAULT;
ALTER TABLE chalkmate.releases DROP CONSTRAINT uq_releases_submission_id;
ALTER TABLE chalkmate.releases ADD CONSTRAINT uq_releases_submission_id_decision_id UNIQUE(submission_id,decision_id);
GRANT UPDATE(rubric_id) ON chalkmate.submissions TO chalkmate_app;

CREATE TABLE chalkmate.question_reviews (
	submission_id UUID NOT NULL,
	extraction_id UUID NOT NULL,
	rubric_id UUID NOT NULL,
	question_id UUID NOT NULL,
	reviewed_by UUID NOT NULL,
	marks JSONB NOT NULL,
	feedback VARCHAR(4000) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_question_reviews PRIMARY KEY (id),
	CONSTRAINT fk_question_reviews_workspace_id_submissions FOREIGN KEY(workspace_id, classroom_id, submission_id) REFERENCES chalkmate.submissions (workspace_id, classroom_id, id),
	CONSTRAINT fk_question_reviews_submission_id_extractions FOREIGN KEY(submission_id, extraction_id) REFERENCES chalkmate.extractions (submission_id, id),
	CONSTRAINT fk_question_reviews_rubric_id_rubrics FOREIGN KEY(rubric_id) REFERENCES chalkmate.rubrics (id),
	CONSTRAINT fk_question_reviews_reviewed_by_users FOREIGN KEY(reviewed_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_question_reviews_class ON chalkmate.question_reviews (classroom_id);
ALTER TABLE chalkmate.question_reviews ENABLE ROW LEVEL SECURITY;
CREATE POLICY question_reviews_read ON chalkmate.question_reviews FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY question_reviews_create ON chalkmate.question_reviews FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.question_reviews TO chalkmate_app;

CREATE TABLE chalkmate.calibrations (
	submission_id UUID NOT NULL,
	extraction_id UUID NOT NULL,
	rubric_id UUID NOT NULL,
	created_by UUID NOT NULL,
	band VARCHAR(20) NOT NULL,
	note VARCHAR(2000) NOT NULL,
	snapshot JSONB NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_calibrations PRIMARY KEY (id),
	CONSTRAINT fk_calibrations_workspace_id_submissions FOREIGN KEY(workspace_id, classroom_id, submission_id) REFERENCES chalkmate.submissions (workspace_id, classroom_id, id),
	CONSTRAINT fk_calibrations_submission_id_extractions FOREIGN KEY(submission_id, extraction_id) REFERENCES chalkmate.extractions (submission_id, id),
	CONSTRAINT fk_calibrations_rubric_id_rubrics FOREIGN KEY(rubric_id) REFERENCES chalkmate.rubrics (id),
	CONSTRAINT fk_calibrations_created_by_users FOREIGN KEY(created_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_calibrations_class ON chalkmate.calibrations (classroom_id);
ALTER TABLE chalkmate.calibrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY calibrations_read ON chalkmate.calibrations FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY calibrations_create ON chalkmate.calibrations FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.calibrations TO chalkmate_app;

CREATE TABLE chalkmate.reevaluations (
	submission_id UUID NOT NULL,
	from_rubric_id UUID NOT NULL,
	to_rubric_id UUID NOT NULL,
	requested_by UUID NOT NULL,
	reason VARCHAR(2000) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_reevaluations PRIMARY KEY (id),
	CONSTRAINT fk_reevaluations_workspace_id_submissions FOREIGN KEY(workspace_id, classroom_id, submission_id) REFERENCES chalkmate.submissions (workspace_id, classroom_id, id),
	CONSTRAINT fk_reevaluations_from_rubric_id_rubrics FOREIGN KEY(from_rubric_id) REFERENCES chalkmate.rubrics (id),
	CONSTRAINT fk_reevaluations_to_rubric_id_rubrics FOREIGN KEY(to_rubric_id) REFERENCES chalkmate.rubrics (id),
	CONSTRAINT fk_reevaluations_requested_by_users FOREIGN KEY(requested_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_reevaluations_class ON chalkmate.reevaluations (classroom_id);
ALTER TABLE chalkmate.reevaluations ENABLE ROW LEVEL SECURITY;
CREATE POLICY reevaluations_read ON chalkmate.reevaluations FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY reevaluations_create ON chalkmate.reevaluations FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.reevaluations TO chalkmate_app;

CREATE OR REPLACE FUNCTION chalkmate.my_results(target_class uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'assessment_title',a.title,'submission_id',s.id,'total',d.total::text,
    'maximum',d.maximum::text,'feedback',d.feedback,'marks',d.marks,
    'question_feedback',d.question_feedback,
    'questions',(SELECT jsonb_agg(jsonb_set(q-'model_answer'-'accepted_alternatives','{criteria}',
      (SELECT jsonb_agg(c-'guidance') FROM jsonb_array_elements(q->'criteria') c)))
      FROM jsonb_array_elements(b.questions) q),
    'released_at',r.created_at) ORDER BY r.created_at DESC),'[]'::jsonb)
  FROM (SELECT DISTINCT ON (submission_id) * FROM chalkmate.releases
    ORDER BY submission_id,created_at DESC,id DESC) r
    JOIN chalkmate.decisions d ON d.id=r.decision_id
    JOIN chalkmate.submissions s ON s.id=r.submission_id
    JOIN chalkmate.assessments a ON a.id=s.assessment_id
    JOIN chalkmate.rubrics b ON b.id=d.rubric_id
    JOIN chalkmate.students st ON st.id=s.student_id
    JOIN chalkmate.enrollments e ON e.student_id=st.id AND e.classroom_id=s.classroom_id
  WHERE s.classroom_id=target_class AND st.user_id=chalkmate.actor() AND e.status='active'
$$;
