# 公共组件约定

- `BaseModal`: `v-model` boolean、`title`、`busy`、`width`；default/footer slots。关闭按钮/Esc仅请求`update:modelValue(false)`，原生dialog直到父级接受并更新model才关闭；用`:model-value`配合异步关闭守卫时，拒绝后保持可见。若声明`@request-close`则只触发该事件，父级接受后自行更新model，避免v-model自动赋false。`close`在model实际改为false后触发。`busy`阻止用户关闭请求。
- `DataTable`: `columns=[{key,label,width,align,sortable}]`、`rows`、`rowKey` string/function、`selectedId`、`sort={key,direction}`、`compact`；emit `row-click(row)`、`update:sort`；`cell-<key>` slot `{row,value,index}`。
- `Pagination`: `v-model` page、`total`、`pageSize=15`、`compact`；默认摘要为共…条、…条/页、第…页，`showTotalPages`按需追加总页数，`textButtons`显示上一页/下一页文字；`summary` slot可定制业务摘要（slot props：`total`、`pageSize`、`page`）；页码自动夹紧。
- `StatusBadge`: `status`、`text`可选、`tone`可选；未知状态展示原值。
- `MetricCard`: `label`、`value`、`unit`、`tone`、`icon`（NavIcon名）；可监听click。
- `FormField`: `label`、`error`、`required`、`hideRequiredMarker`；后者仅隐藏必填星号，默认slot放真实input/select。
- `ChartPanel`: `options` ECharts option、`height=260`；emit `chart-click`。
- `NavIcon`: `name`（overview/field/network/device/monitor/strategy/plan/run/alarm/maintenance/water/settings/audit/chevron/arrow-left/search/refresh/add/close/check/calendar/leaf/download/wifi/user）和`size`。
- `feedback.js`: `notify(message,tone='success')`；`confirmAction({title,message,confirmText,tone})`返回Promise<boolean>。App内统一渲染。
- `useListState(key,defaults)`返回reactive对象，默认`{page:1,pageSize:15,sort:null,selectedId:null,filters:{}}`，离开保存滚动。
- `useDraftGuard(()=>dirty)`注册路由/关闭页面守卫，返回`requestLeave(callback)`和`markClean()`；保存后先更新草稿比较基线再调用markClean；markClean仅免除本次同步导航，后续修改仍受保护。
- `useClock()`返回`{now,displayNow,isReference,today}`；now是真实时钟，displayNow仅在URL reference=1时为参考值。

公共CSS：`.page-stack`、`.panel`、`.panel-title`、`.filters`、`.filter-field`、`.btn`、`.btn-primary`、`.btn-danger`、`.btn-link`、`.btn-sm`、`.form-grid`、`.form-actions`、`.tabs`、`.tab`、`.data-pairs`、`.muted`、`.error-text`、`.empty-state`、`.stat-grid`。

浏览器关闭回归：在frontend目录启动Vite后，运行 `python3 tests/browser/modal-close.spec.py --url http://127.0.0.1:5173`。此验证需要Playwright Python与Chromium，覆盖父级异步拒绝/接受、Esc、提交中关闭限制及独立request-close，且不修改业务数据。
