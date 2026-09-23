import React, { useState, useEffect, useCallback } from "react";
import {
  Compass,
  Sparkles,
  AlertTriangle,
  RefreshCw,
  Filter,
  HelpCircle,
  Layers,
} from "lucide-react";
import {
  SubjectRecommendationsResponse,
  TopicActionResponse,
} from "./types";
import { RecommendationCard } from "./RecommendationCard";
import { RecommendationActionPanel } from "./RecommendationActionPanel";
import { api } from "../../services/api";

interface RecommendationListProps {
  subjectId: string;
  onNavigateToChat?: (query: string) => void;
  onNavigateToExamPriority?: () => void;
}

export const RecommendationList: React.FC<RecommendationListProps> = ({
  subjectId,
  onNavigateToChat,
  onNavigateToExamPriority,
}) => {
  const [data, setData] = useState<SubjectRecommendationsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState<string>("all");

  // Action execution state
  const [executingTopicId, setExecutingTopicId] = useState<string | null>(null);
  const [actionResponse, setActionResponse] = useState<TopicActionResponse | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchRecommendations = useCallback(
    async (sid: string) => {
      setLoading(true);
      setError(null);
      setActionError(null);
      try {
        const res: SubjectRecommendationsResponse = await api.getSubjectRecommendations(sid);
        setData(res);
      } catch (err: unknown) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load personalized recommendations. Please try again."
        );
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    let isMounted = true;
    if (!subjectId) return;

    api.getSubjectRecommendations(subjectId)
      .then((res: SubjectRecommendationsResponse) => {
        if (isMounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load personalized recommendations. Please try again."
          );
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [subjectId]);

  const handleExecuteAction = async (topicId: string) => {
    setExecutingTopicId(topicId);
    setActionError(null);

    try {
      const resp: TopicActionResponse = await api.executeTopicAction(subjectId, topicId);
      setActionResponse(resp);
    } catch (err: unknown) {
      setActionError(
        err instanceof Error
          ? err.message
          : "Failed to execute learning action for this topic."
      );
    } finally {
      setExecutingTopicId(null);
    }
  };

  // --- SKELETON LOADING STATE ---
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse space-y-2">
          <div className="h-7 w-64 bg-white/5 rounded-lg" />
          <div className="h-4 w-96 bg-white/5 rounded-lg" />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-24 bg-white/[0.02] border border-white/5 rounded-2xl animate-pulse"
            />
          ))}
        </div>

        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-40 bg-white/[0.02] border border-white/5 rounded-2xl animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  // --- ERROR STATE ---
  if (error) {
    return (
      <div className="backdrop-blur-md bg-rose-500/10 border border-rose-500/20 rounded-2xl p-8 text-center space-y-3">
        <AlertTriangle className="h-8 w-8 text-rose-400 mx-auto" />
        <h3 className="font-bold text-sm text-rose-200">
          Unable to Load Learning Recommendations
        </h3>
        <p className="text-xs text-rose-300/80 max-w-md mx-auto">{error}</p>
        <button
          onClick={() => fetchRecommendations(subjectId)}
          className="mt-3 inline-flex items-center space-x-1.5 px-4 py-2 bg-white/10 hover:bg-white/15 text-xs font-semibold rounded-xl border border-white/10 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Retry Loading</span>
        </button>
      </div>
    );
  }

  // --- EMPTY STATE ---
  if (!data || data.recommendations.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center space-x-2.5">
            <Compass className="h-6 w-6 text-purple-400" />
            <span>Personalized Learning Actions</span>
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Deterministic recommendations combining Exam Priority, marks weight, and student mastery.
          </p>
        </div>

        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-10 text-center space-y-3">
          <Layers className="h-10 w-10 text-slate-500 mx-auto" />
          <h3 className="font-bold text-slate-200">No Learning Recommendations Yet</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Exam intelligence has not cataloged topics for this course yet. Ingest previous-year question papers in the Subject Vault to automatically generate topic priorities and revision recommendations.
          </p>
        </div>
      </div>
    );
  }

  // Summary Metrics
  const total = data.total_recommendations;
  const practiceCount = data.recommendations.filter((r) => r.recommended_action === "PRACTICE").length;
  const quizCount = data.recommendations.filter((r) => r.recommended_action === "QUIZ").length;
  const assessCount = data.recommendations.filter((r) => r.recommended_action === "ASSESS").length;
  const reviewCount = data.recommendations.filter((r) => r.recommended_action === "REVIEW").length;
  const maintainCount = data.recommendations.filter((r) => r.recommended_action === "MAINTAIN").length;

  const filteredRecommendations =
    actionFilter === "all"
      ? data.recommendations
      : data.recommendations.filter(
          (r) => r.recommended_action.toLowerCase() === actionFilter.toLowerCase()
        );

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold flex items-center space-x-2.5">
            <Compass className="h-6 w-6 text-purple-400" />
            <span className="bg-gradient-to-r from-purple-300 via-indigo-200 to-slate-100 bg-clip-text text-transparent">
              Personalized Learning Actions
            </span>
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Targeted study recommendations derived deterministically from Exam Priority and your mastery history.
          </p>
        </div>

        <div className="flex items-center space-x-2 self-start sm:self-auto">
          {onNavigateToExamPriority && (
            <button
              onClick={onNavigateToExamPriority}
              className="py-2 px-3.5 bg-white/5 hover:bg-white/10 text-xs font-semibold rounded-xl border border-white/5 flex items-center space-x-1.5 text-slate-300 transition-colors"
            >
              <Sparkles className="h-3.5 w-3.5 text-purple-400" />
              <span>View Exam Priority</span>
            </button>
          )}

          <button
            onClick={() => fetchRecommendations(subjectId)}
            className="py-2 px-3.5 bg-white/5 hover:bg-white/10 text-xs font-semibold rounded-xl border border-white/5 flex items-center space-x-1.5 transition-colors"
            title="Refresh recommendations"
          >
            <RefreshCw className="h-3.5 w-3.5 text-slate-400" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Action Execution Error Banner */}
      {actionError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-xs text-red-300 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{actionError}</span>
          </div>
          <button onClick={() => setActionError(null)} className="hover:text-slate-100 font-semibold">
            Dismiss
          </button>
        </div>
      )}

      {/* No Student Data Notice Banner (Mode B) */}
      {!data.has_student_data && (
        <div className="p-4 bg-gradient-to-r from-amber-500/10 via-purple-500/10 to-indigo-500/10 border border-amber-500/20 rounded-2xl flex items-start space-x-3 text-xs">
          <HelpCircle className="h-4.5 w-4.5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold text-amber-200">
              Exam/PYQ Evidence Mode (Assessment Recommended)
            </span>
            <p className="text-slate-300 leading-relaxed">
              These initial recommendations are ranked by historical exam frequency and marks weight.
              Take diagnostic assessment quizzes or submit practice answers to adapt recommendations to your verified mastery.
            </p>
          </div>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {/* Total Actions */}
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-5">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            Total Next Actions
          </div>
          <div className="text-2xl font-bold text-slate-100 mt-2">{total}</div>
          <div className="text-[11px] text-slate-400 mt-1">Topics evaluated across syllabus</div>
        </div>

        {/* Immediate Practice & Quiz */}
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-5">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            High Priority Actions
          </div>
          <div className="text-2xl font-bold text-rose-400 mt-2">
            {practiceCount + quizCount}
            <span className="text-sm font-normal text-slate-400 ml-1.5">
              ({practiceCount} practice, {quizCount} quiz)
            </span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">High-impact topics needing practice</div>
        </div>

        {/* Diagnostic Assessments */}
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-5">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            Diagnostic Assessments
          </div>
          <div className="text-2xl font-bold text-amber-400 mt-2">{assessCount}</div>
          <div className="text-[11px] text-slate-400 mt-1">Topics requiring baseline assessment</div>
        </div>

        {/* Personalization Status */}
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-5">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            Adaptive Personalization
          </div>
          <div className="text-sm font-bold text-indigo-300 mt-2 flex items-center space-x-1.5">
            {data.has_student_data ? (
              <span className="text-emerald-400 font-semibold">Mastery Active</span>
            ) : (
              <span className="text-amber-400 font-semibold">PYQ History Baseline</span>
            )}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {data.has_student_data
              ? "Recommendations adapt as you practice"
              : "Complete quizzes to tailor recommendations"}
          </div>
        </div>
      </div>

      {/* Action Filters Tabs */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-2 border-b border-white/5">
        <span className="text-xs text-slate-500 font-semibold flex items-center space-x-1 pr-2">
          <Filter className="h-3.5 w-3.5" />
          <span>Action:</span>
        </span>

        {[
          { id: "all", label: "All Actions", count: total },
          { id: "practice", label: "Practice", count: practiceCount },
          { id: "quiz", label: "Quizzes", count: quizCount },
          { id: "assess", label: "Assess", count: assessCount },
          { id: "review", label: "Review", count: reviewCount },
          { id: "maintain", label: "Maintain", count: maintainCount },
        ].map((tab) => {
          const active = actionFilter === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActionFilter(tab.id)}
              className={`py-1.5 px-3 rounded-xl text-xs font-semibold transition-all shrink-0 flex items-center space-x-1.5 border ${
                active
                  ? "bg-purple-600/20 text-purple-300 border-purple-500/30"
                  : "bg-white/[0.02] text-slate-400 border-white/5 hover:border-white/10 hover:text-slate-200"
              }`}
            >
              <span>{tab.label}</span>
              <span className="text-[10px] opacity-70 font-mono">({tab.count})</span>
            </button>
          );
        })}
      </div>

      {/* Recommendations Cards List */}
      <div className="space-y-4">
        {filteredRecommendations.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs bg-white/[0.01] border border-white/5 rounded-2xl">
            No topics match the selected &quot;{actionFilter}&quot; filter.
          </div>
        ) : (
          filteredRecommendations.map((rec) => (
            <RecommendationCard
              key={rec.topic_id}
              recommendation={rec}
              onExecuteAction={handleExecuteAction}
              isExecuting={executingTopicId === rec.topic_id}
            />
          ))
        )}
      </div>

      {/* Action Execution Panel Modal */}
      {actionResponse && (
        <RecommendationActionPanel
          actionResponse={actionResponse}
          onClose={() => setActionResponse(null)}
          onRefreshRecommendations={() => fetchRecommendations(subjectId)}
          onNavigateToChat={onNavigateToChat}
        />
      )}
    </div>
  );
};
