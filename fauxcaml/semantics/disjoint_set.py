from collections import defaultdict
from fauxcaml import utils


class DisjointSet:
    def __init__(self):
        self.map = dict()

    def as_dict(self):
        sets = defaultdict(set)
        for member in self.map.keys():
            root = self.root_of(member)
            sets[root].add(member)
        return sets

    def sets(self):
        return self.as_dict().values()

    def family_of(self, x):
        families = self.as_dict()
        return families[self.root_of(x)]

    def __str__(self):
        spaces = "  "
        set_list = ",\n".join(f"{spaces}{utils.set_to_str(s)}" for s in self.sets())
        return f"{{\n{set_list}\n}}"

    def __repr__(self):
        cls_name = self.__class__.__name__
        sets = ", ".join(f"{utils.set_to_str(s)}" for s in self.sets())
        return f"{cls_name}({{ {sets} }})"

    def same_set(self, x, *ys):
        assert len(ys) > 0, "`same_set` requires at least two arguments!"
        x_root = self.root_of(x)
        return all(x_root == self.root_of(y) for y in ys)

    def __contains__(self, other):
        return other in self.map.keys()

    def update(self, other):
        self.map.update(other)

    def add(self, e):
        if e not in self.map.keys():
            self.map[e] = 1  # Root node of tree with size 1.

    def root_of(self, e):
        res = self.map[e]
        if type(res) is int:
            return e
        else:
            parent = res
            root = self.root_of(parent)
            self.map[e] = root  # Path compression heuristic.
            return root

    def join(self, e1, e2):
        r1 = self.root_of(e1)
        r2 = self.root_of(e2)

        self.join_roots(r1, r2)

    def join_roots(self, r1, r2):
        """
        Assumes r1 and r2 are roots.
        """
        size1, size2 = self.map[r1], self.map[r2]

        # Weighting heuristic.
        if size1 > size2:
            self.map[r1] += size2
            self.map[r2] = r1
        else:
            self.map[r2] += size1
            self.map[r1] = r2
