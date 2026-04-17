import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "fs";
import path from "path";

// WebXR requires HTTPS. Use self-signed certs if available, otherwise Vite
// will still work but XR features won't activate on the Quest browser.
function getHttpsConfig() {
  const certPath = path.resolve(__dirname, "certs/cert.pem");
  const keyPath = path.resolve(__dirname, "certs/key.pem");

  if (fs.existsSync(certPath) && fs.existsSync(keyPath)) {
    return {
      cert: fs.readFileSync(certPath),
      key: fs.readFileSync(keyPath),
    };
  }

  console.warn(
    "\n⚠  No certs found. Run `npm run generate-cert` for WebXR HTTPS support.\n"
  );
  return undefined;
}

export default defineConfig({
  plugins: [react()],
  server: {
    https: getHttpsConfig(),
    host: true, // Expose on LAN so Quest 3 can reach it
    port: 5173,
  },
});
