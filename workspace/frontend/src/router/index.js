import { createRouter, createWebHashHistory } from "vue-router";
import { useIrrigation } from "../data/runtime.js";
import { mayLeaveDraft } from "../composables/useDraftGuard.js";
import { notify } from "../composables/feedback.js";
const routes = [
  { path: "/", redirect: "/overview" },
  {
    path: "/login",
    name: "login",
    component: () => import("../views/LoginView.vue"),
    meta: { public: true },
  },
  {
    path: "/overview",
    name: "overview",
    component: () => import("../views/OverviewView.vue"),
    meta: { menu: "overview" },
  },
  {
    path: "/fields",
    name: "fields",
    component: () => import("../views/fields/FieldListView.vue"),
    meta: { menu: "field" },
  },
  {
    path: "/fields/new",
    name: "field-new",
    component: () => import("../views/fields/FieldEditView.vue"),
    meta: { menu: "field", roles: ["ADMIN", "MANAGER"] },
  },
  {
    path: "/fields/:id/edit",
    name: "field-edit",
    component: () => import("../views/fields/FieldEditView.vue"),
    meta: { menu: "field", roles: ["ADMIN", "MANAGER"] },
  },
  {
    path: "/fields/:id",
    name: "field-detail",
    component: () => import("../views/fields/FieldDetailView.vue"),
    meta: { menu: "field" },
  },
  {
    path: "/network",
    name: "network",
    component: () => import("../views/network/NetworkView.vue"),
    meta: { menu: "network" },
  },
  {
    path: "/devices",
    name: "devices",
    component: () => import("../views/devices/DeviceListView.vue"),
    meta: { menu: "device" },
  },
  {
    path: "/devices/:id",
    name: "device-detail",
    component: () => import("../views/devices/DeviceDetailView.vue"),
    meta: { menu: "device" },
  },
  {
    path: "/monitor",
    name: "monitor",
    component: () => import("../views/monitor/MonitorView.vue"),
    meta: { menu: "monitor" },
  },
  {
    path: "/strategies",
    name: "strategies",
    component: () => import("../views/strategies/StrategyListView.vue"),
    meta: { menu: "strategy" },
  },
  {
    path: "/strategies/new",
    name: "strategy-new",
    component: () => import("../views/strategies/StrategyEditView.vue"),
    meta: { menu: "strategy", roles: ["ADMIN", "MANAGER"] },
  },
  {
    path: "/strategies/:id/edit",
    name: "strategy-edit",
    component: () => import("../views/strategies/StrategyEditView.vue"),
    meta: { menu: "strategy", roles: ["ADMIN", "MANAGER"] },
  },
  {
    path: "/plans",
    name: "plans",
    component: () => import("../views/plans/PlanListView.vue"),
    meta: { menu: "plan" },
  },
  {
    path: "/plans/new",
    name: "plan-new",
    component: () => import("../views/plans/PlanEditView.vue"),
    meta: { menu: "plan", roles: ["ADMIN", "MANAGER"] },
  },
  {
    path: "/plans/:id/edit",
    name: "plan-edit",
    component: () => import("../views/plans/PlanEditView.vue"),
    meta: { menu: "plan" },
  },
  {
    path: "/runs",
    name: "runs",
    component: () => import("../views/runs/RunListView.vue"),
    meta: { menu: "run" },
  },
  {
    path: "/runs/:id",
    name: "run-detail",
    component: () => import("../views/runs/RunDetailView.vue"),
    meta: { menu: "run" },
  },
  {
    path: "/alarms",
    name: "alarms",
    component: () => import("../views/alarms/AlarmListView.vue"),
    meta: { menu: "alarm" },
  },
  {
    path: "/maintenance",
    name: "maintenance",
    component: () => import("../views/maintenance/MaintenanceView.vue"),
    meta: { menu: "maintenance" },
  },
  {
    path: "/water",
    name: "water",
    component: () => import("../views/water/WaterReportView.vue"),
    meta: { menu: "water" },
  },
  {
    path: "/settings",
    name: "settings",
    component: () => import("../views/settings/SettingsView.vue"),
    meta: { menu: "settings", roles: ["ADMIN"] },
  },
  {
    path: "/audit",
    name: "audit",
    component: () => import("../views/audit/AuditView.vue"),
    meta: { menu: "audit", roles: ["ADMIN", "MANAGER"] },
  },
  { path: "/:pathMatch(.*)*", redirect: "/overview" },
];
const router = createRouter({ history: createWebHashHistory(), routes });
router.beforeEach(async (to, from) => {
  const runtime = useIrrigation();
  // An expired or revoked session cannot keep a private screen open through
  // a dirty-draft confirmation. Authentication takes precedence over leaving.
  if (!to.meta.public && !runtime.state.user)
    return { name: "login", query: { return: to.fullPath } };
  if (to.name === "login" && !runtime.state.user) return true;
  if (from.matched.length && !(await mayLeaveDraft())) return false;
  if (to.name === "login" && runtime.state.user) return "/overview";
  if (to.meta.roles && !to.meta.roles.includes(runtime.state.user?.role)) {
    notify("无权访问该页面", "danger");
    return "/overview";
  }
  return true;
});
export default router;
