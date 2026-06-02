import { RepoView } from "@/components/repo/repo-view";

export default function RepoPage({ params }: { params: { id: string } }) {
  return <RepoView repoId={params.id} />;
}
