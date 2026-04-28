import pytest
import textwrap

from deutil.proof import Proof

@pytest.mark.parametrize(
    "markdown",
    [
        # Premise + Modus Ponens
        """
        | 1. (A -> B)  premise
        | 2. A  premise
        |-
        | 3. B  MP: 1, 2
        """,
        # Modus Tollens
        """
        | 1. (A -> B)  premise
        | 2. ~B  premise
        |-
        | 3. ~A  MT: 1, 2
        """,
        # Double Negation (elimination)
        """
        | 1. ~~A  premise
        |-
        | 2. A  DN: 1
        """,
        # Double Negation (introduction)
        """
        | 1. A  premise
        |-
        | 2. ~~A  DN: 1
        """,
        # Repeat
        """
        | 1. A  premise
        |-
        | 2. A  repeat: 1
        """,
        # Addition (A -> A v B)
        """
        | 1. A  premise
        |-
        | 2. (A v B)  addition: 1
        """,
        # Addition (A -> B v A)
        """
        | 1. A  premise
        |-
        | 2. (B v A)  add: 1
        """,
        # Disjunctive Syllogism (variant 1)
        """
        | 1. (A v B)  premise
        | 2. ~A  premise
        |-
        | 3. B  DS: 1, 2
        """,
        # Disjunctive Syllogism (variant 2)
        """
        | 1. (A v B)  premise
        | 2. ~B  premise
        |-
        | 3. A  D.S.: 1, 2
        """,
        # Adjunction
        """
        | 1. A  premise
        | 2. B  premise
        |-
        | 3. (A ^ B)  adjunction: 1, 2
        """,
        # Simplification (left)
        """
        | 1. (A ^ B)  premise
        |-
        | 2. A  simplification: 1
        """,
        # Simplification (right)
        """
        | 1. (A ^ B)  premise
        |-
        | 2. B  simp: 1
        """,
        # Bicondition
        """
        | 1. (A -> B)  premise
        | 2. (B -> A)  premise
        |-
        | 3. (A <-> B)  bic: 1, 2
        """,
        # Equivalence (A <-> B, A |- B)
        """
        | 1. (A <-> B)  premise
        | 2. A  premise
        |-
        | 3. B  equivalence: 1, 2
        """,
        # Equivalence (A <-> B, B |- A)
        """
        | 1. (A <-> B)  premise
        | 2. B  premise
        |-
        | 3. A  equiv: 1, 2
        """,
        # Equivalence (A <-> B, ~A |- ~B)
        """
        | 1. (A <-> B)  premise
        | 2. ~A  premise
        |-
        | 3. ~B  equiv: 1, 2
        """,
        # Equivalence (A <-> B, ~B |- ~A)
        """
        | 1. (A <-> B)  premise
        | 2. ~B  premise
        |-
        | 3. ~A  equiv: 1, 2
        """,
        # Conditional Derivation + AssumptionForCD
        """
        |-
        | | 1. A  assumption for C.D.
        | |-
        | | 2. B  premise
        | 3. (A -> B)  C.D. 1-2
        """,
        # Indirect Derivation + AssumptionForID
        """
        |-
        | | 1. ~A  assumption for I.D.
        | |-
        | | 2. B  premise
        | | 3. ~B  premise
        | 4. A  I.D. 1-3
        """,
        # Universal Instantiation
        """
        | 1. \\VxFx  premise
        |-
        | 2. Fa  UI: 1
        """,
        # Existential Generalisation
        """
        | 1. Fa  premise
        |-
        | 2. \\ExFx  EG: 1
        """,
        # Existential Instantiation
        """
        | 1. \\ExFx  premise
        |-
        | 2. Fa  EI: 1
        """,
        # Universal Derivation
        """
        | 1. \\Vx(Fx -> Gx)  premise
        | 2. \\VyFy  premise
        |-
        | | [x']
        | |-
        | | 3. (Fx' -> Gx')  U.I. 1
        | | 4. Fx'           U.I. 2
        | | 5. Gx'           MP: 3, 4
        | 6. \\VzGz          U.D. 3-5
        """,
        # Theorem generic (no theorem number)
        """
        |-
        | 1. (A v ~A)  theorem
        """,
        # Theorem T1-T10
        """
        |-
        | 1. (A v ~A)  theorem: T1
        """,
        """
        |-
        | 1. (~(A -> B) <-> (A ^ ~B))  theorem: T2
        """,
        """
        |-
        | 1. (~(A v B) <-> (~A ^ ~B))  theorem: T3
        """,
        """
        |-
        | 1. ((~A v ~B) <-> ~(A ^ B))  theorem: T4
        """,
        """
        |-
        | 1. (~(A <-> B) <-> (A <-> ~B))  theorem: T5
        """,
        """
        |-
        | 1. (~A -> (A -> B))  theorem: T6
        """,
        """
        |-
        | 1. (A -> (B -> A))  theorem: T7
        """,
        """
        |-
        | 1. ((A -> (B -> R)) -> ((A -> B) -> (A -> R)))  theorem: T8
        """,
        """
        |-
        | 1. ((~A -> ~B) -> ((~A -> B) -> A))  theorem: T9
        """,
        """
        |-
        | 1. ((A -> B) -> (~B -> ~A))  theorem: T10
        """,
    ]
)
def test_all_rule_success_cases(markdown: str) -> None:
    lines = textwrap.dedent(markdown).strip().splitlines()
    proof = Proof.from_markdown(lines)
    proof.check()
