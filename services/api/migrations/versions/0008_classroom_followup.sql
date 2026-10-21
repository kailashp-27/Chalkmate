
CREATE TABLE chalkmate.assignments (
	closed BOOLEAN NOT NULL,
	created_by UUID NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_assignments PRIMARY KEY (id),
	CONSTRAINT fk_assignments_workspace_id_classrooms FOREIGN KEY(workspace_id, classroom_id) REFERENCES chalkmate.classrooms (workspace_id, id),
	CONSTRAINT uq_assignments_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id),
	CONSTRAINT fk_assignments_created_by_users FOREIGN KEY(created_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_assignments_class ON chalkmate.assignments (classroom_id);
ALTER TABLE chalkmate.assignments ENABLE ROW LEVEL SECURITY;

CREATE TABLE chalkmate.assignment_versions (
	assignment_id UUID NOT NULL,
	version INTEGER NOT NULL,
	title VARCHAR(160) NOT NULL,
	instructions VARCHAR(20000) NOT NULL,
	due_at TIMESTAMP WITH TIME ZONE,
	published_at TIMESTAMP WITH TIME ZONE,
	reason VARCHAR(2000) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_assignment_versions PRIMARY KEY (id),
	CONSTRAINT fk_assignment_versions_workspace_id_assignments FOREIGN KEY(workspace_id, classroom_id, assignment_id) REFERENCES chalkmate.assignments (workspace_id, classroom_id, id),
	CONSTRAINT uq_assignment_versions_assignment_id_version UNIQUE (assignment_id, version),
	CONSTRAINT uq_assignment_versions_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id)
)

;
CREATE INDEX ix_assignment_versions_class ON chalkmate.assignment_versions (classroom_id);
ALTER TABLE chalkmate.assignment_versions ENABLE ROW LEVEL SECURITY;

CREATE TABLE chalkmate.assignment_audiences (
	assignment_version_id UUID NOT NULL,
	student_id UUID NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_assignment_audiences PRIMARY KEY (id),
	CONSTRAINT fk_assignment_audiences_workspace_id_assignment_versions FOREIGN KEY(workspace_id, classroom_id, assignment_version_id) REFERENCES chalkmate.assignment_versions (workspace_id, classroom_id, id),
	CONSTRAINT fk_assignment_audiences_workspace_id_enrollments FOREIGN KEY(workspace_id, classroom_id, student_id) REFERENCES chalkmate.enrollments (workspace_id, classroom_id, student_id),
	CONSTRAINT uq_assignment_audiences_assignment_version_id_student_id UNIQUE (assignment_version_id, student_id)
)

;
CREATE INDEX ix_assignment_audiences_class ON chalkmate.assignment_audiences (classroom_id);
ALTER TABLE chalkmate.assignment_audiences ENABLE ROW LEVEL SECURITY;

CREATE TABLE chalkmate.assignment_responses (
	assignment_version_id UUID NOT NULL,
	student_id UUID NOT NULL,
	version INTEGER NOT NULL,
	text VARCHAR(20000) NOT NULL,
	file_path VARCHAR(350),
	filename VARCHAR(180),
	content_type VARCHAR(80),
	late BOOLEAN NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_assignment_responses PRIMARY KEY (id),
	CONSTRAINT fk_assignment_responses_workspace_id_assignment_versions FOREIGN KEY(workspace_id, classroom_id, assignment_version_id) REFERENCES chalkmate.assignment_versions (workspace_id, classroom_id, id),
	CONSTRAINT fk_assignment_responses_workspace_id_enrollments FOREIGN KEY(workspace_id, classroom_id, student_id) REFERENCES chalkmate.enrollments (workspace_id, classroom_id, student_id),
	CONSTRAINT uq_assignment_responses_assignment_version_id_student_i_d3cd UNIQUE (assignment_version_id, student_id, version)
)

;
CREATE INDEX ix_assignment_responses_class ON chalkmate.assignment_responses (classroom_id);
ALTER TABLE chalkmate.assignment_responses ENABLE ROW LEVEL SECURITY;

