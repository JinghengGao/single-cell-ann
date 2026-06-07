import { useState } from "react";

import { WorkspaceShell } from "./components/WorkspaceShell";
import { useWorkspace } from "./hooks/useWorkspace";
import { AnalysisPage } from "./pages/AnalysisPage";
import { DatasetPage } from "./pages/DatasetPage";
import { IndexPage } from "./pages/IndexPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";

export default function App() {
  const workspace = useWorkspace();
  const [view, setView] = useState("analysis");
  const [guestMode, setGuestMode] = useState(false);
  const [entryView, setEntryView] = useState("landing");

  if (!workspace.auth.authenticated && !guestMode) {
    if (entryView === "login") {
      return (
        <LoginPage
          workspace={workspace}
          onBack={() => setEntryView("landing")}
          onBrowse={() => setGuestMode(true)}
        />
      );
    }
    return (
      <LandingPage
        workspace={workspace}
        onLogin={() => setEntryView("login")}
        onBrowse={() => setGuestMode(true)}
      />
    );
  }

  return (
    <WorkspaceShell
      view={view}
      onViewChange={setView}
      guestMode={guestMode}
      onExitGuest={() => {
        setGuestMode(false);
        setEntryView("landing");
      }}
      onLogout={async () => {
        await workspace.handleLogout();
        setEntryView("landing");
      }}
      workspace={workspace}
    >
      {view === "analysis" ? <AnalysisPage workspace={workspace} guestMode={guestMode} /> : null}
      {view === "datasets" ? <DatasetPage workspace={workspace} guestMode={guestMode} /> : null}
      {view === "indexes" ? <IndexPage workspace={workspace} guestMode={guestMode} /> : null}
    </WorkspaceShell>
  );
}
