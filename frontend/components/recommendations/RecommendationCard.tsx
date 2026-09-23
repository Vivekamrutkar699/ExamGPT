import React from "react";
import {
  PenTool,
  Play,
  ClipboardCheck,
  BookOpen,
  CheckCircle,
  Loader2,
  Sparkles,
  Award,
  Layers,
  HelpCircle,
} from "lucide-react";
import { TopicRecommendation, RecommendationAction } from "./types";
import { PriorityBadge } from "../exam-intelligence/PriorityBadge";

interface RecommendationCardProps {
  recommendation: TopicRecommendation;
  onExecuteAction: (topicId: string) => void;
  isExecuting?: boolean;
}

export const RecommendationCard: React.FC<RecommendationCardProps> = ({
  recommendation,
  onExecuteAction,
  isExecuting = false,
}) => {
  const {
    topic_id,
    canonical_label,
    unit_tag,
    priority_label,
    priority_score,
    student_mastery,
    weakness_score,
    evaluation_count,
    recommended_action,
    recommendation_reason,
  } = recommendation;

  const hasMastery = student_mastery !== null && student_mastery !== undefined;
  const masteryPercent = hasMastery ? Math.round(student_mastery * 100) : null;
  const weaknessPercent = weakness_score !== null && weakness_score !== undefined
    ? Math.round(weakness_score * 100)
    : (hasMastery ? Math.max(0, 100 - (masteryPercent ?? 0)) : null);

  const getActionConfig = (action: RecommendationAction) => {
    switch (action) {
      case "PRACTICE":
        return {
          label: "Practice Now",
          description: "Targeted Question Practice",
          icon: PenTool,
          badgeBg: "bg-rose-500/10 text-rose-300 border-rose-500/20",
          buttonBg: "bg-gradient-to-r from-rose-600 to-pink-600 hover:from-rose-500 hover:to-pink-500 text-white",
        };
      case "QUIZ":
        return {
          label: "Take Topic Quiz",
          description: "Topic-Focused Multiple Choice",
          icon: Play,
          badgeBg: "bg-purple-500/10 text-purple-300 border-purple-500/20",
          buttonBg: "bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white",
        };
      case "ASSESS":
        return {
          label: "Take Diagnostic Quiz",
          description: "Diagnostic Baseline Assessment",
          icon: ClipboardCheck,
          badgeBg: "bg-amber-500/10 text-amber-300 border-amber-500/20",
          buttonBg: "bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white",
        };
      case "REVIEW":
        return {
          label: "Review Concepts",
          description: "Grounded Study Chunks & Notes",
          icon: BookOpen,
          badgeBg: "bg-sky-500/10 text-sky-300 border-sky-500/20",
          buttonBg: "bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500 text-white",
        };
      case "MAINTAIN":
        return {
          label: "Review & Maintain",
          description: "Quick Revision & Refresher",
          icon: CheckCircle,
          badgeBg: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
          buttonBg: "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white",
        };
      default:
        return {
          label: "Start Activity",
          description: "Learning Action",
          icon: Sparkles,
          badgeBg: "bg-purple-500/10 text-purple-300 border-purple-500/20",
          buttonBg: "bg-purple-600 hover:bg-purple-500 text-white",
        };
    }
  };

  const actionConfig = getActionConfig(recommended_action);
  const ActionIcon = actionConfig.icon;

  return (
    <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 hover:border-white/10 rounded-2xl p-5 sm:p-6 transition-all space-y-4">
      {/* Top Header: Topic Title, Unit, and Priority Badge */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center space-x-2 flex-wrap gap-y-1">
            <h3 className="font-bold text-base text-slate-100">{canonical_label}</h3>
            {unit_tag && (
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-300 border border-purple-500/20 flex items-center space-x-1">
                <Layers className="h-2.5 w-2.5" />
                <span>{unit_tag}</span>
              </span>
            )}
            <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-md border ${actionConfig.badgeBg}`}>
              {recommended_action}
            </span>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed pt-1">
            {recommendation_reason}
          </p>
        </div>

        <div className="shrink-0 self-start sm:self-auto">
          <PriorityBadge label={priority_label} score={priority_score} />
        </div>
      </div>

      {/* Metrics Row: Mastery, Weakness, and Evaluation History */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 bg-[#111115] border border-white/5 rounded-xl text-xs">
        {/* Student Mastery */}
        <div className="space-y-1">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Student Mastery</div>
          {hasMastery ? (
            <div>
              <div className="text-sm font-bold text-slate-200 flex items-center space-x-1.5">
                <span className={masteryPercent! >= 75 ? "text-emerald-400" : masteryPercent! >= 50 ? "text-indigo-300" : "text-rose-400"}>
                  {masteryPercent}%
                </span>
                <span className="text-[10px] font-normal text-slate-500">mastery</span>
              </div>
              <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden mt-1.5 border border-white/5">
                <div
                  className={`h-full ${
                    masteryPercent! >= 75
                      ? "bg-emerald-500"
                      : masteryPercent! >= 50
                      ? "bg-indigo-500"
                      : "bg-rose-500"
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, masteryPercent!))}%` }}
                />
              </div>
            </div>
          ) : (
            <div className="text-slate-400 flex items-center space-x-1 text-[11px] pt-0.5">
              <HelpCircle className="h-3 w-3 text-amber-400 shrink-0" />
              <span>No attempts recorded</span>
            </div>
          )}
        </div>

        {/* Weakness Score */}
        <div className="space-y-1">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Demonstrated Weakness</div>
          {weaknessPercent !== null ? (
            <div className="text-sm font-bold text-slate-200">
              <span className={weaknessPercent > 50 ? "text-rose-400" : "text-slate-300"}>
                {weaknessPercent}%
              </span>
              <span className="text-[10px] font-normal text-slate-500 ml-1.5">
                {weaknessPercent > 50 ? "High weakness" : "Manageable"}
              </span>
            </div>
          ) : (
            <div className="text-slate-400 text-[11px] pt-0.5">
              <span>Assessment pending</span>
            </div>
          )}
        </div>

        {/* Evaluation History */}
        <div className="space-y-1">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Evaluation Records</div>
          <div className="text-sm font-bold text-slate-200 flex items-center space-x-1.5">
            <Award className="h-3.5 w-3.5 text-purple-400" />
            <span>{evaluation_count}</span>
            <span className="text-[10px] font-normal text-slate-500">
              {evaluation_count === 1 ? "evaluated answer" : "evaluated answers"}
            </span>
          </div>
        </div>
      </div>

      {/* Action Footer Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="text-[11px] text-slate-400 flex items-center space-x-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-purple-400" />
          <span>Recommended next step: <strong className="text-slate-200 font-semibold">{actionConfig.description}</strong></span>
        </div>

        <button
          onClick={() => onExecuteAction(topic_id)}
          disabled={isExecuting}
          className={`py-2.5 px-5 rounded-xl font-bold text-xs flex items-center justify-center space-x-2 transition-all shadow-md active:scale-95 disabled:opacity-50 shrink-0 ${actionConfig.buttonBg}`}
        >
          {isExecuting ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Preparing Action...</span>
            </>
          ) : (
            <>
              <ActionIcon className="h-3.5 w-3.5" />
              <span>{actionConfig.label}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