CREATE TABLE chalkmate.campaign_previews (
	assignment_version_id UUID NOT NULL,
	created_by UUID NOT NULL,
	request JSONB NOT NULL,
	snapshot JSONB NOT NULL,
	digest VARCHAR(64) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_campaign_previews PRIMARY KEY (id),
	CONSTRAINT fk_campaign_previews_workspace_id_assignment_versions FOREIGN KEY(workspace_id, classroom_id, assignment_version_id) REFERENCES chalkmate.assignment_versions (workspace_id, classroom_id, id),
	CONSTRAINT uq_campaign_previews_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id),
	CONSTRAINT fk_campaign_previews_created_by_users FOREIGN KEY(created_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_campaign_previews_class ON chalkmate.campaign_previews (classroom_id);
ALTER TABLE chalkmate.campaign_previews ENABLE ROW LEVEL SECURITY;

CREATE TABLE chalkmate.campaigns (
	assignment_version_id UUID NOT NULL,
	preview_id UUID NOT NULL,
	approved_by UUID NOT NULL,
	request JSONB NOT NULL,
	scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
	provider VARCHAR(20) NOT NULL,
	canceled BOOLEAN NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_campaigns PRIMARY KEY (id),
	CONSTRAINT fk_campaigns_workspace_id_assignment_versions FOREIGN KEY(workspace_id, classroom_id, assignment_version_id) REFERENCES chalkmate.assignment_versions (workspace_id, classroom_id, id),
	CONSTRAINT fk_campaigns_workspace_id_campaign_previews FOREIGN KEY(workspace_id, classroom_id, preview_id) REFERENCES chalkmate.campaign_previews (workspace_id, classroom_id, id),
	CONSTRAINT uq_campaigns_preview_id UNIQUE (preview_id),
	CONSTRAINT uq_campaigns_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id),
	CONSTRAINT fk_campaigns_approved_by_users FOREIGN KEY(approved_by) REFERENCES chalkmate.users (id)
)

;
CREATE INDEX ix_campaigns_class ON chalkmate.campaigns (classroom_id);
ALTER TABLE chalkmate.campaigns ENABLE ROW LEVEL SECURITY;

CREATE TABLE chalkmate.deliveries (
	campaign_id UUID NOT NULL,
	student_id UUID NOT NULL,
	snapshot JSONB NOT NULL,
	payload JSONB NOT NULL,
	status VARCHAR(20) NOT NULL,
	attempts INTEGER NOT NULL,
	first_attempt_at TIMESTAMP WITH TIME ZONE,
	lease_until TIMESTAMP WITH TIME ZONE,
	provider_id VARCHAR(180),
	last_event_at TIMESTAMP WITH TIME ZONE,
	detail VARCHAR(500) NOT NULL,
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_deliveries PRIMARY KEY (id),
	CONSTRAINT fk_deliveries_workspace_id_campaigns FOREIGN KEY(workspace_id, classroom_id, campaign_id) REFERENCES chalkmate.campaigns (workspace_id, classroom_id, id),
	CONSTRAINT fk_deliveries_workspace_id_enrollments FOREIGN KEY(workspace_id, classroom_id, student_id) REFERENCES chalkmate.enrollments (workspace_id, classroom_id, student_id),
	CONSTRAINT uq_deliveries_campaign_id_student_id UNIQUE (campaign_id, student_id),
	CONSTRAINT uq_deliveries_provider_id UNIQUE (provider_id),
	CONSTRAINT uq_deliveries_workspace_id_classroom_id_id UNIQUE (workspace_id, classroom_id, id),
	CONSTRAINT ck_deliveries_valid_status CHECK (status IN ('queued','sending','captured','accepted','delivered','bounced','failed','held','skipped','uncertain','canceled'))
)

;
CREATE INDEX ix_deliveries_class ON chalkmate.deliveries (classroom_id);
ALTER TABLE chalkmate.deliveries ENABLE ROW LEVEL SECURITY;

CREATE TABLE chalkmate.delivery_attempts (
	delivery_id UUID NOT NULL,
	outcome VARCHAR(30) NOT NULL,
	detail VARCHAR(500) NOT NULL,
	provider_id VARCHAR(180),
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	classroom_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_delivery_attempts PRIMARY KEY (id),
	CONSTRAINT fk_delivery_attempts_workspace_id_deliveries FOREIGN KEY(workspace_id, classroom_id, delivery_id) REFERENCES chalkmate.deliveries (workspace_id, classroom_id, id)
)

