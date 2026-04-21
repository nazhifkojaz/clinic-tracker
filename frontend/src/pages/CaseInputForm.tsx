import {
	AlertCircle,
	CheckCircle,
	FileImage,
	Info,
	Loader2,
	Plus,
	Upload,
	X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MAX_PROOF_FILE_SIZE } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { departmentService } from "@/services/departments";
import { rotationService } from "@/services/rotations";
import { studentService } from "@/services/students";
import { submissionService } from "@/services/submissions";
import { useAuthStore } from "@/stores/authStore";
import type { Department, TaskCategory } from "@/types/department";
import type { ReviewerInfo, UploadUrlResponse } from "@/types/submission";

export default function CaseInputForm() {
	const { user } = useAuthStore();
	const navigate = useNavigate();

	// Form state
	const [departmentId, setDepartmentId] = useState("");
	const [taskCategoryId, setTaskCategoryId] = useState("");
	const [supervisorId, setSupervisorId] = useState("");
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
	const [supervisors, setSupervisors] = useState<ReviewerInfo[]>([]);
	const [academicSupervisor, setAcademicSupervisor] =
		useState<ReviewerInfo | null>(null);

	// UI state
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [isLoading, setIsLoading] = useState(true);
	const [isLoadingSupervisors, setIsLoadingSupervisors] = useState(false);
	const [error, setError] = useState("");
	const [success, setSuccess] = useState(false);

	// Fetch departments, current rotation, and academic supervisor on mount
	useEffect(() => {
		const initData = async () => {
			try {
				setIsLoading(true);
				const [deptsData, currentRotation, academicSvData] = await Promise.all([
					departmentService.list(),
					rotationService.getCurrent(),
					studentService.getAcademicSupervisor(),
				]);
				const activeDepts = deptsData.filter((d) => d.is_active);
				setDepartments(activeDepts);
				setAcademicSupervisor(academicSvData.supervisor);

				// Pre-select current rotation's department; dept-change effect handles fetching
				if (currentRotation) {
					setDepartmentId(currentRotation.department_id);
				}
			} catch {
				setError("Failed to load initial data");
			} finally {
				setIsLoading(false);
			}
		};
		initData();
	}, []);

	// Load categories and supervisors when department changes
	useEffect(() => {
		if (!departmentId) {
			setCategories([]);
			setSupervisors([]);
			setTaskCategoryId("");
			setSupervisorId("");
			return;
		}
		const loadDeptData = async () => {
			try {
				setIsLoadingSupervisors(true);
				const [cats, svs] = await Promise.all([
					departmentService.listCategories(departmentId),
					departmentService.listSupervisors(departmentId),
				]);
				setCategories(cats.filter((c) => c.is_active));
				setSupervisors(svs);
				setTaskCategoryId("");
				setSupervisorId("");
			} catch {
				setError("Failed to load department data");
			} finally {
				setIsLoadingSupervisors(false);
			}
		};
		loadDeptData();
	}, [departmentId]);

	const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (!file) return;

		const maxSizeMB = MAX_PROOF_FILE_SIZE / (1024 * 1024);
		if (file.size > MAX_PROOF_FILE_SIZE) {
			setError(`Image file must be less than ${maxSizeMB}MB`);
			return;
		}

		if (!file.type.startsWith("image/")) {
			setError("Please select an image file");
			return;
		}

		setImageFile(file);
		setError("");

		const previewUrl = URL.createObjectURL(file);
		setImagePreview(previewUrl);

		try {
			setIsUploading(true);

			const uploadData: UploadUrlResponse =
				await submissionService.getUploadUrl({
					filename: file.name,
					content_type: file.type,
				});

			const uploadResponse = await fetch(uploadData.upload_url, {
				method: "PUT",
				body: file,
				headers: { "Content-Type": file.type },
			});

			if (!uploadResponse.ok) throw new Error("Failed to upload image");

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

	// Cleanup object URL on unmount or when imagePreview changes
	useEffect(() => {
		return () => {
			if (imagePreview) URL.revokeObjectURL(imagePreview);
		};
	}, [imagePreview]);

	const clearImage = () => {
		setImageFile(null);
		setImagePreview("");
		setUploadedObjectKey("");
		if (imagePreview) URL.revokeObjectURL(imagePreview);
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError("");

		if (!departmentId || !taskCategoryId || !supervisorId) {
			setError("Please select department, task category, and supervisor");
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
				target_supervisor_id: supervisorId,
				task_category_id: taskCategoryId,
				case_count: caseCount,
				proof_key: uploadedObjectKey,
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
		setSupervisorId("");
		setCaseCount(1);
		setNotes("");
		clearImage();
		setSuccess(false);
		setError("");
	};

	const canSubmit =
		departmentId &&
		taskCategoryId &&
		supervisorId &&
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
					<h2 className="text-xl font-semibold">
						Case Submitted Successfully!
					</h2>
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
						<span className="font-medium">
							{user?.institutional_id || "N/A"}
						</span>
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

				{/* Supervisor Selection */}
				<div className="space-y-2">
					<label htmlFor="supervisor" className="text-sm font-medium">
						Assigned Supervisor <span className="text-destructive">*</span>
					</label>
					<select
						id="supervisor"
						value={supervisorId}
						onChange={(e) => setSupervisorId(e.target.value)}
						required
						disabled={!departmentId || isLoadingSupervisors}
						className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
					>
						<option value="">
							{isLoadingSupervisors
								? "Loading supervisors..."
								: departmentId
									? supervisors.length === 0
										? "No supervisors assigned to this department"
										: "Select supervisor"
									: "Select department first"}
						</option>
						{supervisors.map((sv) => (
							<option key={sv.id} value={sv.id}>
								{sv.full_name}
							</option>
						))}
					</select>

					{/* Academic supervisor notice */}
					<div
						className={cn(
							"flex items-start gap-2 rounded-md p-3 text-sm",
							academicSupervisor
								? "bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400"
								: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400",
						)}
					>
						<Info className="mt-0.5 h-4 w-4 shrink-0" />
						{academicSupervisor ? (
							<span>
								Your academic supervisor (
								<span className="font-medium">
									{academicSupervisor.full_name}
								</span>
								) will be notified of this submission.
							</span>
						) : (
							<span>
								No academic supervisor assigned. Consider contacting admin.
							</span>
						)}
					</div>
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
							{departmentId
								? "Select task category"
								: "Select department first"}
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
						onChange={(e) =>
							setCaseCount(Math.max(1, parseInt(e.target.value) || 1))
						}
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
							<p className="text-xs text-muted-foreground">Max size: {MAX_PROOF_FILE_SIZE / (1024 * 1024)}MB</p>
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
										loading="lazy"
										decoding="async"
										className="h-24 w-24 rounded-md object-cover"
									/>
									<div>
										<p className="text-sm font-medium">{imageFile?.name}</p>
										<p className="text-xs text-muted-foreground">
											{imageFile &&
												(imageFile.size / 1024 / 1024).toFixed(2)}{" "}
											MB
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
