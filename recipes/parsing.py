import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ParsedIngredient:
    name: str
    quantity: str
    unit: str
    notes: str


@dataclass
class ParsedInstruction:
    step_number: int
    text: str
    timestamp: Optional[str] = None


UNIT_NORMALIZATION = {
    "cup": "cups",
    "tbsp": "tablespoons",
    "tsp": "teaspoons",
    "oz": "ounces",
    "lb": "pounds",
    "tbs": "tablespoons",
    "ts": "teaspoons",
}


class RecipeParsingService:
    def __init__(self):
        self._quantity_pattern = re.compile(
            r"^(\d+(?:[\d\/\.]+)?(?:\s*-\s*\d+)?)\s*([a-zA-Z]+)?\s*(.+)"
        )
        self._ingredient_section = re.compile(
            r"^(?:ingredients|directions|you[' ]?ll need)[\s:]*$", re.IGNORECASE
        )
        self._instruction_section = re.compile(
            r"^(?:instructions|directions|steps|method| directions)[\s:]*$",
            re.IGNORECASE,
        )
        self._numbered_step = re.compile(r"^\d+[.)]\s+(.+)")
        self._timestamp = re.compile(r"(\d{1,2}:\d{2})\s*[-–]\s*(.+)")

    def parse_ingredients(self, description: str) -> List[ParsedIngredient]:
        ingredients = []
        lines = description.split("\n")
        in_ingredients_section = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if self._ingredient_section.match(line):
                in_ingredients_section = True
                continue

            if self._instruction_section.match(line):
                in_ingredients_section = False
                continue

            if in_ingredients_section or line.startswith(("-", "*", "•")):
                ingredient = self._parse_ingredient_line(line)
                if ingredient:
                    ingredients.append(ingredient)

        return ingredients

    def _parse_ingredient_line(self, line: str) -> Optional[ParsedIngredient]:
        line = line.lstrip("-*• ").strip()

        match = self._quantity_pattern.match(line)
        if match:
            quantity = match.group(1) or ""
            unit = match.group(2) or ""
            name = match.group(3) or line

            unit = UNIT_NORMALIZATION.get(unit.lower(), unit.lower())

            return ParsedIngredient(name=name, quantity=quantity, unit=unit, notes="")

        return ParsedIngredient(name=line, quantity="", unit="", notes="")

    def parse_instructions(self, description: str) -> List[ParsedInstruction]:
        instructions = []
        lines = description.split("\n")
        in_instructions_section = False
        step_num = 1

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if self._instruction_section.match(line):
                in_instructions_section = True
                continue

            if self._ingredient_section.match(line):
                in_instructions_section = False
                continue

            timestamp = None
            text = line

            ts_match = self._timestamp.match(line)
            if ts_match:
                timestamp = ts_match.group(1)
                text = ts_match.group(2)
            elif self._numbered_step.match(line):
                text = self._numbered_step.match(line).group(1)
            elif in_instructions_section and not line.startswith(("-", "*", "•")):
                text = line
            else:
                continue

            instructions.append(
                ParsedInstruction(step_number=step_num, text=text, timestamp=timestamp)
            )
            step_num += 1

        return instructions

    def identify_unparseable(self, lines: List[str]) -> List[str]:
        unparsed = []
        action_verbs = [
            "preheat",
            "mix",
            "add",
            "cook",
            "bake",
            "cut",
            "slice",
            "dice",
            "chop",
            "heat",
            "pour",
            "stir",
            "combine",
            "transfer",
        ]

        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue

            has_quantity = bool(self._quantity_pattern.match(line))
            has_action = any(verb in line.lower() for verb in action_verbs)
            is_bullet = line.startswith(("-", "*", "•"))

            if not has_quantity and not has_action and not is_bullet:
                if not self._ingredient_section.match(
                    line
                ) and not self._instruction_section.match(line):
                    unparsed.append(line)

        return unparsed[:10]
