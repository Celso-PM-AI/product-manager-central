"""Reusable complete PRD Success Matrix fixture for approved-document tests."""


def complete_success_matrix() -> list[dict[str, object]]:
    return [
        {
            "entry_id": "success-test-1",
            "position": 1,
            "requirement_outcome": "The approved product outcome is achieved.",
            "metric": "Outcome completion rate",
            "baseline": "0%",
            "target": "100%",
            "minimum_acceptance_threshold": "95%",
            "measurement_method": "Calculate the share of completed outcomes.",
            "data_source": "Approved product analytics",
            "evaluation_period": "First 30 days after launch",
            "validation_owner": "Product Manager",
            "status": "not_started",
        }
    ]


def complete_prd_agile_hierarchy(
    prefix: str = "hierarchy-test",
) -> list[dict[str, object]]:
    """Return one complete Epic → Capability → Feature → User Story chain."""

    levels = (
        ("epic", None),
        ("capability", "epic"),
        ("feature", "capability"),
        ("user_story", "feature"),
    )
    return [
        {
            "artifact_id": f"{prefix}-{artifact_type}",
            "artifact_type": artifact_type,
            "position": 1,
            "title": f"{artifact_type.replace('_', ' ').title()} title",
            "description": f"Measurable {artifact_type.replace('_', ' ')} outcome.",
            "parent_artifact_id": (
                f"{prefix}-{parent_type}" if parent_type is not None else None
            ),
            "acceptance_criteria": [
                {
                    "criterion_id": f"{prefix}-{artifact_type}-criterion-1",
                    "position": 1,
                    "text": (
                        f"The {artifact_type.replace('_', ' ')} outcome is "
                        "observably satisfied."
                    ),
                }
            ],
        }
        for artifact_type, parent_type in levels
    ]
