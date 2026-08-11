import { useNavigate } from "react-router-dom";
import { LogOut, Settings, User, Shield } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Badge } from "@/components/ui/Badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { cn } from "@/utils/cn";

const roleColors: Record<string, string> = {
  admin: "bg-primary-muted text-primary",
  officer: "bg-primary/10 text-primary",
  viewer: "bg-slate-100 text-slate-700",
};

const roleLabels: Record<string, string> = {
  admin: "Admin",
  officer: "Officer",
  viewer: "Viewer",
};

export function ProfileDropdown() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) {
    return null;
  }

  const initials = user.username
    .split(/[\s_-]/)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const handleLogout = async () => {
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch (error) {
      console.error("Logout failed:", error);
      navigate("/login", { replace: true });
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            "flex items-center gap-2 rounded-xl p-1 pr-3 transition-all duration-200",
            "hover:bg-surface focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
            "transition-colors",
          )}
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
            {initials}
          </div>
          <span className="hidden text-sm font-medium text-slate-700 sm:inline">
            {user.username}
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium text-slate-900">{user.username}</p>
            <p className="text-xs text-slate-500">{user.email}</p>
            <Badge className={cn("mt-1 w-fit text-xs", roleColors[user.role])}>
              <Shield className="mr-1 h-3 w-3" />
              {roleLabels[user.role] || user.role}
            </Badge>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => navigate("/settings")}>
          <User className="mr-2 h-4 w-4" />
          Profile
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => navigate("/settings")}>
          <Settings className="mr-2 h-4 w-4" />
          Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={handleLogout}
          className="text-red-600 focus:bg-red-50 focus:text-red-600"
        >
          <LogOut className="mr-2 h-4 w-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
