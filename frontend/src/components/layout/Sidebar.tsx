import { NavLink } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import {
  LayoutDashboard,
  FilePlus,
  Users,
  Settings,
  Building2,
  ClipboardList,
} from "lucide-react";

const navItems = {
  student: [
    { to: "/", label: "Dashboard", icon: LayoutDashboard },
    { to: "/cases/new", label: "Submit Case", icon: FilePlus },
    { to: "/submissions", label: "My Submissions", icon: ClipboardList },
  ],
  supervisor: [
    { to: "/", label: "Dashboard", icon: LayoutDashboard },
    { to: "/submissions", label: "Submissions", icon: ClipboardList },
  ],
  admin: [
    { to: "/", label: "Dashboard", icon: LayoutDashboard },
    { to: "/submissions", label: "Submissions", icon: ClipboardList },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/departments", label: "Departments", icon: Building2 },
    { to: "/admin/settings", label: "Settings", icon: Settings },
  ],
};

export default function Sidebar() {
  const { user } = useAuthStore();
  if (!user) return null;

  const items = navItems[user.role] || [];

  return (
    <aside className="flex h-full w-60 flex-col border-r bg-card">
      <div className="flex h-14 items-center border-b px-4">
        <span className="text-lg font-semibold">Clinic Tracker</span>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              }`
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
