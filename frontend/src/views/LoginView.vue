<script setup>
import { ref, computed, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useIrrigation } from "../data/runtime.js";
import BrandMark from "../components/BrandMark.vue";
import { confirmAction, notify } from "../composables/feedback.js";
const runtime = useIrrigation(),
  router = useRouter(),
  route = useRoute();
const account = ref(""),
  password = ref(""),
  busy = ref(false),
  error = ref("");
const backedUp = ref(false);
const storageError = computed(() => runtime.state.error);
const visibleError = computed(
  () => error.value || storageError.value?.message ||
    (typeof storageError.value === "string" ? storageError.value : ""),
);
const canRecover = computed(
  () => runtime.state.channel === "preview" &&
    ["STORAGE_CORRUPT", "STORAGE_SCHEMA"].includes(storageError.value?.code),
);
watch(storageError, () => { backedUp.value = false; });
const farmName = computed(
  () =>
    runtime.state.publicFarm?.name ||
    runtime.state.entities.Farm?.[0]?.name ||
    "",
);
async function downloadOriginal() {
  busy.value = true;
  error.value = "";
  try {
    const backup = await runtime.exportCorruptSnapshot();
    const url = URL.createObjectURL(new Blob([backup.content], { type: "application/json;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = backup.fileName;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    backedUp.value = true;
    notify("原始数据备份已生成");
  } catch (failure) {
    error.value = failure.message;
  } finally {
    busy.value = false;
  }
}
async function restoreInitial() {
  if (!canRecover.value || !backedUp.value || busy.value) return;
  if (!await confirmAction({
    title: "恢复本机数据",
    message: "请先保存刚下载的原始数据备份。恢复后将用初始业务数据替换当前损坏快照，是否继续？",
    confirmText: "确认恢复初始数据",
    tone: "danger",
  })) return;
  busy.value = true;
  error.value = "";
  try {
    await runtime.recoverInitialSnapshot({ confirmed: true });
    password.value = "";
    notify("本机数据已恢复，请重新登录");
  } catch (failure) {
    error.value = failure.message;
  } finally {
    busy.value = false;
  }
}
async function submit() {
  error.value = "";
  if (!account.value.trim()) {
    error.value = "请输入账号";
    document.getElementById("login-account")?.focus();
    return;
  }
  if (!password.value) {
    error.value = "请输入密码";
    document.getElementById("login-password")?.focus();
    return;
  }
  busy.value = true;
  try {
    await runtime.login(account.value.trim(), password.value);
    password.value = "";
    const target = String(route.query.return || "/overview");
    await router.replace(
      target.startsWith("/") &&
        !target.startsWith("//") &&
        !target.startsWith("/login")
        ? target
        : "/overview",
    );
  } catch (failure) {
    error.value = failure.message || "账号或密码错误，或账号已停用";
    password.value = "";
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <main class="login-page">
    <form class="login-card" @submit.prevent="submit">
      <div class="login-brand">
        <BrandMark />
        <h1>智能节水灌溉管控系统</h1>
      </div>
      <label for="login-account">账号</label
      ><input
        id="login-account"
        v-model="account"
        autocomplete="username"
        :disabled="busy"
        aria-required="true"
      /><label for="login-password" class="password-label">密码</label
      ><input
        id="login-password"
        v-model="password"
        type="password"
        autocomplete="current-password"
        :disabled="busy"
        aria-required="true"
      />
      <p v-if="visibleError" class="login-error" role="alert">{{ visibleError }}</p>
      <div v-if="canRecover" class="login-recovery">
        <button type="button" class="btn btn-sm" :disabled="busy" @click="downloadOriginal">下载原始备份</button>
        <button type="button" class="btn btn-sm btn-danger" :disabled="busy || !backedUp" title="先下载并保存原始备份后恢复" @click="restoreInitial">恢复初始数据</button>
      </div>
      <button
        type="submit"
        class="btn btn-primary login-submit"
        :disabled="busy"
      >
        {{ busy ? "登录中…" : "登录" }}
      </button>
      <div
        class="login-connection"
        :title="
          runtime.state.channel === 'http'
            ? '服务端连接'
            : '本机预览存储，不代表现场设备连接'
        "
      >
        <span class="status-dot" :class="{ danger: runtime.state.error }" />{{
          runtime.state.error ? "连接异常" : "连接正常"
        }}
      </div>
      <div class="login-farm">{{ farmName }}</div>
    </form>
  </main>
</template>
