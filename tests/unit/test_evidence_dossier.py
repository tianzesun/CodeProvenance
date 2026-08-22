"""Unit tests for the unified evidence dossier and viva questions."""

from src.backend.evaluation.evidence_dossier import (
    EvidenceDossierService,
    generate_viva_questions,
    StudentDossier,
    EvidenceItem,
)


def _job_payload() -> dict:
    return {
        "id": "job-1",
        "threshold": 0.6,
        "results": [
            {
                "file_a": "alice.py",
                "file_b": "bob.py",
                "score": 0.91,
                "risk_level": "high",
                "matching_blocks": [
                    {
                        "lines_a": "10-50",
                        "lines_b": "12-52",
                        "similarity": 0.93,
                        "block_type": "code",
                        "function_name": "dijkstra_shortest_path",
                    }
                ],
            },
            {
                "file_a": "alice.py",
                "file_b": "carol.py",
                "score": 0.42,
                "risk_level": "low",
                "matching_blocks": [],
            },
        ],
        "ai_detection": {
            "submissions": [
                {
                    "name": "alice.py",
                    "ai_probability": 0.78,
                    "confidence": 0.62,
                    "status": "High Risk",
                    "indicators": ["LLM fingerprint patterns"],
                    "flagged_regions": [
                        {"start_line": 10, "end_line": 34, "reason": "low_perplexity"}
                    ],
                },
                {
                    "name": "bob.py",
                    "ai_probability": 0.22,
                    "confidence": 0.55,
                    "status": "Low Risk",
                    "indicators": [],
                    "flagged_regions": [],
                },
            ]
        },
        "web_analysis": {
            "submissions": [
                {
                    "name": "alice.py",
                    "max_similarity": 0.86,
                    "match_count": 2,
                    "sources": [
                        {
                            "name": "org/repo/dijkstra.py",
                            "url": "https://github.com/org/repo/blob/main/dijkstra.py",
                            "source": "github",
                            "similarity": 0.86,
                        },
                        {
                            "name": "so answer",
                            "url": "https://stackoverflow.com/questions/1",
                            "source": "stackoverflow",
                            "similarity": 0.4,
                        },
                    ],
                }
            ]
        },
    }


class TestEvidenceDossierService:
    """The dossier fuses all detectors per student, high bands first."""

    def test_build_fuses_all_sources_per_student(self) -> None:
        dossier = EvidenceDossierService().build(_job_payload())

        assert dossier["job_id"] == "job-1"
        assert dossier["coverage"] == {
            "ai_detection": True,
            "web_analysis": True,
            "pairwise": True,
        }
        students = {entry["student"]: entry for entry in dossier["students"]}
        assert set(students) == {"alice.py", "bob.py", "carol.py"}

        alice = students["alice.py"]
        assert alice["band"] == "high"
        assert alice["ai_probability"] == 0.78
        assert alice["peer_partner"] == "bob.py"
        assert alice["peer_max_similarity"] == 0.91
        assert alice["web_best_match_source"] == "github"
        assert alice["web_best_match_url"].startswith("https://github.com/")
        assert {item["type"] for item in alice["evidence"]} == {
            "ai_detection",
            "peer_similarity",
            "web_provenance",
        }

    def test_students_sorted_high_band_first(self) -> None:
        dossier = EvidenceDossierService().build(_job_payload())
        bands = [entry["band"] for entry in dossier["students"]]
        assert bands == sorted(
            bands, key=lambda band: {"high": 0, "medium": 1, "low": 2}[band]
        )
        assert dossier["students"][0]["student"] == "alice.py"

    def test_peer_similarity_picks_best_partner(self) -> None:
        students = {
            entry["student"]: entry
            for entry in EvidenceDossierService().build(_job_payload())["students"]
        }
        # alice's best partner is bob (0.91) not carol (0.42).
        assert students["alice.py"]["peer_partner"] == "bob.py"
        assert students["alice.py"]["peer_max_similarity"] == 0.91
        # bob's dossier mirrors the same pair from his side.
        assert students["bob.py"]["peer_partner"] == "alice.py"

    def test_viva_questions_reference_evidence(self) -> None:
        alice = {
            entry["student"]: entry
            for entry in EvidenceDossierService().build(_job_payload())["students"]
        }["alice.py"]

        joined = " ".join(alice["viva_questions"])
        assert "walk through" in joined
        assert "10–34" in joined  # flagged region from AI evidence
        assert "dijkstra_shortest_path" in joined  # function from matching block
        assert "https://github.com/" in joined  # web match URL
        assert "Live modification" in joined  # combined AI+peer check

    def test_low_ai_student_still_gets_peer_questions(self) -> None:
        students = {
            entry["student"]: entry
            for entry in EvidenceDossierService().build(_job_payload())["students"]
        }
        # bob's AI score is low (0.22) but his 0.91 similarity with alice is
        # high-severity peer evidence — a viva question is warranted anyway.
        bob = students["bob.py"]
        assert bob["ai_probability"] == 0.22
        assert bob["band"] == "high"
        joined = " ".join(bob["viva_questions"])
        assert "walk through" not in joined  # no AI question
        assert "dijkstra_shortest_path" in joined  # peer question present

        # carol's only evidence is the low 0.42 similarity: low band, no questions.
        carol = students["carol.py"]
        assert carol["band"] == "low"
        assert carol["viva_questions"] == []

    def test_missing_sources_yield_low_band_and_coverage_flags(self) -> None:
        dossier = EvidenceDossierService().build(
            {"id": "job-2", "threshold": 0.6, "results": []}
        )
        assert dossier["coverage"] == {
            "ai_detection": False,
            "web_analysis": False,
            "pairwise": False,
        }
        assert dossier["students"] == []

    def test_malformed_scores_are_skipped(self) -> None:
        payload = _job_payload()
        payload["results"][0]["score"] = "not-a-number"
        students = {
            entry["student"]: entry
            for entry in EvidenceDossierService().build(payload)["students"]
        }
        # The malformed alice-bob pair contributes nothing; alice's only valid
        # peer match is the low 0.42 with carol, and she stays high via AI+web.
        alice = students["alice.py"]
        assert alice["peer_partner"] == "carol.py"
        assert alice["peer_max_similarity"] == 0.42
        assert alice["band"] == "high"


