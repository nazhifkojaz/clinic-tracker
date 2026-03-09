import { Routes, Route } from "react-router-dom";
import NotFound from "@/pages/NotFound";

function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <div className="flex min-h-screen items-center justify-center bg-background">
            <div className="text-center">
              <h1 className="text-4xl font-bold text-foreground">
                Smart Clinic Tracker
              </h1>
              <p className="mt-2 text-muted-foreground">
                Phase 0 — scaffolding complete
              </p>
            </div>
          </div>
        }
      />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

export default App;
