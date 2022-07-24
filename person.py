from typing import List


class Person:
    """
    This class simulates a person with general attributes (currently only includes first and last name)
    """

    def __init__(self, first: str, last: str):
        self.first = first
        self.last = last

    def _enum_f_last(self) -> str:
        return self.first[0] + self.last

    def _enum_first(self) -> str:
        return self.first

    def _enum_fi_last(self) -> str:
        if len(self.first) >= 2:
            return self.first[0:2] + self.last
        return None

    def _enum_first_l(self) -> str:
        if len(self.last) >= 3:
            return self.first + self.last[0:3]
        elif len(self.last) == 2:
            return self.first + self.last
        return None

    def _enum_first_last(self) -> str:
        return self.first + self.last

    def _enum_last_first(self) -> str:
        return self.last + self.first

    def _enum_last_dot_first(self) -> str:
        return self.last + "." + self.first

    def _enum_first_dot_last(self) -> str:
        return self.first + "." + self.last

    def enum_all(self) -> List[str]:
        variations = []
        variations.append(self._enum_first())
        variations.append(self._enum_f_last())
        var_temp = self._enum_fi_last()
        if var_temp:
            variations.append(var_temp)

        var_temp = self._enum_first_l()
        if var_temp:
            variations.append(var_temp)
        variations.append(self._enum_first_last())
        variations.append(self._enum_last_first())
        variations.append(self._enum_last_dot_first())
        variations.append(self._enum_first_dot_last())

        return variations

    def __repr__(self):
        return self.first + " " + self.last
