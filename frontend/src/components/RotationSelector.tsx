import { useCallback, useEffect, useState } from "react";
import type { Rotation } from "@/types/rotation";
import type { Department } from "@/types/department";
import { rotationService } from "@/services/rotations";
import { departmentService } from "@/services/departments";
import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  RefreshCw,
} from "lucide-react";

interface RotationSelectorProps {
  onRotationChange?: (departmentId: string | null) => void;
}

export default function RotationSelector({
  onRotationChange,
}: RotationSelectorProps) {
  const [currentRotation, setCurrentRotation] = useState<Rotation | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isChanging, setIsChanging] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError("");
      const [rotationData, deptsData] = await Promise.all([
        rotationService.getCurrent(),
        departmentService.list(),
      ]);
      setCurrentRotation(rotationData);
      setDepartments(deptsData.filter((d) => d.is_active));
      if (rotationData && onRotationChange) {
        onRotationChange(rotationData.department_id);
      }
    } catch {
      setError("Failed to load rotation data");
    } finally {
      setIsLoading(false);
    }
  }, [onRotationChange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newDeptId = e.target.value;
    const currentDeptId = currentRotation?.department_id;
    const newDept = departments.find((d) => d.id === newDeptId);
    const currentDept = departments.find((d) => d.id === currentDeptId);

    if (newDeptId === currentDeptId) return;

    const confirmMsg =
      currentDept && newDept
        ? `Switch rotation from ${currentDept.name} to ${newDept.name}?`
        : `Set rotation to ${newDept?.name || "this department"}?`;

    if (!window.confirm(confirmMsg)) {
      e.target.value = currentDeptId || "";
      return;
    }

    try {
      setIsChanging(true);
      setError("");
      setSuccess("");
      const newRotation = await rotationService.set({ department_id: newDeptId });
      setCurrentRotation(newRotation);
      setSuccess("Rotation updated successfully");
      onRotationChange?.(newDeptId);
      setTimeout(() => setSuccess(""), 3000);
    } catch {
      setError("Failed to update rotation");
    } finally {
      setIsChanging(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <RefreshCw className="h-4 w-4 animate-spin" />
        <span>Loading rotation...</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <label htmlFor="rotation-select" className="text-sm font-medium">
        Current Rotation
      </label>
      <div className="relative">
        <select
          id="rotation-select"
          value={currentRotation?.department_id || ""}
          onChange={handleChange}
          disabled={isChanging || departments.length === 0}
          className="w-full appearance-none rounded-md border border-input bg-background px-3 py-2 pr-8 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="" disabled>
            {currentRotation
              ? "Select a department to change rotation"
              : "Select your current department rotation"}
          </option>
          {departments.map((dept) => (
            <option key={dept.id} value={dept.id}>
              {dept.name}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="flex items-center gap-2 rounded-md bg-green-500/10 p-2 text-sm text-green-600 dark:text-green-400">
          <CheckCircle className="h-4 w-4" />
          <span>{success}</span>
        </div>
      )}

      {!currentRotation && !isLoading && departments.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Please select your current department rotation to continue.
        </p>
      )}

      {departments.length === 0 && !isLoading && (
        <p className="text-xs text-muted-foreground">
          No active departments available. Contact an administrator.
        </p>
      )}
    </div>
  );
}
