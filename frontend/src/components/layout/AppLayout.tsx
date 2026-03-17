import { Outlet } from "react-router-dom";
import { useState, useCallback } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleMenuToggle = useCallback(() => {
    setSidebarOpen((prev) => !prev);
  }, []);

  const handleCloseMobileMenu = useCallback(() => {
    setSidebarOpen(false);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Overlay backdrop when sidebar is open on mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={handleCloseMobileMenu}
        />
      )}

      <Sidebar open={sidebarOpen} onClose={handleCloseMobileMenu} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar onMenuToggle={handleMenuToggle} />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
