export interface TopicEvidence {
  frequency_rationale: string;
  marks_rationale: string;
  mastery_rationale: string;
  recommendation: string;
}

export type PriorityLabel = "Very High" | "High" | "Medium" | "Low";

export interface ExamPriorityTopic {
  topic_id: string;
  canonical_label: string;
  unit_tag: string | null;
  total_occurrences: number;
  distinct_papers: number;
  avg_marks: number;
  max_marks: number;
  frequency_score: number;
  marks_score: number;
  student_mastery: number | null;
  weakness_score: number | null;
  priority_score: number;
  priority_label: PriorityLabel;
  evaluation_count: number;
  has_student_data: boolean;
  evidence: TopicEvidence;
  recommendation: string;
}

export interface SubjectExamPriorityResponse {
  subject_id: string;
  has_student_data: boolean;
  total_topics: number;
  unresolved_occurrences_count: number;
  topics: ExamPriorityTopic[];
}
