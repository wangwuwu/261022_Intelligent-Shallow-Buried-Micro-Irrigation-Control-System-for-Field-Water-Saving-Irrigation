<script setup>
import NavIcon from "./NavIcon.vue";
defineProps({
  label: String,
  value: [String, Number],
  unit: String,
  tone: { type: String, default: "success" },
  icon: String,
});
</script>
<template>
  <div class="metric-card" :class="`metric-${tone}`">
    <span v-if="icon" class="metric-icon"
      ><NavIcon :name="icon" :size="30"
    /></span>
    <div class="metric-body">
      <span class="metric-label">{{ label }}</span>
      <div class="metric-number">
        {{ value ?? "—"
        }}<span v-if="unit" class="metric-unit">{{ unit }}</span>
      </div>
    </div>
    <slot />
  </div>
</template>
