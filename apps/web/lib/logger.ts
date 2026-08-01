// Minimal structured server-side logger. Emits one JSON object per line
// (easy to ingest in any log aggregator) and never logs raw error objects
// or coordinates directly; callers pass a plain, pre-sanitised `context`.
type Level = "debug" | "info" | "warn" | "error";

const LEVEL_ORDER: Record<Level, number> = { debug: 0, info: 1, warn: 2, error: 3 };

function currentLevel(): Level {
  const v = process.env.LOG_LEVEL;
  return v === "debug" || v === "info" || v === "warn" || v === "error" ? v : "info";
}

function log(level: Level, message: string, context?: Record<string, unknown>) {
  if (LEVEL_ORDER[level] < LEVEL_ORDER[currentLevel()]) return;
  const entry = {
    level,
    message,
    timestamp: new Date().toISOString(),
    ...context,
  };
  const line = JSON.stringify(entry);
  if (level === "error") {
    console.error(line);
  } else if (level === "warn") {
    console.warn(line);
  } else {
    console.log(line);
  }
}

export const logger = {
  debug: (message: string, context?: Record<string, unknown>) => log("debug", message, context),
  info: (message: string, context?: Record<string, unknown>) => log("info", message, context),
  warn: (message: string, context?: Record<string, unknown>) => log("warn", message, context),
  error: (message: string, context?: Record<string, unknown>) => log("error", message, context),
};
