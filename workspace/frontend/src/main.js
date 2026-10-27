import { createApp } from "vue";
import "@fontsource/noto-sans-sc/400.css";
import "@fontsource/noto-sans-sc/500.css";
import "@fontsource/noto-sans-sc/600.css";
import "@fontsource/noto-sans-sc/700.css";
import "./styles/main.css";
import App from "./App.vue";
import router from "./router/index.js";
import { useIrrigation } from "./data/runtime.js";
import { notify } from "./composables/feedback.js";
const runtime = useIrrigation();
try {
  await runtime.load();
} catch (error) {
  runtime.state.error = error;
}
const app = createApp(App);
app.config.errorHandler = (error) => {
  console.error(error);
  notify(error.message || "界面发生错误，请重试", "danger");
};
app.use(router);
await router.isReady();
app.mount("#app");
