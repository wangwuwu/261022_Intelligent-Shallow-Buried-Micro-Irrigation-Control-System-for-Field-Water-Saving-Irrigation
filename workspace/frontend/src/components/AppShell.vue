<script setup>
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useIrrigation } from "../data/runtime.js";
import { useClock, formatShanghaiDate } from "../composables/useClock.js";
import { confirmAction, notify } from "../composables/feedback.js";
import NavIcon from "./NavIcon.vue";
import BrandMark from "./BrandMark.vue";
import BaseModal from "./BaseModal.vue";
const runtime = useIrrigation(),
  route = useRoute(),
  router = useRouter();
const { displayNow } = useClock();
const folded = ref({}),
  accountOpen = ref(false),
  navigationOpen = ref(false);
const roles = {
  ADMIN: "系统管理员",
  MANAGER: "灌溉管理人员",
  OPERATOR: "灌溉操作人员",
  TECHNICIAN: "巡检维护人员",
  VIEWER: "只读查看人员",
};
const farmName = computed(
  () =>
    runtime.state.publicFarm?.name ||
    runtime.state.entities.Farm?.[0]?.name ||
    "",
);
const groups = [
  { name: "田间总览", items: [["overview", "灌溉总览", "/overview"]] },
  {
    name: "田间资源",
    items: [
      ["field", "田块与种植", "/fields"],
      ["network", "管网与轮灌分区", "/network"],
    ],
  },
  {
    name: "感知设备",
    items: [
      ["device", "设备接入台账", "/devices"],
      ["monitor", "墒情与环境监测", "/monitor"],
    ],
  },
  {
    name: "灌溉作业",
    items: [
      ["strategy", "灌溉策略", "/strategies"],
      ["plan", "灌溉计划", "/plans"],
      ["run", "灌溉运行", "/runs"],
    ],
  },
  {
    name: "异常维护",
    items: [
      ["alarm", "运行告警", "/alarms"],
      ["maintenance", "巡检与维护", "/maintenance"],
    ],
  },
  { name: "统计分析", items: [["water", "用水与节水分析", "/water"]] },
  {
    name: "系统管理",
    items: [
      ["settings", "账号与系统配置", "/settings", ["ADMIN"]],
      ["audit", "操作与指令审计", "/audit", ["ADMIN", "MANAGER"]],
    ],
  },
];
const visibleGroups = computed(() =>
  groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !item[3] || item[3].includes(runtime.state.user?.role),
      ),
    }))
    .filter((group) => group.items.length),
);
async function logout() {
  accountOpen.value = false;
  if (
    !(await confirmAction({
      title: "退出当前账号",
      message: "确认退出当前账号？",
      confirmText: "退出登录",
    }))
  )
    return;
  try {
    await runtime.logout();
    await router.replace("/login");
  } catch (error) {
    notify(error.message, "danger");
  }
}
async function navigate(path) {
  navigationOpen.value = false;
  accountOpen.value = false;
  await router.push(path);
}
</script>
<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-brand">
        <BrandMark /><strong>智能节水灌溉管控系统</strong>
      </div>
      <span class="farm-identity">{{ farmName }}</span>
      <div class="topbar-right">
        <time>{{ formatShanghaiDate(displayNow).replaceAll("-", ".") }}</time
        ><button
          type="button"
          class="icon-button settings-button"
          aria-label="账号与系统配置"
          :disabled="runtime.state.user?.role !== 'ADMIN'"
          @click="navigate('/settings')"
        >
          <NavIcon name="settings" :size="28" />
        </button>
        <div class="account-wrap">
          <button
            type="button"
            class="account-button"
            :aria-expanded="accountOpen"
            @click="accountOpen = !accountOpen"
          >
            {{ roles[runtime.state.user?.role] || "" }}
          </button>
          <div v-if="accountOpen" class="account-menu">
            <button type="button" @click="logout">退出登录</button>
          </div>
        </div>
      </div>
      <button
        type="button"
        class="mobile-menu icon-button"
        aria-label="打开业务导航"
        @click="navigationOpen = true"
      >
        <NavIcon name="overview" />
      </button>
    </header>
    <aside class="sidebar" aria-label="业务导航">
      <nav>
        <section
          v-for="group in visibleGroups"
          :key="group.name"
          class="navigation-group"
        >
          <button
            type="button"
            class="group-label"
            :aria-expanded="!folded[group.name]"
            @click="folded[group.name] = !folded[group.name]"
          >
            {{ group.name
            }}<NavIcon
              name="chevron"
              :size="19"
              :class="{ folded: folded[group.name] }"
            />
          </button>
          <div v-show="!folded[group.name]">
            <button
              v-for="item in group.items"
              :key="item[0]"
              type="button"
              class="navigation-item"
              :class="{ active: route.meta.menu === item[0] }"
              :aria-current="route.meta.menu === item[0] ? 'page' : undefined"
              @click="navigate(item[2])"
            >
              <NavIcon :name="item[0]" :size="26" /><span>{{ item[1] }}</span>
            </button>
          </div>
        </section>
      </nav>
      <div
        class="connection-status"
        :title="
          runtime.state.channel === 'http'
            ? '服务端数据连接'
            : '本机预览存储可用；不表示现场设备已连接'
        "
      >
        <span class="status-dot" :class="{ danger: runtime.state.error }" />{{
          runtime.state.error ? "连接异常" : "连接正常"
        }}
      </div>
    </aside>
    <main class="main-content" id="main-content"><slot /></main>
    <BaseModal v-model="navigationOpen" title="业务导航" :width="360"
      ><nav class="mobile-navigation">
        <template v-for="group in visibleGroups" :key="group.name"
          ><h3>{{ group.name }}</h3>
          <button
            v-for="item in group.items"
            :key="item[0]"
            type="button"
            class="navigation-item"
            :class="{ active: route.meta.menu === item[0] }"
            @click="navigate(item[2])"
          >
            <NavIcon :name="item[0]" /><span>{{ item[1] }}</span>
          </button></template
        >
      </nav></BaseModal
    >
  </div>
</template>
