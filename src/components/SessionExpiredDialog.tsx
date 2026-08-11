import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clock, LogIn } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";

export function SessionExpiredDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const handleSessionExpired = () => {
      setIsOpen(true);
    };

    window.addEventListener("auth:session-expired", handleSessionExpired);
    return () => {
      window.removeEventListener("auth:session-expired", handleSessionExpired);
    };
  }, []);

  const handleLogin = () => {
    setIsOpen(false);
    navigate("/login", { replace: true });
  };

  const handleStay = () => {
    setIsOpen(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
            <Clock className="h-6 w-6 text-amber-600" />
          </div>
          <DialogTitle className="text-center">Session Expired</DialogTitle>
          <DialogDescription className="text-center">
            Your session has expired due to inactivity. Please sign in again to
            continue working.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <Button variant="primary" onClick={handleLogin} className="w-full">
            <LogIn className="mr-2 h-4 w-4" />
            Sign In Again
          </Button>
          <Button variant="ghost" onClick={handleStay} className="w-full">
            Stay on Page
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
