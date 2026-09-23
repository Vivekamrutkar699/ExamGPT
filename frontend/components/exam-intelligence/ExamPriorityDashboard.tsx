import React, { useState, useEffect } from "react";
import {
  Sparkles,
  AlertTriangle,
  Info,
  Layers,
  RefreshCw,
  Filter,
  Compass,
} from "lucide-react";
import { api } from "../../services/api";
import { SubjectExamPriorityResponse } from "./types";
import { TopicPriorityCard } from "./TopicPriorityCard";

interface ExamPriorityDashboardProps {
  subjectId: string;
  onNavigateToRecommendations?: () => void;
}

export const ExamPriorityDashboard: React.FC<ExamPriorityDashboardProps> = ({
  subjectId,
  onNavigateToRecommendations,
}) => {
  const [data, setData] = useState<SubjectExamPriorityResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filterLabel, setFilterLabel] = useState<string>("all");

  const fetchPriorityData = (sid: string) => {
    setLoading(true);
    setError(null);
    api.getSubjectExamPriority(sid)
      .then((res) => {
        setData(res);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load exam priority intelligence.");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    let ignore = false;
    if (!subjectId) return;

    api.getSubjectExamPriority(subjectId)
      .then((res) => {
        if (!ignore) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Failed to load exam priority intelligence.");
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [subjectId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse space-y-2">
          <div className="h-7 w-64 bg-white/5 rounded-lg" />
          <div className="h-4 w-96 bg-white/5 rounded-lg" />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-white/[0.02] border border-white/5 rounded-2xl animate-pulse" />
          ))}
        </div>

        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 bg-white/[0.02] border border-white/5 rounded-2xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="backdrop-blur-md bg-rose-500/10 border border-rose-500/20 rounded-2xl p-6 text-center space-y-3">
        <AlertTriangle className="h-8 w-8 text-rose-400 mx-auto" />
        <h3 className="font-bold text-sm text-rose-200">Unable to load Exam Priority data</h3>
        <p className="text-xs text-rose-300/80">{error}</p>
        <button
          onClick={() => fetchPriorityData(subjectId)}
          className="mt-2 inline-flex items-center space-x-1.5 px-4 py-2 bg-white/10 hover:bg-white/15 text-xs font-semibold rounded-lg border border-white/10 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  if (!data || data.topics.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center space-x-2">
            <Sparkles className="h-6 w-6 text-purple-400" />
            <span>Exam Focus & Priority Intelligence</span>
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Deterministic previous-year question frequency, marks weight, and student mastery analysis.
          </p>
        </div>

        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-10 text-center space-y-3">
          <Layers className="h-10 w-10 text-slate-500 mx-auto" />
          <h3 className="font-bold text-slate-200">No Canonical Topics Found</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            No exam topics are recorded for this course yet. Ingest examination papers in the Subject Vault to automatically index PYQ frequency and syllabus focus.
          </p>
        </div>
      </div>
    );
  }

  const filteredTopics = filterLabel === "all"
    ? data.topics
    : data.topics.filter((t) => t.priority_label.toLowerCase() === filterLabel.toLowerCase());

  const highPriorityCount = data.topics.filter(
    (t) => t.priority_label === "Very High" || t.priority_label === "High"
  ).length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold flex items-center space-x-2.5">
            <Sparkles className="h-6 w-6 text-purple-400" />
            <span className="bg-gradient-to-r from-purple-300 via-indigo-200 to-slate-100 bg-clip-text text-transparent">
              Exam Focus & Priority Intelligence
            </span>
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Explainable revision priority derived from previous-year exam frequency, marks weight, and student mastery.
          </p>
        </div>

        <div className="flex items-center space-x-2 self-start sm:self-auto">
          {onNavigateToRecommendations && (
            <button
              onClick={onNavigateToRecommendations}
              className="py-2 px-3.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold rounded-xl flex items-center space-x-1.5 transition-all shadow-sm"
            >
              <Compass className="h-3.5 w-3.5" />
              <span>Recommended Study Actions</span>
            </button>
          )}

          <button
            onClick={() => fetchPriorityData(subjectId)}
            className="py-2 px-3.5 bg-white/5 hover:bg-white/10 text-xs font-semibold rounded-xl border border-white/5 flex items-center space-x-1.5 transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5 text-slate-400" />
            <span>Refresh Analysis</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-5">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            Total Syllabus Topics
          </div>
          <div className="text-2xl font-bold text-slate-100 mt-2">{data.total_topics}</div>
          <div className="text-[11px] text-slate-400 mt-1">
            Canonical topics analyzed across papers
          </div>
        </div>

        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-5">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            High-Impact Focus
          </div>
          <div className="text-2xl font-bold text-rose-400 mt-2">
            {highPriorityCount} <span className="text-sm font-normal text-slate-400">/ {data.total_topics}</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            Topics marked Very High or High Priority
          </div>
        </div>

        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-5">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            Student Personalization
          </div>
          <div className="text-base font-bold text-indigo-300 mt-2 flex items-center space-x-1.5">
            {data.has_student_data ? (
              <span className="text-emerald-400 font-semibold text-sm">Mode A (Mastery Active)</span>
            ) : (
              <span className="text-amber-400 font-semibold text-sm">Mode B (PYQ History Only)</span>
            )}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {data.has_student_data
              ? "Scores adapted to your evaluated weaknesses"
              : "Submit essay evaluations to adapt scores"}
          </div>
        </div>

        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-5">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            Unresolved PYQs
          </div>
          <div className="text-2xl font-bold text-slate-200 mt-2">
            {data.unresolved_occurrences_count}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {data.unresolved_occurrences_count > 0
              ? "Ambiguous questions excluded from topics"
              : "All PYQs safely resolved to topics"}
          </div>
        </div>
      </div>

      {/* Mode B Notice Banner (if no student data) */}
      {!data.has_student_data && (
        <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-xs flex items-start space-x-3 text-indigo-300">
          <Info className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-indigo-200">
              Exam Focus is currently calculated using previous-year exam patterns alone (Mode B).
            </div>
            <div className="text-slate-400 mt-0.5">
              Submit practice answers in the Quizzes & Evaluations section to dynamically re-score topics based on your personal weaknesses.
            </div>
          </div>
        </div>
      )}

      {/* Filtering Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 sm:pb-0">
          <span className="text-xs text-slate-500 mr-2 flex items-center space-x-1">
            <Filter className="h-3 w-3" />
            <span>Priority Filter:</span>
          </span>
          {[
            { key: "all", label: `All (${data.topics.length})` },
            { key: "very high", label: "Very High" },
            { key: "high", label: "High" },
            { key: "medium", label: "Medium" },
            { key: "low", label: "Low" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilterLabel(tab.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                filterLabel === tab.key
                  ? "bg-purple-600/25 text-purple-300 border border-purple-500/40"
                  : "bg-white/5 text-slate-400 hover:text-slate-200 border border-transparent"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="text-xs text-slate-500 self-end sm:self-auto">
          Showing {filteredTopics.length} of {data.topics.length} topics
        </div>
      </div>

      {/* Topics List */}
      <div className="space-y-4">
        {filteredTopics.map((topic, index) => (
          <TopicPriorityCard
            key={topic.topic_id}
            topic={topic}
            rank={index + 1}
          />
        ))}
      </div>
    </div>
  );
};
