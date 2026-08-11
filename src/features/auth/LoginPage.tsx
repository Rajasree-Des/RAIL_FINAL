import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { Eye, EyeOff, Lock, User } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ApiError } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { RailMadadLogo } from "@/components/branding/RailMadadLogo";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Spinner } from "@/components/ui/Spinner";

const loginSchema = z.object({
  username: z.string().min(3, "Username must be at least 3 characters"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  remember_me: z.boolean().default(false),
});

type LoginFormData = z.infer<typeof loginSchema>;

interface LocationState {
  from?: { pathname: string };
}

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      return "Invalid username or password. Please try again.";
    }
    if (error.status >= 500) {
      return "Server error. Please try again in a moment.";
    }
    return error.message || "Sign in failed. Please try again.";
  }
  if (error instanceof TypeError || (error instanceof DOMException && error.name === "AbortError")) {
    return "Cannot reach the API server. Ensure it is running on http://127.0.0.1:8000.";
  }
  return "Cannot reach the API server. Ensure it is running on http://127.0.0.1:8000.";
}

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as LocationState)?.from?.pathname || "/home";

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { remember_me: false },
  });

  const onSubmit = async (data: LoginFormData) => {
    setError(null);
    try {
      await login({
        username: data.username,
        password: data.password,
        remember_me: data.remember_me,
      });
      void navigate(from, { replace: true });
    } catch (err) {
      setError(loginErrorMessage(err));
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4 py-16">
      <div className="w-full max-w-[400px] space-y-8">
        <div className="flex flex-col items-center text-center">
          <RailMadadLogo size="lg" />
          <h1 className="mt-6 text-2xl font-semibold tracking-tight text-slate-900">
            RailMadad Report Center
          </h1>
          <p className="mt-2 text-sm text-slate-500">Sign in to your officer account</p>
        </div>

        <Card className="hover:shadow-card">
          <CardHeader className="pb-2">
            <CardTitle>Welcome back</CardTitle>
            <CardDescription>Enter your credentials to continue</CardDescription>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {error && <Alert variant="error">{error}</Alert>}

              <div className="space-y-1.5">
                <Label htmlFor="username">Username</Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input id="username" className="h-11 rounded-lg pl-10" placeholder="Enter username" {...register("username")} />
                </div>
                {errors.username && <p className="text-xs text-red-600">{errors.username.message}</p>}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    className="h-11 rounded-lg pl-10 pr-10"
                    placeholder="Enter password"
                    {...register("password")}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-600"
                    onClick={() => setShowPassword((s) => !s)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
              </div>

              <div className="flex items-center justify-between text-sm">
                <label className="flex items-center gap-2 text-slate-600">
                  <input type="checkbox" className="rounded border-slate-300 text-primary" {...register("remember_me")} />
                  Remember me
                </label>
                <Link to="/login" className="text-primary transition-colors hover:text-primary-hover">
                  Forgot password?
                </Link>
              </div>

              <Button type="submit" className="h-11 w-full" disabled={isSubmitting}>
                {isSubmitting ? <Spinner size="sm" /> : "Sign In"}
              </Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
