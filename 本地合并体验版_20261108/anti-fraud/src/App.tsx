import PageBoundary from "./components/PageBoundary";
import { useState, useEffect, lazy, Suspense } from "react";
import Layout from "./components/Layout";
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Assistant = lazy(() => import("./pages/Assistant"));
const Alerts = lazy(() => import("./pages/Alerts"));
const Settings = lazy(() => import("./pages/Settings"));
const Reports = lazy(() => import("./pages/Reports"));
const Knowledge = lazy(() => import("./pages/Knowledge"));
import Login from "./pages/Login";
const Evaluation = lazy(() => import("./pages/Evaluation"));
import { Page } from "./types";
import { useApp } from "./context/AppContext";
const pages: Page[] = [
  "dashboard",
  "assistant",
  "alerts",
  "reports",
  "settings",
  "knowledge",
  "evaluation",
];
function fromHash(): Page {
  const p = location.hash.slice(1) as Page;
  return pages.includes(p) ? p : "dashboard";
}
export default function App() {
  const { loggedIn } = useApp();
  const [page, setPage] = useState<Page>(fromHash);
  const [loginRoute, setLoginRoute] = useState(location.hash === "#login");
  const [mode, setMode] = useState("text");
  const [reportOpen, setReportOpen] = useState(false);
  useEffect(() => {
    const onHash = () => { setPage(fromHash()); setLoginRoute(location.hash === "#login"); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  function navigate(p: Page) {
    setLoginRoute(false);
    setPage(p);
    location.hash = p;
    if (p !== "reports") setReportOpen(false);
    window.scrollTo(0, 0);
  }
  // Explicit workspace links are accessible in this backend-free demo.
  if (loginRoute || (!loggedIn && !pages.includes(location.hash.slice(1) as Page)))
    return (
      <Login
        onLogin={(register) => navigate(register ? "settings" : "dashboard")}
      />
    );
  return (
    <Layout page={page} navigate={navigate}>
      <PageBoundary page={page}><Suspense fallback={<section className="panel" role="status" aria-live="polite">正在加载页面，请稍候…</section>}>
      {page === "dashboard" && (
        <Dashboard
          navigate={navigate}
          detect={(m) => {
            setMode(m);
            navigate("assistant");
          }}
        />
      )}
      {page === "assistant" && (
        <Assistant
          mode={mode}
          onReport={() => {
            setReportOpen(true);
            navigate("reports");
          }}
        />
      )}
      {page === "alerts" && <Alerts />}
      {page === "settings" && <Settings />}
      {page === "reports" && <Reports autoOpen={reportOpen} />}{" "}
      {page === "knowledge" && <Knowledge />}
      {page === "evaluation" && <Evaluation />}
      </Suspense></PageBoundary>
    </Layout>
  );
}
