import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { notificationService } from "@/services/notifications";
import { assignmentService } from "@/services/assignments";
import type { NotificationTemplate, NotificationStatus } from "@/types/notification";
import type { MyStudent } from "@/types/assignment";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Mail, CheckCircle2, AlertCircle } from "lucide-react";

export default function SendNotification() {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  const [students, setStudents] = useState<MyStudent[]>([]);
  const [templates, setTemplates] = useState<NotificationTemplate[]>([]);
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [emailStatus, setEmailStatus] = useState<NotificationStatus | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [studentsData, templatesData, statusData] = await Promise.all([
          assignmentService.getMyStudents(),
          notificationService.getTemplates(),
          notificationService.getStatus(),
        ]);
        setStudents(studentsData);
        setTemplates(templatesData);
        setEmailStatus(statusData);
      } catch (error) {
        console.error("Failed to load data:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleTemplateChange = (templateKey: string) => {
    setSelectedTemplate(templateKey);
    const template = templates.find((t) => t.key === templateKey);
    if (template) {
      setSubject(template.subject);
      setMessage(template.message);
    }
  };

  const toggleStudent = (studentId: string) => {
    setSelectedStudentIds((prev) =>
      prev.includes(studentId)
        ? prev.filter((id) => id !== studentId)
        : [...prev, studentId]
    );
  };

  const toggleAll = () => {
    if (selectedStudentIds.length === students.length) {
      setSelectedStudentIds([]);
    } else {
      setSelectedStudentIds(students.map((s) => s.student_id));
    }
  };

  const handleSendClick = () => {
    if (selectedStudentIds.length === 0) {
      return;
    }
    if (!subject.trim() || !message.trim()) {
      return;
    }
    setShowConfirm(true);
  };

  const handleSendConfirm = async () => {
    setIsSending(true);
    setShowConfirm(false);

    try {
      await notificationService.send({
        recipient_ids: selectedStudentIds,
        subject,
        message,
        template_key: selectedTemplate || undefined,
        template_vars: {
          student_name: "{student_name}",
          supervisor_name: user?.full_name || user?.email || "Supervisor",
        },
      });

      navigate("/notifications");
    } catch (error: any) {
      console.error("Failed to send notification:", error);
      setIsSending(false);
    }
  };

  const selectedStudents = students.filter((s) =>
    selectedStudentIds.includes(s.student_id)
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Send Notification</h1>
          <p className="text-muted-foreground">
            Send email notifications to your assigned students
          </p>
        </div>
        {emailStatus && (
          <div className="flex items-center gap-2 text-sm">
            {emailStatus.email_enabled ? (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            ) : (
              <AlertCircle className="h-4 w-4 text-yellow-500" />
            )}
            <span className="text-muted-foreground">
              {emailStatus.email_enabled ? "Email enabled" : "Mock mode"} (
              {emailStatus.mode})
            </span>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Select Recipients */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold flex items-center gap-2 mb-2">
            <Mail className="h-5 w-5" />
            1. Select Recipients
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            Choose students to notify ({selectedStudentIds.length} of{" "}
            {students.length} selected)
          </p>

          {students.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No assigned students found.
            </p>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 pb-2 border-b">
                <input
                  type="checkbox"
                  id="select-all"
                  checked={
                    selectedStudentIds.length === students.length &&
                    students.length > 0
                  }
                  onChange={toggleAll}
                  className="w-4 h-4"
                />
                <Label htmlFor="select-all" className="cursor-pointer font-medium">
                  Select All
                </Label>
              </div>
              <div className="max-h-64 overflow-y-auto space-y-2">
                {students.map((student) => (
                  <div
                    key={student.student_id}
                    className="flex items-center gap-3 p-2 rounded hover:bg-accent"
                  >
                    <input
                      type="checkbox"
                      id={student.student_id}
                      checked={selectedStudentIds.includes(student.student_id)}
                      onChange={() => toggleStudent(student.student_id)}
                      className="w-4 h-4"
                    />
                    <div className="flex-1 min-w-0">
                      <Label
                        htmlFor={student.student_id}
                        className="cursor-pointer truncate font-medium"
                      >
                        {student.student_name}
                      </Label>
                      <p className="text-xs text-muted-foreground truncate">
                        {student.student_code || student.student_email}
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground capitalize">
                      {student.assignment_type}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        {/* Compose Message */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-2">2. Compose Message</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Use a template or write a custom message
          </p>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="template">Template (Optional)</Label>
              <select
                id="template"
                value={selectedTemplate}
                onChange={(e) => handleTemplateChange(e.target.value)}
                className="w-full px-3 py-2 border rounded-md bg-background"
              >
                <option value="">Select a template...</option>
                {templates.map((template) => (
                  <option key={template.key} value={template.key}>
                    {template.key
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (l) => l.toUpperCase())}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="subject">Subject</Label>
              <Input
                id="subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Email subject..."
                className="font-medium"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="message">Message</Label>
              <textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Email message..."
                rows={8}
                className="w-full px-3 py-2 border rounded-md bg-background font-mono text-sm resize-none"
              />
              <p className="text-xs text-muted-foreground">
                Variables: {"{student_name}"}, {"{supervisor_name}"},{" "}
                {"{department}"}, etc.
              </p>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="outline"
                onClick={() => {
                  setSelectedTemplate("");
                  setSubject("");
                  setMessage("");
                  setSelectedStudentIds([]);
                }}
              >
                Clear
              </Button>
              <Button
                onClick={handleSendClick}
                disabled={isSending || selectedStudentIds.length === 0}
              >
                {isSending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  `Send to ${selectedStudentIds.length} student${
                    selectedStudentIds.length !== 1 ? "s" : ""
                  }`
                )}
              </Button>
            </div>
          </div>
        </Card>
      </div>

      {/* Preview */}
      {selectedStudents.length > 0 && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">3. Preview</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Preview of the email that will be sent
          </p>
          <div className="border rounded-lg p-4 space-y-3 bg-muted/30">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase">
                To:
              </p>
              <p className="text-sm">
                {selectedStudents.map((s) => s.student_name).join(", ")}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase">
                Subject:
              </p>
              <p className="text-sm font-medium">{subject || "(No subject)"}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase">
                Message:
              </p>
              <div className="text-sm whitespace-pre-wrap font-mono bg-background p-3 rounded border">
                {message || "(No message)"}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-2">Send Notification?</h3>
            <p className="text-sm text-muted-foreground mb-4">
              You are about to send an email notification to{" "}
              <strong>{selectedStudentIds.length}</strong> student(s).
              {emailStatus && !emailStatus.email_enabled && (
                <span className="block mt-2 text-yellow-600 dark:text-yellow-400">
                  Note: Email is in mock mode. Emails will be logged but not
                  actually sent.
                </span>
              )}
            </p>
            <div className="flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={() => setShowConfirm(false)}
              >
                Cancel
              </Button>
              <Button onClick={handleSendConfirm} disabled={isSending}>
                {isSending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  "Send Now"
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
