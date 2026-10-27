import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const channel = env.VITE_DATA_CHANNEL || (mode === "http" ? "http" : "preview");
  const credentialPath = new URL(
    "./.local/preview-credentials.json",
    import.meta.url,
  );
  return {
    plugins: [
      vue(),
      {
        name: "runhe-preview-inputs",
        resolveId(id) {
          if (
            ["virtual:irrigation-seed", "virtual:preview-credentials"].includes(
              id,
            )
          )
            return "\0" + id;
        },
        load(id) {
          if (id === "\0virtual:irrigation-seed") {
            if (channel === "http") return "export default {}";
            this.addWatchFile(fileURLToPath(new URL("../shared_context.json", import.meta.url)));
            const source = JSON.parse(
              readFileSync(
                new URL("../shared_context.json", import.meta.url),
                "utf8",
              ),
            );
            return `export default ${JSON.stringify(source.entities)}`;
          }
          if (id === "\0virtual:preview-credentials") {
            if (channel === "http") return "export default {}";
            this.addWatchFile(fileURLToPath(credentialPath));
            if (!existsSync(credentialPath))
              return "export default {}";
            return `export default ${readFileSync(credentialPath, "utf8")}`;
          }
        },
      },
    ],
    define: { "import.meta.env.VITE_DATA_CHANNEL": JSON.stringify(channel) },
    server: {
      host: "0.0.0.0",
      port: 5173,
      watch: { usePolling: true, interval: 300 },
      proxy: {
        "/api": {
          target: env.API_PROXY_TARGET || "http://127.0.0.1:3001",
          changeOrigin: true,
        },
      },
    },
    build: { target: "esnext", chunkSizeWarningLimit: 1800 },
  };
});
