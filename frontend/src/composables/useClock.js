import { ref, computed, onMounted, onBeforeUnmount } from "vue";
export function useClock() {
  const now = ref(new Date());
  const isReference =
    new URLSearchParams(window.location.search).get("reference") === "1";
  const displayNow = computed(() =>
    isReference ? new Date("2026-07-28T10:18:43+08:00") : now.value,
  );
  let timer;
  onMounted(() => {
    timer = setInterval(() => (now.value = new Date()), 1000);
  });
  onBeforeUnmount(() => clearInterval(timer));
  const today = computed(() =>
    new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(
      now.value,
    ),
  );
  return { now, displayNow, isReference, today };
}
export function formatShanghaiDate(
  date,
  { dateOnly = false, short = false } = {},
) {
  if (!date) return "—";
  const d = new Date(date);
  if (!Number.isFinite(d.getTime())) return "—";
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(!dateOnly
      ? { hour: "2-digit", minute: "2-digit", second: "2-digit" }
      : {}),
  }).format(d);
  return short ? parts.slice(5) : parts;
}
