import React, { useState } from "react";
import { 
  BookOpen, 
  FileText, 
  Target, 
  Sparkles, 
  ChevronDown, 
  ChevronUp, 
} from "lucide-react";
import { ExamPriorityTopic } from "./types";
import { PriorityBadge } from "./PriorityBadge";
import { SignalProgress } from "./SignalProgress";

interface TopicPriorityCardProps {
  topic: ExamPriorityTopic;
  rank: number;
}

export const TopicPriorityCard: React.FC<TopicPriorityCardProps> = ({ topic, rank }) => {
  const [expanded, setExpanded] = useState(false);
  const isZeroPYQ = topic.total_occurrences === 0;
  const hasMastery = topic.has_student_data && topic.student_mastery !== null;

  return (
    <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 hover:border-white/10 rounded-2xl p-5 sm:p-6 transition-all">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-start space-x-3">
          <span className="flex items-center justify-center h-7 w-7 rounded-lg bg-white/5 text-xs font-mono font-bold text-slate-400 shrink-0 border border-white/5">
            #{rank}
          </span>
          <div>
            <div className="flex items-center space-x-2 flex-wrap gap-y-1">
              <h3 className="font-bold text-base text-slate-100">{topic.canonical_label}</h3>
              {topic.unit_tag && (
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-300 border border-purple-500/20">
                  {topic.unit_tag}
                </span>
              )}
              {isZeroPYQ && (
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-md bg-slate-500/10 text-slate-400 border border-slate-500/20">
                  Syllabus Study (0 PYQ)
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3 self-end sm:self-auto shrink-0">
          <PriorityBadge label={topic.priority_label} score={topic.priority_score} />
        </div>
      </div>

      {/* Signal Bars Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 py-3 px-4 bg-[#111115] border border-white/5 rounded-xl mb-4">
        <SignalProgress
          label="PYQ Frequency"
          value={isZeroPYQ ? 0 : topic.frequency_score}
          displayLabel={
            isZeroPYQ
              ? "0 occurrences"
              : `${topic.total_occurrences} times (${topic.distinct_papers} papers)`
          }
          colorScheme="purple"
          subtext={`Normalized score: ${topic.frequency_score.toFixed(3)}`}
        />

        <SignalProgress
          label="Marks Weight"
          value={isZeroPYQ ? 0 : topic.marks_score}
          displayLabel={
            isZeroPYQ
              ? "No exam marks"
              : `${topic.avg_marks.toFixed(1)} avg / ${topic.max_marks} max`
          }
          colorScheme="indigo"
          subtext={`Normalized score: ${topic.marks_score.toFixed(3)}`}
        />

        <SignalProgress
          label="Student Mastery"
          value={hasMastery ? topic.student_mastery : null}
          displayLabel={
            hasMastery
              ? `${Math.round(topic.student_mastery! * 100)}% (${topic.evaluation_count} eval)`
              : undefined
          }
          colorScheme={hasMastery && topic.student_mastery! < 0.5 ? "rose" : "emerald"}
          isUnavailable={!hasMastery}
          unavailableText="No evaluated answers yet"
          subtext={
            hasMastery && topic.weakness_score !== null
              ? `Weakness: ${(topic.weakness_score * 100).toFixed(0)}%`
              : "Mode B / C applied"
          }
        />
      </div>

      {/* Primary Revision Recommendation Banner */}
      <div className="p-3.5 bg-gradient-to-r from-purple-500/10 to-indigo-500/10 border border-purple-500/20 rounded-xl text-xs flex items-start space-x-2.5">
        <Sparkles className="h-4 w-4 text-purple-400 shrink-0 mt-0.5" />
        <div className="flex-1">
          <span className="font-semibold text-purple-200">Revision Focus: </span>
          <span className="text-slate-300">{topic.recommendation}</span>
        </div>
      </div>

      {/* Accordion Toggle for Detailed Evidence Rationales */}
      <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[11px] font-medium text-slate-400 hover:text-purple-300 flex items-center space-x-1.5 transition-colors"
        >
          <span>{expanded ? "Hide Explainable Evidence" : "View Explainable Evidence"}</span>
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>

        <span className="text-[10px] text-slate-500">
          Exam Focus Score: <span className="font-mono font-semibold text-slate-300">{topic.priority_score.toFixed(3)}</span>
        </span>
      </div>

      {expanded && (
        <div className="mt-3 p-3.5 bg-white/[0.02] border border-white/5 rounded-xl space-y-2 text-xs">
          <div className="flex items-start space-x-2">
            <BookOpen className="h-3.5 w-3.5 text-purple-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-300">Frequency Evidence: </span>
              <span className="text-slate-400">{topic.evidence.frequency_rationale}</span>
            </div>
          </div>

          <div className="flex items-start space-x-2">
            <Target className="h-3.5 w-3.5 text-indigo-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-300">Marks Weight: </span>
              <span className="text-slate-400">{topic.evidence.marks_rationale}</span>
            </div>
          </div>

          <div className="flex items-start space-x-2">
            <FileText className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-300">Mastery Evidence: </span>
              <span className="text-slate-400">{topic.evidence.mastery_rationale}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
