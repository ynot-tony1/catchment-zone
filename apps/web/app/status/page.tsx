import type { Metadata } from "next";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime } from "@/lib/format";
import { getGitSha } from "@/lib/env";
import { getPrismaClient } from "@/lib/prisma";
import { safeQuery } from "@/lib/safe-query";

export const metadata: Metadata = {
  title: "Status",
};

export const dynamic = "force-dynamic";

async function getStatus() {
  const prisma = getPrismaClient();
  const [schoolCount, recentRuns] = await Promise.all([
    prisma.school.count({ where: { status: "OPEN" } }),
    prisma.ingestionRun.findMany({ orderBy: { startedAt: "desc" }, take: 10 }),
  ]);
  return { schoolCount, recentRuns };
}

function runStatusVariant(status: string): "success" | "warning" | "destructive" | "secondary" {
  switch (status) {
    case "SUCCEEDED":
      return "success";
    case "PARTIAL":
      return "warning";
    case "FAILED":
      return "destructive";
    default:
      return "secondary";
  }
}

export default async function StatusPage() {
  const result = await safeQuery("status-page", getStatus, { schoolCount: 0, recentRuns: [] });

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Status</h1>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Database connectivity</CardTitle>
          </CardHeader>
          <CardContent>
            {result.ok ? (
              <Badge variant="success">Reachable</Badge>
            ) : (
              <Badge variant="destructive">Unreachable</Badge>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Deployed version</CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-sm">{getGitSha()}</CardContent>
        </Card>
      </div>

      {!result.ok && (
        <Alert variant="destructive">
          <AlertTitle>Database unreachable</AlertTitle>
          <AlertDescription>
            The application could not reach the database when this page was rendered.
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Recent ingestion runs</CardTitle>
        </CardHeader>
        <CardContent>
          {result.data.recentRuns.length === 0 ? (
            <p className="text-muted-foreground text-sm">No ingestion runs recorded yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Rows processed</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.data.recentRuns.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>{run.source}</TableCell>
                    <TableCell>
                      <Badge variant={runStatusVariant(run.status)}>{run.status}</Badge>
                    </TableCell>
                    <TableCell>{formatDateTime(run.startedAt)}</TableCell>
                    <TableCell>{run.rowsProcessed}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
