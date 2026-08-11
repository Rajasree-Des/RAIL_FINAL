"""Tests for StatisticsBuilder."""

from app.features.summary.statistics_builder import StatisticsBuilder


SAMPLE_ROWS = [
    {
        "division": "SCR",
        "train_number": "12724",
        "complaint_type": "Electrical Equipment",
        "complaint_count": 45,
        "status": "Resolved",
        "resolved_count": 38,
        "unsatisfactory_count": 3,
    },
    {
        "division": "SCR",
        "train_number": "12616",
        "complaint_type": "Water Supply",
        "complaint_count": 32,
        "status": "Pending",
        "resolved_count": 20,
        "unsatisfactory_count": 5,
    },
    {
        "division": "HYB",
        "train_number": "17233",
        "complaint_type": "Cleanliness",
        "complaint_count": 28,
        "status": "Resolved",
        "resolved_count": 25,
        "unsatisfactory_count": 2,
    },
    {
        "division": "SC",
        "train_number": "12704",
        "complaint_type": "Electrical Equipment",
        "complaint_count": 22,
        "status": "Closed",
        "resolved_count": 22,
        "unsatisfactory_count": 1,
    },
]


class TestStatisticsBuilder:
    def setup_method(self):
        self.builder = StatisticsBuilder()

    def test_total_complaints(self):
        stats = self.builder.build(SAMPLE_ROWS, {"report_period": "2026-07-04"})
        assert stats.total_complaints == 4

    def test_resolved_and_pending(self):
        stats = self.builder.build(SAMPLE_ROWS)
        assert stats.resolved_complaints >= 2
        assert stats.pending_complaints >= 1

    def test_resolution_rate(self):
        stats = self.builder.build(SAMPLE_ROWS)
        assert 0 <= stats.resolution_rate <= 100

    def test_top_complaint_types(self):
        stats = self.builder.build(SAMPLE_ROWS)
        assert len(stats.top_complaint_types) >= 1
        assert stats.top_complaint_types[0]["name"] == "Electrical Equipment"

    def test_daily_highlights_generated(self):
        stats = self.builder.build(SAMPLE_ROWS)
        assert len(stats.daily_highlights) >= 1
        assert any("complaints" in h.lower() for h in stats.daily_highlights)

    def test_key_observations_generated(self):
        stats = self.builder.build(SAMPLE_ROWS)
        assert len(stats.key_observations) >= 1

    def test_empty_dataset(self):
        stats = self.builder.build([], {"report_period": "2026-07-04"})
        assert stats.total_complaints == 0
        assert len(stats.daily_highlights) == 1

    def test_unsatisfactory_count(self):
        stats = self.builder.build(SAMPLE_ROWS)
        assert stats.unsatisfactory_count == 11
        assert stats.unsatisfactory_rate > 0
