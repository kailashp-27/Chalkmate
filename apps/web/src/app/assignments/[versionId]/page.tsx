import { WorkspaceApp } from "../../../components/workspace-app";
export default async function Page({
  params,
}: {
  params: Promise<{ versionId: string }>;
}) {
  const { versionId } = await params;
  return <WorkspaceApp assignmentVersion={versionId} />;
}
