<script setup>
const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  rowKey: { type: [String, Function], default: "id" },
  selectedId: [String, Number],
  sort: Object,
  compact: Boolean,
  loading: Boolean,
  emptyText: { type: String, default: "暂无符合条件的记录" },
});
const emit = defineEmits(["row-click", "update:sort"]);
const identity = (row) =>
  typeof props.rowKey === "function" ? props.rowKey(row) : row[props.rowKey];
const sortColumn = (column) => {
  if (column.sortable)
    emit("update:sort", {
      key: column.key,
      direction:
        props.sort?.key === column.key && props.sort.direction === "asc"
          ? "desc"
          : "asc",
    });
};
</script>
<template>
  <div class="table-scroll">
    <table class="data-table" :class="{ compact }">
      <colgroup>
        <col
          v-for="column in columns"
          :key="column.key"
          :style="{
            width:
              typeof column.width === 'number'
                ? column.width + 'px'
                : column.width,
          }"
        />
      </colgroup>
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            :style="{ textAlign: column.align || 'left' }"
            :aria-sort="
              sort?.key === column.key
                ? sort.direction === 'asc'
                  ? 'ascending'
                  : 'descending'
                : undefined
            "
          >
            <button
              v-if="column.sortable"
              class="table-sort"
              type="button"
              @click="sortColumn(column)"
            >
              {{ column.label
              }}<span v-if="sort?.key === column.key" aria-hidden="true">{{
                sort.direction === "asc" ? " ↑" : " ↓"
              }}</span></button
            ><template v-else>{{ column.label }}</template>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, index) in rows"
          :key="identity(row) ?? index"
          :class="{
            selected: selectedId != null && identity(row) === selectedId,
            clickable: true,
          }"
          tabindex="0"
          @click="emit('row-click', row)"
          @keydown.enter.self="emit('row-click', row)"
        >
          <td
            v-for="column in columns"
            :key="column.key"
            :style="{ textAlign: column.align || 'left' }"
          >
            <slot
              :name="'cell-' + column.key"
              :row="row"
              :value="row[column.key]"
              :index="index"
              >{{
                column.format
                  ? column.format(row[column.key], row, index)
                  : (row[column.key] ?? "—")
              }}</slot
            >
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="empty-state">
            {{ loading ? "加载中…" : emptyText }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
