from typing import List


class Person:
    def __init__(self, first, last):
        self.first = first
        self.last = last

        # def _enricher(self, variations: List[str]) -> List[str]:
        #     final_variations = []
        #     for variation in variations:
        #         var_temp = [variation + str(i) for i in range(1, 3)]
        #         final_variations.extend(var_temp)
        #         final_variations.append(variation)

        # return final_variations

    def _enum_f_last(self) -> str:
        return self.first[0] + self.last

    def _enum_fi_last(self) -> str:
        return self.first[0:2] + self.last

    def _enum_first_l(self) -> str:
        return self.first + self.last[0:3]

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
        variations.append(self._enum_f_last())
        variations.append(self._enum_fi_last())
        variations.append(self._enum_first_l())
        variations.append(self._enum_first_last())
        variations.append(self._enum_last_first())
        variations.append(self._enum_last_dot_first())
        variations.append(self._enum_first_dot_last())

        return variations

    # def enum_all_enriched(self) -> List[str]:
    #     variations = self.enum_all()
    #     return self._enricher(variations)

    def __repr__(self):
        return self.first + " " + self.last
