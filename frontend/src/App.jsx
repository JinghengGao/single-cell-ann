import { useState } from "react";

import { WorkspaceShell } from "./components/WorkspaceShell";
import { useWorkspace } from "./hooks/useWorkspace";
import { AnalysisPage } from "./pages/AnalysisPage";
import { DatasetPage } from "./pages/DatasetPage";
import { IndexPage } from "./pages/IndexPage";
import { LoginPage } from "./pages/LoginPage";

export default function App() {
  const workspace = useWorkspace();
  const [view, setView] = useState("analysis");
  const [guestMode, setGuestMode] = useState(false);

  if (!workspace.auth.authenticated && !guestMode) {
    return <LoginPage workspace={workspace} onBrowse={() => setGuestMode(true)} />;
  }

  return (
    <WorkspaceShell
      view={view}
      onViewChange={setView}
      guestMode={guestMode}
      onExitGuest={() => setGuestMode(false)}
      workspace={workspace}
    >
      {view === "analysis" ? <AnalysisPage workspace={workspace} guestMode={guestMode} /> : null}
      {view === "datasets" ? <DatasetPage workspace={workspace} guestMode={guestMode} /> : null}
      {view === "indexes" ? <IndexPage workspace={workspace} guestMode={guestMode} /> : null}
    </WorkspaceShell>
  );
}
