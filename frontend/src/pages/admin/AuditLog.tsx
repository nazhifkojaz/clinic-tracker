import { useState, useEffect } from "react";
import React from "react";
import { auditService } from "@/services/audit";
import type { AuditLogEntry, AuditLogMetadata } from "@/types/audit";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, ScrollText, ChevronDown, ChevronUp, Filter } from "lucide-react";

// Simple date formatting utilities
function formatDateShort(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDateFull(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString("en-US", {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

interface ExpandedRow {
  [key: string]: boolean;
}

interface Filters {
  action: string;
  table_name: string;
  date_from: string;
  date_to: string;
}

const ACTION_LABELS: Record<string, string> = {
  create: "Create",
  update: "Update",
  delete: "Delete",
};

const ACTION_COLORS: Record<string, string> = {
  create: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  update: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  delete: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

function ActionBadge({ action }: { action: string }) {
  const colorClass = ACTION_COLORS[action] || "bg-gray-100 text-gray-800";
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colorClass}`}>
      {ACTION_LABELS[action] || action}
    </span>
  );
}

export default function AuditLog() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [metadata, setMetadata] = useState<AuditLogMetadata | null>(null);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [expanded, setExpanded] = useState<ExpandedRow>({});
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    action: "",
    table_name: "",
    date_from: "",
    date_to: "",
  });
  const [offset, setOffset] = useState(0);
  const limit = 50;

  useEffect(() => {
    fetchData();
  }, [filters, offset]);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const params: any = { limit, offset };
      if (filters.action) params.action = filters.action;
      if (filters.table_name) params.table_name = filters.table_name;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;

      const [logsData, metadataData] = await Promise.all([
        auditService.list(params),
        auditService.getMetadata(),
      ]);

      setEntries(logsData.items);
      setTotal(logsData.total);
      setMetadata(metadataData);
    } catch (error) {
      console.error("Failed to load audit logs:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const updateFilter = (key: keyof Filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setOffset(0);
    setExpanded({});
  };

  const clearFilters = () => {
    setFilters({ action: "", table_name: "", date_from: "", date_to: "" });
    setOffset(0);
    setExpanded({});
  };

  const toggleExpand = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const renderJsonDiff = (
    oldValues: Record<string, unknown> | null,
    newValues: Record<string, unknown> | null,
    action: string
  ) => {
    if (action === "create") {
      return (
        <div className="space-y-1">
          {newValues &&
            Object.entries(newValues).map(([key, value]) => (
              <div key={key} className="flex gap-2 text-sm">
                <span className="font-semibold text-green-600 dark:text-green-400 w-32 shrink-0">
                  + {key}:
                </span>
                <span className="font-mono text-muted-foreground break-all">
                  {String(value)}
                </span>
              </div>
            ))}
        </div>
      );
    }

    if (action === "delete") {
      return (
        <div className="space-y-1">
          {oldValues &&
            Object.entries(oldValues).map(([key, value]) => (
              <div key={key} className="flex gap-2 text-sm">
                <span className="font-semibold text-red-600 dark:text-red-400 w-32 shrink-0">
                  - {key}:
                </span>
                <span className="font-mono text-muted-foreground break-all">
                  {String(value)}
                </span>
              </div>
            ))}
        </div>
      );
    }

    const allKeys = new Set([
      ...Object.keys(oldValues || {}),
      ...Object.keys(newValues || {}),
    ]);

    return (
      <div className="space-y-1">
        {Array.from(allKeys).map((key) => {
          const oldVal = oldValues?.[key];
          const newVal = newValues?.[key];
          const hasChanged = JSON.stringify(oldVal) !== JSON.stringify(newVal);

          if (!hasChanged) return null;

          return (
            <div key={key} className="flex gap-2 text-sm">
              <span className="font-semibold w-32 shrink-0">{key}:</span>
              <div className="flex flex-col gap-0.5">
                {oldVal !== undefined && (
                  <span className="font-mono text-red-600 dark:text-red-400 break-all">
                    - {String(oldVal)}
                  </span>
                )}
                {newVal !== undefined && (
                  <span className="font-mono text-green-600 dark:text-green-400 break-all">
                    + {String(newVal)}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const hasActiveFilters = Object.values(filters).some((v) => v !== "");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ScrollText className="h-6 w-6" />
            Audit Log
          </h1>
          <p className="text-muted-foreground">
            Track all data modifications in the system
          </p>
        </div>
        <span className="text-sm px-3 py-1 bg-secondary rounded-full">
          {total} entries
        </span>
      </div>

      {/* Filters */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Filters
          </h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            {showFilters ? "Hide" : "Show"}
          </Button>
        </div>
        {showFilters && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-2">
                <Label htmlFor="action">Action</Label>
                <select
                  id="action"
                  value={filters.action}
                  onChange={(e) => updateFilter("action", e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  <option value="">All actions</option>
                  {metadata?.actions.map((action) => (
                    <option key={action} value={action}>
                      {ACTION_LABELS[action] || action}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="table">Table</Label>
                <select
                  id="table"
                  value={filters.table_name}
                  onChange={(e) => updateFilter("table_name", e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  <option value="">All tables</option>
                  {metadata?.table_names.map((table) => (
                    <option key={table} value={table}>
                      {table
                        .replace(/_/g, " ")
                        .replace(/\b\w/g, (l) => l.toUpperCase())}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="date_from">From Date</Label>
                <Input
                  id="date_from"
                  type="date"
                  value={filters.date_from}
                  onChange={(e) => updateFilter("date_from", e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="date_to">To Date</Label>
                <Input
                  id="date_to"
                  type="date"
                  value={filters.date_to}
                  onChange={(e) => updateFilter("date_to", e.target.value)}
                />
              </div>
            </div>

            {hasActiveFilters && (
              <div className="flex justify-end">
                <Button variant="outline" size="sm" onClick={clearFilters}>
                  Clear Filters
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Audit Log Table */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-2">Audit Entries</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Showing {Math.min(limit, total - offset)} of {total} entries
        </p>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <ScrollText className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No audit log entries found.</p>
          </div>
        ) : (
          <>
            <div className="border rounded-md overflow-hidden">
              <table className="w-full">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-4 py-2 text-left text-sm font-medium w-[180px]">
                      Time
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium">User</th>
                    <th className="px-4 py-2 text-left text-sm font-medium">Action</th>
                    <th className="px-4 py-2 text-left text-sm font-medium">Table</th>
                    <th className="px-4 py-2 text-left text-sm font-medium">
                      Record ID
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium w-[80px]"></th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <React.Fragment key={entry.id}>
                      <tr
                        className="border-t cursor-pointer hover:bg-muted/50"
                        onClick={() => toggleExpand(entry.id)}
                      >
                        <td className="px-4 py-3 font-mono text-xs">
                          {formatDateShort(entry.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium">
                            {entry.user_name || "System"}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <ActionBadge action={entry.action} />
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-sm font-mono">
                            {entry.table_name}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs font-mono text-muted-foreground">
                            {entry.record_id.slice(0, 8)}...
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleExpand(entry.id);
                            }}
                          >
                            {expanded[entry.id] ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : (
                              <ChevronDown className="h-4 w-4" />
                            )}
                          </Button>
                        </td>
                      </tr>
                      {expanded[entry.id] && (
                        <tr className="border-t bg-muted/30">
                          <td colSpan={6} className="px-4 py-4">
                            <div className="space-y-3">
                              <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                  <span className="font-semibold text-muted-foreground">
                                    User:
                                  </span>{" "}
                                  {entry.user_name || "System"}
                                  {entry.user_id && (
                                    <span className="text-xs text-muted-foreground ml-2 font-mono">
                                      ({entry.user_id.slice(0, 8)}...)
                                    </span>
                                  )}
                                </div>
                                <div>
                                  <span className="font-semibold text-muted-foreground">
                                    Record:
                                  </span>{" "}
                                  <span className="font-mono">{entry.record_id}</span>
                                </div>
                              </div>

                              <div>
                                <p className="font-semibold text-sm text-muted-foreground mb-2">
                                  Changes:
                                </p>
                                <div className="bg-background p-3 rounded border">
                                  {renderJsonDiff(
                                    entry.old_values,
                                    entry.new_values,
                                    entry.action
                                  )}
                                </div>
                              </div>

                              <div className="text-xs text-muted-foreground">
                                {formatDateFull(entry.created_at)}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {total > limit && (
              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">
                  Showing {offset + 1}-{Math.min(offset + limit, total)} of{" "}
                  {total}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                    disabled={offset === 0}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setOffset(offset + limit)}
                    disabled={offset + limit >= total}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
