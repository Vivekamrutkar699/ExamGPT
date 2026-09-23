import React, { useState } from "react";
import {
  X,
  BookOpen,
  CheckCircle,
  AlertTriangle,
  Send,
  Loader2,
  HelpCircle,
  Award,
  MessageSquare,
} from "lucide-react";
import {
  TopicActionResponse,
  EssayEvaluationResult,
  QuizSubmissionResult,
} from "./types";
import { api } from "../../services/api";

interface RecommendationActionPanelProps {
  actionResponse: TopicActionResponse;
  onClose: () => void;
  onRefreshRecommendations?: () => void;
  onNavigateToChat?: (query: string) => void;
}

export const RecommendationActionPanel: React.FC<RecommendationActionPanelProps> = ({
  actionResponse,
  onClose,
  onRefreshRecommendations,
  onNavigateToChat,
}) => {
  const {
    canonical_label,
    unit_tag,
    action,
    reason,
    practice_data,
    quiz_data,
    review_data,
    maintain_data,
  } = actionResponse;

  // --- PRACTICE & MAINTAIN ESSAY SUBMISSION STATE ---
  const [studentAnswers, setStudentAnswers] = useState<Record<string, string>>({});
  const [evaluatingQuestionId, setEvaluatingQuestionId] = useState<string | null>(null);
  const [evaluationResults, setEvaluationResults] = useState<Record<string, EssayEvaluationResult>>({});
  const [evalError, setEvalError] = useState<string | null>(null);

  // --- QUIZ & ASSESS MCQ STATE ---
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [submittingQuiz, setSubmittingQuiz] = useState<boolean>(false);
  const [quizGrade, setQuizGrade] = useState<QuizSubmissionResult | null>(null);
  const [quizError, setQuizError] = useState<string | null>(null);

  // Handler for essay evaluation
  const handleEvaluateEssay = async (questionId: string) => {
    const text = studentAnswers[questionId];
    if (!text || text.trim().length < 10) {
      setEvalError("Please write an answer of at least 10 characters before submitting for evaluation.");
      return;
    }

    setEvaluatingQuestionId(questionId);
    setEvalError(null);

    try {
      const res: EssayEvaluationResult = await api.evaluateEssay(questionId, text);
      setEvaluationResults((prev) => ({ ...prev, [questionId]: res }));
      if (onRefreshRecommendations) {
        onRefreshRecommendations();
      }
    } catch (err: unknown) {
      setEvalError(err instanceof Error ? err.message : "Failed to evaluate answer. Please try again.");
    } finally {
      setEvaluatingQuestionId(null);
    }
  };

  // Handler for MCQ quiz submission
  const handleSubmitQuiz = async () => {
    if (!quiz_data) return;
    setSubmittingQuiz(true);
    setQuizError(null);

    try {
      const grade: QuizSubmissionResult = await api.submitQuizAnswers(quiz_data.quiz_id, quizAnswers);
      setQuizGrade(grade);
      if (onRefreshRecommendations) {
        onRefreshRecommendations();
      }
    } catch (err: unknown) {
      setQuizError(err instanceof Error ? err.message : "Failed to grade quiz. Please try again.");
    } finally {
      setSubmittingQuiz(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/70 backdrop-blur-md overflow-y-auto">
      <div className="w-full max-w-4xl max-h-[90vh] bg-[#0a0a0d] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-200">
        {/* Action Panel Header */}
        <div className="p-6 border-b border-white/5 flex items-start justify-between gap-4 bg-[#111115]/50">
          <div className="space-y-1">
            <div className="flex items-center space-x-2.5 flex-wrap gap-y-1">
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-md border ${
                action === "PRACTICE"
                  ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
                  : action === "QUIZ"
                  ? "bg-purple-500/10 text-purple-300 border-purple-500/20"
                  : action === "ASSESS"
                  ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
                  : action === "REVIEW"
                  ? "bg-sky-500/10 text-sky-300 border-sky-500/20"
                  : "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
              }`}>
                {action} ACTION
              </span>
              <h2 className="text-xl font-bold text-slate-100">{canonical_label}</h2>
              {unit_tag && (
                <span className="text-xs text-slate-400 font-mono bg-white/5 px-2 py-0.5 rounded border border-white/5">
                  {unit_tag}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 max-w-2xl">{reason}</p>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-100 hover:bg-white/5 rounded-xl border border-transparent hover:border-white/10 transition-colors shrink-0"
            aria-label="Close action workspace"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Action Body Content */}
        <div className="flex-1 p-6 overflow-y-auto space-y-6">
          {/* ======================================================== */}
          {/* ACTION 1: PRACTICE WORKSPACE */}
          {/* ======================================================== */}
          {action === "PRACTICE" && (
            <div className="space-y-6">
              {evalError && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-300 flex items-center space-x-2">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>{evalError}</span>
                </div>
              )}

              {(!practice_data || practice_data.length === 0) ? (
                <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-8 text-center space-y-3">
                  <HelpCircle className="h-10 w-10 text-slate-500 mx-auto" />
                  <h4 className="font-bold text-slate-200">No Direct Practice Questions Available</h4>
                  <p className="text-xs text-slate-400 max-w-md mx-auto">
                    There are currently no cataloged previous-year exam questions for this specific topic in the repository.
                    You can consult related lecture notes in the Subject Vault or ask questions to the AI Study Copilot.
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      Topic Practice Questions ({practice_data.length})
                    </span>
                    <span className="text-[11px] text-slate-500">
                      Grounded AI rubric evaluation
                    </span>
                  </div>

                  {practice_data.map((q, idx) => {
                    const result = evaluationResults[q.question_id];
                    const isEvaluating = evaluatingQuestionId === q.question_id;

                    return (
                      <div
                        key={q.question_id}
                        className="bg-[#111115] border border-white/5 rounded-2xl p-5 space-y-4"
                      >
                        {/* Question Metadata Header */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-3">
                          <div className="flex items-center space-x-2">
                            <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 text-[10px] font-bold uppercase tracking-wider">
                              Question {idx + 1}
                            </span>
                            <span className="text-xs text-slate-400 font-medium">
                              Marks Weight: <strong className="text-slate-200">{q.marks_weight} Marks</strong>
                            </span>
                          </div>

                          <div className="flex items-center space-x-2">
                            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                              q.source_scope === "topic"
                                ? "bg-purple-500/10 text-purple-300 border border-purple-500/20"
                                : "bg-amber-500/10 text-amber-300 border border-amber-500/20"
                            }`}>
                              Scope: {q.source_scope === "topic" ? "Topic-Linked" : "Unit Fallback"}
                            </span>
                            {q.unit_tag && (
                              <span className="text-[10px] text-slate-500 bg-white/5 px-2 py-0.5 rounded">
                                {q.unit_tag}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Question Text */}
                        <p className="text-sm font-semibold text-slate-200 leading-relaxed">
                          {q.text}
                        </p>

                        {/* Interactive Answer Input */}
                        <div className="space-y-2">
                          <label className="block text-[11px] font-semibold text-slate-400">
                            Your Technical Answer:
                          </label>
                          <textarea
                            rows={4}
                            value={studentAnswers[q.question_id] || ""}
                            onChange={(e) =>
                              setStudentAnswers((prev) => ({
                                ...prev,
                                [q.question_id]: e.target.value,
                              }))
                            }
                            placeholder="Write your detailed engineering answer here (key definitions, steps, architecture, working)..."
                            className="w-full bg-[#0a0a0d] border border-white/10 focus:border-purple-500/50 rounded-xl p-3.5 text-xs text-slate-100 outline-none leading-relaxed"
                          />
                        </div>

                        {/* Submit Button */}
                        <div className="flex items-center justify-between pt-1">
                          <span className="text-[11px] text-slate-500">
                            Evaluated against SPPU engineering grading criteria
                          </span>

                          <button
                            onClick={() => handleEvaluateEssay(q.question_id)}
                            disabled={isEvaluating}
                            className="py-2 px-4 bg-gradient-to-r from-rose-600 to-pink-600 hover:from-rose-500 hover:to-pink-500 text-white font-bold text-xs rounded-xl flex items-center space-x-1.5 transition-all disabled:opacity-50"
                          >
                            {isEvaluating ? (
                              <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                <span>Evaluating Answer...</span>
                              </>
                            ) : (
                              <>
                                <Send className="h-3.5 w-3.5" />
                                <span>Submit for AI Evaluation</span>
                              </>
                            )}
                          </button>
                        </div>

                        {/* Evaluation Result Display */}
                        {result && (
                          <div className="mt-4 p-4 bg-purple-500/5 border border-purple-500/20 rounded-xl space-y-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-2">
                                <Award className="h-4 w-4 text-purple-400" />
                                <span className="font-bold text-xs text-purple-200">Grading & Mastery Result</span>
                              </div>
                              <div className="text-sm font-bold text-slate-100">
                                <span className="text-purple-300 font-mono">{result.estimated_marks}</span>
                                <span className="text-slate-500 font-normal"> / {result.max_marks} marks</span>
                              </div>
                            </div>

                            <div className="text-xs text-slate-300 leading-relaxed bg-[#0c0c10] p-3 rounded-lg border border-white/5">
                              <strong className="text-slate-200 block mb-1">Evaluator Feedback:</strong>
                              {result.feedback}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ======================================================== */}
          {/* ACTION 2 & 3: QUIZ & DIAGNOSTIC ASSESS WORKSPACE */}
          {/* ======================================================== */}
          {(action === "QUIZ" || action === "ASSESS") && (
            <div className="space-y-6">
              {quizError && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-300 flex items-center space-x-2">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>{quizError}</span>
                </div>
              )}

              {!quiz_data ? (
                <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-8 text-center space-y-3">
                  <HelpCircle className="h-10 w-10 text-slate-500 mx-auto" />
                  <h4 className="font-bold text-slate-200">Quiz Generation Incomplete</h4>
                  <p className="text-xs text-slate-400 max-w-md mx-auto">
                    The quiz could not be built. Please try refreshing or generating a practice quiz in the Quizzes tab.
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Quiz Title & Header */}
                  <div className="p-4 bg-white/[0.02] border border-white/5 rounded-xl flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-sm text-slate-200">{quiz_data.title}</h3>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {action === "ASSESS"
                          ? "Diagnostic Baseline: Complete to measure initial topic mastery."
                          : "Topic Reinforcement: Test retention on key concept questions."}
                      </p>
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                      {quiz_data.total_questions} Questions
                    </span>
                  </div>

                  {/* Questions List */}
                  <div className="space-y-6">
                    {quiz_data.questions.map((q, qidx) => {
                      const feedback = quizGrade?.feedback?.find((f) => f.question_id === q.id);

                      return (
                        <div
                          key={q.id}
                          className="bg-[#111115] border border-white/5 rounded-2xl p-5 space-y-4"
                        >
                          <div className="text-sm font-semibold text-slate-200 flex items-start space-x-2">
                            <span className="text-purple-400 font-bold font-mono">Q{qidx + 1}.</span>
                            <span>{q.question}</span>
                          </div>

                          {/* Multiple Choice Options */}
                          {q.choices ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pl-4">
                              {Object.entries(q.choices).map(([key, label]) => {
                                const isSelected = quizAnswers[q.id] === key;
                                const isCorrect = feedback?.correct_answer === key;
                                const isWrongSubmitted =
                                  feedback && !feedback.is_correct && quizAnswers[q.id] === key;

                                let optStyle = "bg-[#0a0a0d] border-white/5 text-slate-300 hover:border-white/20";
                                if (isSelected) {
                                  optStyle = "bg-purple-600/15 border-purple-500/40 text-purple-200";
                                }
                                if (quizGrade) {
                                  if (isCorrect) {
                                    optStyle = "bg-emerald-500/15 border-emerald-500/40 text-emerald-200";
                                  } else if (isWrongSubmitted) {
                                    optStyle = "bg-rose-500/15 border-rose-500/40 text-rose-200";
                                  }
                                }

                                return (
                                  <button
                                    key={key}
                                    type="button"
                                    disabled={!!quizGrade}
                                    onClick={() =>
                                      setQuizAnswers((prev) => ({ ...prev, [q.id]: key }))
                                    }
                                    className={`p-3 text-left text-xs rounded-xl border transition-all flex items-center justify-between ${optStyle}`}
                                  >
                                    <span className="leading-snug">
                                      <strong className="font-bold mr-1.5">{key}.</strong>
                                      {label}
                                    </span>
                                    {quizGrade && isCorrect && (
                                      <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0 ml-2" />
                                    )}
                                  </button>
                                );
                              })}
                            </div>
                          ) : (
                            <div className="pl-4">
                              <textarea
                                disabled={!!quizGrade}
                                rows={3}
                                value={quizAnswers[q.id] || ""}
                                onChange={(e) =>
                                  setQuizAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                                }
                                placeholder="Write your answer..."
                                className="w-full bg-[#0a0a0d] border border-white/5 p-3 text-xs rounded-xl text-slate-200 outline-none"
                              />
                            </div>
                          )}

                          {/* Feedback Explanation Banner */}
                          {feedback && (
                            <div className="pl-4 pt-1">
                              <div className="p-3 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1">
                                <div className="flex items-center space-x-2">
                                  <span className="font-bold text-slate-300">Result:</span>
                                  <span className={feedback.is_correct ? "text-emerald-400 font-semibold" : "text-rose-400 font-semibold"}>
                                    {feedback.is_correct ? "Correct" : "Needs Review"}
                                  </span>
                                </div>
                                {feedback.explanation && (
                                  <p className="text-slate-400 pt-0.5">{feedback.explanation}</p>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Submission Footer */}
                  {quizGrade ? (
                    <div className="p-5 bg-purple-500/10 border border-purple-500/20 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                          Assessment Complete
                        </div>
                        <div className="text-lg font-bold text-purple-300 mt-0.5">
                          Score: {quizGrade.correct_answers} / {quizGrade.total_questions} ({quizGrade.score_percent}%)
                        </div>
                        <p className="text-[11px] text-slate-400 mt-1">
                          Your topic mastery score will adapt based on this performance.
                        </p>
                      </div>

                      <button
                        onClick={() => {
                          setQuizGrade(null);
                          setQuizAnswers({});
                        }}
                        className="py-2.5 px-4 bg-white/10 hover:bg-white/15 text-xs font-semibold rounded-xl border border-white/10 transition-colors shrink-0"
                      >
                        Retake Quiz
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={handleSubmitQuiz}
                      disabled={submittingQuiz}
                      className="w-full py-3.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-xs rounded-xl flex items-center justify-center space-x-2 transition-all shadow-md disabled:opacity-50"
                    >
                      {submittingQuiz ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          <span>Grading Answers...</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle className="h-4 w-4" />
                          <span>Submit Answers For Grading</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ======================================================== */}
          {/* ACTION 4: REVIEW WORKSPACE */}
          {/* ======================================================== */}
          {action === "REVIEW" && (
            <div className="space-y-6">
              {review_data ? (
                <div className="space-y-6">
                  {/* Summary Box */}
                  <div className="bg-[#111115] border border-white/5 rounded-2xl p-5 space-y-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Syllabus Concept Summary
                    </span>
                    <p className="text-xs text-slate-200 leading-relaxed">
                      {review_data.summary}
                    </p>
                  </div>

                  {/* Grounded Chunks */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                        <BookOpen className="h-3.5 w-3.5 text-sky-400" />
                        <span>Grounded Study Material Chunks ({review_data.supporting_chunks.length})</span>
                      </span>
                      <span className="text-[11px] text-slate-500">From uploaded documents</span>
                    </div>

                    {review_data.supporting_chunks.length === 0 ? (
                      <div className="p-6 bg-white/[0.02] border border-white/5 rounded-xl text-center text-xs text-slate-500">
                        No specific textbook chunks mapped to this topic yet. Upload lecture notes to index relevant excerpts.
                      </div>
                    ) : (
                      review_data.supporting_chunks.map((chunk, cidx) => (
                        <div
                          key={chunk.chunk_id || cidx}
                          className="bg-[#111115] border border-white/5 rounded-xl p-4 space-y-2.5"
                        >
                          <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-white/5 pb-2">
                            <span className="font-semibold text-slate-300 truncate max-w-sm">
                              {chunk.document_name}
                            </span>
                            <div className="flex items-center space-x-2">
                              {chunk.page && (
                                <span className="bg-sky-500/10 text-sky-300 border border-sky-500/20 px-2 py-0.5 rounded text-[10px] font-mono">
                                  Page {chunk.page}
                                </span>
                              )}
                              {chunk.unit_tag && (
                                <span className="bg-white/5 text-slate-400 px-2 py-0.5 rounded text-[10px]">
                                  {chunk.unit_tag}
                                </span>
                              )}
                            </div>
                          </div>
                          <p className="text-xs text-slate-300 leading-relaxed font-sans whitespace-pre-wrap">
                            {chunk.content}
                          </p>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Copilot Navigation Action */}
                  {onNavigateToChat && (
                    <div className="p-4 bg-sky-500/10 border border-sky-500/20 rounded-xl flex items-center justify-between gap-4">
                      <div className="space-y-0.5">
                        <div className="text-xs font-bold text-sky-300">Need deeper clarification?</div>
                        <div className="text-[11px] text-slate-400">
                          Ask questions about {canonical_label} to the AI Study Copilot with cited references.
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          onClose();
                          onNavigateToChat(`Explain ${canonical_label} according to the SPPU syllabus with key points.`);
                        }}
                        className="py-2 px-3.5 bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs rounded-xl flex items-center space-x-1.5 transition-colors shrink-0"
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                        <span>Open in Copilot</span>
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-8 text-center text-slate-500 text-xs">
                  No review material currently loaded for this topic.
                </div>
              )}
            </div>
          )}

          {/* ======================================================== */}
          {/* ACTION 5: MAINTAIN WORKSPACE */}
          {/* ======================================================== */}
          {action === "MAINTAIN" && (
            <div className="space-y-6">
              {maintain_data ? (
                <div className="space-y-6">
                  {/* Takeaways Card */}
                  <div className="bg-[#111115] border border-white/5 rounded-2xl p-5 space-y-3">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 flex items-center space-x-1.5">
                      <CheckCircle className="h-3.5 w-3.5" />
                      <span>Proficiency Status</span>
                    </span>
                    <ul className="space-y-2 text-xs text-slate-200">
                      {maintain_data.key_takeaways.map((point, pidx) => (
                        <li key={pidx} className="flex items-start space-x-2">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                          <span>{point}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Quick Revision Notes */}
                  <div className="bg-[#111115] border border-white/5 rounded-2xl p-5 space-y-3">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Quick Revision Checklist
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-300">
                      {maintain_data.quick_revision_notes.map((note, nidx) => (
                        <div key={nidx} className="p-2.5 bg-white/[0.02] border border-white/5 rounded-lg">
                          {note}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Refresher Sample Question if available */}
                  {maintain_data.sample_question && (
                    <div className="bg-[#111115] border border-white/5 rounded-2xl p-5 space-y-3">
                      <div className="flex items-center justify-between border-b border-white/5 pb-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Refresher Check Question
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">
                          {maintain_data.sample_question.marks_weight} Marks
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-slate-200">
                        {maintain_data.sample_question.text}
                      </p>

                      <textarea
                        rows={3}
                        value={studentAnswers[maintain_data.sample_question.question_id] || ""}
                        onChange={(e) =>
                          setStudentAnswers((prev) => ({
                            ...prev,
                            [maintain_data.sample_question!.question_id]: e.target.value,
                          }))
                        }
                        placeholder="Write a concise answer to verify retention..."
                        className="w-full bg-[#0a0a0d] border border-white/10 rounded-xl p-3 text-xs text-slate-100 outline-none"
                      />

                      <div className="flex justify-end">
                        <button
                          onClick={() =>
                            handleEvaluateEssay(maintain_data.sample_question!.question_id)
                          }
                          disabled={evaluatingQuestionId === maintain_data.sample_question.question_id}
                          className="py-2 px-3.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl flex items-center space-x-1.5 transition-colors disabled:opacity-50"
                        >
                          {evaluatingQuestionId === maintain_data.sample_question.question_id ? (
                            <>
                              <Loader2 className="h-3 w-3 animate-spin" />
                              <span>Evaluating...</span>
                            </>
                          ) : (
                            <>
                              <Send className="h-3 w-3" />
                              <span>Submit Refresher</span>
                            </>
                          )}
                        </button>
                      </div>

                      {evaluationResults[maintain_data.sample_question.question_id] && (
                        <div className="mt-3 p-3 bg-white/5 border border-white/5 rounded-lg text-xs space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-slate-200">Score:</span>
                            <span className="font-mono text-emerald-400">
                              {evaluationResults[maintain_data.sample_question.question_id].estimated_marks} /{" "}
                              {evaluationResults[maintain_data.sample_question.question_id].max_marks} marks
                            </span>
                          </div>
                          <p className="text-slate-400">
                            {evaluationResults[maintain_data.sample_question.question_id].feedback}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-8 text-center text-slate-500 text-xs">
                  No maintain data available.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action Panel Footer */}
        <div className="p-4 border-t border-white/5 bg-[#111115]/50 flex items-center justify-between">
          <div className="text-[11px] text-slate-500">
            Powered by deterministic Exam Priority and verified student performance.
          </div>
          <button
            onClick={onClose}
            className="py-2 px-4 bg-white/5 hover:bg-white/10 text-xs font-semibold rounded-xl text-slate-300 border border-white/5 transition-colors"
          >
            Close Workspace
          </button>
        </div>
      </div>
    </div>
  );
};
