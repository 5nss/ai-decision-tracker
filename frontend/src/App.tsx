import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Link, BrowserRouter, Route, Routes } from "react-router";

import { Layout } from "./components/Layout";
import { Card, EmptyState } from "./components/ui";
import { ApiError } from "./lib/api";
import { PreferencesProvider } from "./lib/preferences";
import { Dashboard } from "./pages/Dashboard";
import { DecisionDetailPage } from "./pages/DecisionDetail";
import { Decisions } from "./pages/Decisions";
import { Evals } from "./pages/Evals";
import { NewDecision } from "./pages/NewDecision";
import { TracesPage } from "./pages/Traces";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      // Don't retry client errors (404, 422); do retry a flaky network once.
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 1,
    },
  },
});

function NotFound() {
  return (
    <Card>
      <EmptyState
        title="Page not found"
        action={
          <Link to="/" className="text-sm font-medium text-accent-ink hover:underline">
            Go to the dashboard
          </Link>
        }
      />
    </Card>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <PreferencesProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="decisions" element={<Decisions />} />
              <Route path="decisions/:id" element={<DecisionDetailPage />} />
              <Route path="new" element={<NewDecision />} />
              <Route path="evals" element={<Evals />} />
              <Route path="traces" element={<TracesPage />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </PreferencesProvider>
    </QueryClientProvider>
  );
}
