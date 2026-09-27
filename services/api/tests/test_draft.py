import json
import unittest

from app.draft import DraftRejected, validate_draft

MANUAL = [
    "Book a borescope of the high-pressure turbine before the next dispatch.",
    "After the borescope is scheduled, record corrected fan speed (NRf) and physical fan speed (Nf).",
    "Check LPT coolant bleed (W32) only once the borescope slot is confirmed.",
]

CASE = {
    "manual": {"id": "4.2", "title": "Hot-section wear", "steps": MANUAL},
    "evidence": [
        {"name": "NRf", "description": "Corrected fan speed", "direction": "high"},
        {"name": "Nf", "description": "Physical fan speed", "direction": "high"},
        {"name": "W32", "description": "LPT coolant bleed", "direction": "low"},
    ],
    "shopMemory": None,
}


def draft(steps: list[dict[str, object]], reason: str = "") -> str:
    return json.dumps({"steps": steps, "reason": reason})


CHEAP_FIRST = [
    {"source": 3, "text": "Check LPT coolant bleed (W32) on wing first.", "sensors": ["W32"]},
    {"source": 2, "text": "Record corrected fan speed (NRf) and physical fan speed (Nf); confirm both read high.", "sensors": ["NRf", "Nf"]},
    {"source": 1, "text": "Book a borescope of the high-pressure turbine only if the readings confirm wear.", "sensors": []},
]


class ValidateDraftTest(unittest.TestCase):
    def test_accepts_a_reorder_of_manual_steps(self) -> None:
        result = validate_draft(draft(CHEAP_FIRST, "The cheap check comes first."), CASE, MANUAL)
        self.assertEqual([step["source"] for step in result["steps"]], [3, 2, 1])
        self.assertEqual([step["moved"] for step in result["steps"]], [True, False, True])
        self.assertEqual(result["reason"], "The cheap check comes first.")

    def test_rejects_a_new_repair(self) -> None:
        steps = [dict(step) for step in CHEAP_FIRST]
        steps[2]["text"] = "Replace the fuel nozzle before dispatch."
        with self.assertRaisesRegex(DraftRejected, "Replace"):
            validate_draft(draft(steps), CASE, MANUAL)

    def test_rejects_a_sensor_that_did_not_move(self) -> None:
        steps = [dict(step) for step in CHEAP_FIRST]
        steps[0]["text"] = "Check T50 before the bleed."
        with self.assertRaisesRegex(DraftRejected, "T50"):
            validate_draft(draft(steps), CASE, MANUAL)

    def test_rejects_a_dropped_step(self) -> None:
        with self.assertRaisesRegex(DraftRejected, "2 steps"):
            validate_draft(draft(CHEAP_FIRST[:2]), CASE, MANUAL)

    def test_rejects_a_repeated_source(self) -> None:
        steps = [dict(step) for step in CHEAP_FIRST]
        steps[1]["source"] = 3
        with self.assertRaisesRegex(DraftRejected, "twice"):
            validate_draft(draft(steps), CASE, MANUAL)

    def test_drops_an_unchecked_reason_but_keeps_steps(self) -> None:
        result = validate_draft(draft(CHEAP_FIRST, "Saves about four thousand dollars."), CASE, MANUAL)
        self.assertIsNone(result["reason"])
        self.assertEqual(len(result["steps"]), 3)

    def test_rejects_an_invented_number(self) -> None:
        steps = [dict(step) for step in CHEAP_FIRST]
        steps[0]["text"] = "Check LPT coolant bleed (W32) within 48 cycles."
        with self.assertRaisesRegex(DraftRejected, "48"):
            validate_draft(draft(steps), CASE, MANUAL)

    def test_rejects_non_json(self) -> None:
        with self.assertRaisesRegex(DraftRejected, "JSON"):
            validate_draft("Sure! Here is the order.", CASE, MANUAL)


if __name__ == "__main__":
    unittest.main()
