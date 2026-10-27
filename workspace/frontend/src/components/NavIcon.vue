<script setup>
import { computed } from "vue";
import {
  IconLayoutGrid,
  IconBorderAll,
  IconHierarchy,
  IconAccessPoint,
  IconActivityHeartbeat,
  IconAdjustmentsHorizontal,
  IconCalendar,
  IconPlayerPlay,
  IconBell,
  IconTool,
  IconChartBar,
  IconSettings,
  IconFileSearch,
  IconChevronDown,
  IconArrowLeft,
  IconSearch,
  IconRefresh,
  IconPlus,
  IconX,
  IconCheck,
  IconLeaf,
  IconDownload,
  IconWifi,
  IconUser,
  IconDroplet,
  IconClock,
  IconAlertTriangle,
  IconChevronLeft,
  IconChevronRight,
  IconShieldCheck,
  IconDeviceDesktop,
  IconSend,
  IconFileDescription,
  IconPlayerPause,
  IconPlayerStop,
} from "@tabler/icons-vue";
const props = defineProps({
  name: String,
  size: { type: [Number, String], default: 24 },
});
const icon = computed(
  () =>
    ({
      overview: IconLayoutGrid,
      field: IconBorderAll,
      network: IconHierarchy,
      device: IconAccessPoint,
      monitor: IconActivityHeartbeat,
      strategy: IconAdjustmentsHorizontal,
      plan: IconCalendar,
      run: IconPlayerPlay,
      alarm: IconBell,
      maintenance: IconTool,
      water: IconChartBar,
      settings: IconSettings,
      audit: IconFileSearch,
      chevron: IconChevronDown,
      "arrow-left": IconArrowLeft,
      search: IconSearch,
      refresh: IconRefresh,
      add: IconPlus,
      close: IconX,
      check: IconCheck,
      calendar: IconCalendar,
      leaf: IconLeaf,
      download: IconDownload,
      wifi: IconWifi,
      user: IconUser,
      droplet: IconDroplet,
      clock: IconClock,
      warning: IconAlertTriangle,
      left: IconChevronLeft,
      right: IconChevronRight,
      shield: IconShieldCheck,
      desktop: IconDeviceDesktop,
      send: IconSend,
      file: IconFileDescription,
      pause: IconPlayerPause,
      stop: IconPlayerStop,
    })[props.name] || IconBorderAll,
);
</script>
<template>
  <component
    :is="icon"
    :size="size"
    :stroke="1.65"
    aria-hidden="true"
    class="nav-icon"
  />
</template>
