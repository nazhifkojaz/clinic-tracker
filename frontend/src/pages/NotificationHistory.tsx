import { useState, useEffect } from "react";
import React from "react";
import { useAuthStore } from "@/stores/authStore";
import { notificationService } from "@/services/notifications";
import type { NotificationRecord } from "@/types/notification";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, Bell, ChevronDown, ChevronUp } from "lucide-react";

interface ExpandedRow {
  [key: string]: boolean;
}

// Simple date formatting utility
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function formatFullDate(dateStr: string): string {
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

export default function NotificationHistory() {
  const { user } = useAuthStore();

  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expanded, setExpanded] = useState<ExpandedRow>({});

  useEffect(() => {
    fetchNotifications();
  }, []);

  const fetchNotifications = async () => {
    try {
      const data = await notificationService.list({ limit: 100 });
      setNotifications(data);
    } catch (error) {
      console.error("Failed to load notification history:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Notification History</h1>
          <p className="text-muted-foreground">
            {user?.role === "admin"
              ? "View all notifications sent"
              : "View your sent notifications"}
          </p>
        </div>
        <span className="text-sm px-3 py-1 bg-secondary rounded-full">
          {notifications.length} total
        </span>
      </div>

      <Card className="p-6">
        <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
          <Bell className="h-5 w-5" />
          Sent Notifications
        </h2>
        <p className="text-sm text-muted-foreground mb-4">
          Email notifications you have sent to students
        </p>

        {notifications.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No notifications sent yet.</p>
          </div>
        ) : (
          <div className="border rounded-md overflow-hidden">
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="px-4 py-2 text-left text-sm font-medium w-[180px]">
                    Date
                  </th>
                  <th className="px-4 py-2 text-left text-sm font-medium">To</th>
                  <th className="px-4 py-2 text-left text-sm font-medium">
                    Subject
                  </th>
                  <th className="px-4 py-2 text-left text-sm font-medium w-[80px]"></th>
                </tr>
              </thead>
              <tbody>
                {notifications.map((notification) => (
                  <React.Fragment key={notification.id}>
                    <tr
                      className="border-t cursor-pointer hover:bg-muted/50"
                      onClick={() => toggleExpand(notification.id)}
                    >
                      <td className="px-4 py-3 font-mono text-xs">
                        {formatDate(notification.sent_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium">
                          {notification.recipient_name}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="truncate max-w-md font-medium">
                          {notification.subject}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleExpand(notification.id);
                          }}
                        >
                          {expanded[notification.id] ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </Button>
                      </td>
                    </tr>
                    {expanded[notification.id] && (
                      <tr className="border-t bg-muted/30">
                        <td colSpan={4} className="px-4 py-4">
                          <div className="space-y-3">
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="font-semibold text-muted-foreground">
                                  From:
                                </span>{" "}
                                {notification.sender_name}
                              </div>
                              <div>
                                <span className="font-semibold text-muted-foreground">
                                  To:
                                </span>{" "}
                                {notification.recipient_name}
                              </div>
                            </div>
                            <div>
                              <p className="font-semibold text-sm text-muted-foreground mb-1">
                                Subject:
                              </p>
                              <p className="text-sm font-medium">
                                {notification.subject}
                              </p>
                            </div>
                            <div>
                              <p className="font-semibold text-sm text-muted-foreground mb-1">
                                Message:
                              </p>
                              <div className="text-sm bg-background p-3 rounded border whitespace-pre-wrap font-mono">
                                {notification.message}
                              </div>
                            </div>
                            <div className="text-xs text-muted-foreground">
                              Sent at {formatFullDate(notification.sent_at)}
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
        )}
      </Card>
    </div>
  );
}
