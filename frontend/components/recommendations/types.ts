import { PriorityLabel } from "../exam-intelligence/types";

export type RecommendationAction = "PRACTICE" | "QUIZ" | "ASSESS" | "REVIEW" | "MAINTAIN";

export interface TopicRecommendation {
  topic_id: string;
  canonical_label: string;
  unit_tag: string | null;
  priority_score: number;
  priority_label: PriorityLabel;
  student_mastery: number | null;
  weakness_score: number | null;
  evaluation_count: number;
  recommended_action: RecommendationAction;
  recommendation_reason: string;
  action_priority: number;
  action_endpoint?: string | null;
}

export interface SubjectRecommendationsResponse {
  subject_id: string;
  has_student_data: boolean;
  total_recommendations: number;
  recommendations: TopicRecommendation[];
}

export interface PracticeResource {
  question_id: string;
  text: string;
  marks_weight: number;
  unit_tag: string | null;
  source_scope: string; // "topic" | "unit"
  submission_endpoint: string;
}

export interface QuizActionQuestion {
  id: string;
  question: string;
  choices?: Record<string, string>;
  [key: string]: unknown;
}

export interface QuizActionData {
  quiz_id: string;
  title: string;
  quiz_type: string;
  total_questions: number;
  questions: QuizActionQuestion[];
  submission_endpoint: string;
}

export interface ReviewChunk {
  chunk_id: string;
  document_name: string;
  page: number | null;
  content: string;
  unit_tag: string | null;
}

export interface ReviewActionData {
  summary: string;
  key_concepts: string[];
  supporting_chunks: ReviewChunk[];
}

export interface MaintainActionData {
  key_takeaways: string[];
  quick_revision_notes: string[];
  sample_question: PracticeResource | null;
}

export interface TopicActionResponse {
  subject_id: string;
  topic_id: string;
  canonical_label: string;
  unit_tag: string | null;
  action: RecommendationAction;
  action_priority: number;
  reason: string;
  practice_data: PracticeResource[] | null;
  quiz_data: QuizActionData | null;
  review_data: ReviewActionData | null;
  maintain_data: MaintainActionData | null;
}

export interface EssayEvaluationResult {
  id: string;
  user_id: string;
  question_id: string;
  user_submitted_answer: string;
  feedback: string;
  estimated_marks: number;
  max_marks: number;
  improvement_points?: Record<string, unknown>;
  evaluated_at: string;
}

export interface QuizSubmissionResult {
  score_percent: number;
  correct_answers: number;
  total_questions: number;
  feedback: Array<{
    question_id: string;
    is_correct: boolean;
    correct_answer?: string;
    explanation?: string;
    matched_keywords?: string[];
  }>;
}