class TestGenerateVivaQuestions:
    """Question generation stays grounded in the evidence items."""

    def test_low_severity_only_generates_no_questions(self) -> None:
        dossier = StudentDossier(student="dave.py")
        dossier.evidence = [
            EvidenceItem(
                type="ai_detection",
                severity="low",
                title="AI likelihood 10%",
                detail="statistical signal profile",
            )
        ]
        assert generate_viva_questions(dossier) == []

    def test_questions_are_capped(self) -> None:
        dossier = StudentDossier(student="erin.py")
        dossier.peer_partner = "frank.py"
        dossier.peer_max_similarity = 0.9
        dossier.web_best_match_url = "https://example.com/x"
        dossier.evidence = [
            EvidenceItem(
                type="ai_detection",
                severity="high",
                title="AI likelihood 90%",
                detail="most predictable region lines 5–20; indicators",
            ),
            EvidenceItem(
                type="peer_similarity",
                severity="high",
                title="matches frank.py",
                detail="3 matching region(s), top function 'solve', risk high",
            ),
            EvidenceItem(
                type="web_provenance",
                severity="high",
                title="matches public source",
                detail="https://example.com/x",
            ),
        ]
        questions = generate_viva_questions(dossier)
        assert len(questions) <= 5
        assert all(isinstance(question, str) for question in questions)


class TestVivaOutcomeMerge:
    """Recorded viva outcomes merge into the matching student dossier."""

    def test_outcome_attached_to_matching_student(self):
        """A recorded outcome lands on its student, not on the others."""
        dossier = EvidenceDossierService().build(
            _job_payload(),
            viva_outcomes=[
                {
                    "submission_name": "alice.py",
                    "outcome": "authorship_confirmed",
                    "notes": "Explained the decomposition clearly.",
                    "conducted_at": "2026-08-22T10:00:00",
                }
            ],
        )
        by_name = {student["student"]: student for student in dossier["students"]}
        assert by_name["alice.py"]["viva_outcome"]["outcome"] == "authorship_confirmed"
        assert by_name["alice.py"]["viva_outcome"]["notes"]
        assert by_name["bob.py"]["viva_outcome"] is None

    def test_no_outcomes_leaves_students_untouched(self):
        """Without outcomes every student has a null viva_outcome."""
        dossier = EvidenceDossierService().build(_job_payload())
        assert all(student["viva_outcome"] is None for student in dossier["students"])

    def test_outcome_for_unknown_student_is_ignored(self):
        """Outcomes naming a student not in the job are dropped."""
        dossier = EvidenceDossierService().build(
            _job_payload(),
            viva_outcomes=[{"submission_name": "ghost.py", "outcome": "inconclusive"}],
        )
        assert all(student["viva_outcome"] is None for student in dossier["students"])
