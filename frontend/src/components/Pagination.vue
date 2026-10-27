<script setup>
import { computed, watch } from "vue";
import NavIcon from "./NavIcon.vue";
const props = defineProps({
  modelValue: { type: Number, default: 1 },
  total: { type: Number, default: 0 },
  pageSize: { type: Number, default: 15 },
  compact: Boolean,
  showTotalPages: Boolean,
  textButtons: Boolean,
});
const emit = defineEmits(["update:modelValue"]);
const pages = computed(() =>
  Math.max(1, Math.ceil(props.total / props.pageSize)),
);
const visible = computed(() => {
  if (pages.value <= 7)
    return Array.from({ length: pages.value }, (_, i) => i + 1);
  const result = [1];
  for (
    let n = Math.max(2, props.modelValue - 1);
    n <= Math.min(pages.value - 1, props.modelValue + 1);
    n++
  )
    result.push(n);
  result.push(pages.value);
  return result.flatMap((n, i) =>
    i && n - result[i - 1] > 1 ? ["…", n] : [n],
  );
});
const go = (n) => {
  if (n >= 1 && n <= pages.value && n !== props.modelValue)
    emit("update:modelValue", n);
};
watch(pages, (n) => {
  if (props.modelValue > n) emit("update:modelValue", n);
});
</script>
<template>
  <div class="pagination" :class="{ compact }">
    <span class="pagination-summary">
      <slot name="summary" :total="total" :page-size="pageSize" :page="modelValue">
        共{{ total }}条，{{ pageSize }}条/页，第{{ modelValue }}页<span
          v-if="showTotalPages"
          >，共{{ pages }}页</span
        >
      </slot>
    </span>
    <div class="pagination-buttons">
      <button
        type="button"
        class="page-button"
        :disabled="modelValue <= 1"
        @click="go(modelValue - 1)"
        aria-label="上一页"
      >
        <template v-if="textButtons">上一页</template>
        <NavIcon v-else name="left" :size="17" /></button
      ><template v-for="(page, i) in visible" :key="i"
        ><span v-if="page === '…'" class="page-ellipsis">…</span
        ><button
          v-else
          type="button"
          class="page-button"
          :class="{ active: page === modelValue }"
          :aria-current="page === modelValue ? 'page' : undefined"
          @click="go(page)"
        >
          {{ page }}
        </button></template
      ><button
        type="button"
        class="page-button"
        :disabled="modelValue >= pages"
        @click="go(modelValue + 1)"
        aria-label="下一页"
      >
        <template v-if="textButtons">下一页</template>
        <NavIcon v-else name="right" :size="17" />
      </button>
    </div>
  </div>
</template>
