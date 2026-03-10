import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { departmentService } from "@/services/departments";
import { rotationService } from "@/services/rotations";
import { submissionService } from "@/services/submissions";
import type { Department, TaskCategory } from "@/types/department";
import type { UploadUrlResponse } from "@/types/submission";
import {
  AlertCircle,
  CheckCircle,
  FileImage,
  Loader2,
  Plus,
  Upload,
  X,
} from "lucide-react";

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

export default function CaseInputForm() {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  // Form state
  const [departmentId, setDepartmentId] = useState("");
  const [taskCategoryId, setTaskCategoryId] = useState("");
  const [caseCount, setCaseCount] = useState(1);
  const [notes, setNotes] = useState("");

  // Image upload state
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState("");
  const [uploadedObjectKey, setUploadedObjectKey] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  // Data loading
  const [departments, setDepartments] = useState<Department[]>([]);
  const [categories, setCategories] = useState<TaskCategory[]>([]);

  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  // Fetch departments and current rotation on mount
  useEffect(() => {
    const initData = async () => {
      try {
        setIsLoading(true);
        const [deptsData, currentRotation] = await Promise.all([
          departmentService.list(),
          rotationService.getCurrent(),
        ]);
        const activeDepts = deptsData.filter((d) => d.is_active);
        setDepartments(activeDepts);

        // Pre-select current rotation's department
        if (currentRotation) {
          setDepartmentId(currentRotation.department_id);
          // Load categories for that department
          const cats = await departmentService.listCategories(
            currentRotation.department_id
          );
          setCategories(cats.filter((c) => c.is_active));
        }
      } catch {
        setError("Failed to load initial data");
      } finally {
        setIsLoading(false);
      }
    };
    initData();
  }, []);

  // Load categories when department changes
  useEffect(() => {
    if (!departmentId) {
      setCategories([]);
      setTaskCategoryId("");
      return;
    }
    const loadCategories = async () => {
      try {
        const cats = await departmentService.listCategories(departmentId);
        setCategories(cats.filter((c) => c.is_active));
        setTaskCategoryId(""); // Clear selected category
      } catch {
        setError("Failed to load task categories");
      }
    };
    loadCategories();
  }, [departmentId]);

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      setError("Image file must be less than 5MB");
      return;
    }

    // Validate file type
    if (!file.type.startsWith("image/")) {
      setError("Please select an image file");
      return;
    }

    setImageFile(file);
    setError("");

    // Show preview
    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);

    // Upload immediately to R2
    try {
      setIsUploading(true);
      setError("");

      // Step 1: Get presigned URL
      const uploadData: UploadUrlResponse = await submissionService.getUploadUrl({
        filename: file.name,
        content_type: file.type,
      });

      // Step 2: Upload directly to R2 via presigned URL
      const uploadResponse = await fetch(uploadData.upload_url, {
        method: "PUT",
        body: file,
        headers: {
          "Content-Type": file.type,
        },
      });

      if (!uploadResponse.ok) {
        throw new Error("Failed to upload image");
      }

      // Step 3: Store the object key for form submission
      setUploadedObjectKey(uploadData.object_key);
    } catch {
      setError("Failed to upload image. Please try again.");
      setImageFile(null);
      setImagePreview("");
      setUploadedObjectKey("");
    } finally {
      setIsUploading(false);
    }
  };

  const clearImage = () => {
    setImageFile(null);
    setImagePreview("");
    setUploadedObjectKey("");
    if (imagePreview) {
      URL.revokeObjectURL(imagePreview);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Validation
    if (!departmentId || !taskCategoryId) {
      setError("Please select department and task category");
      return;
    }
    if (caseCount < 1) {
      setError("Case count must be at least 1");
      return;
    }
    if (!uploadedObjectKey) {
      setError("Please upload a proof image");
      return;
    }

    try {
      setIsSubmitting(true);
      await submissionService.create({
        department_id: departmentId,
        task_category_id: taskCategoryId,
        case_count: caseCount,
        proof_url: uploadedObjectKey,
        notes: notes || null,
      });

      setSuccess(true);
    } catch {
      setError("Failed to submit case. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setDepartmentId("");
    setTaskCategoryId("");
    setCaseCount(1);
    setNotes("");
    clearImage();
    setSuccess(false);
    setError("");
  };

  const canSubmit =
    departmentId &&
    taskCategoryId &&
    caseCount > 0 &&
    uploadedObjectKey &&
    !isUploading;

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (success) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center space-y-4">
        <div className="rounded-full bg-green-500/10 p-4">
          <CheckCircle className="h-12 w-12 text-green-600 dark:text-green-400" />
        </div>
        <div className="text-center">
          <h2 className="text-xl font-semibold">Case Submitted Successfully!</h2>
          <p className="text-muted-foreground">
            Your submission has been recorded and is pending review.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            Submit Another Case
          </button>
          <button
            onClick={() => navigate("/submissions")}
            className="rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            View My Submissions
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Submit Case Record</h1>
        <p className="text-muted-foreground">
          Log your clinical cases with image proof for supervisor review.
        </p>
      </div>

      {/* Student Info */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="mb-3 font-semibold">Student Information</h3>
        <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
          <div>
            <span className="text-muted-foreground">Name: </span>
            <span className="font-medium">{user?.full_name}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Student ID: </span>
            <span className="font-medium">{user?.student_id || "N/A"}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Email: </span>
            <span className="font-medium">{user?.email}</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Department Selection */}
        <div className="space-y-2">
          <label htmlFor="department" className="text-sm font-medium">
            Department <span className="text-destructive">*</span>
          </label>
          <select
            id="department"
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            required
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">Select department</option>
            {departments.map((dept) => (
              <option key={dept.id} value={dept.id}>
                {dept.name}
              </option>
            ))}
          </select>
        </div>

        {/* Task Category Selection */}
        <div className="space-y-2">
          <label htmlFor="category" className="text-sm font-medium">
            Task Category <span className="text-destructive">*</span>
          </label>
          <select
            id="category"
            value={taskCategoryId}
            onChange={(e) => setTaskCategoryId(e.target.value)}
            required
            disabled={!departmentId || categories.length === 0}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">
              {departmentId ? "Select task category" : "Select department first"}
            </option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name} (Required: {cat.required_count})
              </option>
            ))}
          </select>
        </div>

        {/* Case Count */}
        <div className="space-y-2">
          <label htmlFor="caseCount" className="text-sm font-medium">
            Number of Cases <span className="text-destructive">*</span>
          </label>
          <input
            id="caseCount"
            type="number"
            min="1"
            value={caseCount}
            onChange={(e) => setCaseCount(Math.max(1, parseInt(e.target.value) || 1))}
            required
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Image Upload */}
        <div className="space-y-2">
          <label className="text-sm font-medium">
            Proof Image <span className="text-destructive">*</span>
          </label>

          {!imagePreview ? (
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-input bg-muted/20 p-8 transition-colors hover:bg-muted/30">
              <FileImage className="mb-2 h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Upload a photo as proof (JPEG, PNG, GIF, WebP)
              </p>
              <p className="text-xs text-muted-foreground">Max size: 5MB</p>
              <label className="mt-4 cursor-pointer">
                <span className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                  {isUploading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="h-4 w-4" />
                      Choose Image
                    </>
                  )}
                </span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  onChange={handleImageSelect}
                  disabled={isUploading}
                  className="hidden"
                />
              </label>
            </div>
          ) : (
            <div className="relative rounded-lg border bg-muted/20 p-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <img
                    src={imagePreview}
                    alt="Preview"
                    className="h-24 w-24 rounded-md object-cover"
                  />
                  <div>
                    <p className="text-sm font-medium">{imageFile?.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {imageFile && (imageFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                    {uploadedObjectKey && (
                      <p className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                        <CheckCircle className="h-3 w-3" />
                        Uploaded successfully
                      </p>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={clearImage}
                  className="rounded-full p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Notes */}
        <div className="space-y-2">
          <label htmlFor="notes" className="text-sm font-medium">
            Notes <span className="text-muted-foreground">(optional)</span>
          </label>
          <textarea
            id="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Add any additional notes about this submission..."
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Submit Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={!canSubmit || isSubmitting}
            className="flex min-w-[120px] items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Submitting...
              </>
            ) : (
              "Submit Case"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
