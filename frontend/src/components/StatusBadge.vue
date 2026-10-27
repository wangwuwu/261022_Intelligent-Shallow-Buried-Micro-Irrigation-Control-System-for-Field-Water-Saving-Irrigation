<script setup>
import { computed } from "vue";
const props = defineProps({
  status: [String, Boolean],
  text: String,
  tone: String,
});
const words = {
  ENABLED: "启用",
  DISABLED: "停用",
  ONLINE: "在线",
  OFFLINE: "离线",
  VERIFIED: "已核验",
  UNVERIFIED: "未核验",
  VALID: "有效",
  MISSING: "缺失",
  OUT_OF_RANGE: "超量程",
  CALIBRATING: "校准中",
  DRAFT: "草稿",
  PUBLISHED: "已发布",
  EXECUTING: "执行中",
  COMPLETED: "已完成",
  CANCELLED: "已取消",
  QUEUED: "待执行",
  STARTING: "启动中",
  RUNNING: "运行中",
  PAUSING: "暂停中",
  PAUSED: "已暂停",
  RESUMING: "恢复中",
  ADVANCING: "切换中",
  STOPPING: "停止中",
  STOPPED: "已停止",
  FAILED: "失败",
  UNKNOWN: "未知",
  OPEN: "待知悉",
  ACKNOWLEDGED: "已知悉",
  ASSIGNED: "已派工",
  IN_PROGRESS: "处理中",
  PENDING_ACCEPTANCE: "待验收",
  RETURNED: "已退回",
  ACTIVE: "未恢复",
  RECOVERED: "已恢复",
  FINAL: "已结算",
  PROVISIONAL: "暂计",
  INVALID: "无效",
  READY: "可下载",
  PROCESSING: "生成中",
  EXPIRED: "已过期",
  HIGH: "高",
  CRITICAL: "紧急",
  MEDIUM: "中",
  LOW: "低",
  ACCEPTED: "已受理",
  SUCCESS: "成功",
  MEASURED: "实测",
  ALLOCATED: "分摊",
  ESTIMATED: "估算",
  CONFIRMED: "动作确认",
  SENT: "已发送",
  PENDING: "待发送",
  TIMED_OUT: "已超时",
  REJECTED: "已拒绝",
  WAITING: "待执行",
  FINISHING: "结束中",
  SKIPPED: "已跳过",
};
const tone = computed(
  () =>
    props.tone ||
    ([
      "DISABLED",
      "OFFLINE",
      "FAILED",
      "INVALID",
      "ACTIVE",
      "CRITICAL",
      "HIGH",
      "REJECTED",
      "TIMED_OUT",
    ].includes(props.status)
      ? "danger"
      : [
            "DRAFT",
            "QUEUED",
            "UNVERIFIED",
            "RETURNED",
            "PENDING_ACCEPTANCE",
            "PROVISIONAL",
            "ACCEPTED",
            "UNKNOWN",
            "PENDING",
            "PROCESSING",
          ].includes(props.status)
        ? "warning"
        : [
              "PUBLISHED",
              "ASSIGNED",
              "IN_PROGRESS",
              "SENT",
              "ACKNOWLEDGED",
            ].includes(props.status)
          ? "info"
          : ["CLOSED", "STOPPED", "CANCELLED", "EXPIRED", "SKIPPED"].includes(
                props.status,
              )
            ? "neutral"
            : "success"),
);
</script>
<template>
  <span class="status-badge" :class="`tone-${tone}`">{{
    text || words[status] || status || "—"
  }}</span>
</template>
