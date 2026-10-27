<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import * as echarts from "echarts";
const props = defineProps({
  options: { type: Object, default: () => ({}) },
  height: { type: [Number, String], default: 260 },
});
const emit = defineEmits(["chart-click"]);
const host = ref();
let chart, observer;
onMounted(() => {
  chart = echarts.init(host.value, null, { renderer: "svg" });
  chart.setOption({ ...props.options, animation: false });
  chart.on("click", (event) => emit("chart-click", event));
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(host.value);
});
watch(
  () => props.options,
  (options) => chart?.setOption({ ...options, animation: false }, true),
  { deep: true },
);
onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>
<template>
  <div
    ref="host"
    class="chart-panel"
    :style="{ height: typeof height === 'number' ? height + 'px' : height }"
    role="img"
    aria-label="业务数据图表"
  />
</template>
