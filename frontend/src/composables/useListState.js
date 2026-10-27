import { reactive, onBeforeUnmount, onMounted, nextTick } from "vue";
const snapshots = new Map();
export function clearListSnapshots() {
  snapshots.clear();
}
export function useListState(key, defaults = {}) {
  const state = reactive(
    snapshots.get(key) || {
      page: 1,
      pageSize: 15,
      sort: null,
      selectedId: null,
      filters: {},
      scrollTop: 0,
      ...structuredClone(defaults),
    },
  );
  onMounted(async () => {
    await nextTick();
    const scroll = document.querySelector(".main-content");
    if (scroll) scroll.scrollTop = state.scrollTop || 0;
  });
  onBeforeUnmount(() => {
    const scroll = document.querySelector(".main-content");
    state.scrollTop = scroll?.scrollTop || 0;
    snapshots.set(key, structuredClone(JSON.parse(JSON.stringify(state))));
  });
  return state;
}
