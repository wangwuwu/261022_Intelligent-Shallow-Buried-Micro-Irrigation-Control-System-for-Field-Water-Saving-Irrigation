<script setup>
import { computed, nextTick, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppShell from "./components/AppShell.vue";
import BaseModal from "./components/BaseModal.vue";
import { feedbackState, settleConfirmation } from "./composables/feedback.js";
import { useIrrigation } from "./data/runtime.js";
import { clearListSnapshots } from "./composables/useListState.js";
const route = useRoute();
const router = useRouter();
const runtime = useIrrigation();
watch(
  () => runtime.state.user,
  async (user, previousUser) => {
    if (user || !previousUser) return;
    settleConfirmation(false);
    feedbackState.toasts = [];
    if (!route.meta.public) {
      await router.replace({ path: "/login", query: { return: route.fullPath } });
    }
    await nextTick();
    clearListSnapshots();
  },
);
const confirmationOpen = computed({
  get: () => Boolean(feedbackState.confirmation),
  set: (open) => {
    if (!open) settleConfirmation(false);
  },
});
</script>
<template>
  <RouterView v-if="route.meta.public" /><AppShell v-else-if="runtime.state.user"
    ><RouterView
  /></AppShell>
  <div class="toast-stack" aria-live="polite">
    <div
      v-for="toast in feedbackState.toasts"
      :key="toast.id"
      class="toast"
      :class="`toast-${toast.tone}`"
    >
      {{ toast.message }}
    </div>
  </div>
  <BaseModal
    v-model="confirmationOpen"
    :title="feedbackState.confirmation?.title"
    :width="480"
    ><p class="confirmation-message">
      {{ feedbackState.confirmation?.message }}
    </p>
    <template #footer
      ><button type="button" class="btn" @click="settleConfirmation(false)">
        取消</button
      ><button
        type="button"
        class="btn"
        :class="
          feedbackState.confirmation?.tone === 'danger'
            ? 'btn-danger'
            : 'btn-primary'
        "
        @click="settleConfirmation(true)"
      >
        {{ feedbackState.confirmation?.confirmText }}
      </button></template
    ></BaseModal
  >
</template>
