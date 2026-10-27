import { reactive } from "vue";
export const feedbackState = reactive({ toasts: [], confirmation: null });
let sequence = 0;
export function notify(message, tone = "success") {
  const id = ++sequence;
  feedbackState.toasts.push({ id, message: String(message), tone });
  setTimeout(() => {
    feedbackState.toasts = feedbackState.toasts.filter(
      (toast) => toast.id !== id,
    );
  }, 5000);
  return id;
}
export function confirmAction({
  title = "确认操作",
  message = "",
  confirmText = "确认",
  tone = "warning",
} = {}) {
  if (feedbackState.confirmation) return Promise.resolve(false);
  return new Promise((resolve) => {
    feedbackState.confirmation = { title, message, confirmText, tone, resolve };
  });
}
export function settleConfirmation(accepted) {
  const confirmation = feedbackState.confirmation;
  feedbackState.confirmation = null;
  confirmation?.resolve(accepted);
}