;
CREATE INDEX ix_delivery_attempts_class ON chalkmate.delivery_attempts (classroom_id);
ALTER TABLE chalkmate.delivery_attempts ENABLE ROW LEVEL SECURITY;

CREATE TABLE chalkmate.delivery_events (
	id VARCHAR(180) NOT NULL,
	provider_id VARCHAR(180) NOT NULL,
	kind VARCHAR(80) NOT NULL,
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_delivery_events PRIMARY KEY (id)
)

;
ALTER TABLE chalkmate.delivery_events ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION chalkmate.own_student(sid uuid, cid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM chalkmate.students s JOIN chalkmate.enrollments e ON e.student_id=s.id
 WHERE s.id=sid AND s.user_id=chalkmate.actor() AND e.classroom_id=cid AND e.status='active')
$$;
CREATE FUNCTION chalkmate.assignment_access(vid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM chalkmate.assignment_versions v
 JOIN chalkmate.assignment_audiences a ON a.assignment_version_id=v.id
 WHERE v.id=vid AND v.published_at IS NOT NULL AND chalkmate.own_student(a.student_id,v.classroom_id))
$$;
CREATE FUNCTION chalkmate.assignment_visible(aid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM chalkmate.assignment_versions v
 WHERE v.assignment_id=aid AND chalkmate.assignment_access(v.id))
$$;
CREATE FUNCTION chalkmate.assignment_current(aid uuid) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT v.id FROM chalkmate.assignment_versions v WHERE v.assignment_id=aid AND v.published_at IS NOT NULL
 AND (chalkmate.staff(v.classroom_id) OR chalkmate.assignment_visible(aid)) ORDER BY v.version DESC LIMIT 1
$$;
CREATE FUNCTION chalkmate.response_allowed(vid uuid,sid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM chalkmate.assignment_versions v JOIN chalkmate.assignments a ON a.id=v.assignment_id
 JOIN chalkmate.classrooms c ON c.id=v.classroom_id WHERE v.id=vid AND NOT a.closed AND NOT c.archived
 AND v.id=chalkmate.assignment_current(a.id) AND chalkmate.assignment_access(v.id)
 AND chalkmate.own_student(sid,c.id) AND EXISTS(SELECT 1 FROM chalkmate.assignment_audiences x
 WHERE x.assignment_version_id=v.id AND x.student_id=sid))
$$;
CREATE FUNCTION chalkmate.contact_ready(sid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM chalkmate.students s JOIN chalkmate.users u ON u.id=s.user_id
 WHERE s.id=sid AND lower(s.email)=lower(u.email) AND EXISTS(SELECT 1 FROM chalkmate.enrollments e
 WHERE e.student_id=s.id AND chalkmate.staff(e.classroom_id)))
$$;
CREATE FUNCTION chalkmate.contact_suppressed(sid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM chalkmate.students s JOIN chalkmate.deliveries d ON d.student_id=s.id
 WHERE s.id=sid AND d.status='bounced' AND lower(d.snapshot->>'email')=lower(s.email)
 AND EXISTS(SELECT 1 FROM chalkmate.enrollments e WHERE e.student_id=s.id AND chalkmate.staff(e.classroom_id)))
