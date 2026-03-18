import { useEffect, useState } from "react";

/**
 * Hook to read CSS custom properties (variables) that change with the theme.
 * Returns the color value as a string (e.g., "oklch(0.65 0.15 145)").
 */
export function useThemeColor(variableName: string): string {
	const [color, setColor] = useState(() => {
		// Initialize with a default value or read from computed style
		if (typeof window !== "undefined") {
			return (
				getComputedStyle(document.documentElement)
					.getPropertyValue(variableName)
					.trim() || ""
			);
		}
		return "";
	});

	useEffect(() => {
		if (typeof window === "undefined") return;

		const updateColor = () => {
			const computed = getComputedStyle(document.documentElement);
			setColor(computed.getPropertyValue(variableName).trim());
		};

		// Read initial value
		updateColor();

		// Listen for theme changes (when dark class is toggled)
		const observer = new MutationObserver(() => {
			updateColor();
		});

		observer.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["class"],
		});

		return () => observer.disconnect();
	}, [variableName]);

	return color;
}

/**
 * Pre-configured hooks for common chart colors
 */
export function useSuccessColor(): string {
	return useThemeColor("--success");
}

export function useWarningColor(): string {
	return useThemeColor("--warning");
}

export function useDestructiveColor(): string {
	return useThemeColor("--destructive");
}

export function useMutedColor(): string {
	return useThemeColor("--muted");
}

export function usePrimaryColor(): string {
	return useThemeColor("--primary");
}

/**
 * Returns all chart status colors as an object
 */
export function useChartColors() {
	return {
		success: useSuccessColor(),
		warning: useWarningColor(),
		destructive: useDestructiveColor(),
		muted: useMutedColor(),
		primary: usePrimaryColor(),
	};
}
