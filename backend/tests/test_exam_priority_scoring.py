import math
import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.exam_intelligence import (
    ExamIntelligenceService,
    StudentTopicMasteryInput,
    TopicMetricsInput,
    exam_intelligence_service,
)


class ExamPriorityScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ExamIntelligenceService()

    def test_frequency_normalization(self) -> None:
        """
        Verify occurrences [5, 3, 1] normalize to [1.0, 0.6, 0.2].
        """
        t1 = TopicMetricsInput(topic_id="t1", canonical_label="Topic 1", total_occurrences=5)
        t2 = TopicMetricsInput(topic_id="t2", canonical_label="Topic 2", total_occurrences=3)
        t3 = TopicMetricsInput(topic_id="t3", canonical_label="Topic 3", total_occurrences=1)

        results = self.engine.calculate_topic_priorities([t1, t2, t3])
        res_by_id = {r.topic_id: r for r in results}

        self.assertEqual(res_by_id["t1"].frequency_score, 1.0)
        self.assertEqual(res_by_id["t2"].frequency_score, 0.6)
        self.assertEqual(res_by_id["t3"].frequency_score, 0.2)

    def test_marks_normalization(self) -> None:
        """
        Verify average marks [10, 5, 2] normalize to [1.0, 0.5, 0.2].
        """
        t1 = TopicMetricsInput(topic_id="t1", canonical_label="Topic 1", total_occurrences=1, avg_marks=10.0)
        t2 = TopicMetricsInput(topic_id="t2", canonical_label="Topic 2", total_occurrences=1, avg_marks=5.0)
        t3 = TopicMetricsInput(topic_id="t3", canonical_label="Topic 3", total_occurrences=1, avg_marks=2.0)

        results = self.engine.calculate_topic_priorities([t1, t2, t3])
        res_by_id = {r.topic_id: r for r in results}

        self.assertEqual(res_by_id["t1"].marks_score, 1.0)
        self.assertEqual(res_by_id["t2"].marks_score, 0.5)
        self.assertEqual(res_by_id["t3"].marks_score, 0.2)

    def test_mode_a_with_student_mastery(self) -> None:
        """
        Verify Mode A exact formula:
        P_t = 0.40 * F_t + 0.30 * M_t + 0.30 * W_t
        Given F_t = 1.0, M_t = 0.5, mastery = 0.4 (W_t = 0.6):
        P_t = 0.40 * 1.0 + 0.30 * 0.5 + 0.30 * 0.6 = 0.40 + 0.15 + 0.18 = 0.730
        """
        t1 = TopicMetricsInput(topic_id="t1", canonical_label="Topic 1", total_occurrences=10, avg_marks=10.0)
        t2 = TopicMetricsInput(topic_id="t2", canonical_label="Topic 2", total_occurrences=5, avg_marks=5.0)

        mastery_data = {
            "t2": StudentTopicMasteryInput(evaluation_count=3, mastery=0.4)
        }

        results = self.engine.calculate_topic_priorities([t1, t2], student_mastery=mastery_data)
        res_by_id = {r.topic_id: r for r in results}

        res_t2 = res_by_id["t2"]
        self.assertEqual(res_t2.frequency_score, 0.5)  # 5/10
        self.assertEqual(res_t2.marks_score, 0.5)      # 5.0/10.0
        self.assertEqual(res_t2.student_mastery, 0.4)
        self.assertEqual(res_t2.weakness_score, 0.6)
        # P_t = 0.40 * 0.5 + 0.30 * 0.5 + 0.30 * 0.6 = 0.20 + 0.15 + 0.18 = 0.530
        self.assertEqual(res_t2.priority_score, 0.530)
        self.assertEqual(res_t2.priority_label, "Medium")
        self.assertEqual(res_t2.evaluation_count, 3)

    def test_mode_b_without_student_data(self) -> None:
        """
        Verify Mode B exact formula:
        P_t = 0.60 * F_t + 0.40 * M_t
        Given F_t = 1.0, M_t = 0.5, mastery is None:
        P_t = 0.60 * 1.0 + 0.40 * 0.5 = 0.60 + 0.20 = 0.800
        """
        t1 = TopicMetricsInput(topic_id="t1", canonical_label="Topic 1", total_occurrences=10, avg_marks=10.0)
        t2 = TopicMetricsInput(topic_id="t2", canonical_label="Topic 2", total_occurrences=10, avg_marks=5.0)

        results = self.engine.calculate_topic_priorities([t1, t2], student_mastery=None)
        res_by_id = {r.topic_id: r for r in results}

        res_t2 = res_by_id["t2"]
        self.assertEqual(res_t2.frequency_score, 1.0)
        self.assertEqual(res_t2.marks_score, 0.5)
        self.assertIsNone(res_t2.student_mastery)
        self.assertIsNone(res_t2.weakness_score)
        self.assertEqual(res_t2.priority_score, 0.800)
        self.assertEqual(res_t2.priority_label, "Very High")

    def test_mode_c_zero_pyq_occurrences(self) -> None:
        """
        Verify Mode C:
        total_occurrences == 0
        - with mastery 0.2 (weakness 0.8): P_t = 0.30 * 0.8 = 0.240
        - without mastery: P_t = 0.0
        Verify neither can receive High/Medium priority merely from weakness.
        """
        t_with_mastery = TopicMetricsInput(
            topic_id="zero_m", canonical_label="Zero PYQ With Mastery", total_occurrences=0, avg_marks=0.0
        )
        t_without_mastery = TopicMetricsInput(
            topic_id="zero_nom", canonical_label="Zero PYQ Without Mastery", total_occurrences=0, avg_marks=0.0
        )

        mastery_data = {
            "zero_m": StudentTopicMasteryInput(evaluation_count=2, mastery=0.2)
        }

        results = self.engine.calculate_topic_priorities(
            [t_with_mastery, t_without_mastery], student_mastery=mastery_data
        )
        res_by_id = {r.topic_id: r for r in results}

        # With mastery
        r_m = res_by_id["zero_m"]
        self.assertEqual(r_m.frequency_score, 0.0)
        self.assertEqual(r_m.marks_score, 0.0)
        self.assertEqual(r_m.student_mastery, 0.2)
        self.assertEqual(r_m.weakness_score, 0.8)
        self.assertEqual(r_m.priority_score, 0.240)
        self.assertEqual(r_m.priority_label, "Low")

        # Without mastery
        r_nom = res_by_id["zero_nom"]
        self.assertEqual(r_nom.frequency_score, 0.0)
        self.assertEqual(r_nom.marks_score, 0.0)
        self.assertIsNone(r_nom.student_mastery)
        self.assertIsNone(r_nom.weakness_score)
        self.assertEqual(r_nom.priority_score, 0.0)
        self.assertEqual(r_nom.priority_label, "Low")

    def test_mastery_clamping(self) -> None:
        """
        Verify student mastery > 1.0 clamps to 1.0 (weakness = 0.0)
        and mastery < 0.0 clamps to 0.0 (weakness = 1.0).
        """
        t1 = TopicMetricsInput(topic_id="t1", canonical_label="T1", total_occurrences=1, avg_marks=5.0)
        t2 = TopicMetricsInput(topic_id="t2", canonical_label="T2", total_occurrences=1, avg_marks=5.0)

        mastery_data = {
            "t1": StudentTopicMasteryInput(evaluation_count=1, mastery=1.45),   # > 1
            "t2": StudentTopicMasteryInput(evaluation_count=1, mastery=-0.35),  # < 0
        }

        results = self.engine.calculate_topic_priorities([t1, t2], student_mastery=mastery_data)
        res_by_id = {r.topic_id: r for r in results}

        self.assertEqual(res_by_id["t1"].student_mastery, 1.0)
        self.assertEqual(res_by_id["t1"].weakness_score, 0.0)

        self.assertEqual(res_by_id["t2"].student_mastery, 0.0)
        self.assertEqual(res_by_id["t2"].weakness_score, 1.0)

    def test_priority_exact_boundaries(self) -> None:
        """
        Verify exact deterministic boundaries:
        P >= 0.75 -> Very High
        P >= 0.55 -> High
        P >= 0.35 -> Medium
        P < 0.35  -> Low
        """
        # We can construct exact scores using Mode B: P = 0.60 * F + 0.40 * M
        # 1. P = 0.750 exactly: F = 0.75, M = 0.75 -> 0.60*0.75 + 0.40*0.75 = 0.750
        # 2. P = 0.749 exactly: F = 0.749, M = 0.749 -> 0.749 -> High
        # 3. P = 0.550 exactly: F = 0.55, M = 0.55 -> 0.550 -> High
        # 4. P = 0.549 exactly: F = 0.549, M = 0.549 -> 0.549 -> Medium
        # 5. P = 0.350 exactly: F = 0.35, M = 0.35 -> 0.350 -> Medium
        # 6. P = 0.349 exactly: F = 0.349, M = 0.349 -> 0.349 -> Low
        t_vh = TopicMetricsInput(topic_id="vh", canonical_label="A_VH", total_occurrences=750, avg_marks=750.0)
        t_high_upper = TopicMetricsInput(topic_id="h_up", canonical_label="B_H_UP", total_occurrences=749, avg_marks=749.0)
        t_high = TopicMetricsInput(topic_id="h", canonical_label="C_H", total_occurrences=550, avg_marks=550.0)
        t_med_upper = TopicMetricsInput(topic_id="m_up", canonical_label="D_M_UP", total_occurrences=549, avg_marks=549.0)
        t_med = TopicMetricsInput(topic_id="m", canonical_label="E_M", total_occurrences=350, avg_marks=350.0)
        t_low = TopicMetricsInput(topic_id="l", canonical_label="F_L", total_occurrences=349, avg_marks=349.0)
        # Max anchor: 1000 occurrences, 1000 avg_marks
        t_anchor = TopicMetricsInput(topic_id="anchor", canonical_label="Z_Anchor", total_occurrences=1000, avg_marks=1000.0)

        results = self.engine.calculate_topic_priorities(
            [t_vh, t_high_upper, t_high, t_med_upper, t_med, t_low, t_anchor]
        )
        res_by_id = {r.topic_id: r for r in results}

        self.assertEqual(res_by_id["vh"].priority_score, 0.750)
        self.assertEqual(res_by_id["vh"].priority_label, "Very High")

        self.assertEqual(res_by_id["h_up"].priority_score, 0.749)
        self.assertEqual(res_by_id["h_up"].priority_label, "High")

        self.assertEqual(res_by_id["h"].priority_score, 0.550)
        self.assertEqual(res_by_id["h"].priority_label, "High")

        self.assertEqual(res_by_id["m_up"].priority_score, 0.549)
        self.assertEqual(res_by_id["m_up"].priority_label, "Medium")

        self.assertEqual(res_by_id["m"].priority_score, 0.350)
        self.assertEqual(res_by_id["m"].priority_label, "Medium")

        self.assertEqual(res_by_id["l"].priority_score, 0.349)
        self.assertEqual(res_by_id["l"].priority_label, "Low")

    def test_deterministic_sorting(self) -> None:
        """
        Verify sorting order:
        1. priority_score descending
        2. total_occurrences descending
        3. canonical_label ascending
        """
        # All have same priority score (0.60 * 1.0 + 0.40 * 1.0 = 1.0)
        # But different occurrences and labels:
        t_a = TopicMetricsInput(topic_id="1", canonical_label="Zebra Topic", total_occurrences=10, avg_marks=10.0)
        t_b = TopicMetricsInput(topic_id="2", canonical_label="Alpha Topic", total_occurrences=10, avg_marks=10.0)
        t_c = TopicMetricsInput(topic_id="3", canonical_label="Beta Topic", total_occurrences=5, avg_marks=10.0)

        results = self.engine.calculate_topic_priorities([t_a, t_b, t_c])

        # t_b and t_a tie on priority (1.0) and occurrences (10), so tiebreak alphabetically: Alpha Topic before Zebra Topic
        # t_c has lower occurrences (5), so comes after
        self.assertEqual(results[0].canonical_label, "Alpha Topic")
        self.assertEqual(results[1].canonical_label, "Zebra Topic")
        self.assertEqual(results[2].canonical_label, "Beta Topic")

    def test_empty_and_single_topic_input(self) -> None:
        """
        Verify empty input returns empty list, and single topic executes safely.
        """
        self.assertEqual(self.engine.calculate_topic_priorities([]), [])

        single = TopicMetricsInput(topic_id="s1", canonical_label="Single", total_occurrences=4, avg_marks=8.0)
        results = self.engine.calculate_topic_priorities([single])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].frequency_score, 1.0)
        self.assertEqual(results[0].marks_score, 1.0)
        self.assertEqual(results[0].priority_score, 1.0)

    def test_no_nan_or_infinity(self) -> None:
        """
        Verify zero occurrences across all topics and zero marks produce 0.0 without NaN/inf.
        """
        t1 = TopicMetricsInput(topic_id="1", canonical_label="T1", total_occurrences=0, avg_marks=0.0)
        t2 = TopicMetricsInput(topic_id="2", canonical_label="T2", total_occurrences=0, avg_marks=0.0)

        results = self.engine.calculate_topic_priorities([t1, t2])
        for r in results:
            self.assertFalse(math.isnan(r.frequency_score))
            self.assertFalse(math.isnan(r.marks_score))
            self.assertFalse(math.isnan(r.priority_score))
            self.assertFalse(math.isinf(r.priority_score))
            self.assertEqual(r.priority_score, 0.0)

    def test_evidence_generation(self) -> None:
        """
        Verify explainable evidence correctly reflects:
        - student data available
        - no student data
        - zero PYQ history
        """
        t_active = TopicMetricsInput(
            topic_id="active",
            canonical_label="Pipelining",
            total_occurrences=4,
            distinct_papers=3,
            avg_marks=8.3,
            max_marks=10,
        )
        t_zero = TopicMetricsInput(
            topic_id="zero",
            canonical_label="DMA Controller",
            total_occurrences=0,
            distinct_papers=0,
            avg_marks=0.0,
            max_marks=0,
        )

        # 1. With student data
        mastery_data = {
            "active": StudentTopicMasteryInput(evaluation_count=2, mastery=0.42)
        }
        res = self.engine.calculate_topic_priorities([t_active, t_zero], student_mastery=mastery_data)
        res_map = {r.topic_id: r for r in res}

        active_res = res_map["active"]
        self.assertEqual(active_res.evidence.frequency_rationale, "Appeared 4 times across 3 examination papers.")
        self.assertEqual(active_res.evidence.marks_rationale, "Average exam weight is 8.3 marks.")
        self.assertEqual(active_res.evidence.mastery_rationale, "Student mastery is 42% based on 2 evaluated answers.")

        # 2. Without student data
        res_no_student = self.engine.calculate_topic_priorities([t_active], student_mastery=None)
        no_student_ev = res_no_student[0].evidence
        self.assertEqual(
            no_student_ev.mastery_rationale,
            "Student mastery is unavailable because no evaluated answers exist for this topic."
        )

        # 3. Zero PYQ history
        zero_res = res_map["zero"]
        self.assertEqual(
            zero_res.evidence.frequency_rationale,
            "No previous-year question occurrence is currently recorded for this topic."
        )
        self.assertEqual(
            zero_res.evidence.marks_rationale,
            "No previous-year exam marks history exists for this topic."
        )

    def test_deterministic_recommendations(self) -> None:
        """
        Verify recommendations are deterministic and strictly follow signal patterns:
        - High frequency + weak mastery
        - High frequency + no student data
        - Low frequency + weak mastery
        - Zero PYQ history
        """
        t_high = TopicMetricsInput(topic_id="h", canonical_label="High PYQ", total_occurrences=10, avg_marks=10.0)
        t_low = TopicMetricsInput(topic_id="l", canonical_label="Low PYQ", total_occurrences=2, avg_marks=5.0)
        t_zero = TopicMetricsInput(topic_id="z", canonical_label="Zero PYQ", total_occurrences=0, avg_marks=0.0)

        # Case A: High frequency + weak mastery (mastery 0.3 -> weakness 0.7 >= 0.4)
        perf_weak = {
            "h": StudentTopicMasteryInput(evaluation_count=1, mastery=0.3),
            "l": StudentTopicMasteryInput(evaluation_count=1, mastery=0.3),
        }
        res_weak = self.engine.calculate_topic_priorities([t_high, t_low, t_zero], student_mastery=perf_weak)
        weak_map = {r.topic_id: r for r in res_weak}

        self.assertEqual(
            weak_map["h"].evidence.recommendation,
            "Prioritize revision of this topic because it is frequently tested and current mastery is low."
        )
        self.assertEqual(
            weak_map["l"].evidence.recommendation,
            "Review this topic after higher-impact PYQ topics."
        )
        self.assertEqual(
            weak_map["z"].evidence.recommendation,
            "Treat this as syllabus study rather than PYQ-driven exam priority."
        )

        # Case B: High frequency + no student data
        res_no_student = self.engine.calculate_topic_priorities([t_high, t_low], student_mastery=None)
        no_student_map = {r.topic_id: r for r in res_no_student}

        self.assertEqual(
            no_student_map["h"].evidence.recommendation,
            "Prioritize this topic based on its strong previous-year exam history."
        )
        self.assertEqual(
            no_student_map["l"].evidence.recommendation,
            "Study this topic after covering higher-priority exam questions."
        )

    def test_non_finite_occurrences_and_marks_do_not_propagate(self) -> None:
        """
        Verify that NaN, +inf, -inf in total_occurrences and avg_marks:
        1. Do not propagate into frequency_score, marks_score, or priority_score.
        2. Do not corrupt normalization denominators (max_occurrences, max_avg_marks).
        3. Keep all scores finite and within [0.0, 1.0].
        """
        t_nan = TopicMetricsInput(
            topic_id="nan",
            canonical_label="NaN Topic",
            total_occurrences=float("nan"),  # type: ignore
            avg_marks=float("nan"),
        )
        t_pos_inf = TopicMetricsInput(
            topic_id="pos_inf",
            canonical_label="PosInf Topic",
            total_occurrences=float("inf"),  # type: ignore
            avg_marks=float("inf"),
        )
        t_neg_inf = TopicMetricsInput(
            topic_id="neg_inf",
            canonical_label="NegInf Topic",
            total_occurrences=-5,
            avg_marks=float("-inf"),
        )
        t_valid = TopicMetricsInput(
            topic_id="valid",
            canonical_label="Valid Topic",
            total_occurrences=10,
            avg_marks=20.0,
        )

        results = self.engine.calculate_topic_priorities([t_nan, t_pos_inf, t_neg_inf, t_valid])
        res_by_id = {r.topic_id: r for r in results}

        # Denominators should be based strictly on finite values (max_occurrences=10, max_avg_marks=20.0)
        valid_res = res_by_id["valid"]
        self.assertEqual(valid_res.frequency_score, 1.0)
        self.assertEqual(valid_res.marks_score, 1.0)
        self.assertEqual(valid_res.priority_score, 1.0)
        self.assertEqual(valid_res.priority_label, "Very High")

        # Non-finite topics must be sanitized to 0.0 scores
        for tid in ["nan", "pos_inf", "neg_inf"]:
            r = res_by_id[tid]
            self.assertTrue(math.isfinite(r.frequency_score))
            self.assertTrue(math.isfinite(r.marks_score))
            self.assertTrue(math.isfinite(r.priority_score))
            self.assertEqual(r.frequency_score, 0.0)
            self.assertEqual(r.marks_score, 0.0)
            self.assertEqual(r.priority_score, 0.0)
            self.assertEqual(r.priority_label, "Low")

    def test_non_finite_student_mastery_treated_as_unavailable(self) -> None:
        """
        Verify student mastery treats non-finite values (NaN, +inf, -inf)
        as unavailable rather than clamping infinity to 0 or 1.
        """
        t_active = TopicMetricsInput(
            topic_id="active",
            canonical_label="Active Topic",
            total_occurrences=10,
            avg_marks=10.0,
        )
        t_zero = TopicMetricsInput(
            topic_id="zero",
            canonical_label="Zero Topic",
            total_occurrences=0,
            avg_marks=0.0,
        )

        # Test +inf, -inf, NaN across various input formats
        non_finite_mastery_inputs = {
            "nan_obj": StudentTopicMasteryInput(evaluation_count=5, mastery=float("nan")),
            "pos_inf_obj": StudentTopicMasteryInput(evaluation_count=3, mastery=float("inf")),
            "neg_inf_obj": StudentTopicMasteryInput(evaluation_count=4, mastery=float("-inf")),
            "pos_inf_tuple": (2, float("inf")),
            "nan_dict": {"evaluation_count": 2, "mastery": float("nan")},
            "inf_raw": float("inf"),
        }

        for label, mastery_val in non_finite_mastery_inputs.items():
            results = self.engine.calculate_topic_priorities(
                [t_active, t_zero],
                student_mastery={"active": mastery_val, "zero": mastery_val},
            )
            res_by_id = {r.topic_id: r for r in results}

            r_active = res_by_id["active"]
            r_zero = res_by_id["zero"]

            # For active topic (occurrences > 0):
            # If +inf had been clamped to 1.0, weakness would be 0.0 and Mode A score would be:
            # 0.40 * 1.0 + 0.30 * 1.0 + 0.30 * 0.0 = 0.700.
            # But treated as unavailable -> Mode B: 0.60 * 1.0 + 0.40 * 1.0 = 1.000!
            self.assertIsNone(r_active.student_mastery, f"Failed for {label}")
            self.assertIsNone(r_active.weakness_score, f"Failed for {label}")
            self.assertEqual(r_active.evaluation_count, 0, f"Failed for {label}")
            self.assertEqual(r_active.priority_score, 1.000, f"Failed for {label}")
            self.assertEqual(
                r_active.evidence.mastery_rationale,
                "Student mastery is unavailable because no evaluated answers exist for this topic.",
                f"Failed for {label}",
            )

            # For zero topic (occurrences == 0):
            # If -inf had been clamped to 0.0, weakness would be 1.0 and Mode C score would be 0.300.
            # But treated as unavailable -> Mode C without student data: 0.000!
            self.assertIsNone(r_zero.student_mastery, f"Failed for {label}")
            self.assertIsNone(r_zero.weakness_score, f"Failed for {label}")
            self.assertEqual(r_zero.evaluation_count, 0, f"Failed for {label}")
            self.assertEqual(r_zero.priority_score, 0.000, f"Failed for {label}")


if __name__ == "__main__":
    unittest.main()