$$;
REVOKE ALL ON FUNCTION chalkmate.own_student(uuid,uuid),chalkmate.assignment_access(uuid),chalkmate.assignment_visible(uuid),chalkmate.assignment_current(uuid),chalkmate.response_allowed(uuid,uuid),chalkmate.contact_ready(uuid),chalkmate.contact_suppressed(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.own_student(uuid,uuid),chalkmate.assignment_access(uuid),chalkmate.assignment_visible(uuid),chalkmate.assignment_current(uuid),chalkmate.response_allowed(uuid,uuid),chalkmate.contact_ready(uuid),chalkmate.contact_suppressed(uuid) TO chalkmate_app;
CREATE POLICY assignments_read ON chalkmate.assignments FOR SELECT USING(chalkmate.staff(classroom_id) OR chalkmate.assignment_visible(id));
CREATE POLICY assignments_create ON chalkmate.assignments FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
CREATE POLICY assignments_update ON chalkmate.assignments FOR UPDATE USING(chalkmate.staff(classroom_id,true)) WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.assignments TO chalkmate_app;
GRANT UPDATE(closed) ON chalkmate.assignments TO chalkmate_app;
CREATE POLICY assignment_versions_read ON chalkmate.assignment_versions FOR SELECT USING(chalkmate.staff(classroom_id) OR chalkmate.assignment_access(id));
CREATE POLICY assignment_versions_create ON chalkmate.assignment_versions FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
CREATE POLICY assignment_versions_update ON chalkmate.assignment_versions FOR UPDATE USING(chalkmate.staff(classroom_id,true)) WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.assignment_versions TO chalkmate_app;
GRANT UPDATE(published_at) ON chalkmate.assignment_versions TO chalkmate_app;
CREATE POLICY assignment_audiences_read ON chalkmate.assignment_audiences FOR SELECT USING(chalkmate.staff(classroom_id) OR chalkmate.own_student(student_id,classroom_id));
CREATE POLICY assignment_audiences_create ON chalkmate.assignment_audiences FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.assignment_audiences TO chalkmate_app;
CREATE POLICY assignment_responses_read ON chalkmate.assignment_responses FOR SELECT USING(chalkmate.staff(classroom_id) OR (chalkmate.own_student(student_id,classroom_id) AND chalkmate.assignment_access(assignment_version_id)));
CREATE POLICY assignment_responses_create ON chalkmate.assignment_responses FOR INSERT WITH CHECK(chalkmate.response_allowed(assignment_version_id,student_id));
GRANT SELECT,INSERT ON chalkmate.assignment_responses TO chalkmate_app;
GRANT UPDATE(email) ON chalkmate.students TO chalkmate_app;
DROP POLICY audit_create ON chalkmate.audit_events;
CREATE POLICY audit_create ON chalkmate.audit_events FOR INSERT WITH CHECK(actor_id=chalkmate.actor() AND
 (chalkmate.owns(workspace_id) OR chalkmate.staff(classroom_id,true)
 OR (action='invitation.accepted' AND chalkmate.member(workspace_id))
 OR (action='assignment.responded' AND chalkmate.attends(classroom_id))));
CREATE POLICY campaign_previews_read ON chalkmate.campaign_previews FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY campaign_previews_create ON chalkmate.campaign_previews FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.campaign_previews TO chalkmate_app;
CREATE POLICY campaigns_read ON chalkmate.campaigns FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY campaigns_create ON chalkmate.campaigns FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.campaigns TO chalkmate_app;
CREATE POLICY deliveries_read ON chalkmate.deliveries FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY deliveries_create ON chalkmate.deliveries FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.deliveries TO chalkmate_app;
CREATE POLICY delivery_attempts_read ON chalkmate.delivery_attempts FOR SELECT USING(chalkmate.staff(classroom_id));
CREATE POLICY delivery_attempts_create ON chalkmate.delivery_attempts FOR INSERT WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT SELECT,INSERT ON chalkmate.delivery_attempts TO chalkmate_app;
CREATE POLICY campaigns_update ON chalkmate.campaigns FOR UPDATE USING(chalkmate.staff(classroom_id,true)) WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT UPDATE(canceled) ON chalkmate.campaigns TO chalkmate_app;
CREATE POLICY deliveries_update ON chalkmate.deliveries FOR UPDATE USING(chalkmate.staff(classroom_id,true)) WITH CHECK(chalkmate.staff(classroom_id,true));
GRANT UPDATE(status,detail,provider_id) ON chalkmate.deliveries TO chalkmate_app;

GRANT UPDATE(attempts,first_attempt_at,lease_until,last_event_at) ON chalkmate.deliveries TO chalkmate_worker;
CREATE FUNCTION chalkmate.campaign_authorized(c chalkmate.campaigns) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM chalkmate.classrooms r WHERE r.id=c.classroom_id AND NOT r.archived
 AND (EXISTS(SELECT 1 FROM chalkmate.workspaces w WHERE w.id=c.workspace_id AND w.owner_id=c.approved_by)
 OR EXISTS(SELECT 1 FROM chalkmate.classroom_teachers t WHERE t.classroom_id=r.id AND t.user_id=c.approved_by AND t.role='teacher')))
