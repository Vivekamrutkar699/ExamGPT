import React from "react";
import { PriorityLabel } from "./types";

interface PriorityBadgeProps {
  label: PriorityLabel;
  score?: number;
  className?: string;
}

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({
  label,
  score,
  className = "",
}) => {
  let badgeStyles = "bg-slate-500/15 text-slate-300 border-slate-500/30";
  let dotColor = "bg-slate-400";

  switch (label) {
    case "Very High":
      badgeStyles = "bg-rose-500/15 text-rose-300 border-rose-500/30";
      dotColor = "bg-rose-400";
      break;
    case "High":
      badgeStyles = "bg-amber-500/15 text-amber-300 border-amber-500/30";
      dotColor = "bg-amber-400";
      break;
    case "Medium":
      badgeStyles = "bg-indigo-500/15 text-indigo-300 border-indigo-500/30";
      dotColor = "bg-indigo-400";
      break;
    case "Low":
    default:
      badgeStyles = "bg-slate-500/15 text-slate-300 border-slate-500/30";
      dotColor = "bg-slate-400";
      break;
  }

  return (
    <span
      className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${badgeStyles} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
      <span>{label} Priority</span>
      {typeof score === "number" && (
        <span className="opacity-80 font-mono text-[11px]">
          ({score.toFixed(3)})
        </span>
      )}
    </span>
  );
};
