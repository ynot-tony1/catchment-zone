import { PrismaClient } from "@schoolscope/database";
import { getServerEnv } from "@/lib/env";

// Lazy singleton: the client is constructed on first use inside a request,
// never at module evaluation time. This matters because Next.js imports
// server modules during the production build's static analysis pass; a
// top-level `new PrismaClient()` would run then too, and this project has
// no live database to connect to during a build. Constructing lazily and
// caching on `globalThis` (surviving dev-mode hot reload, which otherwise
// creates a fresh client, and connection, on every file save) is the
// standard pattern for Prisma + Next.js.
const globalForPrisma = globalThis as unknown as { __prisma?: PrismaClient };

let client: PrismaClient | undefined;

export function getPrismaClient(): PrismaClient {
  if (client) return client;
  if (globalForPrisma.__prisma) {
    client = globalForPrisma.__prisma;
    return client;
  }

  // Touch env validation so a missing DATABASE_URL fails with a clear
  // message at first query time rather than a cryptic Prisma error.
  getServerEnv();

  client = new PrismaClient({
    log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"],
  });

  if (process.env.NODE_ENV !== "production") {
    globalForPrisma.__prisma = client;
  }

  return client;
}
