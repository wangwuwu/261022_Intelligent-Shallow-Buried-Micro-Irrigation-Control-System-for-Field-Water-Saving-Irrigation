<script setup>
import { ref, watch, nextTick, onBeforeUnmount, getCurrentInstance } from "vue";
import NavIcon from "./NavIcon.vue";

const props = defineProps({
  modelValue: Boolean,
  title: String,
  busy: Boolean,
  width: { type: [Number, String], default: 640 },
});
const emit = defineEmits(["update:modelValue", "request-close", "close"]);
const instance = getCurrentInstance();
const dialog = ref();
let priorFocus;
const close = () => {
  if (props.busy) return;
  // A guarded parent can decline a close request while keeping modelValue true.
  // Only the controlled prop watcher may close the native dialog.
  if (instance.vnode.props?.onRequestClose) emit("request-close");
  else emit("update:modelValue", false);
};
watch(
  () => props.modelValue,
  async (open, wasOpen) => {
    if (open) {
      priorFocus = document.activeElement;
      await nextTick();
      // Native modal dialogs make the background inert and trap keyboard focus.
      if (dialog.value && !dialog.value.open) dialog.value.showModal();
      dialog.value
        ?.querySelector(
          "input:not(:disabled),select:not(:disabled),textarea:not(:disabled),button:not(:disabled)",
        )
        ?.focus();
    } else {
      dialog.value?.close();
      priorFocus?.focus?.();
      if (wasOpen) emit("close");
    }
  },
  { immediate: true },
);
onBeforeUnmount(() => dialog.value?.close());
</script>

<template>
  <Teleport to="body">
    <dialog
      v-if="modelValue"
      ref="dialog"
      class="base-modal"
      :aria-label="title"
      :aria-busy="busy"
      :style="{ width: typeof width === 'number' ? width + 'px' : width }"
      @cancel.prevent="close"
    >
      <header class="modal-header">
        <h2>{{ title }}</h2>
        <button
          type="button"
          class="icon-button"
          :disabled="busy"
          aria-label="关闭"
          @click="close"
        >
          <NavIcon name="close" />
        </button>
      </header>
      <div class="modal-content"><slot /></div>
      <footer v-if="$slots.footer" class="modal-footer">
        <slot name="footer" />
      </footer>
    </dialog>
  </Teleport>
</template>
