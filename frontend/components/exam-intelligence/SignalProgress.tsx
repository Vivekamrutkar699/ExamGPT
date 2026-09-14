import React from "react";

interface SignalProgressProps {
  label: string;
  value: number | null;
  displayLabel?: string;
  colorScheme?: "purple" | "indigo" | "emerald" | "amber" | "rose" | "slate";
  isUnavailable?: boolean;
  unavailableText?: string;
  subtext?: string;
}

export const SignalProgress: React.FC<SignalProgressProps> = ({
  label,
  value,
  displayLabel,
  colorScheme = "purple",
  isUnavailable = false,
  unavailableText = "No evaluated answers yet",
  subtext,
}) => {
  const colorMap = {
    purple: "bg-purple-500",
    indigo: "bg-indigo-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    rose: "bg-rose-500",
    slate: "bg-slate-500",
  };

  const barColor = colorMap[colorScheme] || "bg-purple-500";
  const hasData = !isUnavailable && value !== null && !isNaN(value);
  const clampedPercent = hasData ? Math.round(Math.max(0, Math.min(1, value!)) * 100) : 0;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400 font-medium">{label}</span>
        {hasData ? (
          <span className="text-slate-200 font-semibold text-[11px]">
            {displayLabel ?? `${clampedPercent}%`}
          </span>
        ) : (
          <span className="text-slate-500 italic text-[11px]">
            {unavailableText}
          </span>
        )}
      </div>

      <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden border border-white/5">
        {hasData ? (
          <div
            className={`${barColor} h-full rounded-full transition-all duration-300`}
            style={{ width: `${clampedPercent}%` }}
          />
        ) : (
          <div className="bg-white/5 h-full w-full" />
        )}
      </div>

      {subtext && (
        <p className="text-[10px] text-slate-500 leading-tight">{subtext}</p>
      )}
    </div>
  );
};
