CREATE TABLE chalkmate.review_requests (
 id uuid PRIMARY KEY,
 workspace_id uuid NOT NULL,
 classroom_id uuid NOT NULL,
 submission_id uuid NOT NULL,
 decision_id uuid NOT NULL,
 question_id uuid NOT NULL,
 question_label varchar(100) NOT NULL,
 student_label varchar(400) NOT NULL,
 assessment_title varchar(140) NOT NULL,
 requested_by uuid NOT NULL REFERENCES chalkmate.users(id),
 reason varchar(2000) NOT NULL,
 response varchar(2000),
 resolved_by uuid REFERENCES chalkmate.users(id),
 resolved_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT fk_review_requests_workspace_id_submissions FOREIGN KEY(workspace_id,classroom_id,submission_id)
 REFERENCES chalkmate.submissions(workspace_id,classroom_id,id),
 CONSTRAINT fk_review_requests_submission_id_decisions FOREIGN KEY(submission_id,decision_id)
 REFERENCES chalkmate.decisions(submission_id,id),
 CONSTRAINT uq_review_request_release_question_actor
 UNIQUE(submission_id,decision_id,question_id,requested_by)
);
CREATE INDEX ix_review_requests_class ON chalkmate.review_requests(classroom_id);
ALTER TABLE chalkmate.review_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY review_requests_read ON chalkmate.review_requests FOR SELECT USING(
 chalkmate.staff(classroom_id) OR (requested_by=chalkmate.actor() AND chalkmate.attends(classroom_id))
);
GRANT SELECT ON chalkmate.review_requests TO chalkmate_app;

CREATE FUNCTION chalkmate.request_review(cid uuid,sid uuid,qid uuid,released timestamptz,why text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE paper chalkmate.submissions; rel chalkmate.releases; question jsonb; rid uuid;
 student_label text; assessment_title text;
BEGIN
 -- Lock the same submission as result-release/re-evaluation so a request pins one release.
 SELECT s.* INTO paper FROM chalkmate.submissions s
 JOIN chalkmate.students st ON st.id=s.student_id
 JOIN chalkmate.enrollments e ON e.student_id=st.id AND e.classroom_id=s.classroom_id
 JOIN chalkmate.classrooms c ON c.id=s.classroom_id
 WHERE s.id=sid AND s.classroom_id=cid AND st.user_id=chalkmate.actor()
 AND e.status='active' AND NOT c.archived FOR UPDATE OF s;
 IF NOT FOUND OR why IS NULL OR released IS NULL OR length(btrim(why)) NOT BETWEEN 10 AND 2000 THEN RETURN NULL; END IF;
 SELECT * INTO rel FROM chalkmate.releases WHERE submission_id=sid
 ORDER BY created_at DESC,id DESC LIMIT 1;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF rel.created_at<>released THEN RETURN 'stale'; END IF;
 SELECT q INTO question FROM chalkmate.decisions d JOIN chalkmate.rubrics b ON b.id=d.rubric_id,
 jsonb_array_elements(b.questions) q WHERE d.id=rel.decision_id AND q->>'id'=qid::text;
 IF question IS NULL THEN RETURN NULL; END IF;
 IF EXISTS(SELECT 1 FROM chalkmate.review_requests WHERE submission_id=sid
 AND decision_id=rel.decision_id AND question_id=qid AND requested_by=chalkmate.actor())
 THEN RETURN 'duplicate'; END IF;
 rid:=gen_random_uuid();
 SELECT st.name || ' · ' || st.registration_number,a.title INTO student_label,assessment_title
 FROM chalkmate.students st, chalkmate.assessments a
 WHERE st.id=paper.student_id AND a.id=paper.assessment_id;
 INSERT INTO chalkmate.review_requests(id,workspace_id,classroom_id,submission_id,decision_id,
 question_id,question_label,student_label,assessment_title,requested_by,reason)
 VALUES(rid,paper.workspace_id,cid,sid,rel.decision_id,qid,question->>'label',student_label,
 assessment_title,chalkmate.actor(),btrim(why));
 INSERT INTO chalkmate.audit_events(id,workspace_id,classroom_id,actor_id,action,details)
 VALUES(gen_random_uuid(),paper.workspace_id,cid,chalkmate.actor(),'review.requested',
 jsonb_build_object('request_id',rid,'submission_id',sid,'question_id',qid));
 RETURN rid::text;
END $$;
REVOKE ALL ON FUNCTION chalkmate.request_review(uuid,uuid,uuid,timestamptz,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.request_review(uuid,uuid,uuid,timestamptz,text) TO chalkmate_app;

CREATE FUNCTION chalkmate.respond_review(rid uuid,reply text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE item chalkmate.review_requests;
BEGIN
 SELECT * INTO item FROM chalkmate.review_requests WHERE id=rid FOR UPDATE;
 IF NOT FOUND OR NOT chalkmate.staff(item.classroom_id,true) OR item.resolved_at IS NOT NULL
 OR reply IS NULL OR length(btrim(reply)) NOT BETWEEN 10 AND 2000
 OR EXISTS(SELECT 1 FROM chalkmate.classrooms WHERE id=item.classroom_id AND archived)
 THEN RETURN false; END IF;
 UPDATE chalkmate.review_requests SET response=btrim(reply),resolved_by=chalkmate.actor(),resolved_at=now() WHERE id=rid;
 INSERT INTO chalkmate.audit_events(id,workspace_id,classroom_id,actor_id,action,details)
 VALUES(gen_random_uuid(),item.workspace_id,item.classroom_id,chalkmate.actor(),'review.responded',jsonb_build_object('request_id',rid));
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION chalkmate.respond_review(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.respond_review(uuid,text) TO chalkmate_app;
