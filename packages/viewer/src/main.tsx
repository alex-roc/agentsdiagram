import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { pickTransport } from "./transport";
import "@xyflow/react/dist/style.css";
import "./styles.css";

async function start(): Promise<void> {
  const el = document.getElementById("root");
  if (!el) return;
  const transport = await pickTransport();
  createRoot(el).render(
    <StrictMode>
      <App transport={transport} />
    </StrictMode>,
  );
}

void start();