$$;
CREATE FUNCTION chalkmate.apply_delivery_event(event chalkmate.delivery_events) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE next_status text;
BEGIN
 next_status := CASE event.kind WHEN 'email.delivered' THEN 'delivered' WHEN 'email.bounced' THEN 'bounced'
 WHEN 'email.complained' THEN 'bounced' WHEN 'email.failed' THEN 'held' WHEN 'email.sent' THEN 'accepted' ELSE NULL END;
 IF next_status IS NULL THEN RETURN; END IF;
 UPDATE chalkmate.deliveries d SET status=next_status,
 last_event_at=GREATEST(COALESCE(d.last_event_at,event.occurred_at),event.occurred_at), detail='Verified provider event: '||event.kind
 FROM chalkmate.campaigns c WHERE d.campaign_id=c.id AND c.provider='resend' AND d.provider_id=event.provider_id
 AND d.status<>'bounced' AND (event.kind IN ('email.bounced','email.complained')
 OR ((d.last_event_at IS NULL OR event.occurred_at>=d.last_event_at)
 AND (d.status<>'delivered' OR next_status='delivered')));
END $$;
CREATE FUNCTION chalkmate.record_delivery_event(eid text,pid text,etype text,occurred timestamptz) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE stored chalkmate.delivery_events;
BEGIN
 INSERT INTO chalkmate.delivery_events(id,provider_id,kind,occurred_at) VALUES(eid,pid,etype,occurred) ON CONFLICT DO NOTHING;
 SELECT * INTO stored FROM chalkmate.delivery_events WHERE id=eid;
 IF stored.provider_id<>pid OR stored.kind<>etype OR stored.occurred_at<>occurred THEN RETURN false; END IF;
 PERFORM chalkmate.apply_delivery_event(stored);
 RETURN true;
END $$;
CREATE FUNCTION chalkmate.pending_deliveries() RETURNS SETOF uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE ev chalkmate.delivery_events;
BEGIN
 FOR ev IN SELECT e.* FROM chalkmate.delivery_events e JOIN chalkmate.deliveries d ON d.provider_id=e.provider_id
 WHERE d.status IN ('accepted','uncertain','sending') ORDER BY e.occurred_at LIMIT 100 LOOP
 PERFORM chalkmate.apply_delivery_event(ev); END LOOP;
 UPDATE chalkmate.deliveries SET status='uncertain', detail='Worker receipt was lost; reconcile before retrying',lease_until=NULL
 WHERE status='sending' AND lease_until<now();
 UPDATE chalkmate.deliveries d SET status='held',detail='Teaching access changed or campaign canceled'
 FROM chalkmate.campaigns c WHERE d.campaign_id=c.id AND d.status='queued'
 AND (c.canceled OR NOT chalkmate.campaign_authorized(c));
 RETURN QUERY SELECT d.id FROM chalkmate.deliveries d JOIN chalkmate.campaigns c ON c.id=d.campaign_id
 WHERE d.status='queued' AND d.attempts<3 AND c.scheduled_at<=now() AND NOT c.canceled AND chalkmate.campaign_authorized(c)
 ORDER BY c.scheduled_at,d.created_at LIMIT 50;
END $$;
CREATE FUNCTION chalkmate.claim_delivery(target uuid) RETURNS TABLE(delivery_id uuid,actor_id uuid,email text)
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
 WITH claimed AS (UPDATE chalkmate.deliveries d SET status='sending',attempts=d.attempts+1,
 first_attempt_at=COALESCE(d.first_attempt_at,now()),lease_until=now()+interval '2 minutes',detail='Sending approved private message'
 FROM chalkmate.campaigns c WHERE d.id=target AND d.campaign_id=c.id AND d.status='queued' AND d.attempts<3
 AND c.scheduled_at<=now() AND NOT c.canceled AND chalkmate.campaign_authorized(c) RETURNING d.id,c.approved_by)
 SELECT c.id,c.approved_by,u.email::text FROM claimed c JOIN chalkmate.users u ON u.id=c.approved_by
$$;
REVOKE ALL ON FUNCTION chalkmate.campaign_authorized(chalkmate.campaigns),chalkmate.apply_delivery_event(chalkmate.delivery_events),chalkmate.record_delivery_event(text,text,text,timestamptz),chalkmate.pending_deliveries(),chalkmate.claim_delivery(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION chalkmate.record_delivery_event(text,text,text,timestamptz),chalkmate.pending_deliveries(),chalkmate.claim_delivery(uuid) TO chalkmate_worker;
