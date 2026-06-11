import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./App.css";

if ("serviceWorker" in navigator) {
  import("virtual:pwa-register").then((mod) => {
    const { registerSW } = mod;
    registerSW({ immediate: true });
  }).catch(() => {});
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
