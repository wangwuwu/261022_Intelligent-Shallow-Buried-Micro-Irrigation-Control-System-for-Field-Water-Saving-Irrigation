import { onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { confirmAction } from "./feedback.js";

const guards = new Set();

export async function mayLeaveDraft() {
  const needsConfirmation = [...guards].some((guard) => guard());
  if (!needsConfirmation) return true;
  return confirmAction({
    title: "放弃未保存的修改",
    message: "当前修改尚未保存，确认放弃并离开？",
    confirmText: "放弃修改",
  });
}

export function useDraftGuard(isDirty) {
  let leavingConfirmed = false;
  let savedNavigationTurn = false;
  let navigationTimer;
  const router = useRouter();
  const removeAfterEach = router.afterEach(() => {
    leavingConfirmed = false;
  });
  // A save must update the caller's baseline. This one-turn exemption only
  // prevents the successful save's immediate navigation from prompting again.
  const guard = () =>
    !leavingConfirmed && !savedNavigationTurn && Boolean(isDirty());
  guards.add(guard);

  const beforeUnload = (event) => {
    if (guard()) {
      event.preventDefault();
      event.returnValue = "";
    }
  };
  window.addEventListener("beforeunload", beforeUnload);
  onBeforeUnmount(() => {
    guards.delete(guard);
    removeAfterEach();
    clearTimeout(navigationTimer);
    window.removeEventListener("beforeunload", beforeUnload);
  });

  return {
    markClean() {
      savedNavigationTurn = true;
      clearTimeout(navigationTimer);
      navigationTimer = setTimeout(() => {
        savedNavigationTurn = false;
      }, 0);
    },
    async requestLeave(callback) {
      if (
        guard() &&
        !(await confirmAction({
          title: "放弃未保存的修改",
          message: "当前修改尚未保存，确认放弃并离开？",
          confirmText: "放弃修改",
        }))
      )
        return false;
      leavingConfirmed = true;
      try {
        const result = callback?.();
        if (result?.then) await result;
        // Route-back is asynchronous and has no Promise. The local exemption
        // belongs to this component only and disappears when it unmounts.
        return true;
      } catch (error) {
        leavingConfirmed = false;
        throw error;
      }
    },
  };
}
