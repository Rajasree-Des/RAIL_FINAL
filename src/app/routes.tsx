import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppRootLayout } from "@/layouts/AppRootLayout";
import { AppShell } from "@/layouts/AppShell";
import { ProtectedLayout } from "@/layouts/ProtectedLayout";
import { WorkflowLayout } from "@/layouts/WorkflowLayout";
import { AdminLayout } from "@/layouts/AdminLayout";
import { RequireAdmin } from "@/components/RequireRole";
import { LoginPage } from "@/features/auth/LoginPage";
import { HomePage } from "@/features/home";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { AutomationPage } from "@/features/automation";
import { GeneratedReportsPage } from "@/features/reports";
import { DailySummaryPage } from "@/features/daily-summary";
import {
  MergingPage,
  DivisionPage,
  TrainNoPage,
  TypesPage,
  SCRTrainPage,
  SCRStationPage,
  SummaryPage,
  Report9Page,
  ComprehensivePage,
  Report14Page,
  Report18Page,
  BottomReportPage,
} from "@/features/workflows";
import { TemplateListPage, TemplateEditorPage } from "@/features/admin/templates";
import { PromptListPage, PromptEditorPage } from "@/features/admin/prompts";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { LogsPage } from "@/features/logs";
import { NotFoundPage } from "@/features/errors/NotFoundPage";

export const router = createBrowserRouter([
  {
    element: <AppRootLayout />,
    children: [
      {
        path: "/login",
        element: <LoginPage />,
      },
      {
        path: "/",
        element: <ProtectedLayout />,
        children: [
          {
            element: <AppShell />,
            children: [
              {
                index: true,
                element: <Navigate to="/home" replace />,
              },
              {
                path: "home",
                element: <HomePage />,
              },
              {
                path: "dashboard",
                element: <DashboardPage />,
              },
              {
                path: "reports",
                element: <GeneratedReportsPage />,
              },
              {
                path: "daily-summary",
                element: <DailySummaryPage />,
              },
              {
                path: "automation",
                element: (
                  <RequireAdmin>
                    <AutomationPage />
                  </RequireAdmin>
                ),
              },
              {
                element: <WorkflowLayout />,
                children: [
                  {
                    path: "workflows/merging",
                    element: <MergingPage />,
                  },
                  {
                    path: "workflows/division",
                    element: <DivisionPage />,
                  },
                  {
                    path: "workflows/train-no",
                    element: <TrainNoPage />,
                  },
                  {
                    path: "workflows/types",
                    element: <TypesPage />,
                  },
                  {
                    path: "workflows/scr-train",
                    element: <SCRTrainPage />,
                  },
                  {
                    path: "workflows/scr-station",
                    element: <SCRStationPage />,
                  },
                  {
                    path: "workflows/report9",
                    element: <Report9Page />,
                  },
                  {
                    path: "workflows/comprehensive-10-13",
                    element: <ComprehensivePage />,
                  },
                  {
                    path: "workflows/report14",
                    element: <Report14Page />,
                  },
                  {
                    path: "workflows/report18",
                    element: <Report18Page />,
                  },
                  {
                    path: "workflows/bottom-report",
                    element: <BottomReportPage />,
                  },
                  {
                    path: "workflows/summary",
                    element: <SummaryPage />,
                  },
                ],
              },
              {
                element: <AdminLayout />,
                children: [
                  {
                    path: "admin/templates",
                    element: <TemplateListPage />,
                  },
                  {
                    path: "admin/templates/:id/edit",
                    element: <TemplateEditorPage />,
                  },
                  {
                    path: "admin/templates/new",
                    element: <TemplateEditorPage />,
                  },
                  {
                    path: "admin/prompts",
                    element: <PromptListPage />,
                  },
                  {
                    path: "admin/prompts/new",
                    element: <PromptEditorPage />,
                  },
                  {
                    path: "admin/prompts/:id/edit",
                    element: <PromptEditorPage />,
                  },
                  {
                    path: "admin/automation",
                    element: <Navigate to="/automation" replace />,
                  },
                  {
                    path: "settings",
                    element: <SettingsPage />,
                  },
                  {
                    path: "logs",
                    element: <LogsPage />,
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
]);
